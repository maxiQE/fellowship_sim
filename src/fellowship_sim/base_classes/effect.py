import itertools
from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

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

    is_independently_stackable: bool = field(default=False, init=False)

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

    def on_remove(self, *, is_remove_from_expiration: bool = False) -> None:
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

    def fuse(self, existing: list[Self]) -> bool:
        """Called when self is a new effect incoming on the target and the target already has one or more effects of the same type.

        Return a flag indicating whether to keep self or discard it.

        Default behaviour:
        - Infinite-duration effects cannot be fused (something has gone wrong).
        - Finite-duration effects:
            - renew duration of the existing effect,
            - merge stacks up to cap,
            - discard incomming effect (self)

        Override in subclasses to implement custom fusion logic (e.g. AmethystSplintersDoT).
        """
        from .events import EffectRefreshed

        # independently stackable traits have no fuse logic: we just apply them side-by-side
        if self.is_independently_stackable:
            return True

        # infinite duration, non-stackable: raise Error to prevent user and programming errors
        if self.duration == float("inf"):
            raise DuplicateEffectError(self.name)

        # finite duration, non-stackable: renew duration, add stacks
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

    def on_fuse(self, new_effect: Self) -> None:
        """Called after fuse completes. Override in subclasses for post-fuse behaviour."""

    def _expire(self, seq: int) -> None:
        if seq != self._expiry_seq:
            return  # stale — effect was refreshed or removed since this was scheduled
        self.remove(is_remove_from_expiration=True)

    def remove(self, *, is_remove_from_expiration: bool = False) -> None:
        """Remove this effect.

        Remove triggers the `on_remove` function for specialized processing by subclasses.
        """

        from .events import EffectRemoved

        if self.attached_to is None:
            raise Exception(f"Effect {self} not attached during remove")  # noqa: TRY002, TRY003

        logger.trace(f"effect removed ({'expired' if is_remove_from_expiration else 'dispelled'}): {self}")

        self.owner.state.bus.emit(
            EffectRemoved(
                effect=self,
                target=self.attached_to,
            )
        )

        self.owner.state.bus.unsubscribe_all(self)
        self.on_remove(is_remove_from_expiration=is_remove_from_expiration)  # called while attached_to is still valid
        self.attached_to.effects.remove(self)  # removes from dict; attached_to cleared after on_remove
        self.attached_to = None
        self._expiry_seq += 1


