"""Integration tests — gem effect mechanics."""

import pytest

from fellowship_sim.base_classes import Entity, SnapshotStats, State
from fellowship_sim.base_classes.events import (
    AbilityDamage,
    ComputeCooldownReduction,
    PreDamageSnapshotUpdate,
    UnitDestroyed,
)
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.setup import Elarion
from fellowship_sim.generic_game_logic.gems import (
    AdrenalineRush,
    AncientsWisdom,
    BerserkersZeal,
    BlessingOfTheCommander,
    BlessingOfTheConqueror,
    BlessingOfTheDeathdealer,
    BlessingOfTheVirtuoso,
    ChampionsHeart,
    FelineGrace,
    FirstStrike,
    GemOvercap,
    HarmoniousSoul,
    KillerInstinct,
    MightOfTheMinotaur,
    MysticsIntuition,
    OraclesForesight,
    SealedFate,
    StoicsTeachings,
    TacticiansAcumen,
    ThiefsAlacrity,
    VanguardsResolve,
)
from tests.integration.fixtures import FixedRNG


class TestSimpleStatGems:
    """Gems that grant flat primary or secondary stat bonuses."""

    def test_champions_heart_level_1_adds_15_main_stat(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(ChampionsHeart(owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before + 15)

    def test_champions_heart_level_2_adds_45_main_stat(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(ChampionsHeart(is_level_2=True, owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before + 45)

    def test_stoics_teachings_level_1_adds_25_main_stat(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(StoicsTeachings(owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before + 25)

    def test_stoics_teachings_level_2_adds_75_main_stat(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(StoicsTeachings(is_level_2=True, owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before + 75)

    def test_ancients_wisdom_level_1_multiplies_main_stat_by_1_03(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(AncientsWisdom(owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * 1.03)

    def test_ancients_wisdom_level_2_multiplies_main_stat_by_1_09(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(AncientsWisdom(is_level_2=True, owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * 1.09)

    def test_berserkers_zeal_adds_crit_score(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.crit_percent
        elarion.effects.add(BerserkersZeal(owner=elarion))
        assert elarion.stats.crit_percent > before

    def test_killer_instinct_level_1_adds_3_percent_crit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.crit_percent
        elarion.effects.add(KillerInstinct(owner=elarion))
        assert elarion.stats.crit_percent == pytest.approx(before + 0.03)

    def test_killer_instinct_level_2_adds_9_percent_crit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.crit_percent
        elarion.effects.add(KillerInstinct(is_level_2=True, owner=elarion))
        assert elarion.stats.crit_percent == pytest.approx(before + 0.09)

    def test_blessing_of_the_deathdealer_level_1_multiplies_crit_multiplier(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.crit_multiplier
        elarion.effects.add(BlessingOfTheDeathdealer(owner=elarion))
        assert elarion.stats.crit_multiplier == pytest.approx(before * 1.03)

    def test_blessing_of_the_deathdealer_level_2_multiplies_crit_multiplier(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.crit_multiplier
        elarion.effects.add(BlessingOfTheDeathdealer(is_level_2=True, owner=elarion))
        assert elarion.stats.crit_multiplier == pytest.approx(before * 1.09)

    def test_thiefs_alacrity_adds_haste_score(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(ThiefsAlacrity(owner=elarion))
        assert elarion.stats.haste_percent > before

    def test_feline_grace_level_1_adds_3_percent_haste(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(FelineGrace(owner=elarion))
        assert elarion.stats.haste_percent == pytest.approx(before + 0.03)

    def test_feline_grace_level_2_adds_9_percent_haste(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(FelineGrace(is_level_2=True, owner=elarion))
        assert elarion.stats.haste_percent == pytest.approx(before + 0.09)

    def test_blessing_of_the_virtuoso_level_1_adds_3_percent_haste(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(BlessingOfTheVirtuoso(owner=elarion))
        assert elarion.stats.haste_percent == pytest.approx(before + 0.03)

    def test_vanguards_resolve_adds_expertise_score(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.expertise_percent
        elarion.effects.add(VanguardsResolve(owner=elarion))
        assert elarion.stats.expertise_percent > before

    def test_tacticians_acumen_level_1_adds_3_percent_expertise(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.expertise_percent
        elarion.effects.add(TacticiansAcumen(owner=elarion))
        assert elarion.stats.expertise_percent == pytest.approx(before + 0.03)

    def test_tacticians_acumen_level_2_adds_9_percent_expertise(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.expertise_percent
        elarion.effects.add(TacticiansAcumen(is_level_2=True, owner=elarion))
        assert elarion.stats.expertise_percent == pytest.approx(before + 0.09)

    def test_mystics_intuition_adds_spirit_score(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.spirit_percent
        elarion.effects.add(MysticsIntuition(owner=elarion))
        assert elarion.stats.spirit_percent > before

    def test_oracles_foresight_level_1_adds_3_percent_spirit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.spirit_percent
        elarion.effects.add(OraclesForesight(owner=elarion))
        assert elarion.stats.spirit_percent == pytest.approx(before + 0.03)

    def test_oracles_foresight_level_2_adds_9_percent_spirit(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.spirit_percent
        elarion.effects.add(OraclesForesight(is_level_2=True, owner=elarion))
        assert elarion.stats.spirit_percent == pytest.approx(before + 0.09)


class TestMightOfTheMinotaur:
    """MightOfTheMinotaur: +3% main stat while above 80% HP (+9% at level 2)."""

    def test_adds_3_percent_main_stat_above_80_pct_hp(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        elarion.percent_hp = 1.0
        before = elarion.stats.main_stat
        elarion.effects.add(MightOfTheMinotaur(owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * 1.03)

    def test_no_bonus_at_or_below_80_pct_hp(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(MightOfTheMinotaur(owner=elarion))
        elarion.percent_hp = 0.7
        elarion._recalculate_stats()
        assert elarion.stats.main_stat == pytest.approx(before)

    def test_level_2_adds_9_percent_main_stat_above_80_pct_hp(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        elarion.percent_hp = 1.0
        before = elarion.stats.main_stat
        elarion.effects.add(MightOfTheMinotaur(is_level_2=True, owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * 1.09)


class TestGemOvercap:
    """GemOvercap: main_stat * (1 + overcap * 0.00005) for overcap > 0."""

    @pytest.mark.parametrize("overcap", [100, 500, 2640])
    def test_overcap_main_stat_multiplier(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion, overcap: int
    ) -> None:
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(GemOvercap(owner=elarion, overcap=overcap))
        assert elarion.stats.main_stat == pytest.approx(before * (1 + overcap * 0.00005))


class TestAdrenalineRush:
    """AdrenalineRush: apply AdrenalineRushBuff when damage lands on target at <= 30% HP."""

    def test_buff_applied_on_low_health_target(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.25
        elarion.effects.add(AdrenalineRush(owner=elarion))
        state_no_procs__st.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=enemy,
                is_crit=False,
                is_grievous_crit=False,
                damage=100.0,
            )
        )
        assert elarion.effects.has("adrenaline_rush")

    def test_no_buff_above_30_percent_hp(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.50
        elarion.effects.add(AdrenalineRush(owner=elarion))
        state_no_procs__st.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=enemy,
                is_crit=False,
                is_grievous_crit=False,
                damage=100.0,
            )
        )
        assert not elarion.effects.has("adrenaline_rush")


class TestFirstStrike:
    """FirstStrike: apply FirstStrikeBuff on the first attack against each unique enemy."""

    def test_buff_applied_on_first_hit(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(FirstStrike(owner=elarion))
        state_no_procs__st.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=enemy,
                is_crit=False,
                is_grievous_crit=False,
                damage=100.0,
            )
        )
        assert elarion.effects.has("first_strike_buff")

    def test_second_hit_same_enemy_does_not_reapply(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        fs = FirstStrike(owner=elarion)
        elarion.effects.add(fs)
        for _ in range(2):
            state_no_procs__st.bus.emit(
                AbilityDamage(
                    damage_source=elarion.focused_shot,
                    owner=elarion,
                    target=enemy,
                    is_crit=False,
                    is_grievous_crit=False,
                    damage=100.0,
                )
            )
        assert len(fs._attacked_ids) == 1


class TestSealedFate:
    """SealedFate: +5% crit on targets above 50% HP (+15% at level 2)."""

    def test_adds_crit_percent_on_snapshot_above_50_pct_hp(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.75
        elarion.effects.add(SealedFate(owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state_no_procs__st.bus.emit(event)
        assert event.snapshot.crit_percent == pytest.approx(0.05)

    def test_level_2_adds_15_percent_crit_above_50_pct_hp(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.75
        elarion.effects.add(SealedFate(is_level_2=True, owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state_no_procs__st.bus.emit(event)
        assert event.snapshot.crit_percent == pytest.approx(0.15)

    def test_no_crit_bonus_at_or_below_50_pct_hp(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        enemy.percent_hp = 0.40
        elarion.effects.add(SealedFate(owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state_no_procs__st.bus.emit(event)
        assert event.snapshot.crit_percent == pytest.approx(0.0)


class TestBlessingOfTheConqueror:
    """BlessingOfTheConqueror: +5% damage in boss fights (+15% at level 2); no-op otherwise."""

    def test_scales_snapshot_in_boss_fight(self, unit_elarion__zero_stats: Elarion) -> None:
        state = State(enemies=[Entity()], rng=FixedRNG(value=0.0), is_boss_fight=True).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        enemy = state.enemies[0]
        elarion.effects.add(BlessingOfTheConqueror(owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1050.0)

    def test_level_2_scales_snapshot_by_1_15_in_boss_fight(self, unit_elarion__zero_stats: Elarion) -> None:
        state = State(enemies=[Entity()], rng=FixedRNG(value=0.0), is_boss_fight=True).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        enemy = state.enemies[0]
        elarion.effects.add(BlessingOfTheConqueror(is_level_2=True, owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1150.0)

    def test_no_scaling_outside_boss_fight(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(BlessingOfTheConqueror(owner=elarion))
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state_no_procs__st.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1000.0)


class TestBlessingOfTheCommander:
    """BlessingOfTheCommander: all ability cooldowns drain 4% faster (+12% at level 2)."""

    def test_appends_cdr_modifier_level_1(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        elarion.effects.add(BlessingOfTheCommander(owner=elarion))
        event = ComputeCooldownReduction(ability=elarion.focused_shot, owner=elarion)
        state_no_procs__st.bus.emit(event)
        assert event.cdr_modifiers == [0.04]

    def test_appends_cdr_modifier_level_2(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        elarion.effects.add(BlessingOfTheCommander(is_level_2=True, owner=elarion))
        event = ComputeCooldownReduction(ability=elarion.focused_shot, owner=elarion)
        state_no_procs__st.bus.emit(event)
        assert event.cdr_modifiers == [0.12]


class TestHarmoniousSoul:
    """HarmoniousSoul: gain a stack of HarmoniousSoulBuff each time an enemy is defeated."""

    def test_unit_destroyed_applies_buff(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(HarmoniousSoul(owner=elarion))
        state_no_procs__st.bus.emit(UnitDestroyed(entity=enemy))
        assert elarion.effects.has("harmonious_soul")

    def test_five_kills_give_five_stacks(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(HarmoniousSoul(owner=elarion))
        for _ in range(5):
            state_no_procs__st.bus.emit(UnitDestroyed(entity=enemy))
        buff = elarion.effects.get("harmonious_soul")
        assert buff is not None
        assert buff.stacks == 5

    def test_five_stacks_one_decays_after_5s(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(HarmoniousSoul(owner=elarion))
        for _ in range(5):
            state_no_procs__st.bus.emit(UnitDestroyed(entity=enemy))
        buff = elarion.effects.get("harmonious_soul")
        assert buff is not None

        state_no_procs__st.advance_time(4.999)
        assert buff.stacks == 5  # not yet expired

        state_no_procs__st.advance_time(0.002)  # crosses the 5 s mark
        assert buff.stacks == 4

    def test_new_kill_resets_expiry(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        # kill at t=0 → 1 stack, expiry at t=5
        # kill at t=4 → 2 stacks, expiry pushed to t=9
        # at t=9: 1 stack decayed, expiry pushed to t=14
        # at t=14: 0 stacks → buff removed
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(HarmoniousSoul(owner=elarion))
        state_no_procs__st.bus.emit(UnitDestroyed(entity=enemy))  # t=0, stacks=1

        state_no_procs__st.advance_time(4.0)
        state_no_procs__st.bus.emit(UnitDestroyed(entity=enemy))  # t=4, fuse → stacks=2, expiry=t+5=9
        buff = elarion.effects.get("harmonious_soul")
        assert buff is not None
        assert buff.stacks == 2

        state_no_procs__st.advance_time(4.999)  # t=8.999
        assert buff.stacks == 2  # expiry at t=9, not yet

        state_no_procs__st.advance_time(0.002)  # t=9.001: decay fires, stacks=1, expiry reset to t=14
        assert buff.stacks == 1

        state_no_procs__st.advance_time(4.998)  # t≈13.999, expiry at t=14.0 not yet
        assert buff.stacks == 1

        state_no_procs__st.advance_time(0.003)  # t≈14.002, crosses t=14: stacks=0 → buff removed
        assert not elarion.effects.has("harmonious_soul")

    def test_max_stacks_capped_at_10(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        elarion = unit_elarion__zero_stats
        enemy = state_no_procs__st.enemies[0]
        elarion.effects.add(HarmoniousSoul(owner=elarion))
        for _ in range(15):
            state_no_procs__st.bus.emit(UnitDestroyed(entity=enemy))
        buff = elarion.effects.get("harmonious_soul")
        assert buff is not None
        assert buff.stacks == 10
