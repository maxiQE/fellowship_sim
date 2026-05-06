from collections.abc import Sequence
from dataclasses import dataclass, field

from fellowship_sim.base_classes import Gem, HeroicTrait, Legendary, MasterTrait, RawStats, Weapon
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.elarion.setup_effect import ElarionTalent
from fellowship_sim.generic_game_logic.set_effects import SetEffectName
from fellowship_sim.generic_game_logic.setup_effect import TalentBuild

# Talent builds

# April consensus talent build for Elarion
BASIC_BARRAGE_BUILD: TalentBuild[ElarionTalent] = TalentBuild([
    ElarionTalent.PIERCING_SEEKERS,
    ElarionTalent.FUSILLADE,
    ElarionTalent.LUNAR_FURY,
    ElarionTalent.LUNARLIGHT_AFFINITY,
    ElarionTalent.FERVENT_SUPREMACY,
    ElarionTalent.IMPENDING_HEARTSEEKER,
    ElarionTalent.LAST_LIGHTS,
])

BARRAGE_BUILD__NO_IHB: TalentBuild[ElarionTalent] = BASIC_BARRAGE_BUILD - ElarionTalent.IMPENDING_HEARTSEEKER

BASIC_HWA_BUILD: TalentBuild[ElarionTalent] = TalentBuild([
    ElarionTalent.FINAL_CRESCENDO,
    ElarionTalent.SKYWARD_MUNITIONS,
    ElarionTalent.LETHAL_SHOTS,
    ElarionTalent.LUNARLIGHT_AFFINITY,
    ElarionTalent.FERVENT_SUPREMACY,
    ElarionTalent.RESURGENT_WINDS,
    ElarionTalent.LAST_LIGHTS,
])


# Gems

# +762 overcap; 1 set
GEM_BUILD_10b_6r__1_set: dict[Gem, int] = {
    Gem.BLUE: 3402,
    Gem.RED: 1206,
}

# +114 overcap; 0 set
GEM_BUILD_10b_6r_6p__0_set: dict[Gem, int] = {
    Gem.BLUE: 2754,
    Gem.RED: 1296,
    Gem.PURPLE: 1206,
}

# +114 overcap; 2 set
GEM_BUILD_10b_4w_1r__2_set: dict[Gem, int] = {
    Gem.BLUE: 2754,
    Gem.RED: 120,
    Gem.WHITE: 720,
}

# +102 overcap; 3 set
GEM_BUILD_10b_1r__3_set: dict[Gem, int] = {
    Gem.BLUE: 2742,
    Gem.RED: 120,
}

# +426 overcap; 3 set
GEM_BUILD_10b__3_set: dict[Gem, int] = {
    Gem.BLUE: 3066,
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

    heroic_traits: list[HeroicTrait] | None = field(
        default_factory=lambda: [
            HeroicTrait.WILLFUL_MOMENTUM,
            HeroicTrait.INSPIRED_ALLEGIANCE,
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

    talents: Sequence[ElarionTalent] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: Legendary | None = field(default=Legendary.NECK, init=True)
    weapon_ability: Weapon | None = field(default=Weapon.VOIDBRINGERS_TOUCH, init=True)
    master_trait: MasterTrait | None = field(default=MasterTrait.VISIONS_OF_GRANDEUR, init=True)
    gem_power: dict[Gem, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_6r__1_set}, init=True)


@dataclass(kw_only=True)
class ElarionSetup10b6r6p(ElarionSetup):
    """Alternative build to consensus:

    - replace gem + set setup to 10b6r6p
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[HeroicTrait] | None = field(
        default_factory=lambda: [
            HeroicTrait.WILLFUL_MOMENTUM,
            HeroicTrait.INSPIRED_ALLEGIANCE,
        ],
        init=True,
    )
    sets: list[SetEffectName] | None = field(
        default_factory=lambda: [],
        init=True,
    )
    num_sets: int | None = field(default=0, init=True)

    talents: Sequence[ElarionTalent] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: Legendary | None = field(default=Legendary.NECK, init=True)
    weapon_ability: Weapon | None = field(default=Weapon.VOIDBRINGERS_TOUCH, init=True)
    master_trait: MasterTrait | None = field(default=MasterTrait.VISIONS_OF_GRANDEUR, init=True)
    gem_power: dict[Gem, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_6r_6p__0_set}, init=True)


@dataclass(kw_only=True)
class ElarionSetupAngryMultiplierStack(ElarionSetup):
    """Alternative build to consensus:

    - 2 set setup: Drakheim + Torment
    - 10b 4w 1r

    The objective is to stack main stat modifiers.
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[HeroicTrait] | None = field(
        default_factory=lambda: [
            HeroicTrait.WILLFUL_MOMENTUM,
            HeroicTrait.INSPIRED_ALLEGIANCE,
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

    talents: Sequence[ElarionTalent] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: Legendary | None = field(default=Legendary.NECK, init=True)
    weapon_ability: Weapon | None = field(default=Weapon.VOIDBRINGERS_TOUCH, init=True)
    master_trait: MasterTrait | None = field(default=MasterTrait.VISIONS_OF_GRANDEUR, init=True)
    gem_power: dict[Gem, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_4w_1r__2_set}, init=True)


@dataclass(kw_only=True)
class ElarionSetupAngryThreeSet(ElarionSetup):
    """Alternative build to consensus:

    - 3 set setup: Drakheim + Torment + execute
    - 10b

    The objective is to stack main stat modifiers.
    """

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[HeroicTrait] | None = field(
        default_factory=lambda: [
            HeroicTrait.WILLFUL_MOMENTUM,
            HeroicTrait.INSPIRED_ALLEGIANCE,
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

    talents: Sequence[ElarionTalent] | None = field(default_factory=lambda: BASIC_BARRAGE_BUILD, init=True)
    legendary: Legendary | None = field(default=Legendary.NECK, init=True)
    weapon_ability: Weapon | None = field(default=Weapon.VOIDBRINGERS_TOUCH, init=True)
    master_trait: MasterTrait | None = field(default=MasterTrait.VISIONS_OF_GRANDEUR, init=True)
    gem_power: dict[Gem, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b__3_set}, init=True)


@dataclass(kw_only=True)
class ElarionShimmer(ElarionSetup):
    """HWA build attempt."""

    raw_stats: RawStats

    high_hp_uptime: float | None = field(default=None, init=True)

    heroic_traits: list[HeroicTrait] | None = field(
        default_factory=lambda: [
            HeroicTrait.KINDLING,
            HeroicTrait.INSPIRED_ALLEGIANCE,
        ],
        init=True,
    )
    sets: list[SetEffectName] | None = field(
        default_factory=lambda: [],
        init=True,
    )
    num_sets: int | None = field(default=0, init=True)

    talents: list[ElarionTalent] | None = field(default_factory=lambda: BASIC_HWA_BUILD, init=True)
    legendary: Legendary | None = field(default=Legendary.CLOAK, init=True)
    weapon_ability: Weapon | None = field(default=Weapon.VOIDBRINGERS_TOUCH, init=True)
    master_trait: MasterTrait | None = field(default=MasterTrait.VISIONS_OF_GRANDEUR, init=True)
    gem_power: dict[Gem, int] | None = field(default_factory=lambda: {**GEM_BUILD_10b_6r_6p__0_set}, init=True)
