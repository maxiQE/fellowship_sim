"""Integration tests — generic buff mechanics.

Tests that SpiritOfHeroism and SpiritOfHeroismAura compose correctly with
the stat pipeline and event bus.
"""

import pytest

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.events import UltimateCast
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism, SpiritOfHeroismAura
from tests.integration.fixtures import FixedRNG


class TestSpiritOfHeroism:
    """SpiritOfHeroism: +30% haste, optional main-stat boost, optional haste reduction."""

    @pytest.fixture
    def state_and_elarion(self) -> tuple[State, Elarion]:
        """Single enemy state, Elarion with no setup effects applied."""
        enemy = Entity()
        state = State(enemies=[enemy], rng=FixedRNG(value=0.99)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        return state, elarion

    def test_increases_haste_by_30_percent(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """SpiritOfHeroism (no modifiers) adds +30% haste."""
        state, elarion = state_and_elarion
        haste_before = elarion.stats.haste_percent

        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=20.0,
                ancestral_surge_level=0,
                blessing_of_the_virtuoso_level=0,
                sapphire_aurastone_level=0,
            )
        )

        assert elarion.stats.haste_percent == pytest.approx(haste_before + 0.30)

    def test_blessing_of_virtuoso_level1_reduces_haste(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """With blessing_of_the_virtuoso_level=1: net haste boost is +27% (+30-3%)."""
        state, elarion = state_and_elarion
        haste_before = elarion.stats.haste_percent

        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=20.0,
                ancestral_surge_level=0,
                blessing_of_the_virtuoso_level=1,
                sapphire_aurastone_level=0,
            )
        )

        assert elarion.stats.haste_percent == pytest.approx(haste_before + 0.27)

    def test_blessing_of_virtuoso_level2_reduces_haste(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """With blessing_of_the_virtuoso_level=2: net haste boost is +21% (+30-9%)."""
        state, elarion = state_and_elarion
        haste_before = elarion.stats.haste_percent

        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=20.0,
                ancestral_surge_level=0,
                blessing_of_the_virtuoso_level=2,
                sapphire_aurastone_level=0,
            )
        )

        assert elarion.stats.haste_percent == pytest.approx(haste_before + 0.21)

    def test_ancestral_surge_level1_increases_main_stat(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """With ancestral_surge_level=1: main_stat is multiplied by 1.08."""
        state, elarion = state_and_elarion
        main_stat_before = elarion.stats.main_stat

        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=20.0,
                ancestral_surge_level=1,
                blessing_of_the_virtuoso_level=0,
                sapphire_aurastone_level=0,
            )
        )

        assert elarion.stats.main_stat == pytest.approx(main_stat_before * 1.08)

    def test_ancestral_surge_level2_increases_main_stat_more(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """With ancestral_surge_level=2: main_stat is multiplied by 1.24."""
        state, elarion = state_and_elarion
        main_stat_before = elarion.stats.main_stat

        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=20.0,
                ancestral_surge_level=2,
                blessing_of_the_virtuoso_level=0,
                sapphire_aurastone_level=0,
            )
        )

        assert elarion.stats.main_stat == pytest.approx(main_stat_before * 1.24)

    def test_expires_after_duration(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """SpiritOfHeroism expires after its duration; haste returns to baseline."""
        state, elarion = state_and_elarion
        haste_before = elarion.stats.haste_percent

        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=20.0,
                ancestral_surge_level=0,
                blessing_of_the_virtuoso_level=0,
                sapphire_aurastone_level=0,
            )
        )
        assert elarion.stats.haste_percent == pytest.approx(haste_before + 0.30)

        state.advance_time(21.0)

        assert elarion.stats.haste_percent == pytest.approx(haste_before)


class TestSpiritOfHeroismAura:
    """SpiritOfHeroismAura: fires SpiritOfHeroism on UltimateCast by the aura's owner."""

    @pytest.fixture
    def state_and_elarion(self) -> tuple[State, Elarion]:
        """Single enemy state, Elarion with SpiritOfHeroismAura manually added."""
        enemy = Entity()
        state = State(enemies=[enemy], rng=FixedRNG(value=0.99)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        elarion.effects.add(SpiritOfHeroismAura(owner=elarion))
        return state, elarion

    def test_fires_spirit_of_heroism_on_ultimate_cast(self, state_and_elarion: tuple[State, Elarion]) -> None:
        """Emitting UltimateCast for the aura owner applies SpiritOfHeroism buff."""
        state, elarion = state_and_elarion
        haste_before = elarion.stats.haste_percent

        state.bus.emit(
            UltimateCast(
                ability=elarion.skystrider_supremacy,
                owner=elarion,
                target=state.enemies[0],
            )
        )

        assert elarion.effects.has("spirit_of_heroism")
        assert elarion.stats.haste_percent == pytest.approx(haste_before + 0.30)
