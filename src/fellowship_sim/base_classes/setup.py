from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Generic

from .ability import TCharacter

if TYPE_CHECKING:
    from fellowship_sim.generic_game_logic.buff import SpiritOfHeroismAura

    from .effect import Effect


class SetupTiming(enum.IntEnum):
    """Ordering priority for setup effects within CharacterSetup.finalize().

    Effects with lower timing values are applied first:
      EARLY  → run before everything else (e.g. create permanent auras)
      NORMAL → run after EARLY, before LATE (e.g. configure the auras)
      LATE   → run last (default; most setup effects)
    """

    EARLY = 0
    NORMAL = 1
    LATE = 2


@dataclass(kw_only=True)
class SetupContext:
    """Shared namespace passed to every SetupEffect.apply() during character finalization.

    Effects can read and write fields here to communicate across setup phases.
    """

    spirit_of_heroism_aura: SpiritOfHeroismAura | None = None


class SetupEffect(ABC, Generic[TCharacter]):  # noqa: UP046
    """Abstract base for all setup effects.

    Subclasses declare their phase via the ``timing`` class variable; effects with
    lower timing values are applied first by CharacterSetup.finalize().
    """

    timing: ClassVar[SetupTiming] = SetupTiming.LATE

    @abstractmethod
    def apply(self, character: TCharacter, context: SetupContext) -> None:
        pass


class SetupEffectEarly(SetupEffect[TCharacter]):
    """Setup effect that runs in the EARLY phase."""

    timing: ClassVar[SetupTiming] = SetupTiming.EARLY


class SetupEffectNormal(SetupEffect[TCharacter]):
    """Setup effect that runs in the NORMAL phase."""

    timing: ClassVar[SetupTiming] = SetupTiming.NORMAL


class SetupEffectLate(SetupEffect[TCharacter]):
    """Setup effect that runs in the LATE phase (default)."""

    timing: ClassVar[SetupTiming] = SetupTiming.LATE


@dataclass(kw_only=True)
class SimpleEffectSetup(SetupEffectLate[TCharacter]):
    """Wrap a pre-built Effect instance as a SetupEffectLate."""

    effect: Effect

    def apply(self, character: TCharacter, context: SetupContext) -> None:
        character.effects.add(self.effect)
