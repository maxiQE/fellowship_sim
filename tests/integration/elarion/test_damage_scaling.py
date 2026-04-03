"""Integration tests — stat scaling formula for all damage sources.

Formula (grievous crit, crit_percent >= 1.0):
    damage = base_damage * main_stat/1000 * (1 + expertise_percent) * (1 + crit_percent)

crit_percent > 1.0 makes the crit roll deterministic (grievous path bypasses the RNG),
so the formula is exact. All four stat triplets have crit_percent > 1.0.
Haste is fixed at 0 to decouple per-tick damage from tick count.
"""

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.ability import (
    HeartseekerBarrage,
    LunarlightSalvo,
    Volley,
)
from fellowship_sim.elarion.buff import (
    EmpoweredMultishotChargeBuff,
    FerventSupremacyBuff,
    SkystriderSupremacyBuff,
)
from fellowship_sim.elarion.effect import LunarlightMarkEffect
from fellowship_sim.elarion.entity import Elarion
from tests.integration.fixtures import FixedRNG, compute_expected_damage, compute_expected_damage__with_haste_scaling

STAT_TRIPLETS = [
    (1000.0, 0.00, 1.1),
    (1500.0, 0.05, 1.2),
    (2000.0, 0.10, 1.5),
    (1200.0, 0.20, 1.3),
]


