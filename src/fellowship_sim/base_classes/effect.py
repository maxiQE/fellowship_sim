import itertools
from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

from .timed_events import EffectExpiry, GenericTimedEvent

if TYPE_CHECKING:
    from .entity import Entity, Player
    from .events import ComputeFinalStats
    from .stats import SnapshotStats, StatModifier


_effect_id_counter = itertools.count(1)


class DuplicateEffectError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Effect '{name}' is already active on this entity")


@dataclass(kw_only=True)
class Effect:
    owner: "Entity" = field(init=True)  # Entity from which the effect originates

    name: str = field(default="Unknown Effect", init=False)
    duration: float = field(default=float("inf"), init=False)  # seconds remaining

    stacks: int = field(default=1, init=False)
    max_stacks: int = field(default=1, init=False)

    attached_to: "Entity | None" = field(
        default=None, init=False
    )  # Entity to which the effect is attached; added at on_add step

    id: int = field(default_factory=lambda: next(_effect_id_counter), init=False)  # automatic id
    _expiry_seq: int = field(
        default=0, init=False, repr=False
    )  # Used to suport renewing: this field is increased on renew and makes the former expiration event a no-op

    def __str__(self) -> str:
        dur = "∞" if self.duration == float("inf") else f"{self.duration:.1f}s"
        stacks = f"×{self.stacks}" if self.stacks != 1 else ""
        return f"{self.name}{stacks}({dur})"

    def __repr__(self) -> str:
        return str(self)

    def add(self) -> None:
        """Add this effect.

        Add triggers the `on_add` function for specialized processing by subclasses.
        """

        from .events import EffectApplied

        if self.attached_to is None:
            raise Exception(f"Effect {self} not attached during add")  # noqa: TRY002, TRY003

        self.owner.state.bus.emit(
            EffectApplied(
                effect=self,
                target=self.attached_to,
            )
        )

        self.on_add()

    def on_add(self) -> None:
        """Trigger any code incident on being added."""
        pass

    def on_remove(self) -> None:
        """Trigger any code incident on being removed."""
        pass

    def tick(self, dt: float) -> None:
        """Decrement remaining duration.  Expiry is handled by the queue, not here."""
        if self.duration != float("inf"):
            self.duration -= dt

    def _schedule_expiry(self) -> None:
        """Schedule a queue callback to remove this effect when its duration elapses.
        Uses a version counter so that refreshing the effect silently cancels the old callback:
        the old callback checks its captured seq against self._expiry_seq and is a no-op if stale.
        """

        if self.duration == float("inf"):
            return

        state = self.owner.state
        self._expiry_seq += 1
        seq = self._expiry_seq
        state.schedule(
            time_delay=self.duration,
            callback=EffectExpiry(effect=self, callback=lambda: self._expire(seq)),
        )

    def fuse(self, incoming: "Effect") -> None:
        """Called when an incoming effect of the same name lands on top of this one.

        Default behaviour:
        - Infinite-duration effects cannot be fused (something has gone wrong).
        - Finite-duration effects: renew duration and merge stacks up to cap.

        Override in subclasses to implement custom fusion logic (e.g. AmethystSplintersDoT).
        """
        from .events import EffectRefreshed

        if self.attached_to is None:
            raise Exception(f"Effect {self} not attached during fuse")  # noqa: TRY002, TRY003

        if self.duration == float("inf"):
            raise DuplicateEffectError(self.name)

        self.duration = incoming.duration
        self.stacks = min(self.stacks + incoming.stacks, self.max_stacks)
        self._schedule_expiry()

        self.owner.state.bus.emit(
            EffectRefreshed(
                effect=self,
                target=self.attached_to,
            )
        )

        self.on_fuse()

    def on_fuse(self) -> None:
        """Called after fuse completes. Override in subclasses for post-fuse behaviour."""

    def _expire(self, seq: int) -> None:
        if seq != self._expiry_seq:
            return  # stale — effect was refreshed or removed since this was scheduled
        logger.trace(f"effect expired: {self}")
        self.remove()

    def remove(self) -> None:
        """Remove this effect.

        Remove triggers the `on_remove` function for specialized processing by subclasses.
        """

        from .events import EffectRemoved

        if self.attached_to is None:
            raise Exception(f"Effect {self} not attached during remove")  # noqa: TRY002, TRY003

        self.owner.state.bus.emit(
            EffectRemoved(
                effect=self,
                target=self.attached_to,
            )
        )

        self.owner.state.bus.unsubscribe_all(self)
        self.on_remove()  # called while attached_to is still valid
        self.attached_to.effects.remove(self)  # removes from dict; attached_to cleared after on_remove
        self.attached_to = None
        self._expiry_seq += 1


