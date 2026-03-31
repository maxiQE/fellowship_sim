# Unit tests for base_classes/effect.py

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.effect import Buff, DuplicateEffectError, Effect
from fellowship_sim.base_classes.stats import (
    HastePercentAdditive,
    MainStatAdditiveMultiplierCharacter,
    StatModifier,
)
from fellowship_sim.elarion.entity import Elarion


@dataclass(kw_only=True)
class _DummyEffect(Effect):
    name: str = "dummy"
    duration: float = float("inf")


@dataclass(kw_only=True)
class _StackEffect(Effect):
    name: str = "s"
    duration: float = 10.0
    max_stacks: int = 3


@dataclass(kw_only=True)
class _HasteBuff(Buff):
    name: str = "test_haste"
    duration: float = 10.0
    bonus: float

    def stat_modifiers(self) -> list[StatModifier]:
        return [HastePercentAdditive(value=self.bonus)]


@dataclass(kw_only=True)
class _MainStatBuff(Buff):
    name: str = "test_main_stat"
    duration: float = 10.0
    value: float

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatAdditiveMultiplierCharacter(value=self.value)]


class TestEffectCollection:
    def test_effect_collection_duplicate_raises(self, state_no_procs__st: State) -> None:
        entity = Entity()
        entity.effects.add(_DummyEffect(owner=entity, name="dup"))
        with pytest.raises(DuplicateEffectError):
            entity.effects.add(_DummyEffect(owner=entity, name="dup"))


class TestEffectExpiry:
    def test_effect_expires_via_queue(self, state_no_procs__st: State) -> None:
        entity = Entity()
        entity.effects.add(_DummyEffect(owner=entity, name="expire", duration=2.0))
        state_no_procs__st.advance_time(3.0)
        assert not entity.effects.has("expire")

    def test_effect_renewal_defers_expiry(self, state_no_procs__st: State) -> None:
        """Refreshing an effect cancels the stale expiry callback and schedules a new one."""
        entity = Entity()
        entity.effects.add(_DummyEffect(owner=entity, name="x", duration=2.0))  # expiry at t=2.0
        state_no_procs__st.advance_time(1.0)  # t=1.0, still alive

        entity.effects.add(_DummyEffect(owner=entity, name="x", duration=2.0))  # refresh → expiry at t=3.0
        state_no_procs__st.advance_time(1.5)  # t=2.5: old expiry (t=2.0) was stale
        assert entity.effects.has("x")

        state_no_procs__st.advance_time(1.0)  # t=3.5: new expiry (t=3.0) fires
        assert not entity.effects.has("x")

    def test_effect_renewal_merges_stacks(self, state_no_procs__st: State) -> None:
        entity = Entity()
        entity.effects.add(_StackEffect(owner=entity))  # stacks=1
        entity.effects.add(_StackEffect(owner=entity))  # stacks=2
        entity.effects.add(_StackEffect(owner=entity))  # stacks=3 (cap)
        entity.effects.add(_StackEffect(owner=entity))  # stacks stays at 3

        effect = entity.effects.get("s")
        assert effect is not None
        assert effect.stacks == 3


class TestBuff:
    def test_buff_apply_on_add(self, unit_elarion__zero_stats: Elarion) -> None:
        unit_elarion__zero_stats.effects.add(_HasteBuff(owner=unit_elarion__zero_stats, bonus=0.3))
        assert unit_elarion__zero_stats.stats.haste_percent == pytest.approx(0.3)

    def test_buff_raw_stats_unchanged(self, unit_elarion__zero_stats: Elarion) -> None:
        unit_elarion__zero_stats.effects.add(_HasteBuff(owner=unit_elarion__zero_stats, bonus=0.3))
        assert unit_elarion__zero_stats.raw_stats.haste_percent == pytest.approx(0.0)  # ty:ignore[unresolved-attribute]

    def test_buff_reverts_on_remove(self, unit_elarion__zero_stats: Elarion, state_no_procs__st: State) -> None:
        unit_elarion__zero_stats.effects.add(_HasteBuff(owner=unit_elarion__zero_stats, bonus=0.3))
        state_no_procs__st.advance_time(15.0)  # buff expires after 10s
        assert unit_elarion__zero_stats.stats.haste_percent == pytest.approx(0.0)

    def test_repeated_buff_no_accumulation(self, unit_elarion__zero_stats: Elarion, state_no_procs__st: State) -> None:
        """Applying and expiring the same buff 10 times leaves stats exactly at base."""
        for _ in range(10):
            unit_elarion__zero_stats.effects.add(_MainStatBuff(owner=unit_elarion__zero_stats, value=0.03))
            state_no_procs__st.advance_time(15.0)
        assert unit_elarion__zero_stats.stats.main_stat == pytest.approx(1000.0)

    def test_two_buffs_stack_additively(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        @dataclass(kw_only=True)
        class _SecondHasteBuff(Buff):
            name: str = "haste_2"
            duration: float = 10.0

            def stat_modifiers(self) -> list[StatModifier]:
                return [HastePercentAdditive(value=0.3)]

        player = setup_hasted_elarion(haste=0.1)
        player.effects.add(_HasteBuff(owner=player, bonus=0.2))
        player.effects.add(_SecondHasteBuff(owner=player))
        assert player.stats.haste_percent == pytest.approx(0.6)
