import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from loguru import logger

from fellowship_sim.base_classes import (
    Ability,
    AbilityPeriodicDamage,
    Effect,
    Entity,
    Player,
    RealPPM,
    create_standard_damage,
)
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    ComputeCooldownReduction,
    PreDamageSnapshotUpdate,
    ResourceSpent,
    SpiritProc,
)
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.elarion.ability import (
    CelestialShot,
    FocusedShot,
    HeartseekerBarrage,
    HighwindArrow,
    LunarlightExplosion,
    LunarlightSalvo,
    Multishot,
    SkystriderGrace,
    Volley,
)
from fellowship_sim.elarion.buff import EmpoweredMultishotChargeBuff

if TYPE_CHECKING:
    from fellowship_sim.elarion.setup import Elarion


@dataclass(kw_only=True, repr=False)
class CelestialImpetusProc(Effect):
    """Celestial Impetus: on celestial shot, apply 3 marks to target."""

    owner: "Elarion" = field(init=True)

    name: str = field(default="celestial_impetus_proc", init=False)
    max_stacks: int = field(default=2, init=False)
    duration: float = field(default=15.0, init=False)

    main_target_mark_count: int = field(init=True)
    triggers_impending_barrage: bool = field(init=True)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        state = self.owner.state
        if isinstance(event.ability, CelestialShot) and self.stacks > 0:
            target = event.target
            state.schedule(
                time_delay=0.0,
                callback=GenericTimedEvent(
                    name="celestial_impetus consume stack", callback=lambda: self._consume_stack(target)
                ),
            )
            logger.trace(f"CI: consume-stack scheduled ({self.stacks} stacks → {target})")

    def _consume_stack(self, target: Entity) -> None:
        logger.debug(f"CI stack consumed: {self.main_target_mark_count} marks → {target}")
        target.effects.add(LunarlightMarkEffect(owner=self.owner, stacks=self.main_target_mark_count))

        if self.triggers_impending_barrage:
            self.owner.effects.add(ImpendingHeartseeker(owner=self.owner))
            logger.debug(f"CI: Impending Heartseeker applied to {self.owner}")

        self.stacks -= 1
        if self.stacks == 0:
            self.remove()


@dataclass(kw_only=True, repr=False)
class CelestialImpetusAura(Effect):
    """Permanent aura on Elarion: gain CelestialImpetusProc on focused shot.

    - Each Focused Shot cast may one charge of CIProc, gated by RealPPM (base 2, haste-scaled).
    """

    owner: "Elarion" = field(init=True)

    name: str = field(default="celestial_impetus_aura", init=False)

    main_target_mark_count: int = field(default=3, init=False)
    triggers_impending_barrage: bool = field(default=False, init=False)

    real_ppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self.real_ppm = RealPPM(
            base_ppm=2.0,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        if isinstance(event.ability, FocusedShot) and self.real_ppm.check():
            self.owner.effects.add(
                CelestialImpetusProc(
                    owner=self.owner,
                    main_target_mark_count=self.main_target_mark_count,
                    triggers_impending_barrage=self.triggers_impending_barrage,
                )
            )


@dataclass(kw_only=True, repr=False)
class LunarlightMarkEffect(Effect):
    """Debuff on an enemy. Each time damage is dealt to the marked target,
    fires LunarlightSalvo (or LunarlightExplosion for HeartseekerBarrage hits) and consumes one charge.
    Removes itself when charges reach zero or duration expires.
    LunarlightSalvo/LunarlightExplosion hits do not re-trigger the mark.
    Duplicate applications merge: duration is renewed, stacks are summed up to max_stacks.
    When the triggering ability is HeartseekerBarrage, there is a 20% chance to fire
    LunarlightExplosion (hits the bearer + up to 11 enemies) instead of LunarlightSalvo.
    """

    owner: "Elarion" = field(init=True)

    stacks: int = field(default=1, init=True)  # Mark as init since multiple mechanics can apply multiple stacks at once

    name: str = field(default="lunarlight_mark", init=False)
    duration: float = field(default=15.0, init=False)
    max_stacks: int = field(default=20, init=False)

    explosion_chance: float = field(default=0.20, init=False)

    # Initialize a list of sources which do not trigger
    no_trigger_sources: list[type[Ability[Player]] | type[Effect]] = field(
        default_factory=lambda: [
            LunarlightSalvo,
            LunarlightExplosion,
        ],
        init=False,
    )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage_dealt, owner=self)
        self.owner.state.bus.subscribe(AbilityPeriodicDamage, self._on_damage_dealt, owner=self)

    def _on_damage_dealt(self, event: AbilityDamage | AbilityPeriodicDamage) -> None:
        if event.target is not self.attached_to:
            return

        if isinstance(event.damage_source, tuple(self.no_trigger_sources)):
            return

        proc_chance = 0.5 if event.is_crit else 0.25

        # double proc chance on barrage and volley, if the owner has the appropriate talent
        # fmt: on
        if (self.owner.has_increased_proc_chance_barrage and isinstance(event.damage_source, HeartseekerBarrage)) or (
            self.owner.has_increased_proc_chance_volley and isinstance(event.damage_source, Volley)
        ):
            # fmt:on
            proc_chance = min(1.0, proc_chance * 2)

        state = self.owner.state
        roll = state.rng.random()
        success = roll < proc_chance
        logger.trace(f"mark proc roll ({event.damage_source}): {roll:.3f} vs {proc_chance:.2f} → {success}")

        if not success:
            return

        is_barrage = isinstance(event.damage_source, HeartseekerBarrage)

        roll = state.rng.random() if is_barrage else 0
        proba = self.explosion_chance
        roll_success = roll < proba
        logger.trace(f"explosion roll: roll={roll}, proba={proba}, success={roll_success}")
        if is_barrage and roll_success:
            callback = lambda: self.owner._lunarlight_explosion._do_cast(event.target)
        else:
            callback = lambda: self.owner._lunarlight_salvo._do_cast(event.target)

        state.schedule(time_delay=0.0, callback=GenericTimedEvent(name="lunarlight_mark proc", callback=callback))

        self.stacks -= 1

        logger.debug(f"mark stack consumed on {event.owner} → {self.stacks} remaining")
        if self.stacks <= 0:
            self.remove()


