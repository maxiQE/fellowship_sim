# Unit tests for simulation/scenarios.py

import pytest

from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.scenarios import BossFightScenario, TrashAOEFightScenario

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
        """BossFightScenario produces exactly one enemy."""
        scenario = BossFightScenario(
            duration=60.0,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
        )
        state, _ = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        assert len(state.enemies) == 1

    def test_trash_aoe_fight_creates_correct_enemy_count(self) -> None:
        """TrashAOEFightScenario produces num_enemies enemies in total."""
        scenario = TrashAOEFightScenario(
            pack_duration=60.0,
            num_enemies=5,
            num_enemies_medium=2,
            num_enemies_small=2,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, _ = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        assert len(state.enemies) == 5

    def test_enemies_have_time_to_live_equal_to_duration(self) -> None:
        """Every enemy created by BossFightScenario has time_to_live == scenario.duration."""
        scenario = BossFightScenario(
            duration=90.0,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
        )
        state, _ = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        for enemy in state.enemies:
            assert enemy.time_to_live == 90.0

    def test_initial_spirit_points_set(self) -> None:
        """Elarion starts the fight with spirit_points == scenario.initial_spirit_points."""
        scenario = BossFightScenario(
            duration=60.0,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
            initial_spirit_points=80.0,
        )
        _, elarion = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        assert elarion.spirit_points == pytest.approx(80.0)

    def test_bonus_spirit_per_s_set(self) -> None:
        """Elarion's passive spirit regen rate matches scenario.bonus_spirit_point_per_s."""
        scenario = BossFightScenario(
            duration=60.0,
            bonus_spirit_point_per_s=1.2,
            delay_since_last_fight=15.0,
        )
        _, elarion = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        assert elarion.spirit_point_per_s == pytest.approx(1.2)

    def test_state_information_matches_scenario(self) -> None:
        """state.information reflects is_boss_fight, duration, delay_since_last_fight, is_ult_authorized."""
        scenario = BossFightScenario(
            duration=120.0,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=30.0,
        )
        state, _ = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        assert state.information.is_boss_fight is True
        assert state.information.duration == pytest.approx(120.0)
        assert state.information.delay_since_last_fight == pytest.approx(30.0)
        assert state.information.is_ult_authorized is True

    def test_finalize_character_hook_is_called(self) -> None:
        """When finalize_character is set, it is called exactly once with the Elarion instance."""
        called: list[object] = []
        scenario = BossFightScenario(
            duration=60.0,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
            finalize_character=lambda elarion: called.append(elarion),
        )
        _, elarion = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        assert len(called) == 1
        assert called[0] is elarion

    @pytest.mark.parametrize("seed", [0, 1, 42, 999])
    def test_same_seed_produces_identical_rng_state(self, seed: int) -> None:
        """Two generate_new_scenario calls with the same seed leave the RNG in an identical state."""
        scenario = BossFightScenario(
            duration=60.0,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
        )
        state_a, _ = scenario.generate_new_scenario(_SETUP, rng_seed=seed)
        next_a = state_a.rng.random()

        state_b, _ = scenario.generate_new_scenario(_SETUP, rng_seed=seed)
        next_b = state_b.rng.random()

        assert next_a == next_b

    def test_trash_aoe_medium_enemies_have_correct_ttl(self) -> None:
        """Medium enemies have time_to_live == duration * 0.75 (default health ratio)."""
        scenario = TrashAOEFightScenario(
            pack_duration=100.0,
            num_enemies=3,
            num_enemies_medium=1,
            num_enemies_small=1,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, _ = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        # enemies are ordered: 1 big, 1 medium, 1 small
        assert state.enemies[1].time_to_live == pytest.approx(75.0)

    def test_trash_aoe_small_enemies_have_correct_ttl(self) -> None:
        """Small enemies have time_to_live == duration * 0.50 (default health ratio)."""
        scenario = TrashAOEFightScenario(
            pack_duration=100.0,
            num_enemies=3,
            num_enemies_medium=1,
            num_enemies_small=1,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, _ = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        # enemies are ordered: 1 big, 1 medium, 1 small
        assert state.enemies[2].time_to_live == pytest.approx(50.0)

    def test_enemy_hp_decreases_correctly_after_waiting(self) -> None:
        """After 25s on a 100s fight: big=75%, medium=66.67%, small=50% HP remaining.

        Enemy percent_hp decreases linearly at rate 1/time_to_live per second.
        Default health ratios: big=1.0, medium=0.75, small=0.50.
        """
        scenario = TrashAOEFightScenario(
            pack_duration=100.0,
            num_enemies=3,
            num_enemies_medium=1,
            num_enemies_small=1,
            bonus_spirit_point_per_s=0.5,
            delay_since_last_fight=15.0,
            initial_spirit_points=0.0,
        )
        state, elarion = scenario.generate_new_scenario(_SETUP, rng_seed=0)
        big, medium, small = state.enemies

        elarion.wait(25.0)

        assert big.percent_hp == pytest.approx(0.75)
        assert medium.percent_hp == pytest.approx(2 / 3)
        assert small.percent_hp == pytest.approx(0.50)
