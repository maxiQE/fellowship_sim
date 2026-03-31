# Tests that pin the guarantees of the shared conftest fixtures.

from collections.abc import Callable

import pytest

from fellowship_sim.elarion.entity import Elarion


class TestUnitElarionZeroStats:
    def test_main_stat(self, unit_elarion__zero_stats: Elarion) -> None:
        assert unit_elarion__zero_stats.stats.main_stat == pytest.approx(1000.0)

    def test_crit_multiplier(self, unit_elarion__zero_stats: Elarion) -> None:
        assert unit_elarion__zero_stats.stats.crit_multiplier == pytest.approx(1.0)

    def test_crit_percent_zero(self, unit_elarion__zero_stats: Elarion) -> None:
        assert unit_elarion__zero_stats.stats.crit_percent == pytest.approx(0.0)

    def test_haste_percent_zero(self, unit_elarion__zero_stats: Elarion) -> None:
        assert unit_elarion__zero_stats.stats.haste_percent == pytest.approx(0.0)

    def test_expertise_percent_zero(self, unit_elarion__zero_stats: Elarion) -> None:
        assert unit_elarion__zero_stats.stats.expertise_percent == pytest.approx(0.0)

    def test_spirit_percent_zero(self, unit_elarion__zero_stats: Elarion) -> None:
        assert unit_elarion__zero_stats.stats.spirit_percent == pytest.approx(0.0)

    def test_never_crits_with_low_rng_roll(self, unit_elarion__zero_stats: Elarion) -> None:
        """crit_percent=0 — a roll of 1e-9 is not less than 0.0; crits are impossible."""
        assert not (unit_elarion__zero_stats.stats.crit_percent > 1e-9)


class TestSetupHastedElarion:
    def test_haste_is_set(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.2)
        assert player.stats.haste_percent == pytest.approx(0.2)

    def test_main_stat(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.3)
        assert player.stats.main_stat == pytest.approx(1000.0)

    def test_crit_multiplier(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.3)
        assert player.stats.crit_multiplier == pytest.approx(1.0)

    def test_crit_percent_zero(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.3)
        assert player.stats.crit_percent == pytest.approx(0.0)

    def test_expertise_percent_zero(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.3)
        assert player.stats.expertise_percent == pytest.approx(0.0)

    def test_spirit_percent_zero(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.3)
        assert player.stats.spirit_percent == pytest.approx(0.0)

    def test_never_crits_with_low_rng_roll(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        """crit_percent=0 regardless of haste — still never crits."""
        player = setup_hasted_elarion(haste=0.3)
        assert not (player.stats.crit_percent > 1e-9)
