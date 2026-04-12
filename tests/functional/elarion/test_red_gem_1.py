import pytest

from fellowship_sim.base_classes import Enemy, RawStatsFromPercents, State
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.gems import MightOfTheMinotaur
from tests.conftest import FixedRNG


class TestHighHPBonus:
    @pytest.mark.parametrize("nominal_uptime", [0.4, 0.8, 0.9])
    def test_high_hp_bonus(self, nominal_uptime: float) -> None:
        """Test that primary stat bonus turns on and off."""
        state = State(rng=FixedRNG(0.5))
        Enemy(state=state)
        elarion = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=0.0,
            ),
            high_hp_uptime=nominal_uptime,
        ).finalize(state)

        elarion.effects.add(MightOfTheMinotaur(owner=elarion))

        assert elarion.percent_hp == 1.0
        assert elarion.stats.main_stat == 1030

        expected_delay_1 = nominal_uptime / (1 - nominal_uptime) * 3
        elarion.wait(expected_delay_1 + 0.01)

        assert elarion.percent_hp == 0.7
        assert elarion.stats.main_stat == 1000

        expected_delay_2 = 3
        elarion.wait(expected_delay_2)

        assert elarion.percent_hp == 1.0
        assert elarion.stats.main_stat == 1030

        assert expected_delay_1 / (expected_delay_1 + expected_delay_2) == pytest.approx(nominal_uptime)
