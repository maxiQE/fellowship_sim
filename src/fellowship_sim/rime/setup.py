from dataclasses import dataclass, field

from fellowship_sim.base_classes import HeroicTrait, Legendary, MasterTrait, State, Weapon
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.generic_game_logic.setup_effect import PlayerSetup, SetupEffect

from .entity import Rime
from .setup_effects import (
    RimeDefaultEffectSetup,
    RimeLegendarySelection,
    RimeTalent,
    RimeTalentSelection,
)


@dataclass(kw_only=True)
class RimeSetup(PlayerSetup["Rime"]):
    """Builds a fully wired Rime character ready for simulation."""

    initial_winter_orbs: int = 0

    legendary: Legendary | None = None
    talents: list[RimeTalent] | None = None

    valid_weapon_abilities: frozenset[Weapon] = field(
        default_factory=lambda: frozenset(Weapon), init=False
    )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()

    def _character_default_setup_effects(self) -> list[SetupEffect[Player]]:
        return [RimeDefaultEffectSetup()]

    def _character_pre_generic_setup_effects(self) -> list[SetupEffect[Player]]:
        effects: list[SetupEffect[Player]] = []
        if self.talents is not None:
            effects.append(RimeTalentSelection(talents=self.talents, total_talent_points=self.total_talent_points))
        if self.legendary is not None:
            effects.append(RimeLegendarySelection(selected_legendary=self.legendary))
        return effects

    def _create_character(self, state: State) -> Rime:
        rime = Rime(state=state, raw_stats=self.raw_stats)
        rime.winter_orbs = self.initial_winter_orbs
        return rime


def create_rime(
    state: State,
    raw_stats: RawStats,
    initial_spirit_points: float = 100,
    weapon_ability: Weapon | None = None,
    master_trait: MasterTrait | None = None,
    master_trait_level: int = 4,
    heroic_traits: list[HeroicTrait] | None = None,
    legendary: Legendary | None = None,
    talents: list[RimeTalent] | None = None,
) -> Rime:
    """One-shot factory: build a simulation-ready Rime from stats."""
    return RimeSetup(
        raw_stats=raw_stats,
        initial_spirit_points=initial_spirit_points,
        weapon_ability=weapon_ability,
        master_trait=master_trait,
        master_trait_level=master_trait_level,
        heroic_traits=heroic_traits,
        legendary=legendary,
        talents=talents,
    ).finalize(state=state)
