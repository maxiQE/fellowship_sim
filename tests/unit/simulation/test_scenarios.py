# Unit tests for simulation/scenarios.py

import pytest

from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.scenarios import (
    boss_fight_scenario,
    generate_new_scenario,
    multiple_identical_packs_scenario,
)

_SETUP = ElarionSetup(
    raw_stats=RawStatsFromPercents(
        main_stat=1000.0,
        crit_percent=0.15,
    ),
    talents=[
        # "Piercing Seekers",
        "Fusillade",
        "Lunar Fury",
        "Lunarlight Affinity",
        "Fervent Supremacy",
        "Impending Heartseeker",
        "Last Lights",
    ],
    sets=["Death's Grasp"],
    gem_power={
        "purple__amethyst": 1458,  # purple 6
    },
)


class TestScenarioGeneration:
    """Scenario.generate_new_scenario assembles the State and Elarion from Scenario parameters.

    Covers: enemy count, enemy TTL, initial spirit points, bonus spirit per second,
    state information fields (duration, is_boss_fight, delay_since_last_fight, is_ult_authorized),
    and the optional finalize_character hook.
    """

    def test_boss_fight_creates_single_enemy(self) -> None:
        """boss_fight_scenario produces exactly one enemy."""
        scenario = boss_fight_scenario(
            duration=60.0,
            delay_since_last_fight=15.0,
        )
        state, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        assert len(state.enemies) == 1

    def test_trash_aoe_fight_creates_correct_enemy_count(self) -> None:
        """multiple_identical_packs_scenario produces num_enemies enemies in total."""
        scenario = multiple_identical_packs_scenario(
            pack_duration=60.0,
            num_big=1,
            num_medium=2,
            num_small=2,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        assert len(state.enemies) == 5

    def test_enemies_have_time_to_live_equal_to_duration(self) -> None:
        """Every enemy created by boss_fight_scenario has time_to_live == scenario.duration."""
        scenario = boss_fight_scenario(
            duration=90.0,
            delay_since_last_fight=15.0,
        )
        state, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        for enemy in state.enemies:
            assert enemy.time_to_live == 90.0

    def test_initial_spirit_points_set(self) -> None:
        """Elarion starts the fight with spirit_points == scenario.initial_spirit_points."""
        scenario = boss_fight_scenario(
            duration=60.0,
            delay_since_last_fight=15.0,
            initial_spirit_points=80.0,
        )
        _, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        assert elarion.spirit_points == pytest.approx(80.0)

    def test_state_information_matches_scenario(self) -> None:
        """state.information reflects is_boss_fight, duration, delay_since_last_fight, is_ult_authorized."""
        scenario = boss_fight_scenario(
            duration=120.0,
            delay_since_last_fight=30.0,
        )
        state, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        assert state.main_target.is_boss is True
        assert state.information.delay_since_last_fight == pytest.approx(30.0)
        assert state.information.is_ult_authorized is True

    def test_finalize_character_hook_is_called(self) -> None:
        """When finalize_character is set, it is called exactly once with the Elarion instance."""
        called: list[object] = []
        scenario = boss_fight_scenario(
            duration=60.0,
            delay_since_last_fight=15.0,
            finalize_character=lambda elarion: called.append(elarion),
        )
        _, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        assert len(called) == 1
        assert called[0] is elarion

    @pytest.mark.parametrize("seed", [0, 1, 42, 999])
    def test_same_seed_produces_identical_rng_state(self, seed: int) -> None:
        """Two generate_new_scenario calls with the same seed leave the RNG in an identical state."""
        scenario = boss_fight_scenario(
            duration=60.0,
            delay_since_last_fight=15.0,
        )
        state_a, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=seed)
        next_a = state_a.rng.random()

        state_b, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=seed)
        next_b = state_b.rng.random()

        assert next_a == next_b

    def test_trash_aoe_medium_enemies_have_correct_ttl(self) -> None:
        """Medium enemies have time_to_live == pack_duration * 0.75 (default ratio)."""
        scenario = multiple_identical_packs_scenario(
            pack_duration=100.0,
            num_big=1,
            num_medium=1,
            num_small=1,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        # enemies are ordered: 1 big, 1 medium, 1 small
        assert state.enemies[1].time_to_live == pytest.approx(75.0)

    def test_trash_aoe_small_enemies_have_correct_ttl(self) -> None:
        """Small enemies have time_to_live == pack_duration * 0.50 (default ratio)."""
        scenario = multiple_identical_packs_scenario(
            pack_duration=100.0,
            num_big=1,
            num_medium=1,
            num_small=1,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, _ = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        # enemies are ordered: 1 big, 1 medium, 1 small
        assert state.enemies[2].time_to_live == pytest.approx(50.0)

    def test_enemy_hp_decreases_correctly_after_waiting(self) -> None:
        """After 25s on a 100s fight: big=75%, medium=66.67%, small=50% HP remaining.

        Enemy percent_hp decreases linearly at rate 1/time_to_live per second.
        Default health ratios: big=1.0, medium=0.75, small=0.50.
        """
        scenario = multiple_identical_packs_scenario(
            pack_duration=100.0,
            num_big=1,
            num_medium=1,
            num_small=1,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=0)
        big, medium, small = state.enemies

        elarion.wait(25.0)

        assert big.percent_hp == pytest.approx(0.75)
        assert medium.percent_hp == pytest.approx(2 / 3)
        assert small.percent_hp == pytest.approx(0.50)
