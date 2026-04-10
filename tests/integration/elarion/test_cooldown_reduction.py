"""Integration tests — CDR sources.

SkylitGrace: each active VolleyEffect adds +1.0 CDA to SkystriderGrace's CDR.
  CDR multiplier = 1 + number_of_active_volleys
  SkystriderGrace.base_cooldown = 120s; with CDR=2, cooldown ticks at 2× normal rate.

SkywardMunitions: CelestialShot or Multishot cast → HWA CD -1s, Barrage CD -1s.

RepeatingStars: each Multishot damage hit → Volley CD -0.3s.
  With N enemies: N hits → Volley CD -N×0.3s.
"""

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.effect import (
    RepeatingStars,
    SkywardMunitions,
    VolleyEffect,
)
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup_effect import SkylitGraceSetup
from tests.integration.fixtures import FixedRNG


class TestSkylitGrace:
    """Each active VolleyEffect increases SkystriderGrace CDR by 1.0."""

    def test_one_volley_doubles_skystrider_grace_cdr(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """With 1 active VolleyEffect, SkystriderGrace CDR multiplier = 2.0.
        Advancing time by 1s ticks SkystriderGrace CD by 2.0s (instead of 1.0s).
        """
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        SkylitGraceSetup().apply(elarion, None)  # ty:ignore[invalid-argument-type]

        elarion.skystrider_grace.cooldown = 120.0
        elarion.skystrider_grace.charges = 0

        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.0)  # process first tick without exhausting full Volley duration

        assert len(VolleyEffect.get_volley(state.enemies[0])) == 1

        cd_before = elarion.skystrider_grace.cooldown
        state.advance_time(1.0)
        cd_reduction = cd_before - elarion.skystrider_grace.cooldown

        assert cd_reduction == pytest.approx(2.0, abs=0.01)

    def test_two_volleys_triple_skystrider_grace_cdr(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """With 2 simultaneous VolleyEffects, CDR multiplier = 3.0 → ticks by 3.0s per second."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        SkylitGraceSetup().apply(elarion, None)  # ty:ignore[invalid-argument-type]

        elarion.skystrider_grace.cooldown = 120.0
        elarion.skystrider_grace.charges = 0

        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.0)
        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.0)

        assert len(VolleyEffect.get_volley(state.enemies[0])) == 2

        assert elarion.skystrider_grace._tick

        assert elarion.skystrider_grace._cdr_multiplier == pytest.approx(3.0)

    def test_cdr_returns_to_one_after_volley_expires(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """After all VolleyEffects expire, SkystriderGrace CDR returns to 1.0."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        SkylitGraceSetup().apply(elarion, None)  # ty:ignore[invalid-argument-type]

        elarion.skystrider_grace.cooldown = 120.0
        elarion.skystrider_grace.charges = 0

        elarion.volley._do_cast(state.enemies[0])

        assert elarion.skystrider_grace._cdr_multiplier == pytest.approx(2.0)

        state.advance_time(9.0)  # Volley fully expired (duration = 8.0+1e-9)

        assert len(VolleyEffect.get_volley(state.enemies[0])) == 0

        assert elarion.skystrider_grace._cdr_multiplier == pytest.approx(1.0)


class TestSkywardMunitions:
    """CelestialShot and Multishot each reduce HWA CD and Barrage CD by 1s."""

    @pytest.fixture
    def setup(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> tuple[State, Elarion]:
        elarion = unit_elarion__zero_stats
        elarion.effects.add(SkywardMunitions(owner=elarion))
        elarion.highwind_arrow.cooldown = 15.0
        elarion.highwind_arrow.charges = 0
        elarion.heartseeker_barrage.cooldown = 20.0
        elarion.heartseeker_barrage.charges = 0
        return state_no_procs__st, elarion

    def test_celestial_shot_reduces_hwa_cd(self, setup: tuple[State, Elarion]) -> None:
        """CelestialShot cast reduces HWA cooldown by 1s."""
        state, elarion = setup
        hwa_cd_before = elarion.highwind_arrow.cooldown

        elarion.celestial_shot._do_cast(state.enemies[0])
        state.advance_time(0.0)

        assert elarion.highwind_arrow.cooldown == pytest.approx(hwa_cd_before - 1.0)

    def test_celestial_shot_reduces_barrage_cd(self, setup: tuple[State, Elarion]) -> None:
        """CelestialShot cast reduces HeartseekerBarrage cooldown by 1s."""
        state, elarion = setup
        barrage_cd_before = elarion.heartseeker_barrage.cooldown

        elarion.celestial_shot._do_cast(state.enemies[0])
        state.advance_time(0.0)

        assert elarion.heartseeker_barrage.cooldown == pytest.approx(barrage_cd_before - 1.0)

    def test_multishot_reduces_hwa_and_barrage_cd(self, setup: tuple[State, Elarion]) -> None:
        """Multishot cast reduces both HWA and Barrage cooldown by 1s each."""
        state, elarion = setup
        elarion.multishot.charges = 1
        hwa_cd_before = elarion.highwind_arrow.cooldown
        barrage_cd_before = elarion.heartseeker_barrage.cooldown

        elarion.multishot._do_cast(state.enemies[0])
        state.advance_time(0.0)

        assert elarion.highwind_arrow.cooldown == pytest.approx(hwa_cd_before - 1.0)
        assert elarion.heartseeker_barrage.cooldown == pytest.approx(barrage_cd_before - 1.0)


class TestRepeatingStars:
    """Each Multishot damage hit reduces Volley CD by 0.3s; N enemies → N×0.3s reduction."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3])
    def test_reduces_volley_cd_per_hit(self, num_enemies: int) -> None:
        """N enemies hit → Volley CD reduced by N×0.3s."""
        enemies = [Enemy() for _ in range(num_enemies)]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion

        elarion.effects.add(RepeatingStars(owner=elarion))
        elarion.multishot.charges = 1
        elarion.volley.cooldown = 30.0
        elarion.volley.charges = 0
        volley_cd_before = elarion.volley.cooldown

        elarion.multishot._do_cast(enemies[0])
        elarion.wait(0.2)

        # With num_enemies enemies: 1 main + min(num_enemies-1, 11) secondary hits
        expected_hits = num_enemies  # all hit
        expected_cdr = expected_hits * 0.3

        assert elarion.volley.cooldown == pytest.approx(volley_cd_before - expected_cdr - 0.2, abs=0.001)
