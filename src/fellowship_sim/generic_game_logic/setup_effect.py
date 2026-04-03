"""Generic weapon trait setup effects — applied once after character initialisation."""

import re
from dataclasses import dataclass, field
from typing import Literal, get_args

from loguru import logger

from fellowship_sim.base_classes import Effect
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.setup import SetupContext, SetupEffectEarly, SetupEffectLate
from fellowship_sim.generic_game_logic.buff import BaseCritPercent, RandomizePlayerPercentHP, SpiritOfHeroismAura
from fellowship_sim.generic_game_logic.gems import (
    AdrenalineRush,
    AncientsWisdom,
    BerserkersZeal,
    BlessingOfTheArtisan,
    BlessingOfTheCommander,
    BlessingOfTheConqueror,
    BlessingOfTheDeathdealer,
    BlessingOfTheVirtuoso,
    ChampionsHeart,
    FelineGrace,
    FirstStrike,
    GemOvercap,
    HarmoniousSoul,
    KillerInstinct,
    MightOfTheMinotaur,
    MysticsIntuition,
    OraclesForesight,
    ReapersReprieve,
    ResonatingSoul,
    RoguesResurgence,
    SealedFate,
    SentinelsBastion,
    StoicsTeachings,
    TacticiansAcumen,
    ThiefsAlacrity,
    TitansBlood,
    TranquilResolve,
    UnyieldingVitality,
    VanguardsResolve,
)
from fellowship_sim.generic_game_logic.set_effects import (
    _SET_EFFECTS,
    SetEffectName,
)
from fellowship_sim.generic_game_logic.weapon_traits import (
    _HEROIC_TRAITS,
    _MASTER_TRAITS,
    WeaponHeroicTraitName,
    WeaponMasterTraitName,
)

_UNLOCK_THRESHOLDS: list[int] = [120, 240, 480, 720, 960]
_LEVELUP_THRESHOLDS: list[int] = [1200, 1560, 1920, 2280, 2640]
_OVERCAP_THRESHOLD: int = 2640


@dataclass(kw_only=True)
class DefaultEffectSetup(SetupEffectEarly[Player]):
    """Add the default +5% crit and SpiritOfHeroismAura effects."""

    def apply(self, character: Player, context: SetupContext) -> None:
        soh_aura = SpiritOfHeroismAura(owner=character)
        character.effects.add(BaseCritPercent(owner=character))
        character.effects.add(soh_aura)

        if context.spirit_of_heroism_aura:
            raise Exception("Trying to override already existing spirit_of_heroism_aura on context")  # noqa: TRY002, TRY003
        context.spirit_of_heroism_aura = soh_aura

        character._recalculate_stats()


@dataclass(kw_only=True)
class WeaponMasterTraitSelection(SetupEffectLate[Player]):
    """Apply up to one weapon master trait to the character."""

    master_trait: WeaponMasterTraitName
    trait_level: int = 4

    def __str__(self) -> str:
        level_str = "" if self.trait_level == 4 else f" (lv.{self.trait_level})"
        return f"Master Trait: {self.master_trait}{level_str}"

    def apply(self, character: Player, context: SetupContext) -> None:
        setup = _MASTER_TRAITS[self.master_trait](trait_level=self.trait_level)
        setup.apply(character, context)
        logger.debug(f"setup: weapon master trait '{self.master_trait}' (level {self.trait_level}) applied")


@dataclass(kw_only=True)
class WeaponHeroicTraitSelection(SetupEffectLate[Player]):
    """Apply up to two weapon heroic traits to the character."""

    heroic_traits: list[WeaponHeroicTraitName] = field(default_factory=list)
    trait_level: int = 4

    def __post_init__(self) -> None:
        if len(self.heroic_traits) > 2:
            raise ValueError(f"Up to 2 heroic traits allowed, got {len(self.heroic_traits)}")  # noqa: TRY003

    def __str__(self) -> str:
        level_str = "" if self.trait_level == 4 else f" (lv.{self.trait_level})"
        return f"Heroic Traits: {', '.join(self.heroic_traits)}{level_str}"

    def apply(self, character: Player, context: SetupContext) -> None:
        for name in self.heroic_traits:
            setup = _HEROIC_TRAITS[name](trait_level=self.trait_level)
            setup.apply(character, context)
            logger.debug(f"setup: weapon heroic trait '{name}' (level {self.trait_level}) applied")


