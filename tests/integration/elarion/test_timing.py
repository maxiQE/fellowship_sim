"""Integration tests — tick count, haste breakpoints, and Volley simultaneous stacking.

Volley tick count formula:  num_ticks = 1 + floor(duration / tick_time * (1 + haste))
                          = 1 + floor(8 * (1 + haste))   [duration=8, tick_time=1]

Barrage tick count formula: num_ticks = floor(cast_time / (tick_time / (1 + haste)) + epsilon)
                          = floor(10 * (1 + haste) + 0.01)  [cast_time=2, tick_time=0.2]

These create discrete breakpoints where a small haste change shifts total damage by one tick.
"""

from collections.abc import Callable

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.ability import HeartseekerBarrage, Volley
from fellowship_sim.elarion.effect import ImpendingHeartseeker, VolleyEffect
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup_effect import FusilladeSetup
from tests.integration.fixtures import FixedRNG, compute_expected_damage


class TestVolleyTickCount:
    """Volley fires 1 + floor(8 * (1 + haste)) ticks; rate is snapshot at cast time."""

    @pytest.mark.parametrize(
        "haste,expected_ticks",
        [
            (0.0, 9),  # 1 + floor(8*1.0) = 9
            (0.5, 13),  # 1 + floor(8*1.5) = 13
            (0.25, 11),  # 1 + floor(8*1.25) = 1 + floor(10) = 11
            (0.499, 12),  # 1 + floor(8*1.499) = 1 + floor(11.992) = 12  (just below 0.5)
            (0.5, 13),  # 1 + floor(8*1.499) = 1 + floor(11.992) = 12  (just below 0.5)
        ],
    )
    def test_tick_count(
        self, setup_hasted_elarion: Callable[..., Elarion], state_no_procs__st: State, haste: float, expected_ticks: int
    ) -> None:
        """Volley tick count matches 1 + floor(8 * (1 + haste)) for discrete haste values."""
        elarion = setup_hasted_elarion(haste=haste)
        volley_damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: volley_damages.append(e) if isinstance(e.damage_source, Volley) else None,
        )

        elarion.volley._do_cast(state_no_procs__st.enemies[0])
        state_no_procs__st.advance_time(9.0)  # covers all haste cases

        assert len(volley_damages) == expected_ticks

    def test_snapshot_haste_preserved(self) -> None:
        """Ticks fire at cast-time haste rate even if stats change after cast.

        Cast with haste=0.5 (13 ticks, tick_interval=0.667s).
        Haste at tick time does not affect tick scheduling — rate is baked in at cast.
        """
        enemies = [Enemy()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0))
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=0.5))
        state.character = elarion

        elarion.volley._do_cast(enemies[0])

        # Change haste to 0 after cast — tick_interval is already baked into VolleyEffect
        elarion.raw_stats = RawStatsFromPercents(main_stat=1000.0, haste_percent=0.0)
        elarion._recalculate_stats()

        volley_damages: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: volley_damages.append(e) if isinstance(e.damage_source, Volley) else None,
        )
        state.advance_time(9.0)

        # Still 13 ticks (snapshot preserved haste=0.5 at cast time)
        assert len(volley_damages) == 13


class TestHeartseekerBarrageTickCount:
    @pytest.mark.parametrize(
        "haste,expected_ticks",
        [
            (0.0, 10),
            (0.5, 15),
            (0.2, 12),
        ],
    )
    def test_tick_count(
        self, setup_hasted_elarion: Callable[..., Elarion], state_no_procs__st: State, haste: float, expected_ticks: int
    ) -> None:
        """Barrage breakpoints are at every 10%."""
        elarion = setup_hasted_elarion(haste=haste)
        barrage_damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: barrage_damages.append(e) if isinstance(e.damage_source, HeartseekerBarrage) else None,
        )

        elarion.heartseeker_barrage.cast(state_no_procs__st.enemies[0])

        assert len(barrage_damages) == expected_ticks

    @pytest.mark.parametrize(
        "haste,expected_ticks",
        [
            (0.0, 12),
            (0.04, 13),
            (0.12, 14),
            (0.2, 15),
        ],
    )
    def test_tick_count__with_fusillade(
        self, setup_hasted_elarion: Callable[..., Elarion], state_no_procs__st: State, haste: float, expected_ticks: int
    ) -> None:
        """With fusillade, barrage breakpoints at at 4% (13 hits) then every additional 8%."""
        elarion = setup_hasted_elarion(haste=haste)
        FusilladeSetup().apply(elarion, context=None)  # ty:ignore[invalid-argument-type]
        barrage_damages: list[AbilityDamage] = []
        state_no_procs__st.bus.subscribe(
            AbilityDamage,
            lambda e: barrage_damages.append(e) if isinstance(e.damage_source, HeartseekerBarrage) else None,
        )

        elarion.heartseeker_barrage.cast(state_no_procs__st.enemies[0])

        assert len(barrage_damages) == expected_ticks


