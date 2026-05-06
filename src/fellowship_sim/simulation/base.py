from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING

from fellowship_sim.base_classes.entity import Player

if TYPE_CHECKING:
    from fellowship_sim.base_classes.ability import Ability


class FightOver(Exception):
    """Raised by the scenario's end-of-fight callback to terminate the rotation loop."""


class Rotation[TPlayer: Player](ABC):
    description: str = ""

    @abstractmethod
    def __call__(self, player: TPlayer, /) -> Iterator["Ability | None"]:
        """Yield the next ability to cast (or None to pass), given the current character state.

        Args:
            player: The character being controlled.
        """
        ...
