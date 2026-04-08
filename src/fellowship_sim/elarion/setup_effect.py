"""Setup effects for Elarion — applied once after character initialisation."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from loguru import logger

from fellowship_sim.base_classes import SetupEffectEarly
from fellowship_sim.base_classes.setup import SetupContext, SetupEffectLate
from fellowship_sim.elarion.effect import (
    CelestialImpetusAura,
    FinalCrescendo,
    FocusedExpanseEffect,
    Fusillade,
    HighwindAppliesShimmerEffect,
    LastLights,
    LethalShots,
    LunarFury,
    LunarlightAffinity,
    RepeatingStars,
    SkywardMunitions,
    SpiritEffectProc,
    StarstrikersAscentLegendary,
)

if TYPE_CHECKING:
    from fellowship_sim.elarion.entity import Elarion


class ElarionDefaultEffectSetup(SetupEffectEarly["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.effects.add(CelestialImpetusAura(owner=character))
        character.effects.add(SpiritEffectProc(owner=character))


@dataclass(kw_only=True)
class FinalCrescendoSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.effects.add(FinalCrescendo(owner=character))
        logger.debug("setup: Final Crescendo added")


@dataclass(kw_only=True)
class SkylitGraceSetup(SetupEffectLate["Elarion"]):
    """Enables SkystriderGrace CDR interaction on Volley."""

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        volley = character.volley
        volley.has_skylit_grace = True
        logger.debug("setup: Volley Skylit Grace → enabled")


@dataclass(kw_only=True)
class FusilladeSetup(SetupEffectLate["Elarion"]):
    barrage_new_duration: float = field(default=2.5, init=False)

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        barrage = character.heartseeker_barrage
        barrage.base_player_downtime = self.barrage_new_duration
        character.effects.add(Fusillade(owner=character))
        logger.debug("setup: Fusillade added")


@dataclass(kw_only=True)
class SkywardMunitionsSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.effects.add(SkywardMunitions(owner=character))
        logger.debug("setup: Skyward Munitions added")


@dataclass(kw_only=True)
class RepeatingStarsSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.effects.add(RepeatingStars(owner=character))
        logger.debug("setup: Repeating Stars added")


@dataclass(kw_only=True)
class LunarFurySetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.has_increased_proc_chance_barrage = True
        character.effects.add(LunarFury(owner=character))
        logger.debug("setup: Lunar Fury added; increased proc chance on barrage → enabled")


@dataclass(kw_only=True)
class LethalShotsSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.effects.add(LethalShots(owner=character))
        logger.debug("setup: Lethal Shots added")


@dataclass(kw_only=True)
class PathOfTwilightSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        pass  # no-op


@dataclass(kw_only=True)
class LunarlightAffinitySetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.has_increased_proc_chance_volley = True
        character.effects.add(LunarlightAffinity(owner=character))
        logger.debug("setup: Lunarlight Affinity added; increased proc chance on volley → enabled")


@dataclass(kw_only=True)
class MagicWardSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        pass  # no-op


@dataclass(kw_only=True)
class FerventSupremacySetup(SetupEffectLate["Elarion"]):
    """Enables FerventSupremacy mode on SkystriderSupremacy and reduces its cooldown by 15s."""

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        ability = character.skystrider_supremacy
        ability.is_fervent_supremacy = True
        ability.base_cooldown -= 15.0
        logger.debug(
            "setup: Fervent Supremacy — Skystrider Supremacy talented → enabled, base cooldown → {:.0f}s",
            ability.base_cooldown,
        )


@dataclass(kw_only=True)
class ImpendingHeartseekerSetup(SetupEffectLate["Elarion"]):
    """CelestialImpetus: on stack consumed, also resets barrage CD and grants ImpendingHeartseeker.

    NB: can only run if CelestialImpetusProc aura has already been added to the effects.
    """

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        ci = character.effects.get(CelestialImpetusAura)
        if ci is None:
            raise Exception("Incorrect elarion setup: IBH talent could not modify CI buff")  # noqa: TRY002, TRY003
        else:
            ci.triggers_impending_barrage = True
            logger.debug("setup: Celestial Impetus triggers impending barrage → enabled")


@dataclass(kw_only=True)
class ResurgentWindsSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.lunarlight_mark.has_resurgent_winds_talent = True
        logger.debug("setup: ResurgentWinds added")


@dataclass(kw_only=True)
class LastLightsSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.effects.add(LastLights(owner=character))
        logger.debug("setup: Last Lights added")


@dataclass(kw_only=True)
class SpiritedFortitudeSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        pass  # no-op


@dataclass(kw_only=True)
class TheWeightOfGravitySetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        pass  # no-op


# ---------------------------------------------------------------------------
# Legendary selection
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class ElarionLegendarySelection(SetupEffectLate["Elarion"]):
    """Apply one of the three Elarion legendary item effects."""

    selected_legendary: Literal["Boots", "Cloak", "Neck"]

    def __str__(self) -> str:
        return f"Legendary: {self.selected_legendary}"

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        if self.selected_legendary == "Neck":
            self._apply_neck(character)
        elif self.selected_legendary == "Boots":
            self._apply_boots(character)
        elif self.selected_legendary == "Cloak":
            self._apply_cloak(character)

    def _apply_neck(self, character: "Elarion") -> None:
        character.effects.add(StarstrikersAscentLegendary(owner=character))
        logger.debug("legendary (Neck): Starstriker's Ascent added")

    def _apply_boots(self, character: "Elarion") -> None:
        volley = character.volley
        volley.duration += 2.0
        volley.multishot_extends_duration_by = 0.5
        logger.debug(
            "legendary (Boots): Volley duration → {:.0f}s, multishot extends duration by → 0.5s",
            volley.duration,
        )

    def _apply_cloak(self, character: "Elarion") -> None:
        character.effects.add(HighwindAppliesShimmerEffect(owner=character))
        logger.debug("legendary (Cloak): Highwind Arrow shimmer effect added")


# ---------------------------------------------------------------------------
# Talent selection
# ---------------------------------------------------------------------------

ElarionTalentName = Literal[
    # cost 2
    "Focused Expanse",
    "Piercing Seekers",
    "Final Crescendo",
    # cost 1
    "Skylit Grace",
    "Fusillade",
    "Skyward Munitions",
    # cost 2
    "Repeating Stars",
    "Lunar Fury",
    "Lethal Shots",
    # cost 1
    "Path Of Twilight",
    "Lunarlight Affinity",
    "Magic Ward",
    # cost 3
    "Fervent Supremacy",
    "Impending Heartseeker",
    "Resurgent Winds",
    # cost 1
    "Last Lights",
    "Spirited Fortitude",
    "The Weight Of Gravity",
]

_TALENT_COSTS: dict[str, int] = {
    "Focused Expanse": 2,
    "Piercing Seekers": 2,
    "Final Crescendo": 2,
    "Skylit Grace": 1,
    "Fusillade": 1,
    "Skyward Munitions": 1,
    "Repeating Stars": 2,
    "Lunar Fury": 2,
    "Lethal Shots": 2,
    "Path Of Twilight": 1,
    "Lunarlight Affinity": 1,
    "Magic Ward": 1,
    "Fervent Supremacy": 3,
    "Impending Heartseeker": 3,
    "Resurgent Winds": 3,
    "Last Lights": 1,
    "Spirited Fortitude": 1,
    "The Weight Of Gravity": 1,
}


@dataclass(kw_only=True)
class FocusedExpanseSetup(SetupEffectLate["Elarion"]):
    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.multishot.empowered_ms_bonus_damage *= 1.2
        character.effects.add(FocusedExpanseEffect(owner=character))
        logger.debug("setup: Focused Expanse added")


@dataclass(kw_only=True)
class PiercingSeekerSetup(SetupEffectLate["Elarion"]):
    secondary_damage_multiplier: float = field(default=0.7, init=False)
    num_secondary_targets: int = field(default=1, init=False)

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        character.heartseeker_barrage.secondary_damage_multiplier = self.secondary_damage_multiplier
        character.heartseeker_barrage.num_secondary_targets = self.num_secondary_targets
        logger.debug("setup: Piercing Seekers added")


_TALENT_SETUP: dict[ElarionTalentName, type[SetupEffectLate["Elarion"]]] = {
    "Focused Expanse": FocusedExpanseSetup,
    "Piercing Seekers": PiercingSeekerSetup,
    "Final Crescendo": FinalCrescendoSetup,
    "Skylit Grace": SkylitGraceSetup,
    "Fusillade": FusilladeSetup,
    "Skyward Munitions": SkywardMunitionsSetup,
    "Repeating Stars": RepeatingStarsSetup,
    "Lunar Fury": LunarFurySetup,
    "Lethal Shots": LethalShotsSetup,
    "Path Of Twilight": PathOfTwilightSetup,
    "Lunarlight Affinity": LunarlightAffinitySetup,
    "Magic Ward": MagicWardSetup,
    "Fervent Supremacy": FerventSupremacySetup,
    "Impending Heartseeker": ImpendingHeartseekerSetup,
    "Resurgent Winds": ResurgentWindsSetup,
    "Last Lights": LastLightsSetup,
    "Spirited Fortitude": SpiritedFortitudeSetup,
    "The Weight Of Gravity": TheWeightOfGravitySetup,
}


@dataclass(kw_only=True)
class ElarionTalentSelection(SetupEffectLate["Elarion"]):
    """Apply a list of talent names, validating the total point cost.

    Raises ValueError if the selected talents exceed total_talent_points.
    """

    talents: list[ElarionTalentName] = field(default_factory=list)
    total_talent_points: int = 13

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

    def apply(self, character: "Elarion", context: SetupContext) -> None:
        for talent in self.talents:
            _TALENT_SETUP[talent]().apply(character, context)

            talent_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", talent)
            logger.debug(f"setup: talent '{talent_label}' applied ({_TALENT_COSTS[talent]} pts)")
