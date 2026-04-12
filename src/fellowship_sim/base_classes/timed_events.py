from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ability import Ability
    from .effect import Effect
    from .entity import Entity
    from .state import PlayerStatusCommand


class TimedEvent(ABC):
    """Base class for all scheduled queue callbacks.

    Returns True to signal player_available (halts State.step early).
    Returns None / False to let step continue processing.
    """

    @abstractmethod
    def __call__(self) -> PlayerStatusCommand | None: ...

    @abstractmethod
    def __str__(self) -> str: ...


# ---------------------------------------------------------------------------
# Built-in timed events
# ---------------------------------------------------------------------------


class PlayerUnavailable(TimedEvent):
    """Fired at the start of a cast or wait — signals to run simulation until player available."""

    def __call__(self) -> PlayerStatusCommand:
        from .state import PlayerStatusCommand

        return PlayerStatusCommand.PlayerCastingStart

    def __str__(self) -> str:
        return "player unavailable"

    def __repr__(self) -> str:
        return str(self)


class PlayerAvailableAgain(TimedEvent):
    """Fired at the end of a cast or wait — signals the rotation may proceed."""

    def __call__(self) -> PlayerStatusCommand:
        from .state import PlayerStatusCommand

        return PlayerStatusCommand.PlayerCastingEnd

    def __str__(self) -> str:
        return "player available again"

    def __repr__(self) -> str:
        return str(self)


@dataclass(kw_only=True)
class FightDowntimeStart(TimedEvent):
    name: str
    callback: Callable[[], None] | None = field(default=None, init=True, repr=False)

    def __call__(self) -> PlayerStatusCommand:
        from .state import PlayerStatusCommand

        if self.callback is not None:
            self.callback()

        return PlayerStatusCommand.PlayerDowntimeStart

    def __str__(self) -> str:
        return f"Fight downtime: {self.name}"

    def __repr__(self) -> str:
        return str(self)


@dataclass(kw_only=True)
class FightDowntimeEnd(TimedEvent):
    name: str
    callback: Callable[[], None] | None = field(default=None, init=True, repr=False)

    def __call__(self) -> PlayerStatusCommand:
        from .state import PlayerStatusCommand

        if self.callback is not None:
            self.callback()

        return PlayerStatusCommand.PlayerDowntimeEnd

    def __str__(self) -> str:
        return f"Fight resumes: {self.name}"

    def __repr__(self) -> str:
        return str(self)


class FightOverTimedEvent(TimedEvent):
    """Fired when the scenario duration elapses — raises FightOver to terminate the rotation."""

    def __call__(self) -> None:
        from fellowship_sim.simulation.base import FightOver

        raise FightOver()

    def __str__(self) -> str:
        return "fight over"

    def __repr__(self) -> str:
        return str(self)


@dataclass(kw_only=True)
class DelayedDamage(TimedEvent):
    """Wraps a damage-dealing callback; stores damage_source for queue introspection."""

    damage_source: Ability | Effect
    callback: Callable[[], None] = field(repr=False)

    def __call__(self) -> None:
        self.callback()

    def __str__(self) -> str:
        return f"delayed damage from {self.damage_source}"

    def __repr__(self) -> str:
        return str(self)


@dataclass(kw_only=True)
class EffectExpiry(TimedEvent):
    """Wraps an effect-expiry callback; stores the effect for queue introspection."""

    effect: Effect
    callback: Callable[[], None] = field(repr=False)

    def __call__(self) -> None:
        self.callback()

    def __str__(self) -> str:
        return f"expiry of {self.effect}"

    def __repr__(self) -> str:
        return str(self)


@dataclass(kw_only=True)
class UnitDeathTimedEvent(TimedEvent):
    """Wraps a unit-death callback; stores the effect for queue introspection."""

    entity: Entity
    callback: Callable[[], None] = field(repr=False)

    def __call__(self) -> None:
        self.callback()

    def __str__(self) -> str:
        return f"unit-death of {self.entity}"

    def __repr__(self) -> str:
        return str(self)


@dataclass(kw_only=True)
class GenericTimedEvent(TimedEvent):
    """Named wrapper for callbacks that don't fit a more specific timed event type."""

    name: str
    callback: Callable[[], None] = field(repr=False)

    def __call__(self) -> None:
        self.callback()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)
