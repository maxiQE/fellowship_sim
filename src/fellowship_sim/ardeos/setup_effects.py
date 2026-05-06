import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from loguru import logger

from fellowship_sim.ardeos import ardeos_config
from fellowship_sim.base_classes import Legendary, SetupEffectEarly, SetupEffectLate, base_config
from fellowship_sim.base_classes.setup import SetupContext

from .effect import (
    ApocalypseAura,
    ArdeosSpiritProcAura,
    BackdraftAura,
    CracklingInfernoAura,
    CrashAndBurnAura,
    DevouringFlameAura,
    ExplosivoAura,
    FireBallAccumulatorAura,
    FireFrogsAccumulatorAura,
    FirestarterAura,
    FlareUpAura,
    FrogSquadAura,
    IncinerateHitAura,
    IntensifyingInfernoAura,
    PyrophibianFrenzyAura,
    ReignOfFireAura,
    RollingFlamesAura,
    SlowBurnAura,
    SpontaneousCombustionAura,
)

if TYPE_CHECKING:
    from fellowship_sim.ardeos.entity import Ardeos


# ---------------------------------------------------------------------------
# Always-active default effects
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class ArdeosDefaultEffectSetup(SetupEffectEarly["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(ArdeosSpiritProcAura(owner=character))
        character.effects.add(ApocalypseAura(owner=character))
        character.effects.add(IncinerateHitAura(owner=character))
        character.effects.add(FireBallAccumulatorAura(owner=character))
        character.effects.add(FireFrogsAccumulatorAura(owner=character))


# ---------------------------------------------------------------------------
# Talent setups
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class SlowBurnSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(SlowBurnAura(owner=character))
        logger.debug("setup: Slow Burn added")


@dataclass(kw_only=True)
class FrogSquadSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.fire_frogs.frog_count += 1
        character.fire_frogs.frog_leap_count += 1
        character.effects.add(FrogSquadAura(owner=character))
        logger.debug("setup: Frog Squad added")


@dataclass(kw_only=True)
class GreatBallsOfFireSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.fire_ball.main_damage_multiplier *= ardeos_config.GREAT_BALLS_OF_FIRE_DAMAGE_MULTIPLIER
        logger.debug(f"setup: Great Balls of Fire → fire_ball damage ×{character.fire_ball.main_damage_multiplier:.2f}")


@dataclass(kw_only=True)
class BackdraftSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(BackdraftAura(owner=character))
        logger.debug("setup: Backdraft added")


@dataclass(kw_only=True)
class FlareUpSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(FlareUpAura(owner=character))
        logger.debug("setup: Flare Up added")


@dataclass(kw_only=True)
class CrashAndBurnSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(CrashAndBurnAura(owner=character))
        logger.debug("setup: Crash and Burn added")


@dataclass(kw_only=True)
class AgonizingBlazeSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.searing_blaze.is_agonizing_blaze = True
        logger.debug("setup: Agonizing Blaze added")


@dataclass(kw_only=True)
class FirestarterSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        fb_aura = character.effects.get(FireBallAccumulatorAura)
        ff_aura = character.effects.get(FireFrogsAccumulatorAura)
        if fb_aura is None or ff_aura is None:
            raise Exception("Incorrect Ardeos setup: FirestarterSetup requires accumulator auras")  # noqa: TRY002, TRY003
        fb_aura.fixed_crit_chance = ardeos_config.FIRESTARTER_ACCUMULATOR_FIXED_CRIT_CHANCE
        ff_aura.fixed_crit_chance = ardeos_config.FIRESTARTER_ACCUMULATOR_FIXED_CRIT_CHANCE
        character.effects.add(FirestarterAura(owner=character))
        logger.debug("setup: Firestarter added")


@dataclass(kw_only=True)
class UndyingFlameSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.engulfing_flames.max_charges = ardeos_config.UNDYING_FLAME_EF_CHARGES
        character.engulfing_flames.charges = ardeos_config.UNDYING_FLAME_EF_CHARGES
        character.engulfing_flames.duration += ardeos_config.UNDYING_FLAME_EF_DURATION_EXTENSION
        logger.debug(
            f"setup: Undying Flame → engulfing_flames 2 charges, duration {character.engulfing_flames.duration:.0f}s"
        )


@dataclass(kw_only=True)
class FieryResilienceSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        pass  # defensive talent, not simulated


@dataclass(kw_only=True)
class CracklingInfernoSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(CracklingInfernoAura(owner=character))
        logger.debug("setup: Crackling Inferno added")


@dataclass(kw_only=True)
class MagicWardSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        pass  # defensive talent, not simulated


@dataclass(kw_only=True)
class RollingFlamesSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(RollingFlamesAura(owner=character))
        logger.debug("setup: Rolling Flames added")


@dataclass(kw_only=True)
class PyrophibianFrenzySetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(PyrophibianFrenzyAura(owner=character))
        logger.debug("setup: Pyrophibian Frenzy added")


@dataclass(kw_only=True)
class ReignOfFireSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(ReignOfFireAura(owner=character))
        logger.debug("setup: Reign of Fire added")


@dataclass(kw_only=True)
class IntensifyingInfernoSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(IntensifyingInfernoAura(owner=character))
        logger.debug("setup: Intensifying Inferno added")


@dataclass(kw_only=True)
class SpiritedFortitudeSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        pass  # defensive talent, not simulated


@dataclass(kw_only=True)
class SpontaneousCombustionSetup(SetupEffectLate["Ardeos"]):
    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        character.effects.add(SpontaneousCombustionAura(owner=character))
        logger.debug("setup: Spontaneous Combustion added")


# ---------------------------------------------------------------------------
# Legendary selection
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class ArdeosLegendarySelection(SetupEffectLate["Ardeos"]):
    selected_legendary: Legendary

    def __str__(self) -> str:
        return f"Legendary: {self.selected_legendary}"

    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        if self.selected_legendary == Legendary.NECK:
            self._apply_neck(character)
        elif self.selected_legendary == Legendary.BOOTS:
            self._apply_boots(character)
        elif self.selected_legendary == Legendary.CLOAK:
            self._apply_cloak(character)

    def _apply_neck(self, character: "Ardeos") -> None:
        character.effects.add(ExplosivoAura(owner=character))
        logger.debug("legendary (Neck): Explosivo aura added")

    def _apply_boots(self, character: "Ardeos") -> None:
        character.effects.add(DevouringFlameAura(owner=character))
        logger.debug("legendary (Boots): Devouring Flame aura added")

    def _apply_cloak(self, character: "Ardeos") -> None:
        character.fire_frogs.toad_count = ardeos_config.CLOAK_TOAD_COUNT
        character.fire_frogs.frog_to_toad_conversion_chance = ardeos_config.CLOAK_TOAD_CONVERSION_CHANCE
        logger.debug(
            f"legendary (Cloak): Fire Toad → toad_count={character.fire_frogs.toad_count}, conversion chance={100 * character.fire_frogs.frog_to_toad_conversion_chance}%"
        )


# ---------------------------------------------------------------------------
# Talent selection
# ---------------------------------------------------------------------------


class ArdeosTalent(StrEnum):
    SLOW_BURN = "Slow Burn"
    FROG_SQUAD = "Frog Squad"
    GREAT_BALLS_OF_FIRE = "Great Balls Of Fire"
    BACKDRAFT = "Backdraft"
    FLARE_UP = "Flare Up"
    CRASH_AND_BURN = "Crash And Burn"
    AGONIZING_BLAZE = "Agonizing Blaze"
    FIRESTARTER = "Firestarter"
    UNDYING_FLAME = "Undying Flame"
    FIERY_RESILIENCE = "Fiery Resilience"
    CRACKLING_INFERNO = "Crackling Inferno"
    MAGIC_WARD = "Magic Ward"
    ROLLING_FLAMES = "Rolling Flames"
    PYROPHIBIAN_FRENZY = "Pyrophibian Frenzy"
    REIGN_OF_FIRE = "Reign Of Fire"
    INTENSIFYING_INFERNO = "Intensifying Inferno"
    SPIRITED_FORTITUDE = "Spirited Fortitude"
    SPONTANEOUS_COMBUSTION = "Spontaneous Combustion"


_TALENT_COSTS: dict[ArdeosTalent, int] = {
    ArdeosTalent.SLOW_BURN: 2,
    ArdeosTalent.FROG_SQUAD: 2,
    ArdeosTalent.GREAT_BALLS_OF_FIRE: 2,
    ArdeosTalent.BACKDRAFT: 1,
    ArdeosTalent.FLARE_UP: 1,
    ArdeosTalent.CRASH_AND_BURN: 1,
    ArdeosTalent.AGONIZING_BLAZE: 2,
    ArdeosTalent.FIRESTARTER: 2,
    ArdeosTalent.UNDYING_FLAME: 2,
    ArdeosTalent.FIERY_RESILIENCE: 1,
    ArdeosTalent.CRACKLING_INFERNO: 1,
    ArdeosTalent.MAGIC_WARD: 1,
    ArdeosTalent.ROLLING_FLAMES: 3,
    ArdeosTalent.PYROPHIBIAN_FRENZY: 3,
    ArdeosTalent.REIGN_OF_FIRE: 3,
    ArdeosTalent.INTENSIFYING_INFERNO: 1,
    ArdeosTalent.SPIRITED_FORTITUDE: 1,
    ArdeosTalent.SPONTANEOUS_COMBUSTION: 1,
}

_TALENT_SETUP: dict[ArdeosTalent, type[SetupEffectLate["Ardeos"]]] = {
    ArdeosTalent.SLOW_BURN: SlowBurnSetup,
    ArdeosTalent.FROG_SQUAD: FrogSquadSetup,
    ArdeosTalent.GREAT_BALLS_OF_FIRE: GreatBallsOfFireSetup,
    ArdeosTalent.BACKDRAFT: BackdraftSetup,
    ArdeosTalent.FLARE_UP: FlareUpSetup,
    ArdeosTalent.CRASH_AND_BURN: CrashAndBurnSetup,
    ArdeosTalent.AGONIZING_BLAZE: AgonizingBlazeSetup,
    ArdeosTalent.FIRESTARTER: FirestarterSetup,
    ArdeosTalent.UNDYING_FLAME: UndyingFlameSetup,
    ArdeosTalent.FIERY_RESILIENCE: FieryResilienceSetup,
    ArdeosTalent.CRACKLING_INFERNO: CracklingInfernoSetup,
    ArdeosTalent.MAGIC_WARD: MagicWardSetup,
    ArdeosTalent.ROLLING_FLAMES: RollingFlamesSetup,
    ArdeosTalent.PYROPHIBIAN_FRENZY: PyrophibianFrenzySetup,
    ArdeosTalent.REIGN_OF_FIRE: ReignOfFireSetup,
    ArdeosTalent.INTENSIFYING_INFERNO: IntensifyingInfernoSetup,
    ArdeosTalent.SPIRITED_FORTITUDE: SpiritedFortitudeSetup,
    ArdeosTalent.SPONTANEOUS_COMBUSTION: SpontaneousCombustionSetup,
}


@dataclass(kw_only=True)
class ArdeosTalentSelection(SetupEffectLate["Ardeos"]):
    talents: list[ArdeosTalent] = field(default_factory=list)
    total_talent_points: int = base_config.MAX_TALENT_POINTS

    def __post_init__(self) -> None:
        total_cost = sum(_TALENT_COSTS[t] for t in self.talents)
        if total_cost > self.total_talent_points:
            raise ValueError(  # noqa: TRY003
                f"Talent selection costs {total_cost} points but only {self.total_talent_points} are available "
                f"(talents: {self.talents})"
            )
        logger.debug(f"setup: {total_cost}/{self.total_talent_points} talent points used")

    def __str__(self) -> str:
        return f"Talents: {', '.join(self.talents)}"

    def apply(self, character: "Ardeos", context: SetupContext) -> None:
        for talent in self.talents:
            _TALENT_SETUP[talent]().apply(character, context)

            talent_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", talent)
            logger.debug(f"setup: talent '{talent_label}' applied ({_TALENT_COSTS[talent]} pts)")
