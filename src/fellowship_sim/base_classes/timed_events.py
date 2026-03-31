from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ability import Ability
    from .effect import Effect


class TimedEvent(ABC):
    """Base class for all scheduled queue callbacks.

    Returns True to signal player_available (halts State.step early).
    Returns None / False to let step continue processing.
    """

    @abstractmethod
    def __call__(self) -> bool | None: ...

    @abstractmethod
    def __str__(self) -> str: ...


# ---------------------------------------------------------------------------
# Built-in timed events
# ---------------------------------------------------------------------------


class PlayerAvailableAgain(TimedEvent):
    """Fired at the end of a cast or wait — signals the rotation may proceed."""

    def __call__(self) -> bool:
        return True

    def __str__(self) -> str:
        return "player available again"

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
