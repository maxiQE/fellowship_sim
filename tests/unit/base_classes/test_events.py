# Unit tests for base_classes/events.py

import pytest

from fellowship_sim.base_classes import Effect, Entity, State
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    ComputeCooldownReduction,
    ComputeFinalStats,
    EffectApplied,
    EventBus,
)
from fellowship_sim.base_classes.stats import (
    CritScoreAdditive,
    MainStatAdditiveCharacter,
    RawStatsFromScores,
    secondary_stat_percent_from_score,
)
from fellowship_sim.elarion.entity import Elarion


class TestComputeCooldownReductionResolve:
    @staticmethod
    def _cdr(**kwargs: list[float]) -> ComputeCooldownReduction:
        return ComputeCooldownReduction(ability=None, owner=None, time=0.0, **kwargs)  # ty:ignore[invalid-argument-type]

    def test_no_modifiers_returns_one(self) -> None:
        assert self._cdr().resolve() == pytest.approx(1.0)

    def test_cda_only(self) -> None:
        # (1 + 0.3) = 1.3
        assert self._cdr(cda_modifiers=[0.3]).resolve() == pytest.approx(1.3)

    def test_cdr_only(self) -> None:
        # 1 * 1.5 = 1.5
        assert self._cdr(cdr_modifiers=[1.5]).resolve() == pytest.approx(1.5)

    def test_cda_and_cdr_multiply(self) -> None:
        # (1 + 0.3) * 2.0 = 2.6
        assert self._cdr(cda_modifiers=[0.3], cdr_modifiers=[2.0]).resolve() == pytest.approx(2.6)

    def test_multiple_cda_stack_additively(self) -> None:
        # (1 + 0.1 + 0.2) = 1.3
        assert self._cdr(cda_modifiers=[0.1, 0.2]).resolve() == pytest.approx(1.3)

    def test_multiple_cdr_stack_multiplicatively(self) -> None:
        # 2.0 * 1.5 = 3.0
        assert self._cdr(cdr_modifiers=[2.0, 1.5]).resolve() == pytest.approx(3.0)


class TestEventBusOwnerUnsubscribe:
    def test_event_bus_owner_unsubscribe(self) -> None:
        bus = EventBus()
        entity = Entity()
        effect = Effect(owner=entity)
        owner_a = object()
        owner_b = object()
        calls: list[str] = []

        def handler_a(event: EffectApplied) -> None:
            calls.append("a")

        def handler_b(event: EffectApplied) -> None:
            calls.append("b")

        bus.subscribe(EffectApplied, handler_a, owner=owner_a)
        bus.subscribe(EffectApplied, handler_b, owner=owner_b)
        bus.unsubscribe_all(owner=owner_a)
        bus.emit(EffectApplied(effect=effect, target=entity, time=0.0))

        assert calls == ["b"]


class TestComputeFinalStats:
    def test_compute_final_stats_collects_modifiers_via_bus(
        self,
        unit_elarion__zero_stats: Elarion,
        state_no_procs__st: State,
    ) -> None:
        player = unit_elarion__zero_stats

        def handler(event: ComputeFinalStats) -> None:
            event.modifiers.append(MainStatAdditiveCharacter(value=50))

        state_no_procs__st.bus.subscribe(ComputeFinalStats, handler)
        event = ComputeFinalStats(owner=player, raw_stats=player.raw_stats)
        state_no_procs__st.bus.emit(event)

        mutable = player.raw_stats.to_mutable_stats()
        for m in event.modifiers:
            m.apply(mutable)
        assert mutable.finalize().main_stat == pytest.approx(1050.0)

    def test_compute_final_stats_collects_score_modifiers_via_bus(
        self,
        state_no_procs__st: State,
    ) -> None:
        raw = RawStatsFromScores(main_stat=1000.0, crit_score=500)
        player = Elarion(raw_stats=raw)
        state_no_procs__st.character = player

        def handler(event: ComputeFinalStats) -> None:
            event.modifiers.append(CritScoreAdditive(value=100))

        state_no_procs__st.bus.subscribe(ComputeFinalStats, handler)
        event = ComputeFinalStats(owner=player, raw_stats=raw)
        state_no_procs__st.bus.emit(event)

        mutable = raw.to_mutable_stats()
        for m in event.modifiers:
            m.apply(mutable)
        assert mutable.finalize().crit_percent == pytest.approx(secondary_stat_percent_from_score(600))


class TestEventTimeTagging:
    """Events capture state.time at construction via default_factory."""

    def test_effect_applied_captures_time(self, state_no_procs__st: State) -> None:
        state_no_procs__st.time = 5.0
        entity = Entity()
        effect = Effect(owner=entity)
        event = EffectApplied(effect=effect, target=entity)
        assert event.time == pytest.approx(5.0)

    def test_effect_applied_different_times(self, state_no_procs__st: State) -> None:
        entity = Entity()
        effect = Effect(owner=entity)
        state_no_procs__st.time = 3.0
        e1 = EffectApplied(effect=effect, target=entity)
        state_no_procs__st.time = 12.5
        e2 = EffectApplied(effect=effect, target=entity)
        assert e1.time == pytest.approx(3.0)
        assert e2.time == pytest.approx(12.5)

    def test_ability_damage_captures_time(self, state_no_procs__st: State) -> None:
        state_no_procs__st.time = 7.25
        entity = Entity()
        event = AbilityDamage(
            damage_source=None,  # ty:ignore[invalid-argument-type]
            owner=None,  # ty:ignore[invalid-argument-type]
            target=entity,
            is_crit=False,
            is_grievous_crit=False,
            damage=100.0,
        )
        assert event.time == pytest.approx(7.25)

    def test_ability_cast_success_captures_time(self, state_no_procs__st: State) -> None:
        state_no_procs__st.time = 2.0
        entity = Entity()
        event = AbilityCastSuccess(
            ability=None,  # ty:ignore[invalid-argument-type]
            owner=None,  # ty:ignore[invalid-argument-type]
            target=entity,
        )
        assert event.time == pytest.approx(2.0)

    def test_explicit_time_overrides_factory(self, state_no_procs__st: State) -> None:
        state_no_procs__st.time = 99.0
        entity = Entity()
        effect = Effect(owner=entity)
        event = EffectApplied(effect=effect, target=entity, time=1.0)
        assert event.time == pytest.approx(1.0)