class TestFocusedShotDamageScaling:
    """FocusedShot: damage = base * main_stat/1000 * (1 + expertise) * (1 + crit)."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Single hit matches the grievous-crit damage formula."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()

        expected = compute_expected_damage(
            base_damage=elarion.focused_shot.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 1
        assert damages[0].damage == pytest.approx(expected, rel=1e-6)


class TestCelestialShotDamageScaling:
    """CelestialShot: damage = base * main_stat/1000 * (1 + expertise) * (1 + crit)."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Single hit matches the grievous-crit damage formula."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        elarion.celestial_shot._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()

        expected = compute_expected_damage(
            base_damage=elarion.celestial_shot.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 1
        assert damages[0].damage == pytest.approx(expected, rel=1e-6)


class TestMultishotDamageScaling:
    """Multishot: main and secondary both apply the same formula (no secondary multiplier)."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_main_and_secondary_damage_formula(
        self, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Both hits match the grievous-crit formula (2 enemies → main + 1 secondary)."""
        enemies = [Enemy(), Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state.character = elarion
        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.multishot.charges = 1
        elarion.multishot._do_cast(enemies[0])
        state.step()

        expected = compute_expected_damage(
            base_damage=elarion.multishot.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 2
        assert damages[0].damage == pytest.approx(expected, rel=1e-6)
        assert damages[1].damage == pytest.approx(expected, rel=1e-6)

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    @pytest.mark.parametrize(
        "provider_class,provider_damage_multiplier",
        [
            (SkystriderSupremacyBuff, 1.0),
            (FerventSupremacyBuff, 1.25),
            (EmpoweredMultishotChargeBuff, 1.0),
        ],
    )
    def test_focused_expanse_applies_1_2x_to_all_providers(
        self,
        main_stat: float,
        expertise_percent: float,
        crit_percent: float,
        provider_class: type[SkystriderSupremacyBuff] | type[FerventSupremacyBuff] | type[EmpoweredMultishotChargeBuff],
        provider_damage_multiplier: float,
    ) -> None:
        """With FocusedExpanse active, each provider's per-arrow damage is multiplied by
        1.2 × provider_damage_multiplier. With 1 enemy, all 3 arrows land on the main target."""
        enemies = [Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state.character = elarion
        elarion.multishot.empowered_ms_bonus_damage = 1.2
        elarion.effects.add(provider_class(owner=elarion))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.multishot._do_cast(enemies[0])
        state.step()

        expected = compute_expected_damage(
            base_damage=elarion.multishot.average_damage * 1.2 * provider_damage_multiplier,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 3
        assert all(d.damage == pytest.approx(expected, rel=1e-6) for d in damages)


class TestHighwindArrowDamageScaling:
    """HighwindArrow: main at 100%, secondary at 70%."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_main_target_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Main hit matches the grievous-crit formula at 100%."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        elarion.highwind_arrow._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()

        expected = compute_expected_damage(
            base_damage=elarion.highwind_arrow.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 1
        assert damages[0].damage == pytest.approx(expected, rel=1e-6)

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_secondary_target_at_70_percent(
        self, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Secondary hit matches the formula applied to base * secondary_damage_multiplier."""
        enemies = [Enemy(), Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state.character = elarion
        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.highwind_arrow._do_cast(enemies[0])
        state.step()

        expected_main = compute_expected_damage(
            base_damage=elarion.highwind_arrow.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        expected_secondary = compute_expected_damage(
            base_damage=elarion.highwind_arrow.average_damage * elarion.highwind_arrow.secondary_damage_multiplier,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 2
        assert damages[0].damage == pytest.approx(expected_main, rel=1e-6)
        assert damages[1].damage == pytest.approx(expected_secondary, rel=1e-6)


class TestHeartseekerBarrageDamageScaling:
    """HeartseekerBarrage: per-tick damage matches the formula (haste=0, 10 ticks)."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_per_tick_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Each tick matches the grievous-crit formula; 10 ticks at haste=0."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: damages.append(e) if isinstance(e.damage_source, HeartseekerBarrage) else None,
        )

        elarion.heartseeker_barrage._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(2.1)  # haste=0 → 10 ticks over 2s

        expected_tick = compute_expected_damage(
            base_damage=elarion.heartseeker_barrage.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 10
        assert damages[0].damage == pytest.approx(expected_tick, rel=1e-6)

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    @pytest.mark.parametrize("haste_percent", [0.0, 0.2, 0.5])
    def test_total_damage_formula(
        self,
        state_no_procs__st: State,
        main_stat: float,
        expertise_percent: float,
        crit_percent: float,
        haste_percent: float,
    ) -> None:
        """Each tick matches the grievous-crit formula; 10 ticks at haste=0."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
                haste_percent=haste_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: damages.append(e) if isinstance(e.damage_source, HeartseekerBarrage) else None,
        )

        elarion.heartseeker_barrage._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(2.1)  # haste=0 → 10 ticks over 2s

        base_number_of_ticks = 10
        expected_tick = base_number_of_ticks * compute_expected_damage__with_haste_scaling(
            base_damage=elarion.heartseeker_barrage.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
            haste_percent=haste_percent,
        )

        assert len(damages) == round(10 * (1 + haste_percent))
        assert sum(elem.damage for elem in damages) == pytest.approx(expected_tick, rel=1e-6)


class TestVolleyDamageScaling:
    """Volley: per-tick damage matches the formula (haste=0, first tick)."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_per_tick_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """First tick matches the grievous-crit formula."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: damages.append(e) if isinstance(e.damage_source, Volley) else None,
        )

        elarion.volley._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(10)

        expected_tick = compute_expected_damage(
            base_damage=elarion.volley.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        base_number_of_ticks = 9

        assert len(damages) == base_number_of_ticks
        assert damages[0].damage == pytest.approx(expected_tick, rel=1e-6)

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    @pytest.mark.parametrize("haste_percent", [0.0, 0.25, 0.5])
    def test_total_damage_formula(
        self,
        state_no_procs__st: State,
        main_stat: float,
        expertise_percent: float,
        crit_percent: float,
        haste_percent: float,
    ) -> None:
        """First tick matches the grievous-crit formula."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
                haste_percent=haste_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: damages.append(e) if isinstance(e.damage_source, Volley) else None,
        )

        elarion.volley._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(10)

        base_number_of_ticks = 9
        expected_number_of_hits = 1 + int(8 * (1 + haste_percent))
        expected_total = expected_number_of_hits * compute_expected_damage(
            base_damage=elarion.volley.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )

        assert len(damages) == expected_number_of_hits
        assert sum(elem.damage for elem in damages) == pytest.approx(expected_total, rel=1e-6)


class TestLunarlightSalvoDamageScaling:
    """LunarlightSalvo: direct cast and mark-proc, both snapshot stats at trigger time."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_direct_cast_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Direct _do_cast matches the grievous-crit formula."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        elarion._lunarlight_salvo._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()

        expected = compute_expected_damage(
            base_damage=elarion._lunarlight_salvo.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 1
        assert damages[0].damage == pytest.approx(expected, rel=1e-6)

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_via_mark_proc_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Apply a mark, hit the target → mark procs → salvo fires at current stats."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        state_no_procs__st.enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        # Grievous crit (crit > 1.0) → is_crit=True → proc_chance=0.5; FixedRNG(0.0) → procs
        elarion.focused_shot._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        expected_salvo = compute_expected_damage(
            base_damage=elarion._lunarlight_salvo.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(salvo_hits) == 1
        assert salvo_hits[0].damage == pytest.approx(expected_salvo, rel=1e-6)

    def test_snapshots_at_trigger_time(self) -> None:
        """Salvo damage reflects stats at the moment it fires, not at mark application."""
        main_stat_initial = 1000.0
        main_stat_at_trigger = 2000.0
        expertise = 0.0
        crit = 1.2  # grievous

        enemies = [Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat_initial,
                crit_percent=crit,
                expertise_percent=expertise,
            )
        )
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        # Change stats before the hit occurs (simulates stat change between mark and trigger)
        elarion.raw_stats = RawStatsFromPercents(
            main_stat=main_stat_at_trigger,
            crit_percent=crit,
            expertise_percent=expertise,
        )
        elarion._recalculate_stats()

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 1
        # Salvo snapshots at trigger time → uses main_stat_at_trigger
        expected = compute_expected_damage(
            base_damage=elarion._lunarlight_salvo.average_damage,
            main_stat=main_stat_at_trigger,
            expertise_percent=expertise,
            crit_percent=crit,
        )
        assert salvo_hits[0].damage == pytest.approx(expected, rel=1e-6)


class TestLunarlightExplosionDamageScaling:
    """LunarlightExplosion: directly called via _do_cast (1 enemy = 1 hit)."""

    @pytest.mark.parametrize("main_stat,expertise_percent,crit_percent", STAT_TRIPLETS)
    def test_direct_cast_damage_formula(
        self, state_no_procs__st: State, main_stat: float, expertise_percent: float, crit_percent: float
    ) -> None:
        """Single hit matches the grievous-crit formula."""
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                crit_percent=crit_percent,
                expertise_percent=expertise_percent,
            )
        )
        state_no_procs__st.character = elarion
        damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(AbilityDamage, damages.append)

        elarion._lunarlight_explosion._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.step()

        expected = compute_expected_damage(
            base_damage=elarion._lunarlight_explosion.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        assert len(damages) == 1
        assert damages[0].damage == pytest.approx(expected, rel=1e-6)
