import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from loguru import logger

from .effect import Effect

if TYPE_CHECKING:
    from .entity import Entity, Player


class CastReturnCode(Enum):
    OK = "ok"
    ON_COOLDOWN = "on_cooldown"
    INSUFFICENT_RESOURCES = "insufficient_resources"
    ULTIMATE_FORBIDDEN = "ultimate_forbidden_by_state_information"


# ---------------------------------------------------------------------------
# Check decorator
# ---------------------------------------------------------------------------

_CHECK_ATTR = "_is_can_cast_check"


def can_cast_check(fn: Callable[..., CastReturnCode]) -> Callable[..., CastReturnCode]:
    """Mark a method as a can_cast check. All marked methods are auto-discovered
    and called by can_cast() in base-to-derived MRO order."""
    setattr(fn, _CHECK_ATTR, True)
    return fn


# ---------------------------------------------------------------------------
# Ability
# ---------------------------------------------------------------------------

TCharacter = TypeVar("TCharacter", bound="Player", covariant=True)


@dataclass(kw_only=True)
class Ability(Generic[TCharacter]):  # noqa: UP046
    owner: TCharacter

    # Static info (set per ability subclass via field(init=False))
    base_cast_time: float

    average_damage: float = field(default=0.0, init=False)
    effect_list: list[type[Effect]] = field(default_factory=list, init=False)
    # cooldown and charges parameters
    base_cooldown: float = field(default=0.0, init=False)
    initial_charges: int = field(default=1, init=False)
    max_charges: int = field(default=1, init=False)
    has_hasted_cdr: bool = field(default=False, init=False)
    # channel abilities parameters
    is_channel: bool = field(default=False, init=False)
    tick_time: float = field(default=0.0, init=False)
    # ultimate
    is_ultimate_ability: bool = field(default=False, init=False)

    # Dynamic info (runtime state)
    cooldown: float = field(default=0.0, init=False)
    charges: int = field(init=False)
    _cdr_multiplier: float = field(default=1.0, init=False)

    # AOE settings: number of targets, damage multipliers
    num_secondary_targets: int = field(default=0, init=False)
    main_damage_multiplier: float = field(default=1.0, init=False)
    secondary_damage_multiplier: float = field(default=1.0, init=False)

    def __post_init__(self) -> None:
        self.charges = self.initial_charges

    def __str__(self) -> str:
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(self).__name__)

    def __repr__(self) -> str:
        return str(self)

    def cast(self, target: "Entity") -> CastReturnCode:
        """Cast the ability on target then return once character can act again.

        NB: on abilities without a target, it is ignored silently.
        """
        from .state import get_state  # lazy — state.py → events.py → ability.py at module level
        from .timed_events import PlayerAvailableAgain

        logger.trace(f"attempting cast: {self}")

        result = self._can_cast()
        if result is not CastReturnCode.OK:
            logger.warning(f"cast blocked — {self} ({result.value.replace('_', ' ')})")
            return result

        state = get_state()
        logger.info(f"cast: {self} at t={state.time:.3f}")

        # Cache cast_time ahead of _do_cast: abilities with modified cast time can handle that inside their _do_cast
        cast_time = self.cast_time

        self._do_cast(target)
        self._pay_cost_for_cast(target)

        logger.trace(f"cast finished: {self} at t={state.time:.3f}")

        # Wait until character is available again
        state.schedule(time_delay=cast_time, callback=PlayerAvailableAgain())
        state.step()

        return CastReturnCode.OK

    @property
    def is_available(self) -> bool:
        return self.cooldown <= 0.0 or self.charges > 0

    @property
    def cast_time(self) -> float:
        """Effective cast time, reduced by haste when has_hasted_cdr is True."""
        if self.is_channel:
            return self.base_cast_time
        else:
            return self.base_cast_time / (1 + self.owner.stats.haste_percent)

    @property
    def spirit_cost(self) -> float:
        return self.owner.spirit_ability_cost if self.is_ultimate_ability else 0

    @can_cast_check
    def _check_availability(self) -> CastReturnCode:
        return CastReturnCode.OK if self.is_available else CastReturnCode.ON_COOLDOWN

    @can_cast_check
    def _check_spirit(self) -> CastReturnCode:
        from fellowship_sim.base_classes.state import get_state

        if not self.is_ultimate_ability:
            return CastReturnCode.OK
        if self.owner.spirit_points < self.spirit_cost:
            return CastReturnCode.INSUFFICENT_RESOURCES
        if not get_state().information.is_ult_authorized:
            return CastReturnCode.ULTIMATE_FORBIDDEN
        return CastReturnCode.OK

    def can_cast(self) -> bool:
        return self._can_cast() is CastReturnCode.OK

    def _can_cast(self) -> CastReturnCode:
        """Collect all @can_cast_check methods in base→derived order.
        Iterating reversed MRO means base methods are inserted first;
        subclass methods with the same name overwrite them (override semantics).
        """
        checks: list[Callable[..., CastReturnCode]] = []
        for cls in reversed(type(self).__mro__):
            for _, attr in cls.__dict__.items():
                if callable(attr) and getattr(attr, _CHECK_ATTR, False):
                    checks.append(attr)
        for check in checks:
            result = check(self)
            if result is not CastReturnCode.OK:
                return result
        return CastReturnCode.OK

    def _do_cast(self, target: "Entity") -> None:
        """Realize all consequences from casting the ability.

        Default behavior:
            - deal damage to main target and secondary targets.
            - apply any effects to caster.

        Standard damage abilities and standard self buffs do not need special logic.
        Abilities with complex damage, enemy debuffs or other complexity need to overwrite this.
        """

        from .combat import create_standard_damage  # lazy — combat.py may import ability.py
        from .events import AbilityCastSuccess, UltimateCast  # lazy — events.py imports ability.py
        from .state import get_state

        state = get_state()
        event = AbilityCastSuccess(ability=self, owner=self.owner, target=target)
        state.bus.emit(event)

        if self.is_ultimate_ability:
            state.bus.emit(UltimateCast(ability=self, owner=self.owner, target=target))

        if self.average_damage > 0:
            create_standard_damage(
                state,
                self,
                self.owner,
                target,
                self.average_damage,
                main_damage_multiplier=self.main_damage_multiplier,
                num_secondary_targets=self.num_secondary_targets,
                secondary_damage_multiplier=self.secondary_damage_multiplier,
            )

        for effect_constructor in self.effect_list:
            self.owner.effects.add(effect_constructor(owner=self.owner))

    def _pay_cost_for_cast(self, target: "Entity") -> None:
        """Pay all costs associated to casting the ability."""
        if self.is_ultimate_ability:
            self.owner.spirit_points -= self.spirit_cost

        if self.base_cooldown > 0:
            if self.charges > 0:
                self.charges -= 1
                logger.debug(f"{self} charge consumed ({self.charges}/{self.max_charges})")
            else:
                raise Exception(f"Ability cast despite no charges being availabe; {self.charges = }")  # noqa: TRY002, TRY003

        if self.charges < self.max_charges and self.cooldown <= 0.0:
            self.cooldown = self.base_cooldown
            logger.debug(f"{self} cooldown started ({self.base_cooldown:.1f}s)")

    def _reset_cooldown(self) -> None:
        """Reset this ability to its fully charged, off-cooldown state."""
        self.cooldown = 0.0
        self.charges = self.max_charges
        logger.debug(f"{self} cooldown reset")

    def _add_charge(self) -> None:
        """Add a charge, up to maximum."""
        self.charges = min(self.charges + 1, self.max_charges)
        if self.charges == self.max_charges:
            self._reset_cooldown()
        logger.debug(f"{self!s} charge gained (now {self.charges})")

    def _finalize_cooldown_and_grant_charges(self) -> None:
        """Grant charges while cooldown is <= 0 and charge slots remain."""
        while self.cooldown <= 0.0 and self.max_charges > 0 and self.charges < self.max_charges:
            self.charges += 1
            logger.debug(f"{self} charge ready ({self.charges}/{self.max_charges})")
            if self.charges < self.max_charges:
                self.cooldown += self.base_cooldown
            else:
                self.cooldown = 0.0

    def _reduce_cooldown(self, flat_cdr: float) -> None:
        """Reduce remaining cooldown by flat_cdr seconds, granting charges when ready."""
        if self.cooldown <= 0.0:
            return
        self.cooldown -= flat_cdr
        logger.debug(f"{self} flat CDR -{flat_cdr:.1f}s (remaining {max(self.cooldown, 0.0):.2f}s)")
        self._finalize_cooldown_and_grant_charges()

    def _reduce_cooldown_multiplicative(self, multiplier: float) -> None:
        """Reduce remaining cooldown by multiplier * base_cooldown."""
        self._reduce_cooldown(multiplier * self.base_cooldown)

    def _compute_cooldown_reduction_and_acceleration(self) -> float:
        """Emit ComputeCooldownReduction and return the effective dt to drain from cooldown.

        Builds the event, appends haste CDA when has_hasted_cdr is True, emits it so
        subscribers (e.g. ChronoshiftChannelCDR, VolleyEffect) can inject modifiers,
        then resolves to an effective dt.  Override in subclasses to bypass this logic.
        """
        from .events import ComputeCooldownReduction  # lazy — events.py imports ability.py
        from .state import get_bus

        event = ComputeCooldownReduction(ability=self, owner=self.owner)
        if self.has_hasted_cdr:
            event.cda_modifiers.append(self.owner.stats.haste_percent)
        get_bus().emit(event)
        return event.resolve()

    def _recalculate_cdr_multiplier(self) -> None:
        """Recompute and cache the CDR multiplier for this ability.

        Fires ComputeCooldownReduction to let subscribers inject modifiers,
        then stores the resulting multiplier.  Called by Player.recalculate_cdr_multipliers()
        whenever haste or an effect that modifies CDR changes.
        """
        self._cdr_multiplier = self._compute_cooldown_reduction_and_acceleration()

    def _tick(self, dt: float) -> None:
        """Advance this ability's cooldown by dt seconds.

        When has_hasted_cdr is True the cooldown drains at (1+haste) per real second,
        so a base_cooldown=15s ability is ready in 15/(1+haste) real seconds.
        When the cooldown reaches 0 and the ability has unfilled charge slots,
        a charge is granted and the cooldown restarts for the next one.
        """
        if self.cooldown <= 0.0:
            return
        self.cooldown -= dt * self._cdr_multiplier
        logger.trace(f"{self} cooldown: {max(self.cooldown, 0.0):.3f}s remaining")
        self._finalize_cooldown_and_grant_charges()


