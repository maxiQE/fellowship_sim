import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from loguru import logger

from fellowship_sim.base_classes import Effect, PreDamageSnapshotUpdate, create_standard_damage
from fellowship_sim.base_classes.ability import (
    Ability,
    CastReturnCode,
    can_cast_check,
)
from fellowship_sim.base_classes.entity import Entity

if TYPE_CHECKING:
    from .entity import Elarion  # noqa: F401

from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    ResourceSpent,
)
from fellowship_sim.base_classes.state import get_state
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.elarion.buff import (
    EmpoweredMultishotChargeBuff,
    EmpoweredMultishotProvider,
    EventHorizonBuff,
    FerventSupremacyBuff,
    SkystriderGraceBuff,
    SkystriderSupremacyBuff,
)

# ---------------------------------------------------------------------------
# Elarion-specific ability base
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class ElarionAbility(Ability["Elarion"]):
    """Base class for all Elarion abilities.

    Declares focus_cost, focus_gain, and secondary-target fields.
    Focus economy is handled by FocusAura.
    """

    base_focus_cost: int = 0
    focus_gain: int = 0

    @can_cast_check
    def _check_focus(self) -> CastReturnCode:
        return CastReturnCode.OK if self.owner.focus >= self.focus_cost else CastReturnCode.INSUFFICENT_RESOURCES

    @property
    def focus_cost(self) -> int:
        if self.owner.event_horizon__reduce_focust_cost:
            return math.ceil(self.base_focus_cost * self.owner.event_horizon.focus_cost_multiplier)
        else:
            return self.base_focus_cost

    def _pay_cost_for_cast(self, target: Entity) -> None:
        """Add to pay for focus cost

        NB: focus cost is separated since Multishot needs to overwrite both paying charges and focus cost.
        """
        super()._pay_cost_for_cast(target)

        self._pay_focus_cost(target)

    def _pay_focus_cost(self, target: Entity) -> None:
        focus_cost = self.focus_cost
        if focus_cost:
            self.owner._change_focus(-focus_cost)

            state = get_state()
            state.bus.emit(
                ResourceSpent(
                    ability=self,
                    owner=self.owner,
                    target=target,
                    resource_amount=focus_cost,
                )
            )

        if self.focus_gain:
            self.owner._change_focus(self.focus_gain)


# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class FocusedShot(ElarionAbility):
    """1.5s cast, no CD. Deals damage. Generates 20 focus. 2 PPM CI proc."""

    average_damage: float = field(default=(1212 + 1481) / 2, init=False)
    base_cast_time: float = field(default=1.5, init=False)

    focus_gain: int = field(default=20, init=False)


@dataclass(kw_only=True, repr=False)
class CelestialShot(ElarionAbility):
    """instant cast, GCD, no CD. 15 focus cost. CI proc: applies 3 LunarlightMarks."""

    average_damage: float = field(default=(2591 + 3166) / 2, init=False)

    base_focus_cost: int = field(default=15, init=False)


