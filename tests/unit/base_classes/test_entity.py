# Unit tests for base_classes/entity.py

import pytest

from fellowship_sim.base_classes import Enemy, State, base_config
from tests.conftest import FixedRNG

_T = 100.0
_THRESHOLD = base_config.LOW_HEALTH_THRESHOLD


def _make_enemy(execute_damage_increase: float) -> tuple[State, Enemy]:
    state = State(rng=FixedRNG())
    enemy = Enemy(state=state, time_to_live=_T, execute_damage_increase=execute_damage_increase)
    return state, enemy


class TestEnemyExecuteHpRate:
    """Enemy percent_hp decreases linearly in both phases; total fight duration = time_to_live."""

    @pytest.mark.parametrize("e", [0.0, 0.2, 0.5])
    def test_hp_at_execute_threshold_crossing(self, e: float) -> None:
        """HP equals LOW_HEALTH_THRESHOLD exactly when the normal phase ends."""
        state, enemy = _make_enemy(e)

        r1 = ((1 - _THRESHOLD) + _THRESHOLD / (1 + e)) / _T
        t_execute = (1 - _THRESHOLD) / r1

        state.advance_time(t_execute)

        assert enemy.percent_hp == pytest.approx(_THRESHOLD, abs=1e-9)

    @pytest.mark.parametrize("e", [0.0, 0.2, 0.5])
    def test_normal_phase_is_linear(self, e: float) -> None:
        """HP decreases at constant rate r1 throughout the normal phase."""
        state, enemy = _make_enemy(e)

        r1 = ((1 - _THRESHOLD) + _THRESHOLD / (1 + e)) / _T
        t_execute = (1 - _THRESHOLD) / r1

        steps = 5
        dt = t_execute / steps
        for i in range(1, steps + 1):
            state.advance_time(dt)
            expected = 1.0 - i * dt * r1
            assert enemy.percent_hp == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("e", [0.0, 0.2, 0.5])
    def test_execute_phase_is_linear(self, e: float) -> None:
        """HP decreases at constant rate r2 = r1*(1+e) throughout the execute phase.

        Note: the tick exactly at the threshold boundary has an ambiguous rate (floating-point
        rounding may leave percent_hp just above 0.30, causing one tick to use the normal
        rate). We therefore skip one step past the boundary and use the actual HP there as the
        reference point, then verify that all subsequent steps use r2.
        """
        state, enemy = _make_enemy(e)

        r1 = ((1 - _THRESHOLD) + _THRESHOLD / (1 + e)) / _T
        r2 = r1 * (1 + e)
        t_execute = (1 - _THRESHOLD) / r1
        execute_duration = _T - t_execute

        state.advance_time(t_execute)

        # Skip the ambiguous boundary tick; either rate may be used here.
        skip_dt = execute_duration / 10
        state.advance_time(skip_dt)
        hp_ref = enemy.percent_hp
        assert hp_ref < _THRESHOLD  # confirmed below threshold

        # All subsequent steps must use the execute rate.
        steps = 4
        dt = (execute_duration - skip_dt) / (steps + 2)
        for i in range(1, steps + 1):
            state.advance_time(dt)
            expected = hp_ref - i * dt * r2
            assert enemy.percent_hp == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("e", [0.0, 0.2, 0.5])
    def test_execute_phase_is_faster_than_normal(self, e: float) -> None:
        """Execute phase rate is exactly (1+e) times the normal phase rate."""
        _, enemy = _make_enemy(e)

        assert enemy._execute_hp_rate == pytest.approx(enemy._normal_hp_rate * (1 + e), rel=1e-9)

    @pytest.mark.parametrize("e", [0.0, 0.2, 0.5])
    def test_zero_execute_bonus_gives_uniform_rate(self, e: float) -> None:
        """With e=0 both rates are 1/T; with e>0 execute is faster and normal is slower."""
        _, enemy = _make_enemy(e)

        if e == 0.0:
            assert enemy._normal_hp_rate == pytest.approx(1.0 / _T, rel=1e-9)
            assert enemy._execute_hp_rate == pytest.approx(1.0 / _T, rel=1e-9)
        else:
            assert enemy._execute_hp_rate > enemy._normal_hp_rate
            assert enemy._normal_hp_rate < 1.0 / _T