@dataclass(kw_only=True, repr=False)
class SpiritEffectProc(Effect):
    """Permanent aura on Elarion.

    - Any focus-spending ability can trigger a spirit proc.
    - Proc chance is character.stats.spirit_proc_chance (simple rng roll).
    - On proc: refunds the focus cost of the triggering ability.
    - On proc: applies 5 LunarlightMark stacks to the main target and
      2 stacks to each of 2 randomly chosen secondary enemies.
    """

    owner: "Elarion" = field(init=True)

    name: str = field(default="spirit_effect", init=False)

    main_target_mark_count: int = field(default=5, init=False)
    secondary_target_mark_count: int = field(default=2, init=False)
    num_secondary_targets: int = field(default=2, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(ResourceSpent, self._on_resource_spent, owner=self)

    def _on_resource_spent(self, event: ResourceSpent) -> None:
        state = self.owner.state

        proc_chance = self.owner.stats.spirit_proc_chance
        roll = state.rng.random() if proc_chance > 0 else 0.0
        logger.trace(f"{proc_chance = }, {roll = } in spirit_proc)")
        if proc_chance == 0.0 or roll >= proc_chance:
            return

        ability: Ability[Elarion] = event.ability  # ty:ignore[invalid-assignment]
        target = event.target
        resource_amount = event.resource_amount
        state.schedule(
            time_delay=0.0,
            callback=GenericTimedEvent(
                name="spirit_effect proc", callback=lambda: self._resolve_proc(ability, target, resource_amount)
            ),
        )

        logger.debug(f"spirit proc triggered by {ability}")

    def _resolve_proc(self, ability: Ability["Elarion"], main_target: Entity, resource_amount: int) -> None:
        logger.debug(f"spirit proc resolving: refund {resource_amount} focus, marks →  {main_target}")
        state = self.owner.state

        state.bus.emit(SpiritProc(ability=ability, owner=self.owner, resource_amount=resource_amount))

        # Gain 1 spirit point
        self.owner.spirit_points = min(self.owner.spirit_points + 1, self.owner.max_spirit_points)

        # Refund focus
        self.owner.focus += resource_amount

        # Apply marks
        self._apply_marks(main_target, self.main_target_mark_count)
        for enemy in state.select_targets(main_target, self.num_secondary_targets):
            self._apply_marks(enemy, self.secondary_target_mark_count)

    def _apply_marks(self, enemy: Entity, count: int) -> None:
        enemy.effects.add(LunarlightMarkEffect(owner=self.owner, stacks=count))


@dataclass(kw_only=True, repr=False)
class FinalCrescendo(Effect):
    """Aura: on HWA cast, gain a stack. At 3 stacks, next HWA has +100% damage and bounces to 7 targets.

    Implementation details:
    - Gain stacks on HWA
    - At 3 stacks, apply the buff via a field on the HighwindArrow instance on elarion
    - Consumed on the next HWA cast via AbilityCastSuccess.
    - The ability encodes the effects of the buff.
    """

    owner: "Elarion" = field(init=True)

    name: str = field(default="final_crescendo", init=False)
    stacks: int = field(default=0, init=False)
    max_stacks: int = field(default=3, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, HighwindArrow):
            return

        # if at 3 stacks, clear stacks and remove buff from ability
        if self.stacks == 3:
            self.stacks = 0
            highwind_arrow = self.owner.highwind_arrow
            highwind_arrow.has_final_crescendo_buff = False
            logger.trace(f"Final crescendo applied to HWA: stacks reset {self.stacks}/3; buff removed from HWA")
            return

        # else, add a stack
        else:
            self.stacks += 1
            if self.stacks == 3:
                highwind_arrow = self.owner.highwind_arrow
                highwind_arrow.has_final_crescendo_buff = True
                logger.debug(f"Final_crescendo: stacks {self.stacks}/3; buff added to HWA")
            else:
                logger.trace(f"Final_crescendo: stacks {self.stacks}/3")


@dataclass(kw_only=True, repr=False)
class ResurgentWinds(Effect):
    """Buff: next HighwindArrow is instant, cost no focus and gains +50% damage on targets with LunarlightMarkEffect (NB: multiplicative, stacking with FC).

    Consumed on the next HWA cast via AbilityCastSuccess.
    The ability encodes the effects of the buff.
    """

    owner: "Elarion" = field(init=True)

    name: str = field(default="resurgent_winds", init=False)

    duration: float = field(default=15.0, init=False)
    max_stacks: int = field(default=2, init=False)

    def on_add(self) -> None:

        highwind_arrow = self.owner.highwind_arrow
        highwind_arrow._add_charge()
        highwind_arrow.has_resurgent_winds_buff = True
        logger.debug("Resurgent winds: HWA +1 charge and buff gained")
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def on_remove(self) -> None:
        highwind_arrow = self.owner.highwind_arrow
        highwind_arrow.has_resurgent_winds_buff = False

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, HighwindArrow):
            return

        self.owner.state.schedule(0, GenericTimedEvent(name="Remove resurgent winds", callback=self.remove))


