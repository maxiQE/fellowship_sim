# Unit tests for simulation/rotation.py

from dataclasses import dataclass, field

from fellowship_sim.base_classes import State
from fellowship_sim.base_classes.ability import Ability
from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.simulation.rotation import Optional, PriorityList


@dataclass(kw_only=True)
class _StubAbility(Ability[Elarion]):
    """Instant-cast, zero-downtime ability."""

    base_player_downtime: float = field(default=0.0, init=False)

    def _do_cast(self, target: Entity) -> None:
        pass


def _not_castable(ability: _StubAbility) -> _StubAbility:
    """Mark a stub ability as having no charges and a non-zero cooldown."""
    ability.charges = 0
    ability.cooldown = 999.0
    return ability


class TestOptional:
    """Optional: gate an ability or callable behind a condition."""

    def test_condition_false__does_not_call_element(self, state_always_procs__st: State) -> None:
        """When the condition is False, the element callable is never invoked and None is returned."""
        called: list[bool] = []

        def elem(s: State) -> Ability | None:
            called.append(True)
            return None

        opt = Optional(element=elem, condition=lambda s: False)
        assert opt(state_always_procs__st) is None
        assert called == []

    def test_condition_true_callable_returns_ability(self, unit_elarion__zero_stats: Elarion) -> None:
        """When condition is True and the callable returns an Ability, Optional returns it."""
        ability = _StubAbility(owner=unit_elarion__zero_stats)
        opt = Optional(element=lambda s: ability, condition=lambda s: True)
        assert opt(unit_elarion__zero_stats.state) is ability

    def test_condition_true_callable_returns_none(self, state_always_procs__st: State) -> None:
        """When condition is True but the callable returns None, Optional returns None."""
        opt = Optional(element=lambda s: None, condition=lambda s: True)
        assert opt(state_always_procs__st) is None

    def test_condition_true_ability_not_castable__returns_none(
        self, unit_elarion__zero_stats: Elarion
    ) -> None:
        """When condition is True but the Ability cannot cast, returns None."""
        ability = _not_castable(_StubAbility(owner=unit_elarion__zero_stats))
        opt = Optional(element=ability, condition=lambda s: True)
        assert opt(unit_elarion__zero_stats.state) is None

    def test_condition_true_ability_castable__returns_ability(
        self, unit_elarion__zero_stats: Elarion
    ) -> None:
        """When condition is True and the Ability can cast, it is returned."""
        ability = _StubAbility(owner=unit_elarion__zero_stats)
        assert ability.can_cast()
        opt = Optional(element=ability, condition=lambda s: True)
        assert opt(unit_elarion__zero_stats.state) is ability


class TestPriorityList:
    """PriorityList: try each element in order, return the first non-None result."""

    def test_empty_list__returns_none(self, state_always_procs__st: State) -> None:
        """An empty PriorityList always returns None."""
        assert PriorityList(element_list=[])(state_always_procs__st) is None

    def test_first_ability_castable__returns_it_without_trying_second(
        self, unit_elarion__zero_stats: Elarion
    ) -> None:
        """The first castable Ability is returned; the second is not tried."""
        a1 = _StubAbility(owner=unit_elarion__zero_stats)
        a2 = _StubAbility(owner=unit_elarion__zero_stats)
        assert PriorityList(element_list=[a1, a2])(unit_elarion__zero_stats.state) is a1

    def test_first_ability_not_castable__skips_to_second(
        self, unit_elarion__zero_stats: Elarion
    ) -> None:
        """A non-castable Ability is skipped; the next castable one is returned."""
        a1 = _not_castable(_StubAbility(owner=unit_elarion__zero_stats))
        a2 = _StubAbility(owner=unit_elarion__zero_stats)
        assert PriorityList(element_list=[a1, a2])(unit_elarion__zero_stats.state) is a2

    def test_no_ability_castable__returns_none(
        self, unit_elarion__zero_stats: Elarion
    ) -> None:
        """Returns None when all Abilities have no charges."""
        a1 = _not_castable(_StubAbility(owner=unit_elarion__zero_stats))
        a2 = _not_castable(_StubAbility(owner=unit_elarion__zero_stats))
        assert PriorityList(element_list=[a1, a2])(unit_elarion__zero_stats.state) is None

    def test_callable_returns_ability__stops(self, unit_elarion__zero_stats: Elarion) -> None:
        """A callable that returns an Ability stops iteration and returns it."""
        calls: list[int] = []
        ability = _StubAbility(owner=unit_elarion__zero_stats)

        def first(s: State) -> Ability | None:
            calls.append(1)
            return ability

        def second(s: State) -> Ability | None:
            calls.append(2)
            return ability

        result = PriorityList(element_list=[first, second])(unit_elarion__zero_stats.state)
        assert result is ability
        assert calls == [1]

    def test_callable_returns_none__tries_next(self, unit_elarion__zero_stats: Elarion) -> None:
        """A callable that returns None causes the next element to be tried."""
        calls: list[int] = []
        ability = _StubAbility(owner=unit_elarion__zero_stats)

        def first(s: State) -> Ability | None:
            calls.append(1)
            return None

        def second(s: State) -> Ability | None:
            calls.append(2)
            return ability

        result = PriorityList(element_list=[first, second])(unit_elarion__zero_stats.state)
        assert result is ability
        assert calls == [1, 2]

    def test_mixed_not_castable_ability_then_callable(
        self, unit_elarion__zero_stats: Elarion
    ) -> None:
        """A non-castable Ability is skipped; the subsequent callable is reached."""
        a = _not_castable(_StubAbility(owner=unit_elarion__zero_stats))
        ability = _StubAbility(owner=unit_elarion__zero_stats)
        called: list[bool] = []

        def fallback(s: State) -> Ability | None:
            called.append(True)
            return ability

        result = PriorityList(element_list=[a, fallback])(unit_elarion__zero_stats.state)
        assert result is ability
        assert called == [True]
