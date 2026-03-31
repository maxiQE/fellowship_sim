"""Integration tests — focus spend, gain, regen.

FocusAura subscribes to AbilityCastSuccess (fired inside _do_cast) and handles
focus spending (deducts cost), focus gain (adds amount), and emits ResourceSpent.
FocusAura must be added explicitly to a bare Elarion.

Focus regen is handled by Elarion._tick(dt) called by State._tick during advance_time.
"""

from collections.abc import Callable

import pytest

from fellowship_sim.base_classes import State
from fellowship_sim.elarion.buff import (
    FerventSupremacyBuff,
    SkystriderSupremacyBuff,
)
from fellowship_sim.elarion.entity import Elarion


class TestFocusCost:
    """Check focus update during _pay_cost_for_cast() step of casting."""

    def test_celestial_shot_costs_15_focus(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """CelestialShot costs 15 focus."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        focus_before = elarion.focus

        elarion.celestial_shot._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 15)

    def test_multishot_standard_costs_20_focus(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """Standard Multishot costs 20 focus."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.multishot.charges = 1
        focus_before = elarion.focus

        elarion.multishot._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 20)

    def test_multishot_empowered_with_fervent_costs_10_focus(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """FerventSupremacyBuff empowers Multishot → focus cost halved (ceil(20 * 0.5) = 10)."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.effects.add(FerventSupremacyBuff(owner=elarion))
        focus_before = elarion.focus

        elarion.multishot._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 10)

    def test_multishot_empowered_with_skystrider_costs_10_focus(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """SkystriderSupremacyBuff empowers Multishot → focus cost halved."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.effects.add(SkystriderSupremacyBuff(owner=elarion))
        focus_before = elarion.focus

        elarion.multishot._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 10)

    def test_heartseeker_barrage_costs_30_focus(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """HeartseekerBarrage costs 30 focus."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        focus_before = elarion.focus

        elarion.heartseeker_barrage._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 30)

    def test_volley_costs_30_focus(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """Volley costs 30 focus."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        focus_before = elarion.focus

        elarion.volley._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 30)


class TestFocusGain:
    """FocusAura credits focus grants from abilities."""

    def test_focused_shot_gains_20_focus(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """FocusedShot grants +20 focus."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.focus = 50.0
        focus_before = elarion.focus

        elarion.focused_shot._pay_cost_for_cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before + 20)


class TestFocusRegen:
    """Focus regenerates over time scaled by haste."""

    @pytest.mark.parametrize(
        "haste,dt",
        [
            (0.0, 5.0),
            (0.5, 5.0),
            (0.0, 10.0),
            (0.5, 10.0),
        ],
    )
    def test_focus_regen_rate(
        self,
        state_no_procs__st: State,
        setup_hasted_elarion: Callable[..., Elarion],
        haste: float,
        dt: float,
    ) -> None:
        """Focus regen = focus_regen_rate * (1 + haste) * dt."""
        elarion = setup_hasted_elarion(haste=haste)
        elarion.focus = 0.0

        state_no_procs__st.advance_time(dt)

        expected_gain = elarion.focus_regen_rate * (1 + haste) * dt
        assert elarion.focus == pytest.approx(expected_gain, rel=1e-6)


class TestFocusClipping:
    """Focus is capped at max_focus."""

    def test_focus_does_not_exceed_max_focus(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """FocusedShot gain clipped at max_focus when starting near cap."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.focus = 90.0

        elarion.focused_shot._pay_cost_for_cast(state.enemies[0])  # +20 focus, would go to 110

        assert elarion.focus == pytest.approx(elarion.max_focus)

    def test_focus_spending_does_not_go_negative(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """Mistakenly trying to go beneath 0 raises ValueError."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.focus = 5.0

        with pytest.raises(ValueError):
            elarion.celestial_shot._pay_cost_for_cast(state.enemies[0])

    def test_focus_regen_clips_at_max_focus(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """Focus regen stops at max_focus (100)."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.focus = 95.0

        state.advance_time(10.0)  # would regen far past max_focus

        assert elarion.focus == pytest.approx(elarion.max_focus)