class EffectCollection:
    def __init__(self) -> None:
        self._effects: dict[str, Effect] = {}
        self._entity: Entity | None = None

    def get[T: Effect](self, effect_type: type[T]) -> T | None:
        for effect in self._effects.values():
            if isinstance(effect, effect_type):
                return effect
        return None

    def has[T: Effect](self, effect_type: type[T]) -> bool:
        return any(isinstance(e, effect_type) for e in self._effects.values())

    def add(self, effect: Effect) -> None:
        existing = self._effects.get(effect.name)
        if existing is not None:
            existing.fuse(effect)
            return

        self._effects[effect.name] = effect
        effect.attached_to = self._entity

        effect.add()
        effect._schedule_expiry()

    def remove(self, effect: Effect) -> None:
        del self._effects[effect.name]
        # Note: effect.attached_to is cleared by Effect.remove() after on_remove()

    def __iter__(self) -> Iterator[Effect]:
        return iter(self._effects.values())

    def __len__(self) -> int:
        return len(self._effects)


# ---------------------------------------------------------------------------
# Buff — Effect subclass that modifies character stats while active
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class Buff(Effect):
    """Base class for effects that modify character stats via StatModifiers.

    Subclasses implement stat_modifiers() returning the modifiers this buff contributes.
    On add, the buff subscribes to ComputeFinalStats and triggers recalculation.
    On remove, the subscription is cleared automatically and recalculation runs again.

    If a subclass overrides on_add() or on_remove(), it must call super() to
    ensure recalculation is triggered.
    """

    attached_to: "Player | None" = field(default=None, init=False)

    @abstractmethod
    def stat_modifiers(self) -> "list[StatModifier]":
        """Return the list of modifiers this buff contributes to the character's stats."""

    def on_add(self) -> None:
        from .events import ComputeFinalStats

        self.owner.state.bus.subscribe(ComputeFinalStats, self._on_compute_final_stats, owner=self)
        if self.attached_to is None:
            raise Exception("Buff unnattached in on_add")  # noqa: TRY002, TRY003
        else:
            self.attached_to._recalculate_stats()

    def on_fuse(self) -> None:
        if self.attached_to is None:
            raise Exception("Buff unnattached in on_fuse")  # noqa: TRY002, TRY003
        else:
            self.attached_to._recalculate_stats()

    def on_remove(self) -> None:
        if self.attached_to is None:
            raise Exception("Buff unnattached in on_remove")  # noqa: TRY002, TRY003
        else:
            self.attached_to._recalculate_stats()

    def _on_compute_final_stats(self, event: "ComputeFinalStats") -> None:
        event.modifiers.extend(self.stat_modifiers())


# ---------------------------------------------------------------------------
# DotEffect — generic periodic-damage effect
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DoTEffect(Effect):
    """Generic periodic-damage DoT effect.

    Stats are snapshotted by the caller before creating the effect and passed
    in via the ``snapshot`` field.  Tick interval scales with haste:
        tick_duration = base_tick_duration / (1 + snapshot.haste_percent)

    If ``does_partial_final_tick`` is True, a scaled partial damage fires on
    removal proportional to the fractional tick window at the end of the duration:
        partial_ratio = (duration / base_tick_duration * (1 + haste_percent)) % 1
    Only applies to finite-duration effects.
    """

    owner: "Player"

    snapshot: "SnapshotStats"
    base_tick_duration: float
    does_partial_final_tick: bool = False

    _tick_duration: float = field(default=0.0, init=False)
    _partial_ratio: float = field(default=0.0, init=False)

    def on_add(self) -> None:

        haste_percent = self.owner.stats.haste_percent
        # TODO: fix DOT ticking even when duration % tick_rate == 0
        # Currently, the expiry and the final dot collide, preventing the final dot
        self._tick_duration = (
            self.base_tick_duration / (1 + haste_percent)
        ) - 1e-9  # slightly shave off duration to ensure that all base ticks go through

        if self.does_partial_final_tick and self.duration != float("inf"):
            total = self.duration / self.base_tick_duration * (1 + haste_percent)
            self._partial_ratio = total % 1

        human_readable_name = self.name.replace("_", " ")
        logger.debug(
            f"dot added: {human_readable_name} tick duration={self._tick_duration:.3f}s partial ratio={self._partial_ratio:.3f} on {self.attached_to}",
        )
        state = self.owner.state
        state.schedule(
            time_delay=self._tick_duration,
            callback=GenericTimedEvent(name=f"{self.name} tick", callback=self._fire_tick),
        )

    def on_remove(self) -> None:
        if self.attached_to is not None and self.does_partial_final_tick and self._partial_ratio > 1e-9:
            partial_snap = self.snapshot.scale_average_damage(self._partial_ratio)
            self._deal_periodic(partial_snap, self.attached_to)

    def _fire_tick(self) -> None:

        if self.attached_to is None:
            return
        if self.snapshot is not None:
            self._deal_periodic(self.snapshot, self.attached_to)

        state = self.owner.state
        state.schedule(
            time_delay=self._tick_duration,
            callback=GenericTimedEvent(name=f"{self.name} tick", callback=self._fire_tick),
        )

    def _deal_periodic(self, snapshot: "SnapshotStats", target: "Entity") -> None:
        from .combat import deal_damage

        deal_damage(snapshot, self, target, is_dot=True)
