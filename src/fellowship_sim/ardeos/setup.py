from dataclasses import dataclass, field

from fellowship_sim.base_classes import HeroicTrait, Legendary, MasterTrait, State, Weapon
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.generic_game_logic.setup_effect import PlayerSetup, SetupEffect

from .entity import Ardeos
from .setup_effects import (
    ArdeosDefaultEffectSetup,
    ArdeosLegendarySelection,
    ArdeosTalent,
    ArdeosTalentSelection,
)


@dataclass(kw_only=True)
class ArdeosSetup(PlayerSetup["Ardeos"]):
    initial_embers: int = 0

    legendary: Legendary | None = None
    talents: list[ArdeosTalent] | None = None

    valid_weapon_abilities: frozenset[Weapon] = field(
        default_factory=lambda: frozenset(Weapon), init=False
    )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()

    def _character_default_setup_effects(self) -> list[SetupEffect[Player]]:
        return [ArdeosDefaultEffectSetup()]

    def _character_pre_generic_setup_effects(self) -> list[SetupEffect[Player]]:
        effects: list[SetupEffect[Player]] = []
        if self.talents is not None:
            effects.append(ArdeosTalentSelection(talents=self.talents, total_talent_points=self.total_talent_points))
        if self.legendary is not None:
            effects.append(ArdeosLegendarySelection(selected_legendary=self.legendary))
        return effects

    def _create_character(self, state: State) -> Ardeos:
        ardeos = Ardeos(state=state, raw_stats=self.raw_stats)
        ardeos.embers = self.initial_embers
        return ardeos


def create_ardeos(
    state: State,
    raw_stats: RawStats,
    initial_spirit_points: float = 100,
    initial_embers: int = 0,
    weapon_ability: Weapon | None = None,
    master_trait: MasterTrait | None = None,
    master_trait_level: int = 4,
    heroic_traits: list[HeroicTrait] | None = None,
    legendary: Legendary | None = None,
    talents: list[ArdeosTalent] | None = None,
) -> Ardeos:
    return ArdeosSetup(
        raw_stats=raw_stats,
        initial_spirit_points=initial_spirit_points,
        initial_embers=initial_embers,
        weapon_ability=weapon_ability,
        master_trait=master_trait,
        master_trait_level=master_trait_level,
        heroic_traits=heroic_traits,
        legendary=legendary,
        talents=talents,
    ).finalize(state=state)
