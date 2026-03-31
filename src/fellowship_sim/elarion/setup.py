from dataclasses import dataclass, field
from typing import Literal, get_args

from fellowship_sim.base_classes import SetupContext, SetupEffect, State
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.generic_game_logic.set_effects import SetEffectName
from fellowship_sim.generic_game_logic.setup_effect import (
    GEM_COLORS,
    DefaultEffectSetup,
    GemSetupEffect,
    SetEffectSelection,
    WeaponHeroicTraitSelection,
    WeaponMasterTraitSelection,
)
from fellowship_sim.generic_game_logic.weapon_abilities import WeaponAbilitySetupEffectDict, WeaponName
from fellowship_sim.generic_game_logic.weapon_traits import (
    WeaponHeroicTraitName,
    WeaponMasterTraitName,
)

from .entity import Elarion
from .setup_effect import (
    ElarionDefaultEffectSetup,
    ElarionLegendarySelection,
    ElarionTalentName,
    ElarionTalentSelection,
)

ElarionLegendaryName = Literal["Boots", "Cloak", "Neck"]


@dataclass(kw_only=True)
class ElarionSetup:
    """Builds a fully wired Elarion character ready for simulation.

    Attaches the fixed ability list, optional weapon ability, optional legendary,
    and default permanent effects.
    Must be called after State(...).activate() so effects can subscribe to the bus.
    """

    raw_stats: RawStats
    initial_focus: float = 100
    initial_spirit_points: float = 100

    weapon_ability: WeaponName | None = None

    legendary: ElarionLegendaryName | None = None

    master_trait: WeaponMasterTraitName | None = None
    master_trait_level: int = 4

    heroic_traits: list[WeaponHeroicTraitName] | None = None
    heroic_trait_level: int = 4

    talents: list[ElarionTalentName] | None = None
    total_talent_points: int = 13

    sets: list[SetEffectName] | None = None

    gem_power: dict[GEM_COLORS, int] | None = None
    total_gem_power: int | None = None

    # List of numbers of sets to optimal gem power
    # num_slots = 11
    # t4 = 480
    # t3 = 360
    # 0-1 sets: all T3; 2 * t3 + (num_slots - 1 - 2 * num_set) * 1.35 * t3
    # 2 sets: T4 in +100%; all T3; 2 * t4 + (num_slots - 1 - 2 * num_set) * 1.35 * t3
    # 3 sets: T4 in +100%, T4 in +35%; rest T3; 2 * t4 + 1.35 * t4 + (num_slots - 2 - 2 * num_set) * 1.35 * t3
    # 4 sets: only 3 slots; 3 T4; 2 * t4 + 2 * 1.35 *
    total_gem_power_default: list[int] = field(default_factory=lambda: [5256, 4608, 3876, 2256], init=False)
    setup_effect_list: list[SetupEffect[Player]] = field(init=False)

    def __post_init__(self) -> None:
        num_sets = len(self.sets) if self.sets is not None else 0
        if self.total_gem_power is None:
            if num_sets >= len(self.total_gem_power_default):
                raise ValueError(  # noqa: TRY003
                    f"ElarionSetup configuration error: too many sets equipped ({num_sets} > 4); sets: {self.sets}"
                )
            resolved_gem_power = self.total_gem_power_default[num_sets]
        else:
            resolved_gem_power = self.total_gem_power

        try:
            self._validate_inputs()
            self.setup_effect_list = self._build_setup_effect_list(resolved_gem_power=resolved_gem_power)
        except ValueError as e:
            raise ValueError(f"ElarionSetup configuration error: {e}") from e  # noqa: TRY003

    def _validate_inputs(self) -> None:
        if self.weapon_ability is not None and self.weapon_ability not in get_args(WeaponName):
            raise ValueError(f"invalid weapon_ability {self.weapon_ability!r}; must be one of {get_args(WeaponName)}")  # noqa: TRY003
        if self.legendary is not None and self.legendary not in get_args(ElarionLegendaryName):
            raise ValueError(f"invalid legendary {self.legendary!r}; must be one of {get_args(ElarionLegendaryName)}")  # noqa: TRY003
        if self.master_trait is not None and self.master_trait not in get_args(WeaponMasterTraitName):
            raise ValueError(  # noqa: TRY003
                f"invalid master_trait {self.master_trait!r}; must be one of {get_args(WeaponMasterTraitName)}"
            )
        if self.heroic_traits is not None:
            invalid = [t for t in self.heroic_traits if t not in get_args(WeaponHeroicTraitName)]
            if invalid:
                raise ValueError(f"invalid heroic_traits {invalid!r}; must be one of {get_args(WeaponHeroicTraitName)}")  # noqa: TRY003
        if self.talents is not None:
            invalid_talents = [t for t in self.talents if t not in get_args(ElarionTalentName)]
            if invalid_talents:
                raise ValueError(f"invalid talents {invalid_talents!r}; must be one of {get_args(ElarionTalentName)}")  # noqa: TRY003
        if self.sets is not None:
            invalid_sets = [s for s in self.sets if s not in get_args(SetEffectName)]
            if invalid_sets:
                raise ValueError(f"invalid sets {invalid_sets!r}; must be one of {get_args(SetEffectName)}")  # noqa: TRY003

    def _build_setup_effect_list(self, *, resolved_gem_power: int) -> list[SetupEffect[Player]]:
        setup_effects: list[SetupEffect[Player]] = [
            DefaultEffectSetup(),
            ElarionDefaultEffectSetup(),
        ]
        if self.talents is not None:
            setup_effects.append(
                ElarionTalentSelection(talents=self.talents, total_talent_points=self.total_talent_points)
            )
        if self.legendary is not None:
            setup_effects.append(ElarionLegendarySelection(selected_legendary=self.legendary))
        if self.weapon_ability is not None:
            setup_effects.append(WeaponAbilitySetupEffectDict[self.weapon_ability]())
        if self.master_trait is not None:
            setup_effects.append(
                WeaponMasterTraitSelection(master_trait=self.master_trait, trait_level=self.master_trait_level)
            )
        if self.heroic_traits is not None:
            setup_effects.append(
                WeaponHeroicTraitSelection(heroic_traits=self.heroic_traits, trait_level=self.heroic_trait_level)
            )
        if self.gem_power is not None:
            setup_effects.append(GemSetupEffect(gem_power=self.gem_power, total_gem_power=resolved_gem_power))
        if self.sets is not None:
            setup_effects.append(SetEffectSelection(sets=self.sets))
        return setup_effects

    def finalize(self, state: State) -> Elarion:
        elarion = Elarion(raw_stats=self.raw_stats, focus=self.initial_focus)
        elarion.spirit_points = self.initial_spirit_points

        state.character = elarion

        context = SetupContext()
        for setup_effect in self.setup_effect_list:
            setup_effect.apply(elarion, context)

        elarion._recalculate_stats()

        return elarion