@dataclass(kw_only=True, repr=False)
class ImpendingHeartseeker(Effect):
    """Buff: next HeartseekerBarrage cast gains +10% damage per subsequent tick (linear scaling).

    Consumed on the next HeartseekerBarrage cast via AbilityCastSuccess.
    The ability encodes the effects of the buff.
    """

    owner: "Elarion" = field(init=True)

    name: str = field(default="impending_heartseeker", init=False)
    duration: float = field(default=15.0, init=False)

    def on_add(self) -> None:

        barrage = self.owner.heartseeker_barrage
        barrage._reset_cooldown()
        barrage.has_impending_barrage = True
        logger.debug("Impending Heartseeker: Heartseeker Barrage cooldown reset and buff gained")
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def on_remove(self) -> None:
        barrage = self.owner.heartseeker_barrage
        barrage.has_impending_barrage = False

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, HeartseekerBarrage):
            return

        self.remove()


@dataclass(kw_only=True, repr=False)
class Fusillade(Effect):
    """Setup passive: HeartseekerBarrage gains +20% crit chance."""

    owner: "Elarion" = field(init=True)

    name: str = field(default="fusillade", init=False)

    crit_bonus: float = field(default=0.20, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if not isinstance(event.damage_source, HeartseekerBarrage):
            return
        event.snapshot = event.snapshot.add_crit_percent(self.crit_bonus)
        logger.trace("Fusillade: barrage crit chance +0.20")


@dataclass(kw_only=True, repr=False)
class FocusedExpanseEffect(Effect):
    """"""

    owner: "Elarion" = field(init=True)
    name: str = field(default="focused_expanse", init=False)

    proc_chance: float = field(default=0.20, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, (FocusedShot, Multishot)):
            return

        roll = self.owner.state.rng.random()

        if roll < self.proc_chance:
            self.owner.effects.add(EmpoweredMultishotChargeBuff(owner=self.owner))


@dataclass(kw_only=True, repr=False)
class LastLights(Effect):
    """Passive: +30% crit chance on targets with <30% remaining HP.

    Subscribes globally to PreDamageSnapshotUpdate and patches the snapshot
    just before damage is applied.
    """

    name: str = field(default="last_lights", init=False)

    hp_percent_threshold: float = field(default=0.30, init=False)
    crit_bonus: float = field(default=0.30, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if event.target.percent_hp < self.hp_percent_threshold:
            event.snapshot = event.snapshot.add_crit_percent(self.crit_bonus)
            logger.trace(
                "Last Lights: +{:.0%} crit on {} (percent hp={:.1%})",
                self.crit_bonus,
                event.target,
                event.target.percent_hp,
            )


@dataclass(kw_only=True, repr=False)
class VolleyEffect(Effect):
    """DoT-style effect applied to a target when Volley is cast.

    Fires AbilityDamage ticks at haste-adjusted intervals.
    Haste is snapshotted at cast time and initialized by caller

    tick_interval = base_tick_time / (1 + haste)
    num_ticks     = 1 + floor(volley_duration / base_tick_time * (1 + haste))
    """

    owner: "Elarion" = field(init=True)

    tick_interval: float
    duration: float

    ability: "Volley"

    multishot_extends_duration_by: float
    has_skylit_grace: bool

    name: str = field(default="", init=False)

    _counter: ClassVar[int] = 0

    def __post_init__(self) -> None:
        VolleyEffect._counter += 1
        self.name = f"Volley (ongoing effect) [{VolleyEffect._counter}]"

    @staticmethod
    def get_volley(enemy: Entity) -> "list[VolleyEffect]":
        return [e for e in enemy.effects if isinstance(e, VolleyEffect)]

    def on_add(self) -> None:
        state = self.owner.state

        logger.debug(f"volley effect created with: duration={self.duration}s; tick interval={self.tick_interval}s")

        if self.has_skylit_grace:
            state.bus.subscribe(ComputeCooldownReduction, self._on_compute_cdr, owner=self)
            self.owner._recalculate_cdr_multipliers()
            logger.debug("volley effect: Skylit Grace CDR active")

        if self.multishot_extends_duration_by > 0:
            state.bus.subscribe(AbilityCastSuccess, self._on_multishot_cast, owner=self)
            logger.debug("volley effect: multishot extends duration active")

        state.schedule(time_delay=0.0, callback=GenericTimedEvent(name="volley tick", callback=self._do_tick))

    def on_remove(self) -> None:
        if self.has_skylit_grace:
            self.owner._recalculate_cdr_multipliers()

    def _on_multishot_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, Multishot):
            return
        if self.duration <= 0:
            return

        self.duration += self.multishot_extends_duration_by
        self._schedule_expiry()
        logger.debug(f"volley effect: multishot cast extending duration to {self.duration}s)")

    def _on_compute_cdr(self, event: ComputeCooldownReduction) -> None:
        if not isinstance(event.ability, SkystriderGrace):
            return
        event.cdrecovery_modifiers.append(1.0)
        logger.trace("Volley (Skylit Grace): Skystrider Grace CDA +1.0")

    def _do_tick(self) -> None:
        if self.attached_to is None:
            return

        state = self.owner.state

        create_standard_damage(
            state=state,
            damage_source=self.ability,
            owner=self.owner,
            target=self.attached_to,
            base_damage=self.ability.average_damage,
            num_secondary_targets=self.ability.num_secondary_targets,
            secondary_damage_multiplier=self.ability.secondary_damage_multiplier,
        )

        state.schedule(
            time_delay=self.tick_interval, callback=GenericTimedEvent(name="volley tick", callback=self._do_tick)
        )


@dataclass(kw_only=True, repr=False)
class SkywardMunitions(Effect):
    """Passive: CelestialShot and Multishot casts reduce HighwindArrow and HeartseekerBarrage cooldowns by 1s."""

    owner: "Elarion" = field(init=True)

    name: str = field(default="skyward_munitions", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_ability_cast, owner=self)

    def _on_ability_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, (CelestialShot, Multishot)):
            return

        hwa = self.owner.highwind_arrow
        hwa._reduce_cooldown(1.0)
        barrage = self.owner.heartseeker_barrage
        barrage._reduce_cooldown(1.0)

        ability_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(event.ability).__name__)
        logger.trace(f"Skyward Munitions: {ability_label} → Highwind Arrow/Heartseeker Barrage CD -1s")