class WeaponAbility(Ability["Player"]):
    """Mixin for weapon abilities: CDR and CDA are not applicable.

    Weapon ability cooldowns drain at exactly 1s per real second —
    haste acceleration and all external CDR/CDA modifiers are ignored.
    """

    def _compute_cooldown_reduction_and_acceleration(self) -> float:
        logger.debug("skipped cooldown reduction calculation on weapon ability: CDA and CDR do not apply")
        return 1


# ---------------------------------------------------------------------------
# Uninitialized ability sentinels
# ---------------------------------------------------------------------------


class WeaponAbilityNotInitialized:
    """Sentinel placed in weapon-ability slots when no weapon is equipped.

    Logs a warning and passes through (returns ``None``) on any attribute access
    so that optional weapon-ability checks degrade gracefully.
    Rejects field mutations to protect the shared singleton.
    """

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"Cannot set '{name}' on an uninitialized weapon ability slot")  # noqa: TRY003

    def __getattr__(self, name: str) -> Any:
        logger.warning(f"weapon ability not initialized: '{name}' accessed — weapon not equipped, skipping")

        def _noop(*args: Any, **kwargs: Any) -> None:
            return None

        return _noop

    def __str__(self) -> str:
        return "weapon ability not initialized"

    def __repr__(self) -> str:
        return str(self)


WEAPON_ABILITY_NOT_INITIALIZED: WeaponAbilityNotInitialized = WeaponAbilityNotInitialized()
