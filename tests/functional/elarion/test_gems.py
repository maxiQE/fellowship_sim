import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism
from fellowship_sim.generic_game_logic.setup_effect import (
    AncestralSurgeSetup,
    BlessingOfTheProphetSetup,
    BlessingOfTheVirtuosoSetup,
)
from tests.conftest import FixedRNG


class TestSpiritOfHeroismModifiers:
    """Setup effects (gems) that modify Spirit of Heroism stats or behavior."""

    def test_blessing_of_virtuoso(self) -> None:
        """Test blessing of the virtuoso: more haste out of ult; normal 30% haste during ult."""
        for is_level_2 in [False, True]:
            state = State(enemies=[Enemy()], rng=FixedRNG(value=0.0))
            target = state.enemies[0]
            setup = ElarionSetup(
                raw_stats=RawStatsFromPercents(
                    main_stat=1000.0,
                    crit_percent=0.0,
                    expertise_percent=0.0,
                    haste_percent=0.0,
                    spirit_percent=0.0,
                ),
            )

            virtuoso_setup = BlessingOfTheVirtuosoSetup(is_level_2=is_level_2)
            setup.setup_effect_list.append(virtuoso_setup)

            elarion = setup.finalize(state)
            assert elarion.stats.haste_percent == 0.09 if is_level_2 else 0.03

            elarion.spirit_points = 100
            elarion.event_horizon.cast(target)

            assert elarion.effects.has(SpiritOfHeroism)
            assert elarion.effects.has(EventHorizonBuff)
            assert elarion.stats.haste_percent == pytest.approx(0.3)

    def test_ancestral_surge(self) -> None:
        """Test ancestral surge: raised max spirit points; more main stat during ult."""
        for is_level_2 in [False, True]:
            state = State(enemies=[Enemy()], rng=FixedRNG(value=0.0))
            target = state.enemies[0]
            setup = ElarionSetup(
                raw_stats=RawStatsFromPercents(
                    main_stat=1000.0,
                    crit_percent=0.0,
                    expertise_percent=0.0,
                    haste_percent=0.0,
                    spirit_percent=0.0,
                ),
            )

            ancestral_surge_setup = AncestralSurgeSetup(is_level_2=is_level_2)
            setup.setup_effect_list.append(ancestral_surge_setup)

            elarion = setup.finalize(state)
            assert elarion.max_spirit_points == 100 + (30 if is_level_2 else 10)

            elarion.spirit_points = 100
            elarion.event_horizon.cast(target)

            assert elarion.effects.has(SpiritOfHeroism)
            assert elarion.effects.has(EventHorizonBuff)
            assert elarion.stats.main_stat == pytest.approx(1000 * (1.24 if is_level_2 else 1.08))

    def test_blessing_of_the_prophet(self) -> None:
        """Test blessing of the prophet: reduced spirit point cost and increased SOH duration."""
        for is_level_2 in [False, True]:
            state = State(enemies=[Enemy()], rng=FixedRNG(value=0.0))
            target = state.enemies[0]
            setup = ElarionSetup(
                raw_stats=RawStatsFromPercents(
                    main_stat=1000.0,
                    crit_percent=0.0,
                    expertise_percent=0.0,
                    haste_percent=0.0,
                    spirit_percent=0.0,
                ),
            )

            prophet_setup = BlessingOfTheProphetSetup(is_level_2=is_level_2)
            setup.setup_effect_list.append(prophet_setup)

            elarion = setup.finalize(state)
            elarion.spirit_point_per_s = 0

            assert elarion.spirit_point_per_s == 0
            assert elarion.spirit_ability_cost == 100 - (15 if is_level_2 else 5)

            elarion.spirit_points = 100
            elarion.event_horizon.cast(target)

            assert elarion.spirit_points == (15 if is_level_2 else 5)

            soh = elarion.effects.get(SpiritOfHeroism)
            assert elarion.effects.has(EventHorizonBuff)
            assert soh.duration == pytest.approx(20 - 0.7 + (18 if is_level_2 else 6))

            elarion.wait(20 - 0.7 + (18 if is_level_2 else 6) - 0.1)
            assert elarion.effects.has(SpiritOfHeroism)

            elarion.wait(0.2)
            assert not elarion.effects.has(SpiritOfHeroism)