class TestImpendingHeartseeker:
    """ImpendingHeartseeker ramps barrage damage by +10% per tick and resets CD on add."""

    @pytest.mark.parametrize(
        "main_stat,expertise_percent,crit_percent",
        [
            (1000.0, 0.00, 1.1),
            (1500.0, 0.10, 1.5),
        ],
    )
    def test_total_damage(self, main_stat: float, expertise_percent: float, crit_percent: float) -> None:
        """Total barrage damage with ImpendingHeartseeker ramp equals base_tick * 14.5.

        damage_step = 0.10 per tick: tick k has multiplier (1 + k * 0.10)
        At haste=0: 10 ticks (k=0..9)
        Total multiplier sum = sum(1 + k*0.10, k=0..9) = 10 + 0.1*45 = 14.5
        """
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
        elarion.effects.add(ImpendingHeartseeker(owner=elarion))

        barrage_damages: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: barrage_damages.append(e) if isinstance(e.damage_source, HeartseekerBarrage) else None,
        )

        elarion.heartseeker_barrage._do_cast(enemies[0])
        state.advance_time(2.1)

        base_tick_expected = compute_expected_damage(
            base_damage=elarion.heartseeker_barrage.average_damage,
            main_stat=main_stat,
            expertise_percent=expertise_percent,
            crit_percent=crit_percent,
        )
        expected_total = base_tick_expected * sum(1.0 + k * 0.10 for k in range(10))

        assert len(barrage_damages) == 10
        total_damage = sum(e.damage for e in barrage_damages)
        assert total_damage == pytest.approx(expected_total, rel=1e-5)

    def test_resets_barrage_cd(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """ImpendingHeartseeker.on_add resets HeartseekerBarrage cooldown."""
        elarion = unit_elarion__zero_stats

        elarion.heartseeker_barrage.cooldown = 20.0
        elarion.heartseeker_barrage.charges = 0

        elarion.effects.add(ImpendingHeartseeker(owner=elarion))

        assert elarion.heartseeker_barrage.cooldown == 0.0
        assert elarion.heartseeker_barrage.charges == elarion.heartseeker_barrage.max_charges


class TestVolleyStacking:
    """Two Volley instances can coexist and tick independently; each expires at its own time."""

    def test_two_instances_both_active_simultaneously(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """Cast Volley twice mid-duration → both VolleyEffect instances active on target."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.0)  # first tick only

        state.advance_time(3.0)  # advance partway (less than Volley duration=8s)

        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.0)  # process second volley's first tick only

        assert len(VolleyEffect.get_volley(state.enemies[0])) == 2

    def test_two_instances_each_tick_independently(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """With 2 simultaneous VolleyEffects, both fire their first tick when cast back-to-back."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        volley_hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: volley_hits.append(e) if isinstance(e.damage_source, Volley) else None,
        )

        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.5)
        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(0.0)  # second volley fires its first tick

        assert len(volley_hits) == 2

        state.advance_time(0.75)
        # t=1.25: volley 1 has fired twice, volley 2 has fired once
        assert len(volley_hits) == 3

        state.advance_time(0.5)
        # t=1.75: both have fired twice
        assert len(volley_hits) == 4

    def test_first_volley_expires_before_second(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """First Volley expires at ~t=8s; second (cast at t=3) expires at ~t=11s."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats

        elarion.volley._do_cast(state.enemies[0])
        state.advance_time(3.0)
        elarion.volley._do_cast(state.enemies[0])

        assert len(VolleyEffect.get_volley(state.enemies[0])) == 2

        # Advance past first Volley's expiry (t=8+eps), but before second's (t=11+eps)
        state.advance_time(5.5)  # now at t=8.5

        assert len(VolleyEffect.get_volley(state.enemies[0])) == 1
