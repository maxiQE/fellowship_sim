from __future__ import annotations

import contextvars
import heapq
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from fellowship_sim.base_classes.entity import Enemy

from .events import EventBus
from .timed_events import FightOverTimedEvent, TimedEvent

if TYPE_CHECKING:
    from .entity import Entity, Player


@dataclass(kw_only=True)
class StateInformation:
    is_boss_fight: bool = False
    duration: float = float("inf")
    delay_since_last_fight: float | None = 20.0
    is_ult_authorized: bool = True


class RNG(Protocol):
    def random(self) -> float: ...


# ---------------------------------------------------------------------------
# Context-local singleton (thread- and asyncio-safe)
# ---------------------------------------------------------------------------

_state_var: contextvars.ContextVar[State | None] = contextvars.ContextVar("state", default=None)


def get_state() -> State:
    state = _state_var.get()
    if state is None:
        raise RuntimeError("no active State — construct a State before running the sim")  # noqa: TRY003
    return state


def get_bus() -> EventBus:
    return get_state().bus


# ---------------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class State:
    enemies: list[Enemy] = field(default_factory=list, init=True)
    bus: EventBus = field(default_factory=EventBus, init=True)
    rng: RNG = field(default_factory=random.Random, init=True)

    time: float = field(default=0.0, init=False)
    character: Player | None = field(default=None, init=False)

    information: StateInformation = field(default_factory=StateInformation)

    _queue: list[tuple[float, int, TimedEvent]] = field(default_factory=list, init=False, repr=False)
    _queue_seq: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.information.duration != float("inf"):
            self.schedule(time_delay=self.information.duration, callback=FightOverTimedEvent())
        _state_var.set(self)

    def __str__(self) -> str:
        return f"State(t={self.time:.3f}, enemies={len(self.enemies)})"

    def __repr__(self) -> str:
        return str(self)

    @property
    def num_enemies(self) -> int:
        return len(self.enemies)

    def deactivate(self) -> None:
        """Clear the active state in the current context.
        After this call, get_state() raises until another State is activated."""
        _state_var.set(None)

    def schedule(self, time_delay: float, callback: TimedEvent) -> None:
        """Schedule callback to fire after time_delay seconds from now.
        Returning True from callback halts step() early (player_available semantics).
        """
        if time_delay < 0:
            raise ValueError(f"Negative time delay: {time_delay}")  # noqa: TRY003

        trigger_time = self.time + time_delay
        heapq.heappush(self._queue, (trigger_time, self._queue_seq, callback))
        self._queue_seq += 1

        logger.trace(f"scheduled event at t={trigger_time:.3f} (queue length={len(self._queue)})")

    def _tick(self, dt: float) -> None:
        """Tick abilities and effects by dt without advancing self.time."""
        logger.trace("tick(dt={:.4f}) at t={:.3f}", dt, self.time)
        if self.character is not None:
            self.character._tick(dt)
            for ability in self.character.abilities:
                ability._tick(dt)
            for effect in list(self.character.effects):
                effect.tick(dt)
        for enemy in self.enemies:
            enemy._tick(dt)
            for effect in list(enemy.effects):
                effect.tick(dt)

    def step(self) -> None:
        """Process scheduled events until a callback returns True (player_available signal)
        or the queue is empty.  State is the sole time driver; callers only schedule events.
        """
        while self._queue:
            trigger_time, _, callback = heapq.heappop(self._queue)
            elapsed = trigger_time - self.time
            if elapsed > 0:
                self._tick(elapsed)
            self.time = trigger_time

            # Callback returns True if player is available
            if callback():
                # Clear all events at time 0 to avoid weird situations
                while self._queue and self._queue[0][0] == self.time:
                    trigger_time, _, callback = heapq.heappop(self._queue)
                    callback()

                # Return control to player
                return

    def advance_time(self, dt: float) -> None:
        """Advance time by dt, processing events in order (no halt on player_available).
        Kept for tests and explicit raw-time advancement (e.g. effect-decay checks).
        """
        logger.debug("advance time +{:.3f}s (t={:.3f} → {:.3f})", dt, self.time, self.time + dt)
        target = self.time + dt
        while self._queue and self._queue[0][0] <= target:
            trigger_time, _, callback = heapq.heappop(self._queue)
            elapsed = trigger_time - self.time
            if elapsed > 0:
                self._tick(elapsed)
            self.time = trigger_time
            callback()
        remaining = target - self.time
        if remaining > 0:
            self._tick(remaining)
        self.time = target

    def select_targets(
        self,
        main_target: Entity | None,
        num: int,
        priority_func: Callable[[Entity], float] | None = None,
    ) -> list[Entity]:
        """
        Select up to 'num' enemies, prioritizing those with the highest priority score.

        - If no priority_func is provided, select enemies uniformly
        - If a priority_func is provided:

            - Highest priority enemies are necessarily selected.
            - If there is a tie the number of targets is insufficient to select all the tied enemies,
                a uniformly random subset is chosen.

        Args:
            main_target: An entity to exclude from selection.
                On abilities with a main target and secondary targets, this is used to exclude the main target.
            num: The maximum number of targets to return.
            priority_func: A callable that takes an Entity and returns a float score.
                Higher scores are targeted first.

        Returns:
            A list of selected Entity objects.
        """
        pool: list[Entity] = [e for e in self.enemies if e is not main_target]

        if len(pool) == 0:
            return []

        if priority_func is not None:
            priorities: list[float] = [priority_func(e) for e in pool]
        else:
            priorities: list[float] = [0.0] * len(pool)

        result = []
        n_select = min(num, len(pool))

        # Select targets by priority until we find a group of equal priority with too many members
        # Then select randomly in that group
        while n_select > 0:
            # Find the current highest priority value
            max_val: float = max(priorities)

            # Get indices of all entities sharing that max priority
            sub_pool_indices: list[int] = [idx for idx, val in enumerate(priorities) if val == max_val]

            # If there are less than n_select, select all
            # Else, select randommly
            if n_select >= len(sub_pool_indices):
                selected_indices = sub_pool_indices
            else:
                remaining = list(sub_pool_indices)
                selected_indices = []
                for _ in range(n_select):
                    idx = int(self.rng.random() * len(remaining))
                    selected_indices.append(remaining.pop(idx))

            # Add to selection
            for idx in selected_indices:
                result.append(pool[idx])
            for idx in sorted(selected_indices, reverse=True):
                pool.pop(idx)
                priorities.pop(idx)
            n_select -= len(selected_indices)

        return result
