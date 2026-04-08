import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger

from .ability import Ability
from .effect import Effect
from .entity import Entity, Player
from .stats import RawStats, SnapshotStats, StatModifier

# ---------------------------------------------------------------------------
# Event variants
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class AbilityCastStart:
    """Fired when a cast begins (before the cast time elapses)."""

    ability: Ability[Player]
    owner: Player
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"cast start: {self.ability.owner} → {self.target}")


@dataclass(kw_only=True)
class AbilityCastSuccess:
    ability: Ability[Player]
    owner: Player
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"{self}")

    def __str__(self) -> str:
        return f"ability cast success ({self.ability} by {self.owner})"


@dataclass(kw_only=True)
class AbilityActivated:
    """Fired when an ability becomes available (proc, cooldown reset, etc.)."""

    ability: Ability[Player]
    owner: Player
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"ability activated: {self.ability}")


@dataclass(kw_only=True)
class AbilityChannelStart:
    """Fired when a channeled ability begins its channel phase."""

    ability: Ability[Player]
    owner: Player
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"channel start: {self.ability} → {self.target}")


@dataclass(kw_only=True)
class AbilityChannelSuccess:
    """Fired when a channel completes successfully."""

    ability: Ability[Player]
    owner: Player
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"channel success: {self.ability} → {self.target}")


@dataclass(kw_only=True)
class PreDamageSnapshotUpdate:
    """Fired by deal_damage() just before applying damage.

    Both global bus listeners and cast-specific closures may replace
    ``snapshot`` (a frozen dataclass — reassign the field, don't mutate).
    Cast-specific listeners are called after the bus has fired.

    ``is_dot`` is True when the hit originates from a DoT/periodic tick
    (deal_damage called with is_dot=True).  Listeners that only want to
    modify direct hits should check ``not event.is_dot``.
    """

    damage_source: Ability[Player] | Effect
    target: Entity
    snapshot: SnapshotStats
    is_dot: bool = False
    predamage_snapshot_modifiers: list[Callable[["PreDamageSnapshotUpdate"], None]] = field(default_factory=list)
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"pre-damage snapshot: {self.damage_source} → {self.target}")

    def finalize(self) -> SnapshotStats:
        for modifier in self.predamage_snapshot_modifiers:
            modifier(self)
        return self.snapshot


def current_state_time() -> float:
    from fellowship_sim.base_classes.state import get_state

    state = get_state()
    return state.time


@dataclass(kw_only=True)
class AbilityDamage:
    damage_source: Ability[Player] | Effect
    owner: Entity
    target: Entity
    is_crit: bool
    is_grievous_crit: bool
    damage: float
    time: float = field(default_factory=current_state_time)

    def __post_init__(self) -> None:
        self.target._take_damage(self)
        logger.opt(colors=True).info(f"{self}")

    def __str__(self) -> str:
        crit_text = f"{self.damage:>6.0f}"
        if self.is_grievous_crit:
            crit_text = f"<red>{crit_text}</red>"
        elif self.is_crit:
            crit_text = f"<yellow>{crit_text}</yellow>"
        return f"{crit_text} dmg by {self.damage_source} on {self.target}"


@dataclass(kw_only=True)
class AbilityPeriodicDamage:
    """Fired when a DoT/HoT tick deals damage."""

    damage_source: Ability[Player] | Effect
    owner: Entity
    target: Entity
    is_crit: bool
    is_grievous_crit: bool
    damage: float
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        self.target._take_damage(self)
        logger.opt(colors=True).info(f"{self}")

    def __str__(self) -> str:
        crit_text = f"{self.damage:>6.0f}"
        if self.is_grievous_crit:
            crit_text = f"<red>{crit_text}</red>"
        elif self.is_crit:
            crit_text = f"<yellow>{crit_text}</yellow>"
        return f"{crit_text} dmg by {self.damage_source} on {self.target}"


@dataclass(kw_only=True)
class ResourceChanged:
    """Fired whenever a player resource (focus, mana, …) changes."""

    owner: Entity
    resource_amount: float
    delta: float
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"resource changed: {self.owner} {self.delta:+.0f} → {self.resource_amount:.0f}")


@dataclass(kw_only=True)
class ResourceSpent:
    owner: Entity
    ability: Ability[Player]
    target: Entity
    resource_amount: int
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"{self}")

    def __str__(self) -> str:
        return f"resource spent ({self.resource_amount} by {self.ability})"


@dataclass(kw_only=True)
class EffectApplied:
    """Fired when an effect is first added to an entity."""

    effect: Effect
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:

        from .config import IMPORTANT_EFFECTS

        if self.effect.name in IMPORTANT_EFFECTS:
            logger.success(f"effect applied: {self.effect} on {self.target}")
        else:
            logger.debug(f"effect applied: {self.effect} on {self.target}")


@dataclass(kw_only=True)
class EffectRemoved:
    """Fired when an effect expires or is removed from an entity."""

    effect: Effect
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:

        from .config import IMPORTANT_EFFECTS

        if self.effect.name in IMPORTANT_EFFECTS:
            logger.success(f"effect removed: {self.effect} on {self.target}")
        else:
            logger.debug(f"effect removed: {self.effect} on {self.target}")