def create_elarion(
    state: State,
    raw_stats: RawStats,
    initial_focus: float = 100,
    initial_spirit_points: float = 100,
    weapon_ability: WeaponName | None = None,
    legendary: ElarionLegendaryName | None = None,
    master_trait: WeaponMasterTraitName | None = None,
    master_trait_level: int = 4,
    heroic_traits: list[WeaponHeroicTraitName] | None = None,
    talents: list[ElarionTalentName] | None = None,
    total_talent_points: int = 13,
) -> Elarion:
    """One-shot factory: build a simulation-ready Elarion from stats.

    Requires State(...).activate() to have been called first.

    Args:
        raw_stats:            Character stats (use RawStatsFromPercents or RawStatsFromScores).
        initial_focus:        Starting focus (default 100).
        weapon_ability:       Which weapon ability to equip, or None.
        legendary:            Which legendary item effect to apply, or None.
        master_trait:         Which weapon master trait to apply, or None.
        master_trait_level:   Trait level 1-4 (default 4).
        heroic_traits:        Up to 2 weapon heroic trait names to apply, or None.
        talents:              List of talent names to activate, or None.
        total_talent_points:  Budget for talent selection (default 13).
    """
    return ElarionSetup(
        raw_stats=raw_stats,
        initial_focus=initial_focus,
        initial_spirit_points=initial_spirit_points,
        weapon_ability=weapon_ability,
        legendary=legendary,
        master_trait=master_trait,
        master_trait_level=master_trait_level,
        heroic_traits=heroic_traits,
        talents=talents,
        total_talent_points=total_talent_points,
    ).finalize(
        state=state,
    )
