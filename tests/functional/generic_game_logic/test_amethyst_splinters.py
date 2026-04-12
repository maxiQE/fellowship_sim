import pytest

from fellowship_sim.base_classes import AbilityDamage, AbilityPeriodicDamage, Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.weapon_traits import AmethystSplintersDoT
from tests.conftest import FixedRNG

_CRIT_DAMAGE = 10_000.0


class TestAmethystSplinters:
    """Total DoT damage and tick rate for AmethystSplinters at various haste values."""

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
            master_trait="Amethyst Splinters",
        ).finalize(state)

    def _emit_crit(self, state: State, elarion: Elarion, damage: float = _CRIT_DAMAGE, is_dot: bool = False) -> None:
        if is_dot:
            state.bus.emit(
                AbilityPeriodicDamage(
                    damage_source=elarion.celestial_shot,
                    owner=elarion,
                    target=state.enemies[0],
                    is_crit=True,
                    is_grievous_crit=False,
                    damage=damage,
                )
            )
        else:
            state.bus.emit(
                AbilityDamage(
                    damage_source=elarion.celestial_shot,
                    owner=elarion,
                    target=state.enemies[0],
                    is_crit=True,
                    is_grievous_crit=False,
                    damage=damage,
                )
            )

    def test_total_damage_scales_with_haste(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """Total DoT damage equals crit_damage × 10% × (1 + haste_percent), regardless of haste."""
        ticks: list[float] = []

        def append_splinters_event(e: AbilityPeriodicDamage) -> None:
            if isinstance(e.damage_source, AmethystSplintersDoT):
                ticks.append(e.damage)

        state.bus.subscribe(AbilityPeriodicDamage, append_splinters_event)

        self._emit_crit(state=state, elarion=elarion)
        state.advance_time(8.5)

        expected = _CRIT_DAMAGE * 0.10 * (1 + haste_percent)
        assert sum(ticks) == pytest.approx(expected, rel=1e-6)

        self._emit_crit(state=state, elarion=elarion, is_dot=True)
        state.advance_time(8.5)

        expected = 2 * _CRIT_DAMAGE * 0.10 * (1 + haste_percent)
        assert sum(ticks) == pytest.approx(expected, rel=1e-6)

    def test_tick_rate_scales_with_haste(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """Tick interval equals 2s / (1 + haste_percent)."""
        timestamps: list[float] = []

        def append_splinters_event(e: AbilityPeriodicDamage) -> None:
            if isinstance(e.damage_source, AmethystSplintersDoT):
                timestamps.append(e.time)

        state.bus.subscribe(AbilityPeriodicDamage, append_splinters_event)

        self._emit_crit(state=state, elarion=elarion)
        state.advance_time(8.5)

        tick_time = 2.0 / (1 + haste_percent)
        # All intervals between regular ticks equal tick_time.
        # The last tick may be a partial (fires at expiry, shorter interval) — excluded.
        assert len(timestamps) >= 4
        for i in range(len(timestamps) - 2):
            assert timestamps[i + 1] - timestamps[i] == pytest.approx(tick_time, abs=1e-9)

        assert timestamps[-1] == pytest.approx(8.0, abs=1e-9)

    def test_tick_schedule_preserved_after_renewal(self, state: State, elarion: Elarion, haste_percent: float) -> None:
        """After a second crit renews the DoT mid-duration, the tick grid from t=0 is preserved."""
        time_second_crit = 6.12345

        timestamps: list[float] = []

        def append_splinters_event(e: AbilityPeriodicDamage) -> None:
            if isinstance(e.damage_source, AmethystSplintersDoT):
                timestamps.append(e.time)

        state.bus.subscribe(AbilityPeriodicDamage, append_splinters_event)

        self._emit_crit(state=state, elarion=elarion)
        state.schedule(
            time_delay=time_second_crit,
            callback=GenericTimedEvent(
                name="second crit",
                callback=lambda: self._emit_crit(state=state, elarion=elarion),
            ),
        )
        state.advance_time(20.0)

        tick_time = 2.0 / (1 + haste_percent)
        # All intervals between ticks equal tick_time.
        # The last tick may be partial (fires at expiry) — excluded.
        assert len(timestamps) >= 4
        for i in range(len(timestamps) - 2):
            assert timestamps[i + 1] - timestamps[i] == pytest.approx(tick_time, abs=1e-9)

        assert timestamps[-1] == pytest.approx(time_second_crit + 8.0, abs=1e-9)