@dataclass(kw_only=True, repr=False)
class Multishot(ElarionAbility):
    """1.5s cast, no CD. 20 focus cost. Hits primary + up to num_secondary_targets enemies."""

    average_damage: float = field(default=(2173 + 2655) / 2, init=False)

    max_charges: int = field(default=5, init=False)
    initial_charges: int = field(default=0, init=False)
    base_focus_cost: int = field(default=20, init=False)
    num_secondary_targets: int = field(default=11, init=False)

    empowered_num_arrows_min: int = field(default=3, init=False)
    empowered_ms_bonus_damage: float = field(default=1.0, init=False)

    _empowered_providers: list[EmpoweredMultishotProvider] = field(default_factory=list, init=False)

    def is_empowered(self) -> bool:
        """Boolean check for whether the ability is empowered (in-game: yellow border on ability)."""
        return len(self._empowered_providers) >= 1

    def empowered_by(
        self,
    ) -> Literal["Not empowered", "Fervent Supremacy", "Skystrider Supremacy", "Empowered Multishot"]:
        """Human-readable information on which ability variant will fire on cast."""
        provider_instance = self._empowered_by__instance()

        if provider_instance is None:
            return "Not empowered"
        elif isinstance(provider_instance, FerventSupremacyBuff):
            return "Fervent Supremacy"
        elif isinstance(provider_instance, SkystriderSupremacyBuff):
            return "Skystrider Supremacy"
        elif isinstance(provider_instance, EmpoweredMultishotChargeBuff):
            return "Empowered Multishot"
        else:
            raise Exception(f"Unrecognized provider: {provider_instance} with class {type(provider_instance)}")  # noqa: TRY002, TRY003

    def _empowered_by__instance(self) -> "EmpoweredMultishotProvider | None":
        """Return the highest-priority empowered provider (lowest consume_priority value)."""
        if len(self._empowered_providers) == 0:
            return None
        return min(self._empowered_providers, key=lambda p: p.consume_priority)

    def register_empowered_provider(self, provider: EmpoweredMultishotProvider) -> None:
        self._empowered_providers.append(provider)

        provider_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(provider).__name__)
        logger.debug(f"Multishot: empowered provider registered: {provider_label}")

    def unregister_empowered_provider(self, provider: EmpoweredMultishotProvider) -> None:
        if provider in self._empowered_providers:
            self._empowered_providers.remove(provider)

        provider_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(provider).__name__)
        logger.debug(f"Multishot: empowered provider unregistered: {provider_label}")

    @can_cast_check
    def _check_availability(self) -> CastReturnCode:
        """Overwritten: empowered charges can be used instead of normal ones."""
        if self.charges > 0 or self.is_empowered():
            return CastReturnCode.OK
        return CastReturnCode.ON_COOLDOWN

    @property
    def focus_cost(self) -> int:
        """Overwritten: empowered MS has half-focus cost."""
        divisor = 2 if self.is_empowered() else 1
        return math.ceil(super().focus_cost / divisor)

    def _do_cast(self, target: "Entity") -> None:
        """Overwritten:

        - FS empowered MS has bonus damage.
        - FE -> all empowered MS has bonus damage.
        - empowered MS has a minimum number of arrows.
        """
        # Standard behavior: emit event
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        # NON-STANDARD: update average damage if empowered by FS or FE talent
        provider = self._empowered_by__instance()

        base_damage = self.average_damage
        num_arrows_min = 1
        if provider:
            # buff damage if provider is FerventSupremacy
            base_damage *= provider.damage_multiplier

            # generic damage buff for empowered MS if FE is active
            base_damage *= self.empowered_ms_bonus_damage

            num_arrows_min = self.empowered_num_arrows_min

        num_secondary_targets = min(state.num_enemies - 1, self.num_secondary_targets)
        n_arrows_on_main = max(1, num_arrows_min - num_secondary_targets)

        logger.debug(f"multishot: {n_arrows_on_main} arrow(s) on {target}")

        # Standard behavior: create damage
        create_standard_damage(
            state,
            self,
            self.owner,
            target,
            base_damage=base_damage,
            main_damage_multiplier=self.main_damage_multiplier,
            num_secondary_targets=self.num_secondary_targets,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
        )

        # NON-STANDARD: Bonus arrows on main if empowered
        for _ in range(1, n_arrows_on_main):
            create_standard_damage(
                state,
                self,
                self.owner,
                target,
                base_damage=base_damage,
                main_damage_multiplier=self.main_damage_multiplier,
                num_secondary_targets=0,  # No secondary targets
                secondary_damage_multiplier=self.secondary_damage_multiplier,
            )

    def _pay_cost_for_cast(self, target: Entity) -> None:
        """Overwritten:
        - overwrite normal charge logic
        - pay standard focus cost
        """
        # Standard behavior: pay focus cost
        # !! Pay focus cost first before removing the charge from the empowered provider !!
        self._pay_focus_cost(target)

        # NON-STANDARD: consume charges from empowered provider instead
        provider = self._empowered_by__instance()

        if provider is not None:
            provider.consume_charge()

        # Standard behavior:
        elif self.charges > 0:
            self.charges -= 1
            logger.debug(f"{self} charge consumed ({self.charges}/{self.max_charges})")
        else:
            raise Exception(f"Ability cast despite no charges being availabe; {self.charges = }")  # noqa: TRY002, TRY003


