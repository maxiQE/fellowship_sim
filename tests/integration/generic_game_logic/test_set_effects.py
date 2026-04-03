"""Integration tests — set bonus effect mechanics."""

import pytest

from fellowship_sim.base_classes import SnapshotStats, State
from fellowship_sim.base_classes.events import (
    PreDamageSnapshotUpdate,
    UltimateCast,
)
from fellowship_sim.elarion.setup import Elarion
from fellowship_sim.generic_game_logic.set_effects import (
    DarkProphecyBuff,
    DeathsGrasp,
    DraconicMightBuff,
    DrakheimsAbsolution,
    DrakheimsAbsolutionBuff,
    EldrinDeceit,
    HauntingLament,
    SintharasVeil,
    SinWarding,
    TormentOfBaelAurum,
    TuzariGrace,
)


class TestPassiveStatBuffSetEffects:
    """Set effects that grant flat secondary or primary stat bonuses."""

    def test_eldrin_deceit_adds_3_percent_crit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """EldrinDeceit grants +3% Critical Strike Chance."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.crit_percent
        elarion.effects.add(EldrinDeceit(owner=elarion))
        assert elarion.stats.crit_percent == pytest.approx(before + 0.03)

    def test_haunting_lament_adds_3_percent_spirit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """HauntingLament grants +3% Spirit."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.spirit_percent
        elarion.effects.add(HauntingLament(owner=elarion))
        assert elarion.stats.spirit_percent == pytest.approx(before + 0.03)

    def test_sintharas_veil_adds_3_percent_spirit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """SintharasVeil grants +3% Spirit."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.spirit_percent
        elarion.effects.add(SintharasVeil(owner=elarion))
        assert elarion.stats.spirit_percent == pytest.approx(before + 0.03)

    def test_sin_warding_adds_3_percent_expertise(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """SinWarding grants +3% Expertise."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.expertise_percent
        elarion.effects.add(SinWarding(owner=elarion))
        assert elarion.stats.expertise_percent == pytest.approx(before + 0.03)

    def test_tuzari_grace_adds_3_percent_haste(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """TuzariGrace grants +3% Haste."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(TuzariGrace(owner=elarion))
        assert elarion.stats.haste_percent == pytest.approx(before + 0.03)

    def test_torment_of_baelaurum_multiplies_main_stat_by_1_04(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """TormentOfBaelAurum multiplies main_stat by 1.04 (true multiplier)."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(TormentOfBaelAurum(owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * 1.04)


class TestDeathsGrasp:
    """DeathsGrasp: +3% Spirit and +15% damage dealt to targets at or below 30% HP."""

    def test_adds_3_percent_spirit(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """DeathsGrasp grants +3% Spirit passively."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.spirit_percent
        elarion.effects.add(DeathsGrasp(owner=elarion))
        assert elarion.stats.spirit_percent == pytest.approx(before + 0.03)

    def test_adds_15_percent_damage_bonus_on_low_health_target(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """PreDamageSnapshotUpdate scales average_damage by +15% when target is at 25% HP."""
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.25
        elarion.effects.add(DeathsGrasp(owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state_no_procs__st.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1150.0)

    def test_no_damage_bonus_above_30_percent_hp(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """Snapshot is not modified when target is above 30% HP."""
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.50
        elarion.effects.add(DeathsGrasp(owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state_no_procs__st.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1000.0)


class TestDrakheimsAbsolution:
    """DrakheimsAbsolution: UltimateCast by the aura owner → +20% Main Stat for 20s."""

    def test_ultimate_cast_applies_main_stat_buff(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """UltimateCast by the aura owner applies DrakheimsAbsolutionBuff (+20% main stat)."""
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(DrakheimsAbsolution(owner=elarion))
        before = elarion.stats.main_stat
        state_no_procs__st.bus.emit(UltimateCast(ability=elarion.skystrider_supremacy, owner=elarion, target=enemy))
        assert elarion.effects.has(DrakheimsAbsolutionBuff)
        assert elarion.stats.main_stat == pytest.approx(before * 1.20)


class TestDarkProphecyBuff:
    """DarkProphecyBuff: +25% Haste for 20s (triggered by DarkProphecy rPPM proc)."""

    def test_adds_25_percent_haste(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """DarkProphecyBuff grants +25% Haste."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(DarkProphecyBuff(owner=elarion))
        assert elarion.stats.haste_percent == pytest.approx(before + 0.25)


class TestDraconicMightBuff:
    """DraconicMightBuff: +18% Main Stat for 14s (triggered by DraconicMight crit rPPM proc)."""

    def test_adds_18_percent_main_stat(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """DraconicMightBuff grants +18% Main Stat (additive multiplier)."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(DraconicMightBuff(owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * 1.18)