@dataclass(kw_only=True, repr=False)
class RepeatingStars(Effect):
    """Passive: each Multishot damage hit reduces Volley's cooldown by 0.3s."""

    owner: "Elarion" = field(init=True)

    name: str = field(default="repeating_stars", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if event.owner is not self.attached_to:
            return
        if not isinstance(event.damage_source, Multishot):
            return

        volley = self.owner.volley
        volley._reduce_cooldown(0.3)
        logger.trace("Repeating Stars: Multishot hit → Volley CD -0.3s")


@dataclass(kw_only=True, repr=False)
class LethalShots(Effect):
    """Passive: each HighwindArrow hit has a 40% chance to add +100% crit_percent to the snapshot.

    Applied independently per hit via PreDamageSnapshotUpdate.
    A crit_percent above 1.0 triggers grievous-crit logic in deal_damage.
    """

    name: str = field(default="lethal_shots")

    proc_chance: float = field(default=0.40, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if not isinstance(event.damage_source, HighwindArrow):
            return

        roll = self.owner.state.rng.random()
        if roll < self.proc_chance:
            event.snapshot = event.snapshot.add_crit_percent(1.0)
            logger.trace(f"Lethal Shots: proc ({roll:.3f} < {self.proc_chance:.2f}) → +100% crit on {event.target}")
        else:
            logger.trace("Lethal Shots: no proc ({:.3f} >= {:.2f})", roll, self.proc_chance)


@dataclass(kw_only=True, repr=False)
class LunarFury(Effect):
    """Setup passive: LunarlightSalvo and LunarlightExplosion deal +30% damage.
    HeartseekerBarrage hits gain double proc chance on LunarlightMark.
    """

    name: str = field(default="lunarlight_fury", init=False)

    bonus_damage_percent: float = field(default=0.3, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if not isinstance(event.damage_source, (LunarlightSalvo, LunarlightExplosion)):
            return

        event.snapshot = event.snapshot.scale_average_damage(1 + self.bonus_damage_percent)

        source_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(event.damage_source).__name__)
        logger.trace(f"Lunar Fury: {source_label} +30% damage")


@dataclass(kw_only=True, repr=False)
class LunarlightAffinity(Effect):
    """Setup passive: LunarlightSalvo and LunarlightExplosion gain +40% crit_percent.
    Volley hits gain double proc chance on LunarlightMark.
    """

    name: str = field(default="lunarlight_affinity", init=False)

    bonus_crit_percent: float = field(default=0.4, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if not isinstance(event.damage_source, (LunarlightSalvo, LunarlightExplosion)):
            return
        event.snapshot = event.snapshot.add_crit_percent(self.bonus_crit_percent)

        source_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(event.damage_source).__name__)
        logger.trace(f"Lunarlight Affinity: {source_label} +40% crit chance")


@dataclass(kw_only=True, repr=False)
class Shimmer(Effect):
    """Debuff on an enemy: take +10% damage per stack from all sources.

    max_stacks=2: 1 stack → +10%, 2 stacks → +20%.
    Duration 9s; reapplication fuses (renews duration, adds stacks up to cap).
    Applied via PreDamageSnapshotUpdate just before damage is dealt.
    """

    name: str = field(default="shimmer", init=False)
    duration: float = field(default=9.0, init=False)

    max_stacks: int = field(default=2, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if event.target is not self.attached_to:
            return
        event.snapshot = event.snapshot.scale_average_damage(1.0 + 0.10 * self.stacks)
        logger.trace(
            "shimmer: {} +{:.0%} damage on {} ({} stacks)",
            event.damage_source,
            0.10 * self.stacks,
            event.target,
            self.stacks,
        )


@dataclass(kw_only=True, repr=False)
class HighwindAppliesShimmerEffect(Effect):
    """Permanent aura: each HighwindArrow damage hit applies Shimmer to the target."""

    name: str = field(default="hwa_shimmer_aura", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if not isinstance(event.damage_source, HighwindArrow):
            return
        event.target.effects.add(Shimmer(owner=self.owner))
        logger.trace(f"Highwind Arrow shimmer aura: Shimmer applied to {event.target}")


@dataclass(kw_only=True, repr=False)
class StarstrikersAscentLegendary(Effect):
    """Legendary: on Spirit proc, 50% chance to gain ImpendingHeartseeker (which resets barrage CD)."""

    owner: "Elarion" = field(init=True)

    name: str = field(default="startstrikers_ascent", init=False)

    proc_chance: float = field(default=0.50, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SpiritProc, self._on_spirit_proc, owner=self)

    def _on_spirit_proc(self, event: SpiritProc) -> None:
        roll = self.owner.state.rng.random()
        if roll < self.proc_chance:
            self.owner.effects.add(ImpendingHeartseeker(owner=self.owner))
            logger.debug(
                "Starstriker's Ascent: proc ({:.3f} < {:.2f}) → Impending Heartseeker applied", roll, self.proc_chance
            )
        else:
            logger.trace("Starstriker's Ascent: no proc ({:.3f} >= {:.2f})", roll, self.proc_chance)
