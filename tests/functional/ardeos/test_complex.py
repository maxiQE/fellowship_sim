import math

from fellowship_sim.ardeos.effect import SearingBlazeDoT
from fellowship_sim.ardeos.entity import Ardeos
from fellowship_sim.base_classes import AbilityPeriodicDamage, State
from tests.conftest import SequenceRNG


class TestBlazeSpam:
    """Spamming Searing Blaze on a single target results in weird behavior."""

    def test_searing_blaze_spam__no_agonizing_blaze(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Spamming untalented searing blaze causes no damage and gains no cinders and embers."""
        num_casts = 60
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, SearingBlazeDoT) else None,
        )

        assert ardeos.cinders == 0
        assert ardeos.embers == 0

        for _ in range(num_casts):
            ardeos.searing_blaze.cast(state.main_target)

        assert len(hits) == 0
        assert ardeos.cinders == 0
        assert ardeos.embers == 0

    def test_searing_blaze_spam__with_agonizing_blaze(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Spamming agonizing searing blaze causes damage and gains cinders and embers."""
        num_casts = 60

        ardeos.searing_blaze.is_agonizing_blaze = True

        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, SearingBlazeDoT) else None,
        )

        assert ardeos.cinders == 0
        assert ardeos.embers == 0

        for _ in range(num_casts):
            ardeos.searing_blaze.cast(state.main_target)
            dot = state.main_target.effects.get(SearingBlazeDoT)
            assert dot is not None
            assert dot.agonizing_blaze_stacks == min(10, 1 + len(hits))

        assert len(hits) == math.floor(state.time / 2 * (1 + ardeos.stats.haste_percent))
        assert ardeos.cinders == math.floor(state.time / 2 * 1) % 100
        assert ardeos.embers == math.floor(state.time / 2 * 1) // 100
