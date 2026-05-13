from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from loguru import logger

from fellowship_sim.base_classes import Ability, Player, RealPPM
from fellowship_sim.base_classes.effect import AccumulatorEffect, DoTEffect, Effect
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    AbilityPeriodicDamage,
    EffectRefreshed,
    PreDamageSnapshotUpdate,
    Resource,
    ResourceSpent,
    SnapshotCreation,
    SpiritProc,
)
from fellowship_sim.base_classes.timed_events import GenericTimedEvent

from . import ardeos_config

if TYPE_CHECKING:
    from fellowship_sim.ardeos.entity import Ardeos
    from fellowship_sim.base_classes.stats import SnapshotStats


# ---------------------------------------------------------------------------
# DoT effects
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class ArdeosCinderGeneratingDoT(DoTEffect):
    owner: "Ardeos"

    cinder_tick_interval: float = field(init=False)
    cinder_tick_amount: int = field(init=False)

    def on_add(self) -> None:
        super().on_add()
        self.schedule_cinder_tick()

    def schedule_cinder_tick(self) -> None:
        self.owner.state.schedule(
            time_delay=self.cinder_tick_interval,
            callback=GenericTimedEvent(name=f"{self.name} cinder tick", callback=self._do_cinder_tick),
        )

    def _do_cinder_tick(self) -> None:
        if self.attached_to is None:
            return
        self.owner._change_cinder(self.cinder_tick_amount)
        self.schedule_cinder_tick()


@dataclass(kw_only=True, repr=False)
class SearingBlazeDoT(ArdeosCinderGeneratingDoT):
    name: str = field(default="searing_blaze_dot", init=False)
    average_damage: float = field(
        default=(ardeos_config.SEARING_BLAZE_DAMAGE_MIN + ardeos_config.SEARING_BLAZE_DAMAGE_MAX) / 2,
        init=False,
    )
    duration: float = field(default=ardeos_config.SEARING_BLAZE_DURATION, init=False)
    base_tick_interval: float = field(default=ardeos_config.SEARING_BLAZE_TICK_INTERVAL, init=False)
    cinder_tick_interval: float = field(default=ardeos_config.SEARING_BLAZE_TICK_INTERVAL, init=False)
    cinder_tick_amount: int = field(default=ardeos_config.SEARING_BLAZE_CINDER_TICK_AMOUNT, init=False)

    is_agonizing_blaze: bool = field(init=True)
    agonizing_blaze_stacks: int = field(default=1, init=False)
    agonizing_blaze_damage_per_stack: float = field(default=ardeos_config.AGONIZING_BLAZE_DAMAGE_PER_STACK, init=False)
    agonizing_blaze_max_stacks: int = field(default=ardeos_config.AGONIZING_BLAZE_MAX_STACKS, init=False)

    pandemic_duration_fraction: float = field(default=0.3, init=False)
    _max_duration: float = field(default=ardeos_config.SEARING_BLAZE_DURATION, init=False)

    @property
    def max_duration(self) -> float:
        return self._max_duration

    @property
    def average_tick_damage_snapshot(self) -> "SnapshotStats":
        snapshot = super().average_tick_damage_snapshot
        if self.is_agonizing_blaze and self.agonizing_blaze_stacks > 0:
            snapshot = snapshot.scale_average_damage(
                1 + self.agonizing_blaze_damage_per_stack * (self.agonizing_blaze_stacks - 1)
            )
        return snapshot

    def _fire_tick(self, guard: int) -> None:
        super()._fire_tick(guard)
        if self.is_agonizing_blaze and guard == self._tick_interval_change_guard and self.attached_to is not None:
            self.agonizing_blaze_stacks = min(self.agonizing_blaze_stacks + 1, self.agonizing_blaze_max_stacks)

    def fuse(self, existing: list[Self]) -> bool:  # ty:ignore[invalid-method-override]
        """Called when self is a new effect incoming on the target and the target already has one or more effects of the same type.

        Return a flag indicating whether to keep self or discard it.

        Overwritten: if self.is_agonizing_blaze, this becomes a stacking dot
        for stacking dots, we keep existing instead of keeping incoming.
        We're back to standard effect fuse.

        if not self.is_agonizing_blaze, we do the standard dot fuse: discard existing and keep incomming

        In both cases, we have "pandemic" (wow terminology) extension of the duration.
        New duration is the sum of current duration + new duration up to 130% of base duration.
        This also extends max duration.
        """
        if not self.is_agonizing_blaze:
            current = existing[0]
            new_duration = min(self.duration + current.duration, (1 + self.pandemic_duration_fraction) * self.duration)
            self.duration = new_duration
            self._max_duration = new_duration

            for dot in existing:
                dot.remove(is_remove_from_expiration=False)

            return True

        else:
            current = existing[0]
            if current.attached_to is None:
                raise Exception(f"current existing effect {current} is unnattached during fuse")  # noqa: TRY002, TRY003

            # reset duration with pandemic increase
            new_duration = min(self.duration + current.duration, (1 + self.pandemic_duration_fraction) * self.duration)
            current.duration = new_duration
            current._max_duration = new_duration

            current._schedule_expiry()

            self.owner.state.bus.emit(
                EffectRefreshed(
                    effect=current,
                    target=current.attached_to,
                )
            )

            current.on_fuse(self)

            return False


