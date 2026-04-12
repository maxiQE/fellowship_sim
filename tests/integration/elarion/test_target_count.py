"""Integration tests — max targets per ability.

Hit count is collected by subscribing to AbilityDamage events.

NOTE: Volley secondary targets are NOT implemented in the current code
(Volley._do_cast only appends to the main target, despite num_secondary_targets=11).
Tests for Volley with multiple enemies are expected to FAIL until this is implemented.

Volley simultaneous stacking tests have moved to test_timing.py.
"""

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.ability import Volley
from fellowship_sim.elarion.effect import LunarlightMarkEffect
from fellowship_sim.elarion.entity import Elarion
from tests.integration.fixtures import FixedRNG, count_hits


def _make_state(num_enemies: int) -> tuple[State, Elarion, list[Enemy]]:
    state = State(rng=FixedRNG(value=0.0))
    enemies = [Enemy(state=state) for _ in range(num_enemies)]
    elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))
    return state, elarion, enemies


class TestFocusedShotTargetCount:
    """FocusedShot always hits exactly 1 target regardless of enemy count."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_hits_exactly_one_target(self, num_enemies: int) -> None:
        """FocusedShot is single-target: always 1 hit."""
        state, elarion, enemies = _make_state(num_enemies)
        hits = count_hits(state, lambda: elarion.focused_shot._do_cast(enemies[0]))
        assert len(hits) == 1


class TestCelestialShotTargetCount:
    """CelestialShot always hits exactly 1 target regardless of enemy count."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_hits_exactly_one_target(self, num_enemies: int) -> None:
        """CelestialShot is single-target: always 1 hit."""
        state, elarion, enemies = _make_state(num_enemies)
        hits = count_hits(state, lambda: elarion.celestial_shot._do_cast(enemies[0]))
        assert len(hits) == 1


class TestMultishotTargetCount:
    """Multishot hits 1 primary + up to 11 secondary = 12 max hits."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_max_12_hits(self, num_enemies: int) -> None:
        """Multishot: 1 primary + up to 11 secondary = 12 max hits."""
        state, elarion, enemies = _make_state(num_enemies)
        elarion.multishot.charges = 1
        hits = count_hits(state, lambda: elarion.multishot._do_cast(enemies[0]))
        assert len(hits) == min(num_enemies, 12)


class TestHighwindArrowTargetCount:
    """HighwindArrow hits 1 primary + up to 2 secondary = 3 max hits."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8])
    def test_max_3_hits(self, num_enemies: int) -> None:
        """HighwindArrow: 1 primary + up to 2 secondary = 3 max hits."""
        state, elarion, enemies = _make_state(num_enemies)
        hits = count_hits(state, lambda: elarion.highwind_arrow._do_cast(enemies[0]))
        assert len(hits) == min(num_enemies, 3)


class TestLunarlightMarkTargetCount:
    """LunarlightMark applies to 1 primary + up to 11 secondary targets."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_marks_up_to_12_targets(self, num_enemies: int) -> None:
        """LunarlightMark (cast): applies marks to 1 primary + up to 11 secondary targets."""
        _state, elarion, enemies = _make_state(num_enemies)
        elarion.lunarlight_mark._do_cast(enemies[0])
        # marks applied synchronously in _do_cast; no step needed to avoid expiry at t=15

        marked_count = sum(1 for e in enemies if e.effects.has(LunarlightMarkEffect))
        assert marked_count == min(num_enemies, 12)


class TestLunarlightExplosionTargetCount:
    """LunarlightExplosion hits 1 primary + up to 11 secondary = 12 max hits."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_max_12_hits(self, num_enemies: int) -> None:
        """LunarlightExplosion: 1 primary + up to 11 secondary = 12 max hits."""
        state, elarion, enemies = _make_state(num_enemies)
        hits = count_hits(state, lambda: elarion._lunarlight_explosion._do_cast(enemies[0]))
        assert len(hits) == min(num_enemies, 12)


class TestLunarlightSalvoTargetCount:
    """LunarlightSalvo always hits exactly 1 target (no secondaries)."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_hits_only_primary(self, num_enemies: int) -> None:
        """LunarlightSalvo: always hits exactly 1 target (no secondaries)."""
        state, elarion, enemies = _make_state(num_enemies)
        hits = count_hits(state, lambda: elarion._lunarlight_salvo._do_cast(enemies[0]))
        assert len(hits) == 1


class TestVolleyPerTickTargetCount:
    """Volley per tick: expected 12 max hits, but secondary targeting is not yet implemented."""

    @pytest.mark.parametrize("num_enemies", [1, 2, 3, 8, 12, 16])
    def test_per_tick_hits_primary_and_up_to_11_secondary(self, num_enemies: int) -> None:
        """Volley per tick: expected 1 primary + up to 11 secondary = 12 max hits per tick.

        NOTE: secondary targets for Volley are NOT implemented. With >1 enemy,
        only 1 hit per tick is expected (main target only). This test will FAIL
        for num_enemies > 1 until Volley secondary targeting is implemented.
        """
        state, elarion, enemies = _make_state(num_enemies)
        volley_hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: volley_hits.append(e) if isinstance(e.damage_source, Volley) else None,
        )
        elarion.volley._do_cast(enemies[0])
        state.advance_time(0.2)  # process first tick and its delayed hit

        expected = min(num_enemies, 12)
        assert len(volley_hits) == expected