@dataclass(kw_only=True)
class SetEffectSelection(SetupEffectLate[Player]):
    """Apply one or more set bonus effects to the character."""

    sets: list[SetEffectName]

    def __str__(self) -> str:
        return f"Sets: {', '.join(self.sets)}"

    def apply(self, character: Player, context: SetupContext) -> None:
        for name in self.sets:
            character.effects.add(_SET_EFFECTS[name](owner=character))
            logger.debug(f"setup: set effect '{name}' applied")


@dataclass(kw_only=True)
class RandomizePlayerPercentHPSetup(SetupEffectLate[Player]):
    """Setup effect to randomly shift player HP from 100% to low_hp_percent."""

    high_hp_uptime: float = field(default=0.80, init=True)

    def __str__(self) -> str:
        return f"High HP uptime: {100 * self.high_hp_uptime:.0f}%"

    def apply(self, character: Player, context: SetupContext) -> None:
        if self.high_hp_uptime < 1.0:
            character.effects.add(RandomizePlayerPercentHP(owner=character, high_hp_uptime=self.high_hp_uptime))
            logger.debug("setup: 'randomize player percent hp' applied")
        else:
            logger.warning(
                "setup: 'randomize player percent hp' NOT APPLIED because requested uptime of 100% disables it. Set to `None` to disable this warning."
            )


@dataclass(kw_only=True)
class _GenericGemSetupEffectLate(SetupEffectLate[Player]):
    """Common protocol for all gem setup-effects."""

    is_level_2: bool = False