@dataclass(kw_only=True, repr=False)
class EngulfingFlamesDoT(ArdeosCinderGeneratingDoT):
    name: str = field(default="engulfing_flames_dot", init=False)
    average_damage: float = field(
        default=(ardeos_config.ENGULFING_FLAMES_DAMAGE_MIN + ardeos_config.ENGULFING_FLAMES_DAMAGE_MAX) / 2,
        init=False,
    )
    duration: float = field(init=True)  # set by ability; talent can extend it
    base_tick_interval: float = field(default=ardeos_config.ENGULFING_FLAMES_TICK_INTERVAL, init=False)
    cinder_tick_interval: float = field(default=ardeos_config.ENGULFING_FLAMES_TICK_INTERVAL, init=False)
    cinder_tick_amount: int = field(default=ardeos_config.ENGULFING_FLAMES_CINDER_TICK_AMOUNT, init=False)

    def fuse(self, existing: list[Self]) -> bool:  # ty:ignore[invalid-method-override]
        return True


@dataclass(kw_only=True, repr=False)
class IncinerateDoT(DoTEffect):
    name: str = field(default="incinerate_dot", init=False)
    average_damage: float = field(
        default=(ardeos_config.INCINERATE_DOT_DAMAGE_MIN + ardeos_config.INCINERATE_DOT_DAMAGE_MAX) / 2,
        init=False,
    )
    duration: float = field(default=ardeos_config.INCINERATE_DOT_DURATION, init=False)
    base_tick_interval: float = field(default=ardeos_config.INCINERATE_DOT_TICK_INTERVAL, init=False)
    max_stacks: int = field(default=99, init=False)
    damage_bonus_per_stack: float = field(default=ardeos_config.INCINERATE_DOT_DAMAGE_BONUS_PER_STACK, init=False)

    @property
    def average_tick_damage_snapshot(self) -> "SnapshotStats":
        return super().average_tick_damage_snapshot.scale_average_damage(
            1 + self.damage_bonus_per_stack * (self.stacks - 1)
        )

    def fuse(self, existing: list[Self]) -> bool:  # ty:ignore[invalid-method-override]
        """Called when self is a new effect incoming on the target and the target already has one or more effects of the same type.

        Return a flag indicating whether to keep self or discard it.

        Overwritten: for stacking dots, we keep existing instead of keeping incoming.
        We're back to standard effect fuse.
        """
        current = existing[0]
        if current.attached_to is None:
            raise Exception(f"current existing effect {current} is unnattached during fuse")  # noqa: TRY002, TRY003

        # reset duration
        current.duration = self.duration
        current.stacks = min(self.stacks + current.stacks, current.max_stacks)
        current._schedule_expiry()

        self.owner.state.bus.emit(
            EffectRefreshed(
                effect=current,
                target=current.attached_to,
            )
        )

        current.on_fuse(self)

        return False


