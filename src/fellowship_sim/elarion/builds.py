from dataclasses import dataclass, field

from fellowship_sim.base_classes import RawStats
from fellowship_sim.elarion.setup import ElarionLegendaryName, ElarionSetup
from fellowship_sim.elarion.setup_effect import ElarionTalentName
from fellowship_sim.generic_game_logic.set_effects import SetEffectName
from fellowship_sim.generic_game_logic.setup_effect import GemColorName
from fellowship_sim.generic_game_logic.weapon_abilities import WeaponName
from fellowship_sim.generic_game_logic.weapon_traits import WeaponHeroicTraitName, WeaponMasterTraitName

# Talent builds

# April consensus talent build for Elarion
BASIC_BARRAGE_BUILD: list[ElarionTalentName] = [
    "Piercing Seekers",
    "Fusillade",
    "Lunar Fury",
    "Lunarlight Affinity",
    "Fervent Supremacy",
    "Impending Heartseeker",
    "Last Lights",
]


BARRAGE_BUILD__NO_IHB: list[ElarionTalentName] = [
    "Piercing Seekers",
    "Fusillade",
    "Lunar Fury",
    "Lunarlight Affinity",
    "Fervent Supremacy",
    "Last Lights",
]


# Gems

# +762 overcap; 1 set
GEM_BUILD_10b_6r__1_set: dict[GemColorName, int] = {
    "blue__saphire": 3402,
    "red__ruby": 1206,
}

# +114 overcap; 0 set
GEM_BUILD_10b_6r_6p__0_set: dict[GemColorName, int] = {
    "blue__saphire": 2754,
    "red__ruby": 1296,
    "purple__amethyst": 1206,
}

# +114 overcap; 2 set
GEM_BUILD_10b_4w_1r__2_set: dict[GemColorName, int] = {
    "blue__saphire": 2754,
    "red__ruby": 120,
    "white__diamond": 720,
}

# +102 overcap; 3 set
GEM_BUILD_10b_1r__3_set: dict[GemColorName, int] = {
    "blue__saphire": 2742,
    "red__ruby": 120,
}

# +426 overcap; 3 set
GEM_BUILD_10b__3_set: dict[GemColorName, int] = {
    "blue__saphire": 3066,
}

# Full setups


@dataclass(kw_only=True)
class ElarionSetupBasic(ElarionSetup):
    """April consensus for Elarion.

    - Standard barrage build talents
    - Neck Legendary.
    - Voidbringer's Touch with Visions Of Grandeur.
    - WM and IA
    - 10b 6r (+762 overcap)
    - Drakheim
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[WeaponHeroicTraitName] | None = field(
        default_factory=lambda: [
            "Willful Momentum",
            "Inspired Allegiance",
        ],
        init=True,
    )
    sets: list[SetEffectName] | None = field(
        default_factory=lambda: [
            "Drakheim's Absolution",
        ],
        init=True,
    )
    num_sets: int | None = field(default=1, init=True)

    talents: list[ElarionTalentName] | None = field(default_factory=lambda: [*BASIC_BARRAGE_BUILD], init=True)
    legendary: ElarionLegendaryName | None = field(default="Neck", init=True)
    weapon_ability: WeaponName | None = field(default="Voidbringer's Touch", init=True)
    master_trait: WeaponMasterTraitName | None = field(default="Visions Of Grandeur", init=True)
    gem_power: dict[GemColorName, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_6r__1_set}, init=True)


@dataclass(kw_only=True)
class ElarionSetup10b6r6p(ElarionSetup):
    """Alternative build to consensus:

    - replace gem + set setup to 10b6r6p
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[WeaponHeroicTraitName] | None = field(
        default_factory=lambda: [
            "Willful Momentum",
            "Inspired Allegiance",
        ],
        init=True,
    )
    sets: list[SetEffectName] | None = field(
        default_factory=lambda: [],
        init=True,
    )
    num_sets: int | None = field(default=0, init=True)

    talents: list[ElarionTalentName] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: ElarionLegendaryName | None = field(default="Neck", init=True)
    weapon_ability: WeaponName | None = field(default="Voidbringer's Touch", init=True)
    master_trait: WeaponMasterTraitName | None = field(default="Visions Of Grandeur", init=True)
    gem_power: dict[GemColorName, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_6r_6p__0_set}, init=True)


@dataclass(kw_only=True)
class ElarionSetupAngryMultiplierStack(ElarionSetup):
    """Alternative build to consensus:

    - 2 set setup: Drakheim + Torment
    - 10b 4w 1r

    The objective is to stack main stat modifiers.
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[WeaponHeroicTraitName] | None = field(
        default_factory=lambda: [
            "Willful Momentum",
            "Inspired Allegiance",
        ],
        init=True,
    )
    sets: list[SetEffectName] | None = field(
        default_factory=lambda: [
            "Drakheim's Absolution",
            "Torment of Bael'Aurum",
        ],
        init=True,
    )
    num_sets: int | None = field(default=2, init=True)

    talents: list[ElarionTalentName] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: ElarionLegendaryName | None = field(default="Neck", init=True)
    weapon_ability: WeaponName | None = field(default="Voidbringer's Touch", init=True)
    master_trait: WeaponMasterTraitName | None = field(default="Visions Of Grandeur", init=True)
    gem_power: dict[GemColorName, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_4w_1r__2_set}, init=True)


@dataclass(kw_only=True)
class ElarionSetupAngryThreeSet(ElarionSetup):
    """Alternative build to consensus:

    - 3 set setup: Drakheim + Torment
    - 10b 4w 1r

    The objective is to stack main stat modifiers.
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[WeaponHeroicTraitName] | None = field(
        default_factory=lambda: [
            "Willful Momentum",
            "Inspired Allegiance",
        ],
        init=True,
    )
    sets: list[SetEffectName] | None = field(
        default_factory=lambda: [
            "Drakheim's Absolution",
            "Torment of Bael'Aurum",
            "Death's Grasp",
        ],
        init=True,
    )
    num_sets: int | None = field(default=3, init=True)

    talents: list[ElarionTalentName] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: ElarionLegendaryName | None = field(default="Neck", init=True)
    weapon_ability: WeaponName | None = field(default="Voidbringer's Touch", init=True)
    master_trait: WeaponMasterTraitName | None = field(default="Visions Of Grandeur", init=True)
    gem_power: dict[GemColorName, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b__3_set}, init=True)