@dataclass(kw_only=True, repr=False)
class HighwindArrow(ElarionAbility):
    """2s cast (haste-reduced), 15s CD. Primary + up to 2 secondary at 70% damage."""

    base_cooldown: float = field(default=15.0, init=False)
    base_cast_time: float = field(default=2.0, init=False)
    base_player_downtime: float = field(default=2.0, init=False)
    average_damage: float = field(default=(8370 + 10230) / 2, init=False)
    max_charges: int = field(default=3, init=False)
    initial_charges: int = field(default=3, init=False)
    has_hasted_cdr: bool = field(default=True, init=False)

    base_focus_cost: int = field(default=30, init=False)

    num_secondary_targets: int = field(default=2, init=False)
    secondary_damage_multiplier: float = field(default=0.7, init=False)

    has_final_crescendo_buff: bool = field(default=False, init=False)
    final_crescendo_damage_multiplier: float = field(default=2.0, init=False)
    final_crescendo_num_secondary_targets: int = field(default=7, init=False)

    has_resurgent_winds_buff: bool = field(default=False, init=False)
    resurgent_winds_cast_time: float = field(default=0, init=False)
    resurgent_winds_player_downtime: float = field(default=1.5, init=False)
    resurgent_winds_damage_multiplier: float = field(default=1.5, init=False)

    def is_empowered(self) -> bool:
        """Boolean check for whether the ability is empowered (in-game: yellow border on ability)."""
        return self.has_final_crescendo_buff or self.has_resurgent_winds_buff

    def empowered_by(
        self,
    ) -> Literal["FC + RW", "FC", "RW", "Not empowered"]:
        if self.has_final_crescendo_buff and self.has_resurgent_winds_buff:
            ans = "FC + RW"
        elif self.has_final_crescendo_buff:
            ans = "FC"
        elif self.has_resurgent_winds_buff:
            ans = "RW"
        else:
            ans = "Not empowered"
        return ans

    @property
    def cast_time(self) -> float:
        """Overwritten: resurgent winds gives instant cast time (with GCD)."""
        if self.has_resurgent_winds_buff:
            return self.resurgent_winds_cast_time / (1 + self.owner.stats.haste_percent)
        return super().cast_time

    @property
    def player_downtime(self) -> float:
        """Overwritten: resurgent winds gives instant cast time (with GCD)."""
        if self.has_resurgent_winds_buff:
            return self.resurgent_winds_player_downtime / (1 + self.owner.stats.haste_percent)
        return super().player_downtime

    @property
    def focus_cost(self) -> int:
        """Overwritten: resurgent winds has no focus cost."""
        if self.has_resurgent_winds_buff:
            return 0
        else:
            return super().focus_cost

    def _do_cast(self, target: Entity) -> None:
        """Overwritten:
        - modify final crescendo stacks;
        - modify base damage and number of secondary targets on FC attack;
        - add RW modifier if active
        """
        # NON-STANDARD: cache buff values; they will get cleared on AbilityCastSuccess
        is_fc_hwa = self.has_final_crescendo_buff
        is_rw_hwa = self.has_resurgent_winds_buff

        # Standard behavior: emit event
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        # NON-STANDARD: update damage and secondaries if this shot if modified by FC
        base_damage = self.average_damage
        num_secondary_targets = self.num_secondary_targets
        if is_fc_hwa:
            base_damage *= self.final_crescendo_damage_multiplier
            num_secondary_targets = self.final_crescendo_num_secondary_targets

        cast_specific_predamage_snapshot_modifiers: list[Callable[..., None]] = []
        if is_rw_hwa:
            cast_specific_predamage_snapshot_modifiers = [self._rw_snapshot_modifier]

        # NON-STANDARD: HWA gives multishot charges if hitting 3 or more enemies
        if state.num_enemies >= 3:
            self.owner.multishot._add_charge()

        # Standard behavior: create damage
        create_standard_damage(
            state,
            self,
            self.owner,
            target,
            base_damage=base_damage,
            num_secondary_targets=num_secondary_targets,
            cast_specific_predamage_snapshot_modifiers=cast_specific_predamage_snapshot_modifiers,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
        )

    def _rw_snapshot_modifier(self, event: PreDamageSnapshotUpdate) -> None:
        """Modify HWA damage if target has a LunarlightMark effect."""

        from fellowship_sim.elarion.effect import LunarlightMarkEffect

        if not isinstance(event.damage_source, HighwindArrow):
            return

        if event.target.effects.has(LunarlightMarkEffect):
            event.snapshot = event.snapshot.scale_average_damage(self.resurgent_winds_damage_multiplier)
            logger.trace(f"Resurgent Winds: Highwind Arrow x1.5 on marked target {event.target}")