@dataclass(kw_only=True, repr=False)
class FireBallDoT(AccumulatorEffect):
    name: str = field(default="fireball_dot", init=False)
    owner: "Ardeos"
    duration: float = field(default=ardeos_config.FIREBALL_DOT_DURATION, init=False)
    base_tick_interval: float = field(default=ardeos_config.FIREBALL_DOT_TICK_INTERVAL, init=False)

    crit_percent_override: float = field(init=True)

    def _fire_tick(self, guard: int) -> None:
        super()._fire_tick(guard)
        if guard != self._tick_interval_change_guard or self.attached_to is None:
            return

        if self.owner.state.rng.random() < 0.5:
            self.owner._change_cinder(2)


@dataclass(kw_only=True, repr=False)
class FireFrogsDoT(AccumulatorEffect):
    name: str = field(default="firefrogs_dot", init=False)
    duration: float = field(default=ardeos_config.FIREFROGS_DOT_DURATION, init=False)
    base_tick_interval: float = field(default=ardeos_config.FIREFROGS_DOT_TICK_INTERVAL, init=False)

    crit_percent_override: float = field(init=True)


@dataclass(kw_only=True, repr=False)
class CracklingInfernoBurnDoT(AccumulatorEffect):
    name: str = field(default="crackling_inferno_burn_dot", init=False)
    duration: float = field(default=ardeos_config.CRACKLING_INFERNO_DOT_DURATION, init=False)
    base_tick_interval: float = field(default=ardeos_config.CRACKLING_INFERNO_DOT_TICK_INTERVAL, init=False)


# ---------------------------------------------------------------------------
# Single effects
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class WildfireEffect(Effect):
    owner: Player
    dot_tick_acceleration: float = field(default=ardeos_config.WILDFIRE_DOT_TICK_ACCELERATION, init=False)
    duration: float = field(default=ardeos_config.WILDFIRE_DURATION, init=False)

    def on_add(self) -> None:
        self.owner.dot_tick_rate *= 1 - self.dot_tick_acceleration

    def on_remove(self, *, is_remove_from_expiration: bool = False) -> None:
        self.owner.dot_tick_rate = 1


@dataclass(kw_only=True, repr=False)
class ReignOfFireEffect(Effect):
    """Next FireBall cast gains +100% crit. Consumed on cast."""

    owner: "Ardeos"

    name: str = field(default="reign_of_fire_effect", init=False)
    crit_bonus: float = field(default=ardeos_config.REIGN_OF_FIRE_CRIT_BONUS, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SnapshotCreation, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: SnapshotCreation) -> None:
        from .ability import FireBall

        if not isinstance(event.damage_source, FireBall):
            return

        event.snapshot = event.snapshot.add_crit_percent(self.crit_bonus)
        self.remove()
        logger.debug("Reign of Fire effect: FireBall +100% crit → consumed")