class EffectCollection:
    def __init__(self) -> None:
        self._effects: list[Effect] = []
        self._entity: Entity | None = None

    def get[T: Effect](self, effect_type: type[T]) -> T | None:
        """Return the first active effect of type effect_type, or None if absent."""
        for effect in self._effects:
            if isinstance(effect, effect_type):
                return effect
        return None

    def filter[T: Effect](self, effect_type: type[T]) -> list[T]:
        """Return the list of active effect of type effect_type."""
        return [effect for effect in self._effects if isinstance(effect, effect_type)]

    def has[T: Effect](self, effect_type: type[T]) -> bool:
        """Return True if any active effect is an instance of effect_type."""
        return any(isinstance(e, effect_type) for e in self._effects)

    def add[T: Effect](self, new_effect: T) -> None:
        """Add effect to the collection.

        If an effect with the same name is already active, calls fuse() on the
        existing effect instead of adding a duplicate.
        """
        existing = self.filter(type(new_effect))
        if len(existing):
            insert_new_effect = new_effect.fuse(existing)

            if not insert_new_effect:
                return

        self._effects.append(new_effect)
        new_effect.attached_to = self._entity

        new_effect.add()
        new_effect._schedule_expiry()

    def remove(self, effect: Effect) -> None:
        """Remove effect from the internal dict. Called by Effect.remove() after on_remove()."""
        self._effects.remove(effect)
        # Note: effect.attached_to is cleared by Effect.remove() after on_remove()

    def __iter__(self) -> Iterator[Effect]:
        return iter(self._effects)

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

    def on_fuse(self, new_effect: Self) -> None:  # ty:ignore[invalid-method-override]
        if self.attached_to is None:
            raise Exception("Buff unnattached in on_fuse")  # noqa: TRY002, TRY003
        else:
            self.attached_to._recalculate_stats()

    def on_remove(self, *, is_remove_from_expiration: bool = False) -> None:
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
    """Generic periodic-damage DoT effect."""

    owner: "Player"

    average_damage: float = field(init=False)
    duration: float = field(init=False)
    base_tick_interval: float = field(init=False)
    does_partial_final_tick: bool = field(default=True, init=False)
    does_immediate_tick: bool = field(default=False, init=False)
    is_scaled_by_expertise: bool = field(default=True, init=False)
    is_scaled_by_main_stat: bool = field(default=True, init=False)
    crit_percent_override: float | None = field(default=None, init=False)

    last_elapsed_fraction__value: float = field(init=False)
    last_elapsed_fraction__time: float = field(init=False)
    last_elapsed_fraction__tick_interval: float = field(init=False)

    _tick_interval_change_guard: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.last_elapsed_fraction__value = 0
        self.last_elapsed_fraction__time = self.owner.state.time
        self.last_elapsed_fraction__tick_interval = self.tick_interval

    @property
    def tick_interval(self) -> float:
        return self.base_tick_interval / (1 + self.owner.stats.haste_percent) / self.owner.dot_tick_acceleration

    @property
    def elapsed_fraction(self) -> float:
        return (
            self.last_elapsed_fraction__value
            + (self.owner.state.time - self.last_elapsed_fraction__time) / self.last_elapsed_fraction__tick_interval
        )

    @property
    def average_tick_damage_snapshot(self) -> "SnapshotStats":
        from fellowship_sim.base_classes import SnapshotStats

        if self.attached_to is None:
            raise Exception("Unattached DoT can't compute its damage")  # noqa: TRY002, TRY003

        snapshot = SnapshotStats.from_base_damage_and_character(
            base_damage=self.average_damage,
            character=self.owner,
            damage_source=self,
            is_scaled_by_expertise=self.is_scaled_by_expertise,
            is_scaled_by_main_stat=self.is_scaled_by_main_stat,
        )

        if self.crit_percent_override is not None:
            snapshot = snapshot.fixed_crit_percent(self.crit_percent_override)
        return snapshot

    def recompute_tick_time(self) -> None:
        # invalidate previous tick
        self._tick_interval_change_guard += 1

        # Compute new tick time
        remaining_tick_interval = (1 - self.elapsed_fraction) * self.tick_interval
        self.schedule_tick(remaining_tick_interval)

    def schedule_tick(self, tick_interval: float) -> None:
        guard = self._tick_interval_change_guard

        self.last_elapsed_fraction__value = self.elapsed_fraction
        self.last_elapsed_fraction__time = self.owner.state.time
        self.last_elapsed_fraction__tick_interval = self.tick_interval

        self.owner.state.schedule(
            time_delay=tick_interval,
            callback=GenericTimedEvent(name=f"{self.name} tick", callback=lambda: self._fire_tick(guard)),
        )

    def deal_tick_damage(self, ratio: float = 1) -> None:
        from fellowship_sim.base_classes import deal_damage

        if self.attached_to is None:
            raise Exception(f"Dot {self} unattached during deal_damage")  # noqa: TRY002, TRY003

        deal_damage(
            snapshot=self.average_tick_damage_snapshot.scale_average_damage(ratio),
            damage_origin=self,
            target=self.attached_to,
            is_dot=True,
        )

    @property
    def max_duration(self) -> float:
        return type(self).duration

    def extend_duration(self, duration_increase: float) -> None:
        self.duration = min(self.duration + duration_increase, self.max_duration)
        self._schedule_expiry()

    def on_add(self) -> None:
        self.owner.register_dot(self)

        if self.does_immediate_tick:
            self.deal_tick_damage()

        self.schedule_tick(self.tick_interval)

        human_readable_name = self.name.replace("_", " ")
        logger.debug(
            f"dot added: {human_readable_name} tick interval={self.tick_interval:.3f}s on {self.attached_to}",
        )

    def on_remove(self, *, is_remove_from_expiration: bool = False) -> None:
        self.owner.unregister_dot(self)

        if self.attached_to is not None and self.does_partial_final_tick and is_remove_from_expiration:
            partial_ratio = self.elapsed_fraction
            self.deal_tick_damage(partial_ratio)

    def _fire_tick(self, guard: int) -> None:
        if self.attached_to is None or guard != self._tick_interval_change_guard:
            return

        self.deal_tick_damage()

        self.last_elapsed_fraction__value = 0
        self.last_elapsed_fraction__time = self.owner.state.time
        self.schedule_tick(self.tick_interval)

    def fuse(self, existing: list[Self]) -> bool:  # ty:ignore[invalid-method-override]
        """Called when self is a new effect incoming on the target and the target already has one or more effects of the same type.

        Return a flag indicating whether to keep self or discard it.

        Overwritten: fot DoTs, we keep the incoming, and discard the existing DoT.
        """
        for dot in existing:
            dot.remove(is_remove_from_expiration=False)

        return True


@dataclass(kw_only=True, repr=False)
class AccumulatorEffect(DoTEffect):
    """Damage-over-time with variable damage."""

    average_damage: float = field(init=True)
    is_scaled_by_expertise: bool = field(default=False, init=False)
    is_scaled_by_main_stat: bool = field(default=False, init=False)
    crit_percent_override: float | None = field(default=0.0, init=False)

    def fuse(self, existing: list[Self]) -> bool:  # ty:ignore[invalid-method-override]
        """Called when self is a new effect incoming on the target and the target already has one or more effects of the same type.

        Return a flag indicating whether to keep self or discard it.

        Overwritten for custom updating of the stored damage.

        remaining_duration_fraction = current_duration / initial_duration
        (type(self).duration is the class-level default, i.e. the initial duration)

        The fraction (1 - remaining_duration_fraction) of self.average_damage has already
        been paid out via past ticks, so only the remaining fraction is kept.
        new_effect.average_damage is added in full, as none of it has been dealt yet.

        NB: this seems to be game-accurate.
        """
        from .events import EffectRefreshed

        current = existing[0]

        if current.attached_to is None:
            raise Exception(f"current existing effect {current} is unnattached during fuse")  # noqa: TRY002, TRY003

        remaining_duration_fraction = current.duration / type(self).duration
        current.average_damage = remaining_duration_fraction * current.average_damage + self.average_damage

        current.duration = self.duration

        current._schedule_expiry()

        self.owner.state.bus.emit(
            EffectRefreshed(
                effect=current,
                target=current.attached_to,
            )
        )

        current.on_fuse(self)

        return False