@dataclass(kw_only=True)
class BlessingOfTheVirtuosoSetup(_GenericGemSetupEffectLate):
    """Yellow gem (slot 5): permanent +3%/+9% haste buff; sets spirit_of_heroism_aura.blessing_of_the_virtuoso_level.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    def apply(self, character: "Player", context: SetupContext) -> None:

        aura = context.spirit_of_heroism_aura
        if aura is None:
            raise RuntimeError(  # noqa: TRY003
                "BlessingOfTheVirtuosoSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )

        aura.blessing_of_the_virtuoso_level = 2 if self.is_level_2 else 1
        character.effects.add(BlessingOfTheVirtuoso(is_level_2=self.is_level_2, owner=character))

        logger.debug(
            "gem setup: Blessing of the Virtuoso level {} (virtuoso level={}, haste=+{}%)",
            2 if self.is_level_2 else 1,
            aura.blessing_of_the_virtuoso_level,
            9 if self.is_level_2 else 3,
        )


@dataclass(kw_only=True)
class AncestralSurgeSetup(_GenericGemSetupEffectLate):
    """Blue gem (slot 4): +10/+30 max spirit; sets spirit_of_heroism_aura.ancestral_surge_level.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    def apply(self, character: Player, context: SetupContext) -> None:
        bonus = 30 if self.is_level_2 else 10
        character.max_spirit_points += bonus
        level = 2 if self.is_level_2 else 1
        aura = context.spirit_of_heroism_aura
        if aura is None:
            raise RuntimeError(  # noqa: TRY003
                "AncestralSurgeSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )
        aura.ancestral_surge_level = level
        logger.debug(f"gem setup: Ancestral Surge level {level} (+{bonus} max spirit)")


@dataclass(kw_only=True)
class BlessingOfTheProphetSetup(_GenericGemSetupEffectLate):
    """Blue gem (slot 5): SpiritOfHeroism +6s/+18s duration; spirit_ability_cost -5/-15.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    def apply(self, character: Player, context: SetupContext) -> None:
        duration_bonus = 18.0 if self.is_level_2 else 6.0
        cost_reduction = 15.0 if self.is_level_2 else 5.0
        aura = context.spirit_of_heroism_aura
        if aura is None:
            raise RuntimeError(  # noqa: TRY003
                "BlessingOfTheProphetSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )
        aura.soh_duration += duration_bonus
        character.spirit_ability_cost -= cost_reduction
        logger.debug(
            "gem setup: Blessing of the Prophet level {} (+{:.0f}s spirit of heroism duration, -{:.0f} spirit cost)",
            2 if self.is_level_2 else 1,
            duration_bonus,
            cost_reduction,
        )


GEM_COLORS = Literal[
    "red__ruby",
    "purple__amethyst",
    "yellow__topaz",
    "green__emerald",
    "blue__saphire",
    "white__diamond",
]

# NB: all gem effects have the is_level_2 keyword argument
_GEM_EFFECTS: dict[GEM_COLORS, list[type[_GenericGemSetupEffectLate] | type[Effect]]] = {
    "red__ruby": [
        MightOfTheMinotaur,
        ChampionsHeart,
        UnyieldingVitality,
        TitansBlood,
        BlessingOfTheConqueror,
    ],
    "purple__amethyst": [
        SealedFate,
        BerserkersZeal,
        ReapersReprieve,
        KillerInstinct,
        BlessingOfTheDeathdealer,
    ],
    "yellow__topaz": [
        AdrenalineRush,
        ThiefsAlacrity,
        RoguesResurgence,
        FelineGrace,
        BlessingOfTheVirtuosoSetup,
    ],
    "green__emerald": [
        FirstStrike,
        VanguardsResolve,
        SentinelsBastion,
        TacticiansAcumen,
        BlessingOfTheCommander,
    ],
    "blue__saphire": [
        AncestralSurgeSetup,
        MysticsIntuition,
        ResonatingSoul,
        OraclesForesight,
        BlessingOfTheProphetSetup,
    ],
    "white__diamond": [
        HarmoniousSoul,
        StoicsTeachings,
        TranquilResolve,
        AncientsWisdom,
        BlessingOfTheArtisan,
    ],
}


@dataclass(kw_only=True)
class GemSetupEffect(SetupEffectLate[Player]):
    """Apply gem effects to a character based on gem color and power.

    Unlock thresholds (one effect per step): 120, 240, 480, 720, 960.
    Level-up thresholds (effects leveled in order): 1200, 1560, 1920, 2280, 2640.
    Power above 2640 generates a GemOvercap bonus: k * 0.005% main stat where k = power - 2640.
    """

    gem_power: dict[GEM_COLORS, int]

    total_gem_power: int = field(default=5256, init=True)
    gem_trait_level: dict[GEM_COLORS, tuple[int, int]] = field(init=False)
    overcap_power: int = field(init=False)

    def __post_init__(self) -> None:
        invalid_keys = [k for k in self.gem_power if k not in get_args(GEM_COLORS)]
        if invalid_keys:
            raise ValueError(f"invalid gem_power keys {invalid_keys!r}; must be one of {get_args(GEM_COLORS)}")  # noqa: TRY003
        total_gem_power = sum(self.gem_power.values())
        if total_gem_power > self.total_gem_power:
            raise ValueError(f"Configured gem power {total_gem_power} exceeds maximum {self.total_gem_power}")  # noqa: TRY003
        self.gem_trait_level = {
            gem_color: (
                sum(1 for t in _UNLOCK_THRESHOLDS if power >= t),
                sum(1 for t in _LEVELUP_THRESHOLDS if power >= t),
            )
            for gem_color, power in self.gem_power.items()
        }
        self.overcap_power = sum(
            power - _OVERCAP_THRESHOLD for gem_color, power in self.gem_power.items() if power > _OVERCAP_THRESHOLD
        )

    def __str__(self) -> str:
        trait_level_info = []
        for gem_color in get_args(GEM_COLORS):
            if gem_color not in self.gem_power:
                continue
            num_unlocked, num_leveled = self.gem_trait_level[gem_color]
            total_trait_level = num_unlocked + num_leveled
            prefix = gem_color.split("__")[0][0]
            trait_level_info.append((total_trait_level, prefix))

        # Sort by total_trait_level, ignore color to keep order unchanged
        trait_level_info.sort(key=lambda tup: tup[0], reverse=True)

        trait_level_info = [f"{total_trait_level}{prefix}" for total_trait_level, prefix in trait_level_info]

        power_level_info = sorted(
            [(power, gem_color.split("__")[0][0]) for gem_color, power in self.gem_power.items()],
            key=lambda tup: tup[0],
            reverse=True,
        )

        return f"Gems: {' '.join(trait_level_info)} (+{self.overcap_power}) [{', '.join(f'{p}{c}' for p, c in power_level_info)}]"

    def apply(self, character: Player, context: SetupContext) -> None:
        for gem_color in self.gem_power:
            effects = _GEM_EFFECTS[gem_color]
            num_unlocked, num_leveled = self.gem_trait_level[gem_color]

            for i, effect_cls in enumerate(effects[:num_unlocked]):
                is_level_2 = i < num_leveled
                if issubclass(effect_cls, _GenericGemSetupEffectLate):
                    effect_cls(is_level_2=is_level_2).apply(character, context)
                else:
                    # NB: all gem effects have the is_level_2 keyword argument
                    character.effects.add(effect_cls(is_level_2=is_level_2, owner=character))  # ty:ignore[unknown-argument]

                gem_label = gem_color.replace("__", ": ").replace("_", " ")
                effect_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", effect_cls.__name__)
                logger.debug(
                    "gem setup: {} {} (level {})",
                    gem_label,
                    effect_label,
                    2 if is_level_2 else 1,
                )

        if self.overcap_power > 0:
            character.effects.add(GemOvercap(overcap=self.overcap_power, owner=character))
