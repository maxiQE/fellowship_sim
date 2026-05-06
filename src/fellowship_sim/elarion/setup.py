from collections.abc import Sequence
from dataclasses import dataclass, field

from fellowship_sim.base_classes import HeroicTrait, Legendary, MasterTrait, State, Weapon
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.generic_game_logic.setup_effect import PlayerSetup, SetupEffect

from .entity import Elarion
from .setup_effect import (
    ElarionDefaultEffectSetup,
    ElarionLegendarySelection,
    ElarionTalent,
    ElarionTalentSelection,
)


@dataclass(kw_only=True)
class ElarionSetup(PlayerSetup["Elarion"]):
    """Builds a fully wired Elarion character ready for simulation."""

    initial_focus: float = 100
    legendary: Legendary | None = None
    talents: Sequence[ElarionTalent] | None = None

    valid_weapon_abilities: frozenset[Weapon] = field(
        default_factory=lambda: frozenset(Weapon), init=False
    )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()

    def _character_default_setup_effects(self) -> list[SetupEffect[Player]]:
        return [ElarionDefaultEffectSetup()]

    def _character_pre_generic_setup_effects(self) -> list[SetupEffect[Player]]:
        effects: list[SetupEffect[Player]] = []
        if self.talents is not None:
            effects.append(ElarionTalentSelection(talents=self.talents, total_talent_points=self.total_talent_points))
        if self.legendary is not None:
            effects.append(ElarionLegendarySelection(selected_legendary=self.legendary))
        return effects

    def _create_character(self, state: State) -> Elarion:
        return Elarion(state=state, raw_stats=self.raw_stats, focus=self.initial_focus)


def create_elarion(
    state: State,
    raw_stats: RawStats,
    initial_focus: float = 100,
    initial_spirit_points: float = 100,
    weapon_ability: Weapon | None = None,
    legendary: Legendary | None = None,
    master_trait: MasterTrait | None = None,
    master_trait_level: int = 4,
    heroic_traits: list[HeroicTrait] | None = None,
    talents: Sequence[ElarionTalent] | None = None,
) -> Elarion:
    """One-shot factory: build a simulation-ready Elarion from stats."""
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
    ).finalize(state=state)
