from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fellowship_sim.elarion.entity import Elarion


class FightOver(Exception):
    """Raised by the scenario's end-of-fight callback to terminate the rotation loop."""


class Rotation(ABC):
    description: str = ""

    @abstractmethod
    def run(self, elarion: "Elarion") -> None: ...
