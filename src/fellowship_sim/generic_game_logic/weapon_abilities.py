from dataclasses import dataclass, field
from typing import Literal

from loguru import logger

from fellowship_sim.base_classes import (
    AbilityPeriodicDamage,
    DoTEffect,
    Effect,
    Entity,
    SetupContext,
    SetupEffectLate,
    create_standard_damage,
    deal_damage,
)
from fellowship_sim.base_classes.ability import WeaponAbility
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    ComputeCooldownReduction,
    PreDamageSnapshotUpdate,
)
from fellowship_sim.base_classes.state import get_state
from fellowship_sim.base_classes.stats import SnapshotStats
from fellowship_sim.base_classes.timed_events import DelayedDamage, GenericTimedEvent


@dataclass(kw_only=True, repr=False)
class VoidbringersTouchEffect(Effect):
    """Debuff on target: accumulates 10% of all damage the caster deals.

    Explodes when stored_damage reaches max_stored_damage, or on expiry.
    Explosion deals min(max_stored_damage, stored_damage), scaled by expertise
    and the caster's global damage multiplier, with +100% crit chance (grievous crit).

    Renew on re-apply: keeps existing stored_damage, resets duration only.
    """

    name: str = field(default="voidbringers_touch", init=False)
    duration: float = field(default=15.0, init=False)
    max_stored_damage: float
    ability: "VoidbringersTouch"

    stored_damage: float = field(default=0.0, init=False)
    _exploded: bool = field(default=False, init=False)

    def on_add(self) -> None:
        self._target = self.attached_to
        get_state().bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        get_state().bus.subscribe(AbilityPeriodicDamage, self._on_damage, owner=self)

    def fuse(self, incoming: Effect) -> None:
        """Keep existing stored_damage; renew duration only."""
        self.duration = incoming.duration
        self._schedule_expiry()
        logger.warning("Voidbringer's Touch: double apply to same target wastes damage!")
        logger.debug(
            "Voidbringer's Touch: renewed duration (stored={:.0f}/{:.0f})", self.stored_damage, self.max_stored_damage
        )

    def _on_damage(self, event: AbilityDamage | AbilityPeriodicDamage) -> None:
        if event.damage_source is self:
            return

        self.stored_damage += event.damage * 0.10
        logger.trace(
            "Voidbringer's Touch: +{:.0f} stored ({:.0f}/{:.0f})",
            event.damage * 0.10,
            self.stored_damage,
            self.max_stored_damage,
        )
        if self.stored_damage >= self.max_stored_damage and not self._exploded:
            self._exploded = True
            state = get_state()
            state.schedule(
                time_delay=0.0, callback=GenericTimedEvent(name="voidbringers_touch explode", callback=self.remove)
            )

    def on_remove(self) -> None:
        self._fire_explosion()

    def _fire_explosion(self) -> None:
        if self.attached_to is None:
            raise Exception(f"{self!s} unattached during _fire_explosion")  # noqa: TRY002, TRY003

        base_damage = min(self.max_stored_damage, self.stored_damage)
        snapshot = SnapshotStats.from_base_damage_and_character(
            base_damage=base_damage,
            character=self.ability.owner,
            is_scaled_by_main_stat=False,
            is_scaled_by_expertise=True,
        )

        snapshot = snapshot.add_crit_percent(1.0)

        logger.debug(
            f"Voidbringer's Touch: explosion on {self.attached_to} — base={base_damage:.0f}, final avg={snapshot.average_damage:.0f}"
        )
        deal_damage(snapshot, self, self.attached_to)


@dataclass(kw_only=True, repr=False)
class VoidbringersTouch(WeaponAbility):
    """Weapon ability: 90s cooldown, instant cast, 1 charge.

    On cast: applies VoidbringersTouchEffect to the target.
    max_stored_damage = 42.5 * character.main_stat.
    """

    base_player_downtime: float = field(default=0.0, init=False)
    base_cooldown: float = field(default=90.0, init=False)

    def _do_cast(self, target: Entity) -> None:
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        max_stored = 42.5 * self.owner.stats.main_stat
        target.effects.add(VoidbringersTouchEffect(ability=self, max_stored_damage=max_stored, owner=self.owner))
        logger.debug(f"Voidbringer's Touch: applied to {target} (max stored={max_stored:.0f})")