@dataclass(kw_only=True)
class EffectRefreshed:
    """Fired when an existing effect is renewed/fused."""

    effect: Effect
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:

        from .config import IMPORTANT_EFFECTS

        if self.effect.name in IMPORTANT_EFFECTS:
            logger.success(f"effect refreshed: {self.effect} on {self.target}")
        else:
            logger.debug(f"effect refreshed: {self.effect} on {self.target}")


@dataclass(kw_only=True)
class ComputeCooldownReduction:
    """Fired each tick for an ability that is on cooldown.

    Listeners append values to ``cda_modifiers`` (CooldownAccelerationAdditive)
    or ``cdr_modifiers`` (CooldownReductionAdditive).

    effective_dt = dt * (1 + sum(cda)) * (1 + sum(cdr))

    Haste is injected into ``cda_modifiers`` by the tick logic when
    ``ability.has_hasted_cdr`` is True — listeners must not add it again.
    """

    ability: Ability[Player]
    owner: Player
    cda_modifiers: list[float] = field(default_factory=list)
    cdr_modifiers: list[float] = field(default_factory=list)
    cdrecovery_modifiers: list[float] = field(default_factory=list)
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"compute CDR: {self.ability}")

    def resolve(self) -> float:
        cdr_multiplier = 1
        for elem in self.cdr_modifiers:
            cdr_multiplier *= elem
        cooldown_reduction_multiplier = (1 + sum(self.cda_modifiers)) * cdr_multiplier + sum(self.cdrecovery_modifiers)
        return cooldown_reduction_multiplier


@dataclass(kw_only=True)
class UltimateCast:
    """Fired when an UltimateAbility is successfully cast."""

    ability: Ability[Player]
    owner: Player
    target: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"ultimate cast: {self.ability} by {self.owner}")


@dataclass(kw_only=True)
class SpiritProc:
    """Fired when the Spirit passive refunds resource on a crit."""

    ability: Ability[Player]
    owner: Entity
    resource_amount: float
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"spirit proc: {self.ability} → {self.resource_amount:.1f}")


@dataclass(kw_only=True)
class UnitDestroyed:
    """Fired when a unit's HP reaches zero."""

    entity: Entity
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"unit destroyed: {self.entity}")


@dataclass(kw_only=True)
class ComputeFinalStats:
    """Fired to collect StatModifiers before finalizing a character's FinalStats.

    Handlers append modifiers to ``modifiers``; the caller applies them to the
    MutableStats seeded from ``raw_stats`` and then finalizes.
    """

    owner: Player
    raw_stats: RawStats
    modifiers: list[StatModifier] = field(default_factory=list)
    time: float = field(default_factory=lambda: current_state_time())

    def __post_init__(self) -> None:
        logger.debug(f"compute final stats: {self.owner}")


# fmt: off
SimEvent = (
    AbilityActivated
    | AbilityCastStart
    | ComputeCooldownReduction
    | AbilityCastSuccess
    | AbilityChannelStart
    | AbilityChannelSuccess
    | AbilityDamage
    | AbilityPeriodicDamage
    | EffectApplied
    | EffectRefreshed
    | EffectRemoved
    | PreDamageSnapshotUpdate
    | ResourceChanged
    | ResourceSpent
    | SpiritProc
    | UltimateCast
    | UnitDestroyed
    | ComputeFinalStats
)
# fmt: on

# Handlers are registered per event type, so they only ever receive that specific
# subtype. Using Callable[..., None] avoids a false contravariance error from the
# type checker — a handler for AbilityCastSuccess is not assignable to Callable[[SimEvent], None].
EventHandler = Callable[..., None]


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)
        # Maps owner id → registered (event_type, handler) pairs for bulk unsubscribe.
        # Uses id() rather than the object itself because non-frozen dataclasses are unhashable.
        self._owner_handlers: dict[int, list[tuple[type, EventHandler]]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler, owner: object | None = None) -> None:
        self._handlers[event_type].append(handler)
        if owner is not None:
            self._owner_handlers[id(owner)].append((event_type, handler))

        event_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", event_type.__name__).lower()
        logger.debug(f"bus subscribe: {event_label} ← {getattr(handler, '__qualname__', repr(handler))}")

    def unsubscribe_all(self, owner: object) -> None:
        pairs = self._owner_handlers.pop(id(owner), [])
        for event_type, handler in pairs:
            self._handlers[event_type].remove(handler)
        if pairs:
            logger.debug(f"bus unsubscribe all: {owner} ({len(pairs)} handler(s))")

    def emit(self, event: SimEvent) -> None:
        handlers = list(self._handlers.get(type(event), []))

        event_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(event).__name__).lower()
        logger.debug(f"bus emit: {event_label} ({len(handlers)} listener(s))")
        for handler in handlers:
            logger.trace(f"  → {getattr(handler, '__qualname__', repr(handler))}")
            handler(event)