# ---------------------------------------------------------------------------
# Aura + effect pairs
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DevouringFlameAura(Effect):
    """Permanent aura: manages DevouringFlameDebuff on targets based on EngulfingFlamesDoT presence."""

    owner: "Ardeos"

    name: str = field(default="devouring_flame_aura", init=False)
    damage_per_ef_stack: float = field(default=ardeos_config.DEVOURING_FLAME_DAMAGE_PER_EF_STACK, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        ef_count = len(event.target.effects.filter(EngulfingFlamesDoT))
        if ef_count == 0:
            return

        multiplier = (1 + self.damage_per_ef_stack) ** ef_count
        event.snapshot = event.snapshot.scale_average_damage(multiplier)
        logger.trace(f"Devouring Flame: {ef_count} EF stack(s) → ×{multiplier:.3f} on {self.attached_to}")


@dataclass(kw_only=True, repr=False)
class SlowBurnAura(Effect):
    """Permanent aura: FireBallDoT tick → SearingBlazeDoT and EngulfingFlamesDoT +0.5s."""

    owner: "Ardeos"

    name: str = field(default="slow_burn_aura", init=False)
    dot_duration_extension: float = field(default=ardeos_config.SLOW_BURN_DOT_DURATION_EXTENSION, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityPeriodicDamage, self._on_dot_tick, owner=self)

    def _on_dot_tick(self, event: AbilityPeriodicDamage) -> None:
        if not isinstance(event.damage_source, FireBallDoT):
            return
        target = event.target
        for dot in list(target.effects.filter(SearingBlazeDoT)) + list(target.effects.filter(EngulfingFlamesDoT)):
            dot.extend_duration(self.dot_duration_extension)
        logger.trace(f"Slow Burn: FireBall DoT tick → EF/SB +0.5s on {target}")


@dataclass(kw_only=True, repr=False)
class BackdraftAura(Effect):
    """Permanent aura: Detonate cast → all SearingBlazeDoT durations +1.5s (cap 24s)."""

    owner: "Ardeos"

    name: str = field(default="backdraft_aura", init=False)

    searing_blaze_duration_extension: float = field(default=ardeos_config.BACKDRAFT_SB_DURATION_EXTENSION, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        from .ability import Detonate

        if not isinstance(event.ability, Detonate):
            return
        count = 0
        for enemy in self.owner.state.enemies:
            for dot in enemy.effects.filter(SearingBlazeDoT):
                dot.extend_duration(self.searing_blaze_duration_extension)
                count += 1

        logger.debug(
            f"Backdraft: Detonate → {count} SB dot(s) +{self.searing_blaze_duration_extension:.1f}s (cap {ardeos_config.SEARING_BLAZE_DURATION:.0f}s)"
        )


@dataclass(kw_only=True, repr=False)
class FlareUpAura(Effect):
    """Permanent aura: InfernalWave hit → 50% damage to other enemies with SearingBlazeDoT."""

    owner: "Ardeos"

    name: str = field(default="flare_up_aura", init=False)

    damage_echo_fraction: float = field(default=0.5, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import InfernalWave

        if not isinstance(event.damage_source, InfernalWave):
            return

        base_damage = self.damage_echo_fraction * event.damage
        primary_target = event.target

        for enemy in self.owner.state.enemies:
            if enemy is not primary_target and enemy.effects.has(SearingBlazeDoT):
                splash = AbilityDamage(
                    damage_source=self,
                    owner=self.owner,
                    target=enemy,
                    is_crit=False,
                    is_grievous_crit=False,
                    damage=base_damage,
                    is_secondary=True,
                )
                self.owner.state.bus.emit(splash)

        logger.trace("Flare Up: InfernalWave hit → 50% splash to SB targets")


@dataclass(kw_only=True, repr=False)
class CrashAndBurnAura(Effect):
    """Permanent aura: SearingBlazeDoT tick → FireBall CD -0.1s."""

    owner: "Ardeos"

    name: str = field(default="crash_and_burn_aura", init=False)
    fireball_cdr: float = field(default=ardeos_config.CRASH_AND_BURN_FIREBALL_CDR, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityPeriodicDamage, self._on_dot_tick, owner=self)

    def _on_dot_tick(self, event: AbilityPeriodicDamage) -> None:
        if not isinstance(event.damage_source, SearingBlazeDoT):
            return
        self.owner.fire_ball._remove_cooldown(self.fireball_cdr)
        logger.trace("Crash and Burn: SB tick → FireBall CD -0.1s")


@dataclass(kw_only=True, repr=False)
class RollingFlamesAura(Effect):
    """Permanent aura: SearingBlazeDoT tick → EF CD -0.25s; InfernalWave cast → EF CD -1s."""

    owner: "Ardeos"

    name: str = field(default="rolling_flames_aura", init=False)
    ef_cdr_per_sb_tick: float = field(default=ardeos_config.ROLLING_FLAMES_EF_CDR_PER_SB_TICK, init=False)
    ef_cdr_per_iw_cast: float = field(default=ardeos_config.ROLLING_FLAMES_EF_CDR_PER_IW_CAST, init=False)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityPeriodicDamage, self._on_dot_tick, owner=self)
        bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_dot_tick(self, event: AbilityPeriodicDamage) -> None:
        if not isinstance(event.damage_source, SearingBlazeDoT):
            return
        self.owner.engulfing_flames._remove_cooldown(self.ef_cdr_per_sb_tick)
        logger.trace("Rolling Flames: SB tick → EF CD -0.25s")

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        from .ability import InfernalWave

        if not isinstance(event.ability, InfernalWave):
            return
        self.owner.engulfing_flames._remove_cooldown(self.ef_cdr_per_iw_cast)
        logger.debug("Rolling Flames: InfernalWave cast → EF CD -1s")


@dataclass(kw_only=True, repr=False)
class CracklingInfernoAura(Effect):
    """Permanent aura: InfernalWave +20% crit; on crit applies CracklingInfernoBurnDoT."""

    owner: "Ardeos"

    name: str = field(default="crackling_inferno_aura", init=False)
    iw_crit_bonus: float = field(default=ardeos_config.CRACKLING_INFERNO_IW_CRIT_BONUS, init=False)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(SnapshotCreation, self._on_pre_damage, owner=self)
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_pre_damage(self, event: SnapshotCreation) -> None:
        from .ability import InfernalWave

        if not isinstance(event.damage_source, InfernalWave):
            return
        event.snapshot = event.snapshot.add_crit_percent(self.iw_crit_bonus)
        logger.trace("Crackling Inferno: InfernalWave +20% crit")

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import InfernalWave

        if not isinstance(event.damage_source, InfernalWave) or not event.is_crit:
            return
        event.target.effects.add(CracklingInfernoBurnDoT(owner=self.owner, average_damage=0.60 * event.damage))


@dataclass(kw_only=True, repr=False)
class PyrophibianFrenzyAura(Effect):
    """Permanent aura: any DoT crit → 8% chance to spawn a Fire Frog."""

    owner: "Ardeos"

    name: str = field(default="pyrophibian_frenzy_aura", init=False)
    proc_chance: float = field(default=ardeos_config.PYROPHIBIAN_FRENZY_PROC_CHANCE, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityPeriodicDamage, self._on_dot_tick, owner=self)

    def _on_dot_tick(self, event: AbilityPeriodicDamage) -> None:
        if not event.is_crit:
            return
        if self.owner.state.rng.random() >= self.proc_chance:
            return
        self.owner.fire_frogs._frog_attack(event.target)
        logger.debug("Pyrophibian Frenzy: DoT crit → spawn Fire Frog")


@dataclass(kw_only=True, repr=False)
class ReignOfFireAura(Effect):
    """Permanent aura: Detonate at 1.5 PPM → FireBall +1 charge + ReignOfFireEffect."""

    owner: "Ardeos"

    name: str = field(default="reign_of_fire_aura", init=False)
    ppm: float = field(default=ardeos_config.REIGN_OF_FIRE_BASE_PPM, init=False)
    real_ppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self.real_ppm = RealPPM(
            base_ppm=self.ppm,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        from .ability import Detonate

        if not isinstance(event.ability, Detonate):
            return
        if not self.real_ppm.check():
            return
        self.owner.fire_ball._add_charge()
        self.owner.effects.add(ReignOfFireEffect(owner=self.owner))
        logger.debug("Reign of Fire: Detonate PPM proc → FireBall +1 charge + effect")


@dataclass(kw_only=True, repr=False)
class ExplosivoAura(Effect):
    """Permanent aura: Apocalypse hits → up to +150% damage based on target max HP."""

    owner: "Ardeos"

    name: str = field(default="explosivo_aura", init=False)

    max_multiplier: float = field(default=2.50, init=False)
    fireball_cdr: float = field(default=ardeos_config.EXPLOSIVO_FIREBALL_CDR, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        from .ability import FireBall

        if not isinstance(event.ability, FireBall):
            return
        self.owner.apocalypse._remove_cooldown(self.fireball_cdr)
        logger.trace("Explosivo: FireBall cast → Apocalypse CD -8s")

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import Apocalypse

        if not isinstance(event.damage_source, Apocalypse):
            return

        multiplier = self.max_multiplier * event.target.percent_hp
        event.snapshot = event.snapshot.scale_average_damage(multiplier)

        logger.trace(f"Explosivo: Apocalypse hit → damage multiplier: {multiplier}")


@dataclass(kw_only=True, repr=False)
class SpontaneousCombustionAura(Effect):
    """Permanent aura: SearingBlazeDoT/EngulfingFlamesDoT ticks → roll for +100% crit."""

    owner: "Ardeos"

    name: str = field(default="spontaneous_combustion_aura", init=False)
    base_proc_chance: float = field(default=ardeos_config.SPONTANEOUS_COMBUSTION_BASE_PROC_CHANCE, init=False)
    crit_scaling: float = field(default=ardeos_config.SPONTANEOUS_COMBUSTION_CRIT_SCALING, init=False)
    crit_bonus: float = field(default=ardeos_config.SPONTANEOUS_COMBUSTION_CRIT_BONUS, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SnapshotCreation, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: SnapshotCreation) -> None:
        if not isinstance(event.damage_source, (SearingBlazeDoT, EngulfingFlamesDoT)):
            return
        proc_chance = self.base_proc_chance + self.owner.stats.crit_percent * self.crit_scaling
        if self.owner.state.rng.random() >= proc_chance:
            return
        event.snapshot = event.snapshot.add_crit_percent(self.crit_bonus)
        logger.trace(f"Spontaneous Combustion: proc ({proc_chance:.2%}) → +100% crit")


@dataclass(kw_only=True, repr=False)
class FrogSquadAura(Effect):
    """Permanent aura: FireFrogs direct hits deal +10% damage."""

    owner: "Ardeos"

    name: str = field(default="frog_squad_aura", init=False)
    damage_bonus: float = field(default=ardeos_config.FROG_SQUAD_DAMAGE_BONUS, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SnapshotCreation, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: SnapshotCreation) -> None:
        from .ability import FireFrogs

        if not isinstance(event.damage_source, FireFrogs):
            return
        event.snapshot = event.snapshot.scale_average_damage(1 + self.damage_bonus)
        logger.trace("Frog Squad: FireFrogs direct hit → +10% damage")


@dataclass(kw_only=True, repr=False)
class FirestarterAura(Effect):
    """Permanent aura: all DoT hits gain +20% crit chance."""

    owner: "Ardeos"

    name: str = field(default="firestarter_aura", init=False)
    dot_crit_bonus: float = field(default=ardeos_config.FIRESTARTER_DOT_CRIT_BONUS, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SnapshotCreation, self._on_snapshot_creation, owner=self)

    def _on_snapshot_creation(self, event: SnapshotCreation) -> None:
        if not isinstance(event.damage_source, DoTEffect):
            return

        event.snapshot = event.snapshot.add_crit_percent(self.dot_crit_bonus)
        logger.trace("Firestarter: DoT hit → +20% crit")


@dataclass(kw_only=True, repr=False)
class IntensifyingInfernoAura(Effect):
    """Permanent aura: InfernalWave → +15% damage per unique DoT type on target."""

    owner: "Ardeos"

    name: str = field(default="intensifying_inferno_aura", init=False)
    damage_per_dot_type: float = field(default=ardeos_config.INTENSIFYING_INFERNO_DAMAGE_PER_DOT_TYPE, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import InfernalWave

        if not isinstance(event.damage_source, InfernalWave) or event.is_dot:
            return
        unique_dot_count = len({type(e) for e in event.target.effects if isinstance(e, DoTEffect)})
        if unique_dot_count == 0:
            return
        multiplier = 1.0 + self.damage_per_dot_type * unique_dot_count
        event.snapshot = event.snapshot.scale_average_damage(multiplier)
        logger.trace(f"Intensifying Inferno: {unique_dot_count} unique DoT type(s) → ×{multiplier:.2f}")


@dataclass(kw_only=True, repr=False)
class IncinerateHitAura(Effect):
    """Permanent aura: each Incinerate hit → extend all active DoTs by 1.5s + stack IncinerateDoT."""

    owner: "Ardeos"

    name: str = field(default="incinerate_hit_aura", init=False)
    dot_extension: float = field(default=ardeos_config.INCINERATE_HIT_DOT_EXTENSION, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import Incinerate

        if not isinstance(event.damage_source, Incinerate):
            return
        for effect in event.target.effects:
            if isinstance(effect, DoTEffect):
                effect.extend_duration(self.dot_extension)

        event.target.effects.add(IncinerateDoT(owner=self.owner))

        logger.trace(f"Incinerate hit: all DoTs +1.5s on {event.target}; IncinerateDoT stack added")


@dataclass(kw_only=True, repr=False)
class ApocalypseAura(Effect):
    """Permanent aura: Apocalypse hit → apply SearingBlazeDoT to every target hit."""

    owner: "Ardeos"

    name: str = field(default="apocalypse_aura", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import Apocalypse

        if not isinstance(event.damage_source, Apocalypse):
            return
        self.owner.searing_blaze._apply_searing_blaze(event.target)


@dataclass(kw_only=True, repr=False)
class FireBallAccumulatorAura(Effect):
    """Permanent aura: FireBall direct hit → create FireBallDoT for 20% of hit damage."""

    owner: "Ardeos"

    name: str = field(default="fireball_accumulator_aura", init=False)
    fixed_crit_chance: float = field(default=0.0, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FireBall

        if not isinstance(event.damage_source, FireBall):
            return

        dot = FireBallDoT(
            owner=self.owner,
            average_damage=0.20 * event.damage,
            crit_percent_override=self.fixed_crit_chance,
        )

        event.target.effects.add(dot)


@dataclass(kw_only=True, repr=False)
class FireFrogsAccumulatorAura(Effect):
    """Permanent aura: FireFrogs direct hit → create/update single FireFrogsDoT for 100% of hit damage."""

    owner: "Ardeos"

    name: str = field(default="firefrogs_accumulator_aura", init=False)
    fixed_crit_chance: float = field(default=0.0, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FireFrogs

        if not isinstance(event.damage_source, FireFrogs):
            return

        dot = FireFrogsDoT(
            owner=self.owner,
            average_damage=1.0 * event.damage,
            crit_percent_override=self.fixed_crit_chance,
        )
        event.target.effects.add(dot)


@dataclass(kw_only=True, repr=False)
class ArdeosSpiritProcAura(Effect):
    owner: "Ardeos"

    name: str = field(default="ardeos_spirit_effect", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(ResourceSpent, self._on_resource_spent, owner=self)

    def _on_resource_spent(self, event: ResourceSpent) -> None:
        if event.resource_type != Resource.EMBERS:
            return

        state = self.owner.state

        proc_chance = self.owner.stats.spirit_proc_chance

        roll = state.rng.random() if proc_chance > 0 else 0.0
        logger.trace(f"{proc_chance = }, {roll = } in spirit_proc)")
        if proc_chance == 0.0 or roll >= proc_chance:
            return

        ability = event.ability
        resource_amount = event.resource_amount
        self._resolve_proc(ability, resource_amount)

        logger.debug(f"spirit proc triggered by {event.ability}")

    def _resolve_proc(self, ability: Ability, resource_amount: int) -> None:
        logger.debug(f"spirit proc resolving: refund {resource_amount} ember")
        state = self.owner.state

        state.bus.emit(SpiritProc(ability=ability, owner=self.owner, resource_amount=resource_amount))

        self.owner.spirit_points = min(
            self.owner.spirit_points + self.owner.spirit_point_gain_on_proc, self.owner.max_spirit_points
        )

        # Refund resources
        self.owner._gain_ember(resource_amount)