@dataclass(kw_only=True, repr=False)
class Volley(ElarionAbility):
    """1.5s cast, 30s CD, 30 focus. DoT: 1+floor(8*(1+haste)) ticks at 1/(1+haste) interval.
    TODO: secondary targets (up to 11 additional, 100% damage each).
    """

    base_cooldown: float = field(default=30.0, init=False)
    average_damage: float = field(default=(977 + 1195) / 2, init=False)

    base_focus_cost: int = field(default=30, init=False)

    num_secondary_targets: int = field(default=11, init=False)

    duration: float = field(default=8.0 + 1e-9, init=False)
    tick_time: float = field(default=1.0, init=False)
    has_skylit_grace: bool = field(default=False, init=False)
    multishot_extends_duration_by: float = field(default=0, init=False)

    def _do_cast(self, target: Entity) -> None:
        from fellowship_sim.elarion.effect import VolleyEffect

        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        haste_percent = self.owner.stats.haste_percent
        target.effects.add(
            VolleyEffect(
                owner=self.owner,
                tick_interval=self.tick_time / (1 + haste_percent),
                duration=self.duration,
                ability=self,
                multishot_extends_duration_by=self.multishot_extends_duration_by,
                has_skylit_grace=self.has_skylit_grace,
            )
        )


@dataclass(kw_only=True, repr=False)
class HeartseekerBarrage(ElarionAbility):
    """2s channel, 20s CD, 30 focus.
    Fires every tick_time/(1+haste) seconds for base_cast_time seconds.
    Secondary targets (when num_secondary_targets >= 1) are selected from marked enemies only.
    """

    base_cooldown: float = field(default=20.0, init=False)
    base_player_downtime: float = field(default=2.0, init=False)
    average_damage: float = field(default=(1124 + 1373) / 2, init=False)

    is_channel: bool = field(default=True, init=False)
    tick_time: float = field(default=0.2, init=False)

    delay_until_hit: float = field(
        default=0.05, init=False
    )  # Flight time of the missile; this matters for volley reset during ultimate

    base_focus_cost: int = field(default=30, init=False)

    num_secondary_targets: int = field(default=0, init=False)
    secondary_damage_multiplier: float = field(default=0.0, init=False)

    has_impending_barrage: bool = field(default=False, init=False)
    impending_barrage_step: float = field(default=0.1, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten: to check for IHB buff and apply it to channel."""
        # gets cleared at AbilityCastSuccess
        has_impending_barrage = self.has_impending_barrage

        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        # Special barrage modifier
        damage_step = self.impending_barrage_step if has_impending_barrage else 0

        # snapshot haste and compute the number of ticks
        haste = self.owner.stats.haste_percent
        tick_interval = self.tick_time / (1 + haste)
        # Having this epsilon is necessary to ensure that breakpoints are reached exactly: it offsets the floor rounding slightly
        epsilon = 0.001
        num_ticks = math.floor(self.player_downtime / tick_interval + epsilon)

        # shaving a slight amount off tick_interval to ensure that when player is available, all shots have been fired
        tick_interval *= 0.99

        logger.debug(
            f"barrage channel start: scheduling {num_ticks} tick(s) on {target} (interval={tick_interval:.3f}s)"
        )

        def _next_barrage_tick() -> None:
            self._schedule_barrage_tick(
                main_target=target,
                tick_interval=tick_interval,
                hit_counter=0,
                total_count=num_ticks,
                damage_step=damage_step,
            )

        state.schedule(
            time_delay=tick_interval, callback=GenericTimedEvent(name="barrage tick", callback=_next_barrage_tick)
        )

    def _schedule_barrage_tick(
        self,
        main_target: Entity,
        tick_interval: float,
        hit_counter: int,
        total_count: int,
        damage_step: float = 0.0,
    ) -> None:
        """Schedule one HeartseekerBarrage tick with full channel context.

        hit_counter: 0-based index of this tick within the channel.
        is_impending: True for the final tick (reserved for explosion/proc effects).
        damage_step: per-tick additive damage multiplier increment (e.g. 0.10 for ImpendingHeartseeker).
        Tick k deals snapshot * (1.0 + k * damage_step). Bounce targets take 70% of the primary hit.
        Secondary targets are chosen at fire-time from enemies that currently have LunarlightMark.
        """
        state = get_state()

        tick_multiplier = 1.0 + hit_counter * damage_step
        scaled_base_damage = self.average_damage * tick_multiplier
        logger.trace(
            f"barrage tick: index={hit_counter} / {total_count}, damage multiplier={tick_multiplier:.1f}",
        )

        from fellowship_sim.elarion.effect import LunarlightMarkEffect

        def priority_target_marked_enemies(enemy: Entity) -> float:
            if enemy.effects.get(LunarlightMarkEffect) is not None:
                return 1.0
            else:
                return 0.0

        create_standard_damage(
            state=state,
            damage_source=self,
            owner=self.owner,
            target=main_target,
            base_damage=scaled_base_damage,
            num_secondary_targets=self.num_secondary_targets,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
            delay_until_hit=self.delay_until_hit,
            priority_func=priority_target_marked_enemies,
        )

        if hit_counter < total_count - 1:

            def _next_barrage_tick() -> None:
                self._schedule_barrage_tick(
                    main_target=main_target,
                    tick_interval=tick_interval,
                    hit_counter=hit_counter + 1,
                    total_count=total_count,
                    damage_step=damage_step,
                )

            state.schedule(
                time_delay=tick_interval, callback=GenericTimedEvent(name="barrage tick", callback=_next_barrage_tick)
            )


@dataclass(kw_only=True, repr=False)
class LunarlightMark(ElarionAbility):
    """Instant cast, 30s CD. Applies 3 LunarlightMark stacks to the main target and
    3 stacks to up to 11 secondary targets.
    """

    base_cooldown: float = field(default=30.0, init=False)
    base_player_downtime: float = field(default=0.0, init=False)

    num_secondary_targets: int = field(default=11, init=False)
    mark_stacks: int = field(default=3, init=False)

    has_increased_proc_chance_volley: bool = field(default=False, init=False)
    has_increased_proc_chance_barrage: bool = field(default=False, init=False)

    has_resurgent_winds_talent: bool = field(default=False, init=False)

    def _do_cast(self, target: Entity) -> None:
        from fellowship_sim.elarion.effect import (
            LunarlightMarkEffect,  # deferred — avoids circular import
            ResurgentWinds,
        )

        # Standard behavior: emit event
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        # NON-STANDARD: add resurgent_winds buff on highwind arrow, if talented
        if self.has_resurgent_winds_talent:
            self.owner.effects.add(ResurgentWinds(owner=self.owner))

        # NON-STANDARD: ability resolution, add marks to targets
        target.effects.add(
            LunarlightMarkEffect(
                owner=self.owner,
                stacks=self.mark_stacks,
            )
        )
        secondaries = state.select_targets(target, self.num_secondary_targets)
        for secondary in secondaries:
            secondary.effects.add(
                LunarlightMarkEffect(
                    owner=self.owner,
                    stacks=self.mark_stacks,
                )
            )

        logger.debug(
            f"lunarlight mark: +{self.mark_stacks} stacks on {target} and {len(secondaries)} secondary target(s)"
        )


@dataclass(kw_only=True, repr=False)
class LunarlightSalvo(ElarionAbility):
    """Triggered proc (no CD, no cast time). Fires when LunarlightMark procs."""

    average_damage: float = field(default=(2033 + 2485) / 2, init=False)

    max_charges: int = field(default=0, init=False)
    initial_charges: int = field(default=0, init=False)

    def cast(self, target: "Entity") -> CastReturnCode:
        raise Exception(f"{self!s} is a fake ability and is not callable.")  # noqa: TRY002, TRY003

    def _do_cast(self, target: "Entity") -> None:
        """Overwritten to remove the event."""
        create_standard_damage(
            get_state(),
            self,
            self.owner,
            target,
            self.average_damage,
            main_damage_multiplier=self.main_damage_multiplier,
            num_secondary_targets=self.num_secondary_targets,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
        )


@dataclass(kw_only=True, repr=False)
class LunarlightExplosion(ElarionAbility):
    """Triggered proc. Fires when LunarlightMark procs on a HeartseekerBarrage hit (20% chance).
    Deals full damage to the bearer and up to 11 additional enemies.
    """

    average_damage: float = field(default=(2033 + 2485) / 2, init=False)

    max_charges: int = field(default=0, init=False)
    initial_charges: int = field(default=0, init=False)

    num_secondary_targets: int = field(default=11, init=False)

    def cast(self, target: "Entity") -> CastReturnCode:
        raise Exception(f"{self!s} is a fake ability and is not callable.")  # noqa: TRY002, TRY003

    def _do_cast(self, target: "Entity") -> None:
        """Overwritten to remove the event."""
        create_standard_damage(
            get_state(),
            self,
            self.owner,
            target,
            self.average_damage,
            main_damage_multiplier=self.main_damage_multiplier,
            num_secondary_targets=self.num_secondary_targets,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
        )


@dataclass(kw_only=True, repr=False)
class SkystriderGrace(ElarionAbility):
    """Instant cast, 120s CD. Applies SkystriderGrace buff (+30% haste, 20s)."""

    base_player_downtime: float = field(default=0.0, init=False)
    base_cooldown: float = field(default=120.0, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [SkystriderGraceBuff], init=False)


@dataclass(kw_only=True, repr=False)
class EventHorizon(ElarionAbility):
    """0.7s cast (haste-reduced), no CD. Applies EventHorizon buff

    - +20% damage
    - CDA to all abilities
    - flat cooldown reduction to volley (from barrage damage) and to barrage (from HWA damage)
    """

    base_cast_time: float = field(default=0.7, init=False)
    base_player_downtime: float = field(default=0.7, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [EventHorizonBuff], init=False)

    is_ultimate_ability: bool = field(default=True, init=False)

    focus_cost_multiplier: float = field(default=0.5, init=False)


@dataclass(kw_only=True, repr=False)
class SkystriderSupremacy(ElarionAbility):
    """Instant cast, 40s CD. Empowers Multishot in one of two ways:

    Base (is_fervent_supremacy=False): applies SkystriderSupremacyBuff — 4s window of
        unlimited empowered casts (3+ arrows, no extra damage).
    Talented (is_fervent_supremacy=True): applies FerventSupremacyBuff — 4 charges of
        empowered casts with +50% damage each.
    """

    base_player_downtime: float = field(default=0.0, init=False)
    base_cooldown: float = field(default=40.0, init=False)

    is_fervent_supremacy: bool = field(default=False, init=False)

    def _do_cast(self, target: Entity) -> None:
        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        if self.is_fervent_supremacy:
            self.owner.effects.add(FerventSupremacyBuff(owner=self.owner))
            logger.debug("Skystrider Supremacy (talented): Fervent Supremacy buff applied")
        else:
            self.owner.effects.add(SkystriderSupremacyBuff(owner=self.owner))
            logger.debug("Skystrider Supremacy: Skystrider Supremacy buff applied")