# ---------------------------------------------------------------------------
# Chronoshift
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class ChronoshiftChannelCDR(Effect):
    """Temporary effect active during the Chronoshift channel.

    Appends +8.0 to CDA modifiers for every ComputeCooldownReduction event
    fired by the caster's abilities, giving 800% extra CDR (9x total drain rate).
    Expires automatically at the end of the channel duration.
    """

    owner: Player

    name: str = field(default="chronoshift_cdr", init=False)
    duration: float = field(default=3.0, init=True)  # overridden to match channel duration at construction

    def on_add(self) -> None:
        get_state().bus.subscribe(ComputeCooldownReduction, self._on_cdr, owner=self)
        self.owner._recalculate_cdr_multipliers()

    def on_remove(self) -> None:
        self.owner._recalculate_cdr_multipliers()

    def _on_cdr(self, event: ComputeCooldownReduction) -> None:
        event.cdr_modifiers.append(8.0)
        logger.trace(f"Chronoshift CDR: 800% CDR on {event.ability}")


@dataclass(kw_only=True, repr=False)
class Chronoshift(WeaponAbility):
    """Weapon ability: 180s cooldown, 3s channel, 1 charge.

    Pulses (5192-6345) damage every tick_time/(1+haste) seconds to all enemies
    (up to 12), snapshotting stats at cast time.  A partial tick fires at the
    end of the channel proportional to the remaining time within the last tick
    window.  During the channel, all of the caster's ability cooldowns drain
    at 9x their normal rate (+800% CDA).
    """

    base_player_downtime: float = field(default=3.0, init=False)
    base_cooldown: float = field(default=180.0, init=False)
    average_damage: float = field(default=(5192 + 6345) / 2, init=False)
    is_channel: bool = field(default=True, init=False)
    tick_time: float = field(default=1.5, init=False)
    num_secondary_targets: int = field(default=12, init=False)

    def _do_cast(self, target: Entity) -> None:
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        haste = self.owner.stats.haste_percent
        tick_interval = self.tick_time / (1 + haste)
        num_full_ticks = int(self.player_downtime // tick_interval)
        partial_ratio = (self.player_downtime % tick_interval) / tick_interval

        logger.debug(
            "chronoshift: {} full tick(s) + partial={:.3f}, interval={:.3f}s on up to {} enemies",
            num_full_ticks,
            partial_ratio,
            tick_interval,
            self.num_secondary_targets,
        )

        for k in range(num_full_ticks):
            delay = (k + 1) * tick_interval
            state.schedule(
                time_delay=delay,
                callback=DelayedDamage(damage_source=self, callback=self._fire_tick_all),
            )

        if partial_ratio > 1e-9:
            state.schedule(
                time_delay=self.player_downtime,
                callback=DelayedDamage(damage_source=self, callback=lambda: self._fire_tick_all(partial_ratio)),
            )

        self.owner.effects.add(ChronoshiftChannelCDR(duration=self.player_downtime, owner=self.owner))

    def _fire_tick_all(self, ratio: float = 1.0) -> None:
        create_standard_damage(
            state=get_state(),
            damage_source=self,
            owner=self.owner,
            target=None,
            base_damage=self.average_damage * ratio,
            num_secondary_targets=self.num_secondary_targets,
        )


# ---------------------------------------------------------------------------
# Nature's Fury
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class NaturesFuryAura(Effect):
    """Permanent aura attached to NaturesFury: grants +30% crit to all NaturesFury hits.

    Injected as a SnapshotModifier on AbilityCastSuccess so the bonus applies
    uniformly to main and secondary hits through the standard snapshot pipeline.
    """

    name: str = field(default="natures_fury_aura", init=False)
    ability: "NaturesFury | None" = None

    def on_add(self) -> None:
        get_state().bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if event.damage_source is not self.ability:
            return
        event.snapshot = event.snapshot.add_crit_percent(0.30)


@dataclass(kw_only=True, repr=False)
class NaturesFury(WeaponAbility):
    """Weapon ability: 60s cooldown, 1.5s cast, 1 charge.

    Hits main target and up to 3 additional enemies (4 total).
    All hits gain +30% crit chance (via NaturesFuryAura).
    Main target takes +100% damage (2x multiplier).
    """

    base_cooldown: float = field(default=60.0, init=False)
    average_damage: float = field(default=(12_579 + 15_374) / 2, init=False)

    num_secondary_targets: int = field(default=3, init=False)
    main_damage_multiplier: float = field(default=2.0, init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.owner.effects.add(NaturesFuryAura(ability=self, owner=self.owner))


# ---------------------------------------------------------------------------
# Icicles of An'zhyr
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class CurseOfAnzhyr(DoTEffect):
    """Infinite-duration DoT applied by the final wave of IciclesOfAnzhyr.

    Ticks every 3s (scaled by snapshot haste) dealing periodic damage.
    Enemies afflicted take +200% direct damage from IciclesOfAnzhyr (+200% = 3x total).
    Re-applying is a no-op: the existing curse continues unchanged.
    """

    name: str = field(default="curse_of_anzhyr", init=False)
    base_tick_duration: float = field(default=3.0, init=False)

    def fuse(self, incoming: Effect) -> None:
        """Re-applying has no effect — the curse continues unchanged."""
        logger.debug("Curse of An'zhyr: fuse ignored — curse continues unchanged")

    def on_add(self) -> None:
        super().on_add()
        get_state().bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if event.is_dot:
            return
        if event.target is not self.attached_to:
            return
        if not isinstance(event.damage_source, IciclesOfAnzhyr):
            return
        event.snapshot = event.snapshot.scale_average_damage(3.0)
        logger.trace(f"Curse of An'zhyr: +200% direct damage from Icicles of An'zhyr on {event.target}")


@dataclass(kw_only=True, repr=False)
class IciclesOfAnzhyr(WeaponAbility):
    """Weapon ability: 30s cooldown, instant cast, 1 charge.

    Fires 3 waves at t+1s, t+2s, t+3s, each hitting up to 12 enemies.
    The third wave also applies CurseOfAnzhyr to every target hit.
    Enemies bearing CurseOfAnzhyr take +200% direct damage from this ability.
    """

    base_cooldown: float = field(default=30.0, init=False)
    average_damage: float = field(default=(1296 + 1584) / 2, init=False)

    dot_average_damage: float = field(default=(345 + 422) / 2, init=False)

    num_secondary_targets: int = field(default=12, init=False)

    def _do_cast(self, target: Entity) -> None:
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        for wave_num in range(1, 4):
            is_final = wave_num == 3
            state.schedule(
                time_delay=float(wave_num),
                callback=DelayedDamage(damage_source=self, callback=lambda f=is_final: self._fire_wave(f)),
            )
        logger.debug(
            "Icicles of An'zhyr: 3 waves scheduled on up to {} enemies",
            self.num_secondary_targets,
        )

    def _fire_wave(self, is_final: bool) -> None:
        state = get_state()
        logger.trace(f"icicles: wave at t={state.time:.3f}, final wave={is_final}")
        for enemy in state.enemies[: self.num_secondary_targets]:
            deal_damage(SnapshotStats.from_ability_and_character(ability=self, character=self.owner), self, enemy)
            if is_final:
                dot_snapshot = SnapshotStats.from_base_damage_and_character(
                    base_damage=self.dot_average_damage, character=self.owner
                )
                enemy.effects.add(CurseOfAnzhyr(snapshot=dot_snapshot, owner=self.owner))


class EquipVoidbringersTouch(SetupEffectLate[Player]):
    def __str__(self) -> str:
        return "Weapon: Voidbringer's Touch"

    def apply(self, character: Player, context: SetupContext) -> None:
        ability = VoidbringersTouch(owner=character)
        character.weapon_ability = ability
        character.voidbringers_touch = ability
        character.abilities.append(ability)


class EquipChronoshift(SetupEffectLate[Player]):
    def __str__(self) -> str:
        return "Weapon: Chronoshift"

    def apply(self, character: Player, context: SetupContext) -> None:
        ability = Chronoshift(owner=character)
        character.weapon_ability = ability
        character.chronoshift = ability
        character.abilities.append(ability)


class EquipNaturesFury(SetupEffectLate[Player]):
    def __str__(self) -> str:
        return "Weapon: Nature's Fury"

    def apply(self, character: Player, context: SetupContext) -> None:
        ability = NaturesFury(owner=character)
        character.weapon_ability = ability
        character.natures_fury = ability
        character.abilities.append(ability)


class EquipIcicles(SetupEffectLate[Player]):
    def __str__(self) -> str:
        return "Weapon: Icicles of Anzhyr"

    def apply(self, character: Player, context: SetupContext) -> None:
        ability = IciclesOfAnzhyr(owner=character)
        character.weapon_ability = ability
        character.icicles_of_anzhyr = ability
        character.abilities.append(ability)


WeaponName = Literal[
    "Voidbringer's Touch",
    "Chronoshift",
    "Nature's Fury",
    "Icicles of Anzhyr",
]

WeaponAbilitySetupEffectDict: dict[WeaponName, type[SetupEffectLate[Player]]] = {
    "Voidbringer's Touch": EquipVoidbringersTouch,
    "Chronoshift": EquipChronoshift,
    "Nature's Fury": EquipNaturesFury,
    "Icicles of Anzhyr": EquipIcicles,
}
