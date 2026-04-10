from dataclasses import replace

import pytest

from fellowship_sim.base_classes import AbilityDamage, Enemy, State
from fellowship_sim.base_classes.events import SpiritProc
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.ability import HeartseekerBarrage
from fellowship_sim.elarion.effect import FinalCrescendo, ImpendingHeartseeker, Shimmer, VolleyEffect
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup
from tests.conftest import FixedRNG

_ZERO_STATS = RawStatsFromPercents(
    main_stat=1000.0,
    crit_percent=0.0,
    expertise_percent=0.0,
    haste_percent=0.0,
    spirit_percent=0.0,
)


class TestBootsLegendary:
    """Boots legendary: Volley base duration +2s; each Multishot cast extends active Volley by 0.5s."""

    @pytest.fixture(params=[0.0, 0.2, 0.5])
    def haste_percent(self, request: pytest.FixtureRequest) -> float:
        return request.param  # type: ignore[no-any-return]

    @pytest.fixture
    def state(self) -> State:
        return State(enemies=[Enemy()], rng=FixedRNG(value=0.0))

    @pytest.fixture
    def elarion(self, state: State, haste_percent: float) -> Elarion:
        return ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste_percent,
                spirit_percent=0.0,
            ),
            legendary="Boots",
        ).finalize(state)

    def test_volley_base_duration_increased_by_2s(self, state: State, elarion: Elarion) -> None:
        """Boots legendary adds 2s to Volley's base duration (8s → 10s)."""
        assert elarion.volley.duration == pytest.approx(10.0, abs=1e-6)

    def test_multishot_extends_active_volley(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """Each Multishot cast while Volley is active extends remaining duration by 0.5s.

        Multishot starts with 0 charges; SkystriderSupremacy (instant) empowers it.
        """
        target = state.enemies[0]
        elarion.skystrider_supremacy.cast(target)  # instant; empowers multishot
        elarion.volley.cast(target)

        volley_effect = VolleyEffect.get_volley(target)[0]
        duration_before = volley_effect.duration

        elarion.multishot.cast(target)

        multishot_cast_time = 1.5 / (1 + haste_percent)
        assert volley_effect.duration == pytest.approx(duration_before - multishot_cast_time + 0.5, abs=1e-6)

    def test_multishot_extends_active_volley__complex_ultimate(
        self, state: State, elarion: Elarion, haste_percent: float
    ) -> None:
        """Multiple Multishot casts each extend Volley by 0.5s, in a realistic scenario.

        This scenario mimics an ultimate window:
        - volley
        - barrage -> reset volley
        - volley
        - multishot spam
        """
        elarion.multishot.charges = 5
        elarion.skystrider_supremacy.is_fervent_supremacy = True
        elarion.spirit_points = 100

        target = state.enemies[0]

        elarion.skystrider_supremacy.cast(target)
        elarion.event_horizon.cast(target)
        elarion.skystrider_grace.cast(target)

        t1 = state.time
        elarion.volley.cast(target)
        elarion.heartseeker_barrage.cast(target)
        elarion.volley._reset_cooldown()

        t2 = state.time
        elarion.volley.cast(target)

        # empowered multishot
        for _ in range(4):
            assert elarion.multishot.is_empowered()
            elarion.multishot.cast(target)

        # normal multishot
        for _ in range(5):
            assert not elarion.multishot.is_empowered()
            elarion.multishot.cast(target)

        volleys = VolleyEffect.get_volley(target)

        # Duration = base_time (8) + boots extension (2) + 9 multishot casts * extension (0.5)
        assert state.time + volleys[0].duration == pytest.approx(t1 + 8 + 2 + 9 * 0.5)
        assert state.time + volleys[1].duration == pytest.approx(t2 + 8 + 2 + 9 * 0.5)


class TestNeckLegendary:
    """Neck legendary (Starstriker's Ascent): spirit proc has 50% chance to grant ImpendingHeartseeker."""

    @pytest.fixture
    def state(self) -> State:
        return State(enemies=[Enemy()], rng=FixedRNG(value=0.0))

    @pytest.fixture
    def elarion(self, state: State) -> Elarion:
        return ElarionSetup(raw_stats=_ZERO_STATS, legendary="Neck").finalize(state)

    def test_spirit_proc_applies_impending_heartseeker(self, state: State, elarion: Elarion) -> None:
        """RNG(0.0) < 0.5 proc_chance → ImpendingHeartseeker is granted on spirit proc."""
        state.bus.emit(SpiritProc(ability=elarion.celestial_shot, owner=elarion, resource_amount=15.0))
        assert isinstance(elarion.effects.get(ImpendingHeartseeker), ImpendingHeartseeker)

    def test_spirit_proc_no_buff_when_rng_fails(self) -> None:
        """RNG(1.0) >= 0.5 proc_chance → ImpendingHeartseeker is not granted."""
        state = State(enemies=[Enemy()], rng=FixedRNG(value=1.0))
        elarion = ElarionSetup(raw_stats=_ZERO_STATS, legendary="Neck").finalize(state)
        state.bus.emit(SpiritProc(ability=elarion.celestial_shot, owner=elarion, resource_amount=15.0))
        assert elarion.effects.get(ImpendingHeartseeker) is None

    def test_chained_neck_procs_on_barrage(self, state: State) -> None:
        """Getting both a spirit proc and a neck proc enables elarion to chain IHB."""
        elarion = ElarionSetup(raw_stats=replace(_ZERO_STATS, spirit_percent=0.25), legendary="Neck").finalize(state)
        # rng = SequenceRNG(values=[])
        # state.rng = rng

        target = state.enemies[0]

        barrage_damage: list[AbilityDamage] = []

        def record_barrage_damage(event: AbilityDamage) -> None:
            if isinstance(event.damage_source, HeartseekerBarrage):
                barrage_damage.append(event)

        state.bus.subscribe(AbilityDamage, record_barrage_damage)

        elarion.heartseeker_barrage.cast(target)
        elarion.wait(0.2)

        assert isinstance(elarion.effects.get(ImpendingHeartseeker), ImpendingHeartseeker)
        assert elarion.heartseeker_barrage.has_impending_barrage
        assert len(barrage_damage) == 10
        # all damage is critical -> 2 * base_damage
        assert all(
            elem.damage == pytest.approx(2 * elarion.heartseeker_barrage.average_damage) for elem in barrage_damage
        )

        barrage_damage = []
        elarion.heartseeker_barrage.cast(target)
        elarion.wait(0.2)

        assert isinstance(elarion.effects.get(ImpendingHeartseeker), ImpendingHeartseeker)
        assert elarion.heartseeker_barrage.has_impending_barrage
        assert len(barrage_damage) == 10
        assert all(
            elem.damage == pytest.approx(2 * elarion.heartseeker_barrage.average_damage * (1 + idx * 0.1))
            for idx, elem in enumerate(barrage_damage)
        )

        barrage_damage = []
        elarion.heartseeker_barrage.cast(target)
        elarion.wait(0.2)

        assert isinstance(elarion.effects.get(ImpendingHeartseeker), ImpendingHeartseeker)
        assert elarion.heartseeker_barrage.has_impending_barrage
        assert len(barrage_damage) == 10
        assert all(
            elem.damage == pytest.approx(2 * elarion.heartseeker_barrage.average_damage * (1 + idx * 0.1))
            for idx, elem in enumerate(barrage_damage)
        )


class TestCloakLegendary:
    """Cloak legendary: each HighwindArrow damage hit applies Shimmer debuff to the target."""

    @pytest.fixture
    def state(self) -> State:
        return State(enemies=[Enemy()], rng=FixedRNG(value=0.0))

    @pytest.fixture
    def elarion(self, state: State) -> Elarion:
        return ElarionSetup(raw_stats=_ZERO_STATS, legendary="Cloak").finalize(state)

    def test_highwind_arrow_applies_shimmer(self, state: State, elarion: Elarion) -> None:
        """Casting HighwindArrow applies Shimmer to the target."""
        target = state.enemies[0]
        elarion.highwind_arrow.cast(target)
        elarion.wait(0.2)
        assert isinstance(target.effects.get(Shimmer), Shimmer)

    def test_highwind_arrow_applies_shimmer__final_crescendo_interaction(self, state: State, elarion: Elarion) -> None:
        """Casting HighwindArrow from a FC HWA applies Shimmer to 8 enemies in a group of 12."""
        for _ in range(11):
            state.enemies.append(Enemy())
        assert state.num_enemies == 12

        final_crescendo = FinalCrescendo(owner=elarion)
        elarion.effects.add(final_crescendo)

        target = state.enemies[0]

        elarion.highwind_arrow.cast(target)
        elarion.wait(0.2)

        # 3 shimmer debuffs present after first cast
        assert len([e for e in state.enemies if e.effects.has(Shimmer)]) == 3

        elarion.highwind_arrow.cast(target)
        elarion.wait(0.2)
        elarion.highwind_arrow.cast(target)
        elarion.wait(0.2)

        # wait for shimmer debuff to expire and for hwa to recharge
        elarion.wait(20.0)

        assert final_crescendo.stacks == 3
        assert elarion.highwind_arrow.charges == 1
        assert elarion.highwind_arrow.has_final_crescendo_buff is True

        # no shimmer debuff present
        assert len([e for e in state.enemies if e.effects.has(Shimmer)]) == 0

        # final crescendo HWA
        elarion.highwind_arrow.cast(target)
        elarion.wait(0.2)

        assert len([e for e in state.enemies if e.effects.has(Shimmer)]) == 8
