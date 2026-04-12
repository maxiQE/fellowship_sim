import pytest

from fellowship_sim.base_classes import AbilityDamage, Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.ability import HeartseekerBarrage
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.elarion.setup_effect import FocusedExpanseSetup, FusilladeSetup
from tests.conftest import FixedRNG


class TestCastTimes:
    """Each hasted ability's cast time equals base_cast_time / (1 + haste_percent).

    Exception: HeartseekerBarrage is a channel — its window is always base_cast_time (2.0s).
    """

    @pytest.fixture(params=[0.0, 0.2, 0.5])
    def haste_percent(self, request: pytest.FixtureRequest) -> float:
        return request.param  # type: ignore[no-any-return]

    @pytest.fixture
    def state(self) -> State:
        state = State(rng=FixedRNG(value=0.0))
        Enemy(state=state)
        return state

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
        ).finalize(state)

    def test_focused_shot(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """FocusedShot cast time is 1.5 / (1 + haste_percent)."""
        elarion.focused_shot.cast(state.enemies[0])
        assert state.time == pytest.approx(1.5 / (1 + haste_percent), abs=1e-9)

    def test_celestial_shot(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """CelestialShot cast time is 1.5 / (1 + haste_percent)."""
        elarion.celestial_shot.cast(state.enemies[0])
        assert state.time == pytest.approx(1.5 / (1 + haste_percent), abs=1e-9)

    def test_multishot(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """Multishot cast time is 1.5 / (1 + haste_percent).

        Multishot starts with 0 charges; SkystriderSupremacy (instant) empowers it.
        """
        elarion.skystrider_supremacy.cast(state.enemies[0])  # instant; empowers multishot
        elarion.multishot.cast(state.enemies[0])
        assert state.time == pytest.approx(1.5 / (1 + haste_percent), abs=1e-9)

    def test_highwind_arrow(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """HighwindArrow cast time is 2.0 / (1 + haste_percent)."""
        elarion.highwind_arrow.cast(state.enemies[0])
        assert state.time == pytest.approx(2.0 / (1 + haste_percent), abs=1e-9)

    def test_volley(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """Volley cast time is 1.5 / (1 + haste_percent)."""
        elarion.volley.cast(state.enemies[0])
        assert state.time == pytest.approx(1.5 / (1 + haste_percent), abs=1e-9)

    def test_heartseeker_barrage(self, state: State, elarion: Elarion) -> None:
        """HeartseekerBarrage is a channel: cast window is always base_cast_time (2.0s), haste-independent.

        Haste only affects tick rate (more hits fit in the window), not the window itself.
        """
        elarion.heartseeker_barrage.cast(state.enemies[0])
        assert state.time == pytest.approx(2.0, abs=1e-9)

    def test_cast_times__complex_rotation(self, state: State, elarion: Elarion) -> None:
        """Cast times accumulate correctly over a multi-ability rotation."""
        target = state.enemies[0]
        haste_percent = elarion.stats.haste_percent
        elarion.multishot.charges = 5

        # LLM is instant
        elarion.lunarlight_mark.cast(target)
        assert state.time == pytest.approx(0.0, abs=1e-9)

        # No haste scaling on barrage
        elarion.heartseeker_barrage.cast(target)
        assert state.time == pytest.approx(2.0, abs=1e-9)

        # HWA: hasted 2s cast
        elarion.highwind_arrow.cast(target)
        assert state.time == pytest.approx(2.0 + 2.0 / (1 + haste_percent), abs=1e-9)

        # MS: hasted 1.5 cast
        elarion.multishot.cast(target)
        assert state.time == pytest.approx(2.0 + (2.0 + 1.5) / (1 + haste_percent), abs=1e-9)

        # EH: hasted 0.7 cast
        elarion.event_horizon.cast(target)
        assert state.time == pytest.approx(2.0 + (2.0 + 1.5 + 0.7) / (1 + haste_percent), abs=1e-9)

        # haste modified by EH
        assert elarion.stats.haste_percent == haste_percent + 0.3

        reference_time = state.time
        haste_percent = elarion.stats.haste_percent

        # HWA: hasted 2s cast
        elarion.highwind_arrow.cast(target)
        assert state.time == pytest.approx(reference_time + 2.0 / (1 + haste_percent), abs=1e-9)

        # MS: hasted 1.5 cast
        elarion.multishot.cast(target)
        assert state.time == pytest.approx(reference_time + (2.0 + 1.5) / (1 + haste_percent), abs=1e-9)

        # wait for EH to drop
        elarion.wait(20)

        # haste modified by EH dropping
        assert elarion.stats.haste_percent == haste_percent - 0.3

        reference_time = state.time
        haste_percent = elarion.stats.haste_percent

        # HWA: hasted 2s cast
        elarion.highwind_arrow.cast(target)
        assert state.time == pytest.approx(reference_time + 2.0 / (1 + haste_percent), abs=1e-9)

        # MS: hasted 1.5 cast
        elarion.multishot.cast(target)
        assert state.time == pytest.approx(reference_time + (2.0 + 1.5) / (1 + haste_percent), abs=1e-9)


class TestComplexBreakpoints:
    @pytest.mark.parametrize(
        "haste, num_casts", [(0.0, 3), (0.124, 3), (0.126, 4), (0.49, 4), (0.51, 5), (0.874, 5), (0.876, 6)]
    )
    @pytest.mark.parametrize("has_fe", [False, True])
    def test_skystrider_supremacy_breakpoints(self, haste: float, num_casts: int, has_fe: bool) -> None:
        """Skysupremacy breakpoints: 3 hits normally, 4 at 12.5%, 5 at 50%, 6 at 87.5%.

        NB: these are probably impossible in-game since they require sending the first multishot immediately after the supremacy cast.
        """
        # Note the "no-crits" RNG
        state = State(rng=FixedRNG(value=1.0))
        Enemy(state=state)
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
        )
        if has_fe:
            setup.setup_effect_list.append(FocusedExpanseSetup())

        elarion = setup.finalize(state)

        elarion.multishot.charges = 0

        elarion.skystrider_supremacy.cast(target)

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        for _ in range(num_casts):
            elarion.multishot.cast(target)

        assert len(damages) == 3 * num_casts  # fire three arrows per cast
        assert all(
            event.damage == pytest.approx(elarion.multishot.average_damage * (1.25 if has_fe else 1.0))
            for event in damages
        )

        # No more empowered buff and no more charges
        with pytest.raises(AssertionError):
            elarion.multishot.cast(target)

    @pytest.mark.parametrize(
        "haste, remaining_gcd, remaining_cooldown, barrage_hit_count",
        [
            (0.0, 7, 9.172, 16),
            (0.06, 6, 8.018, 17),
            (0.14, 5, 6.814, 18),
            (0.22, 4, 5.609, 19),
            (0.30, 3, 4.404, 20),
            (0.38, 3, 3.199, 21),
            (0.46, 2, 1.994, 22),
            (0.54, 1, 0.790, 23),
            (0.62, 0, 0.0, 24),
        ],
    )
    def test_event_horizon_volley_reset_breakpoints(
        self, haste: float, remaining_gcd: int, remaining_cooldown: float, barrage_hit_count: int
    ) -> None:
        """Test how many GCDs are needed after a barrage to be able to cast volley again during EH.

        NB: with fusillade talent.
        Breakpoints are at when haste_percent + 30% (from EH) crosses the barrage breakpoints at 4% + every 8%:
        -  0% -> 30% -> 16
        -  6% -> 36% -> 17
        - 14% -> 44% -> 18
        - 22% -> 52% -> 19
        - 30% -> 60% -> 20
        - 38% -> 68% -> 21
        - 46% -> 76% -> 22
        - 54% -> 84% -> 23
        - 62% -> 92% -> 24

        NB: includes an approximation of the flight time of the barrage projectile and a small wait for that projectile to arrive.
        This is the observed CD at the end of the barrage cast.
        """
        state = State(rng=FixedRNG(value=1.0))
        Enemy(state=state)
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
        )
        setup.setup_effect_list.append(FusilladeSetup())
        elarion = setup.finalize(state)

        barrage_damages: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: barrage_damages.append(e) if isinstance(e.damage_source, HeartseekerBarrage) else None,
        )

        elarion.spirit_points = 100

        elarion.event_horizon.cast(target)
        elarion.volley.cast(target)
        elarion.heartseeker_barrage.cast(target)
        elarion.wait(0.06)

        hit_count = len(barrage_damages)
        assert hit_count == barrage_hit_count
        # NB: -1 because the final hit is still flying through the air at that point

        assert elarion.volley.cooldown == pytest.approx(remaining_cooldown, abs=0.01)

        for _ in range(remaining_gcd):
            assert elarion.volley.cooldown > 0
            elarion.focused_shot.cast(target)

        assert elarion.volley.cooldown == pytest.approx(0)
