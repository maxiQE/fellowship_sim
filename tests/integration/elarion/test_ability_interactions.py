"""Integration tests — multi-ability functional interactions.

Tests that discrete mechanics compose correctly across ability boundaries.
"""

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.buff import (
    EmpoweredMultishotChargeBuff,
    EventHorizonBuff,
    FerventSupremacyBuff,
    SkystriderSupremacyBuff,
)
from fellowship_sim.elarion.effect import (
    FinalCrescendo,
    HighwindAppliesShimmerEffect,
    LethalShots,
    LunarlightMarkEffect,
    ResurgentWinds,
    Shimmer,
)
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup_effect import FocusedExpanseSetup
from tests.integration.fixtures import FixedRNG


class TestMultishotChargeSystem:
    """HWA grants Multishot charges; Fervent/Skystrider supremacy empower Multishot casts."""

    @pytest.fixture
    def state_3e(self) -> tuple[State, Elarion, list[Enemy]]:
        enemies = [Enemy(), Enemy(), Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        return state, elarion, enemies

    def test_hwa_grants_multishot_charge_with_two_or_more_secondaries(
        self, state_3e: tuple[State, Elarion, list[Enemy]]
    ) -> None:
        """HWA with ≥2 secondary targets grants exactly 1 normal Multishot charge, capping at 5."""
        state, elarion, enemies = state_3e

        elarion.multishot.charges = 0

        for idx in range(10):
            assert elarion.multishot.charges == min(idx, 5)

            elarion.highwind_arrow._do_cast(enemies[0])
            state.step()

    def test_hwa_does_not_grant_multishot_charge_with_one_secondary(self) -> None:
        """HWA with only 1 secondary target (2 enemies total) → no charge granted."""
        enemies = [Enemy(), Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        charges_before = elarion.multishot.charges

        elarion.highwind_arrow._do_cast(enemies[0])
        state.step()

        assert elarion.multishot.charges == charges_before

    def test_fervent_supremacy_buff_applies_damage_bonus(self, state_no_procs__st: State) -> None:
        """FerventSupremacyBuff: empowered Multishot deals 1.5x per-hit damage.
        With 1 enemy and multishot_num_arrows_min=3, all 3 arrows go to main target.
        All hits should be 1.5x the baseline single-arrow damage.
        """
        # Baseline: standard Multishot with 1 charge
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state_no_procs__st.character = elarion
        elarion.multishot.charges = 1
        baseline_damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, lambda e: baseline_damages.append(e))
        elarion.multishot._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)
        assert len(baseline_damages) == 1
        baseline = baseline_damages[0].damage

        # Empowered: FerventSupremacyBuff active (fires 3 arrows on 1 enemy, 1.5x each)
        enemies2 = [Enemy()]
        state2 = State(enemies=enemies2, rng=FixedRNG(value=0.0))
        elarion2 = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state2.character = elarion2
        elarion2.effects.add(FerventSupremacyBuff(owner=elarion2))

        empowered_damages: list[AbilityDamage] = []
        state2.bus.subscribe(AbilityDamage, empowered_damages.append)

        elarion2.multishot._do_cast(enemies2[0])
        state2.advance_time(0.0)

        assert len(empowered_damages) == 3
        assert all(e.damage == pytest.approx(baseline * 1.25, rel=1e-6) for e in empowered_damages)

    def test_fervent_supremacy_charge_consumed_per_cast(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """4 stacks consumed over 4 casts via cast() API; buff removed at 0.
        consume_charge() is only called in cast(), not _do_cast().
        """
        elarion = unit_elarion__zero_stats
        elarion.effects.add(FerventSupremacyBuff(owner=elarion))

        buff = elarion.effects.get(FerventSupremacyBuff)
        assert buff is not None
        assert isinstance(buff, FerventSupremacyBuff)
        assert buff.stacks == 4

        for expected_stacks in [3, 2, 1, 0]:
            elarion.multishot.cast(state_no_procs__st.enemies[0])  # cast() calls consume_charge()
            if expected_stacks > 0:
                remaining_buff = elarion.effects.get(FerventSupremacyBuff)
                assert remaining_buff is not None
                assert remaining_buff.stacks == expected_stacks
            else:
                assert elarion.effects.get(FerventSupremacyBuff) is None

    def test_empowered_cast_does_not_consume_normal_charge(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """Empowered Multishot cast (via FerventSupremacyBuff) does not consume a normal charge."""
        elarion = unit_elarion__zero_stats
        elarion.multishot.charges = 0
        elarion.effects.add(FerventSupremacyBuff(owner=elarion))

        assert elarion.multishot._can_cast()

        elarion.multishot._pay_cost_for_cast(state_no_procs__st.enemies[0])

        assert elarion.multishot.charges == 0

    def test_empowered_multishot_has_lower_priority_than_skystrider_supremacy(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """When both buffs are present, empowered_multishot keeps it charge."""
        elarion = unit_elarion__zero_stats

        skystrider_supremacy = SkystriderSupremacyBuff(owner=elarion)
        empowered_ms = EmpoweredMultishotChargeBuff(owner=elarion)
        elarion.effects.add(skystrider_supremacy)
        elarion.effects.add(empowered_ms)

        assert skystrider_supremacy.stacks == 1
        assert empowered_ms.stacks == 1

        elarion.multishot._pay_cost_for_cast(state_no_procs__st.enemies[0])

        assert skystrider_supremacy.stacks == 1  # NB: does not have a charge mechanic
        assert empowered_ms.stacks == 1

    def test_empowered_multishot_has_lower_priority_than_fervent_supremacy(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """When both buffs are present, empowered_multishot keeps it charge."""
        elarion = unit_elarion__zero_stats

        fervent_supremacy = FerventSupremacyBuff(owner=elarion)
        empowered_ms = EmpoweredMultishotChargeBuff(owner=elarion)
        elarion.effects.add(fervent_supremacy)
        elarion.effects.add(empowered_ms)

        assert fervent_supremacy.stacks == 4
        assert empowered_ms.stacks == 1

        elarion.multishot._pay_cost_for_cast(state_no_procs__st.enemies[0])

        assert fervent_supremacy.stacks == 3
        assert empowered_ms.stacks == 1

    @pytest.mark.parametrize("has_fervent_supremacy", [False, True])
    def test_focused_expanse_buffs_both_supremacies(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion, has_fervent_supremacy: bool
    ) -> None:
        """Focused expanse buffs any multishot by +20% damage."""
        elarion = unit_elarion__zero_stats
        target = state_no_procs__st.enemies[0]

        # Setup effect: boost empowered MS damage by +20% damage
        FocusedExpanseSetup().apply(elarion, context=None)  # ty:ignore[invalid-argument-type]

        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        if not has_fervent_supremacy:
            elarion.effects.add(EmpoweredMultishotChargeBuff(owner=elarion))
            elarion.multishot.cast(target)  # empowered MS

            elarion.skystrider_supremacy.cast(target)
            elarion.multishot.cast(target)  # sky supremacy

            assert len(damages) == 6
            assert all(event.damage == pytest.approx(elarion.multishot.average_damage * 1.2) for event in damages)

        else:
            elarion.skystrider_supremacy.is_fervent_supremacy = True
            elarion.skystrider_supremacy.cast(target)
            elarion.multishot.cast(target)  # fervent supremacy
            elarion.multishot.cast(target)  # fervent supremacy

            assert len(damages) == 6
            assert all(
                event.damage == pytest.approx(elarion.multishot.average_damage * 1.2 * 1.25) for event in damages
            )


class TestResurgentWinds:
    """ResurgentWinds overrides HWA cast time and adds a damage bonus vs marked targets."""

    def test_overrides_hwa_cast_time(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """ResurgentWinds: HWA cast time override set to 1.5s for a single cast."""
        elarion = unit_elarion__zero_stats
        elarion.effects.add(ResurgentWinds(owner=elarion))

        elarion.highwind_arrow.cast(state_no_procs__st.enemies[0])
        assert state_no_procs__st.time == pytest.approx(1.5)

        elarion.highwind_arrow.cast(state_no_procs__st.enemies[0])
        assert state_no_procs__st.time == pytest.approx(1.5 + 2.0)

    def test_damage_bonus_on_marked_target(self, state_no_procs__st: State) -> None:
        """ResurgentWinds: HWA deals 1.5x damage to a marked target, for a single cast."""
        target = Enemy()
        state = State(
            enemies=[target],
            rng=FixedRNG(value=1.0),  # FixedRNG(value=1.0) to prevent mark from exploding
        )
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion

        elarion.effects.add(ResurgentWinds(owner=elarion))
        target.effects.add(LunarlightMarkEffect(owner=elarion, stacks=5))

        marked_damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, marked_damages.append)
        elarion.highwind_arrow._do_cast(target)  # first cast: buffed
        state.step()

        elarion.highwind_arrow._do_cast(target)  # second cast: unbuffed
        state.step()

        assert all(event.damage_source == elarion.highwind_arrow for event in marked_damages)
        assert marked_damages[0].damage == pytest.approx(elarion.highwind_arrow.average_damage * 1.5, rel=1e-6)
        assert marked_damages[1].damage == pytest.approx(elarion.highwind_arrow.average_damage, rel=1e-6)

    def test_damage_bonus_on_marked_target_with_final_crescendo(self, state_no_procs__st: State) -> None:
        """RW and FC damage stacks multiplicatively."""
        target = Enemy()
        state = State(
            enemies=[target],
            rng=FixedRNG(value=1.0),  # FixedRNG(value=1.0) to prevent mark from exploding
        )
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion

        fc = FinalCrescendo(owner=elarion)
        elarion.effects.add(fc)

        # setup final crescendo
        for _ in range(3):
            elarion.highwind_arrow.cast(target)
            elarion.highwind_arrow.charges = 3

        assert fc.stacks == 3
        assert elarion.highwind_arrow.has_final_crescendo_buff

        elarion.effects.add(ResurgentWinds(owner=elarion))
        target.effects.add(LunarlightMarkEffect(owner=elarion, stacks=5))

        marked_damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, marked_damages.append)

        elarion.highwind_arrow.cast(target)  # first cast: buffed

        assert all(event.damage_source == elarion.highwind_arrow for event in marked_damages)
        assert marked_damages[0].damage == pytest.approx(elarion.highwind_arrow.average_damage * 1.5 * 2, rel=1e-6)


class TestEventHorizon:
    """EventHorizonBuff scales all damage by 1.20, halves focus cost, and chains CDR via HWA and Barrage."""

    def test_damage_scaling(self, state_no_procs__st: State) -> None:
        """EventHorizonBuff: all damage scaled by 1.20."""
        # Baseline
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state_no_procs__st.character = elarion
        baseline_damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, baseline_damages.append)
        elarion.focused_shot._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()
        baseline = baseline_damages[0].damage

        # With EventHorizon
        enemies2 = [Enemy()]
        state2 = State(enemies=enemies2, rng=FixedRNG(value=0.0))
        elarion2 = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state2.character = elarion2
        elarion2.effects.add(EventHorizonBuff(owner=elarion2))
        eh_damages: list[AbilityDamage] = []
        state2.bus.subscribe(AbilityDamage, eh_damages.append)
        elarion2.focused_shot._do_cast(enemies2[0])
        state2.step()

        assert eh_damages[0].damage == pytest.approx(baseline * 1.20, rel=1e-6)

    def test_hwa_reduces_barrage_cd(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """Each HWA hit during EventHorizon reduces Barrage CD by 0.5s.
        Uses advance_time(0.0) to avoid EventHorizon 20s buff expiry.
        """
        elarion = unit_elarion__zero_stats
        elarion.effects.add(EventHorizonBuff(owner=elarion))

        elarion.heartseeker_barrage.cooldown = 20.0
        elarion.heartseeker_barrage.charges = 0

        # 1 enemy → 1 HWA hit per cast
        elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)

        assert elarion.heartseeker_barrage.cooldown == pytest.approx(19.5)

    def test_barrage_reduces_volley_cd(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """Each Barrage tick during EventHorizon reduces Volley CD by 1.0s.
        advance_time(0.0) processes first tick at t=0 only.
        """
        elarion = unit_elarion__zero_stats
        elarion.effects.add(EventHorizonBuff(owner=elarion))

        elarion.volley.cooldown = 30.0
        elarion.volley.charges = 0

        elarion.heartseeker_barrage._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)

        assert elarion.volley.cooldown == pytest.approx(29.0)

    def test_focus_cost_halved(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """EventHorizonBuff halves the focus cost of all abilities. Focus deducted synchronously."""
        elarion = unit_elarion__zero_stats

        elarion.effects.add(EventHorizonBuff(owner=elarion))

        focus_before = elarion.focus
        # CelestialShot base cost=15 → halved; ceil(15 * 0.5) = 8
        elarion.celestial_shot._pay_cost_for_cast(state_no_procs__st.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 8)


class TestFinalCrescendo:
    """4th HWA cast has 2x damage and 7 secondary targets."""

    @pytest.fixture
    def state_8e(self) -> tuple[State, Elarion, list[Enemy]]:
        enemies = [Enemy() for _ in range(8)]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        return state, elarion, enemies

    def test_activates_on_fourth_cast(self, state_8e: tuple[State, Elarion, list[Enemy]]) -> None:
        """First 3 HWA casts accumulate stacks; 4th cast triggers FC (2x dmg, 7 secondaries)."""
        state, elarion, enemies = state_8e
        fc_aura = FinalCrescendo(owner=elarion)
        elarion.effects.add(fc_aura)

        damages_per_cast: list[list[AbilityDamage]] = []
        for _ in range(4):
            cast_damages: list[AbilityDamage] = []
            state.bus.subscribe(
                AbilityDamage,
                lambda e, d=cast_damages: d.append(e),
                owner=cast_damages,  # required for unsubscribe_all to work
            )
            elarion.highwind_arrow._do_cast(enemies[0])
            state.advance_time(0.0)
            state.bus.unsubscribe_all(cast_damages)
            damages_per_cast.append(cast_damages)

        # Casts 1-3: normal HWA → 1 main + min(2, 7) = 3 hits each
        for i in range(3):
            hwa_hits = [e for e in damages_per_cast[i] if e.damage_source is elarion.highwind_arrow]
            assert len(hwa_hits) == 3, f"Cast {i + 1} should have 3 HWA hits, got {len(hwa_hits)}"

        # Cast 4 (FC): 1 main + 7 secondary = 8 hits; main damage 2x normal
        fc_hwa_hits = [e for e in damages_per_cast[3] if e.damage_source is elarion.highwind_arrow]
        assert len(fc_hwa_hits) == 8

        normal_main = damages_per_cast[0][0].damage
        fc_main = fc_hwa_hits[0].damage
        assert fc_main == pytest.approx(normal_main * 2, rel=1e-5)

    def test_stacks_reset_after_trigger(self, state_8e: tuple[State, Elarion, list[Enemy]]) -> None:
        """After the 4th (FC) cast, stacks reset to 0."""
        state, elarion, enemies = state_8e
        fc_aura = FinalCrescendo(owner=elarion)
        elarion.effects.add(fc_aura)

        for idx in range(4):
            assert fc_aura.stacks == idx
            elarion.highwind_arrow._do_cast(enemies[0])
            state.step()

        assert fc_aura.stacks == 0


class TestLethalShots:
    """LethalShots: 40% per-hit chance to add +100% crit_percent for that hit."""

    def test_proc_adds_crit(self) -> None:
        """LethalShots proc (roll < 0.40): HWA hit is a grievous crit, damage much higher.
        FixedRNG(0.0): PreDamageSnapshotUpdate roll = 0.0 < 0.40 → proc.
        """
        enemies = [Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        elarion.effects.add(LethalShots(owner=elarion))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.highwind_arrow._do_cast(enemies[0])
        state.step()

        # With +100% crit_percent (grievous): damage = avg * (1 + 1.0) = avg * 2.0
        base_avg = elarion.highwind_arrow.average_damage * 1000.0 / 1000.0  # main_stat=1000
        expected_grievous = base_avg * (1 + 1.0)  # crit_percent=1.0 (added by LethalShots)
        assert damages[0].damage == pytest.approx(expected_grievous, rel=1e-6)

    def test_no_proc_normal_damage(self) -> None:
        """LethalShots no proc (roll >= 0.40): HWA damage is normal (no crit).
        FixedRNG(0.5): roll=0.5 >= 0.40 → no proc; crit_percent=0 → no crit.
        """
        enemies = [Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.5))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        elarion.effects.add(LethalShots(owner=elarion))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.highwind_arrow._do_cast(enemies[0])
        state.step()

        base_avg = elarion.highwind_arrow.average_damage * 1000.0 / 1000.0
        assert damages[0].damage == pytest.approx(base_avg, rel=1e-6)


class TestShimmer:
    """Shimmer (Cloak legendary): +10% per stack via HighwindAppliesShimmerEffect, max 2 stacks."""

    def test_stacks_increase_damage(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """Shimmer: 1 stack → +10% damage. Applied on HWA hit via HighwindAppliesShimmerEffect.
        Shimmer applied after first hit (via AbilityDamage handler), active for second hit.
        Use advance_time(0.0) to avoid Shimmer expiry at t=9.
        """
        elarion = unit_elarion__zero_stats
        elarion.effects.add(HighwindAppliesShimmerEffect(owner=elarion))

        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        # First HWA cast: no Shimmer yet → base damage, Shimmer applied after hit
        elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)
        first_hit = damages[-1].damage

        # Second HWA cast: 1 Shimmer stack active (+10%)
        elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)
        second_hit = [e for e in damages if e.damage_source is elarion.highwind_arrow][-1].damage

        assert second_hit == pytest.approx(first_hit * 1.10, rel=1e-6)

    def test_caps_at_two_stacks(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """After 2+ applications, Shimmer stays at 2 stacks (max_stacks=2).
        Use advance_time(0.0) to avoid expiry at t=9 that would remove Shimmer.
        """
        elarion = unit_elarion__zero_stats
        elarion.effects.add(HighwindAppliesShimmerEffect(owner=elarion))

        for _ in range(3):
            elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
            state_no_procs__st.advance_time(0.0)

        shimmer = state_no_procs__st.enemies[0].effects.get(Shimmer)
        assert shimmer is not None
        assert isinstance(shimmer, Shimmer)
        assert shimmer.stacks == 2

    def test_second_application_renews_duration(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """A second Shimmer application before expiry fuses and renews duration."""
        elarion = unit_elarion__zero_stats
        elarion.effects.add(HighwindAppliesShimmerEffect(owner=elarion))

        # Apply first Shimmer
        elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)

        shimmer_1 = state_no_procs__st.enemies[0].effects.get(Shimmer)
        assert isinstance(shimmer_1, Shimmer)

        # Advance time partway (Shimmer duration=9s, so still active at t=5)
        state_no_procs__st.advance_time(5.0)

        # Apply second Shimmer (fuses: stacks up to 2, duration renewed to 9s from t=5)
        elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(0.0)

        shimmer_2 = state_no_procs__st.enemies[0].effects.get(Shimmer)
        assert shimmer_2 is not None
        assert shimmer_2.stacks == 2
        assert shimmer_2.duration == pytest.approx(9.0, abs=0.01)
