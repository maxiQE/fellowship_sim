"""Shared utilities for integration tests."""

from collections.abc import Callable

from fellowship_sim.base_classes import State
from fellowship_sim.base_classes.events import AbilityDamage


class FixedRNG:
    """Fake RNG that always returns the same value, for fully deterministic tests."""

    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


class SequenceRNG:
    """Fake RNG that returns values from a fixed sequence, cycling when exhausted.

    Use 2.0 as a sentinel meaning 'never proc' (2.0 >= any realistic proc_chance).
    """

    def __init__(self, values: list[float]) -> None:
        self._values = values
        self._index = 0

    def random(self) -> float:
        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value


def count_hits(
    state: State,
    cast_fn: Callable[[], None],
    *,
    filter_fn: Callable[[AbilityDamage], bool] | None = None,
) -> list[AbilityDamage]:
    """Subscribe to AbilityDamage, run cast_fn + state.step(), return matching events.

    filter_fn: if provided, only events for which filter_fn(event) is True are collected.
    """
    damages: list[AbilityDamage] = []

    def _handler(event: AbilityDamage) -> None:
        if filter_fn is None or filter_fn(event):
            damages.append(event)

    state.bus.subscribe(AbilityDamage, _handler)
    cast_fn()
    state.step()
    return damages


def compute_expected_damage(
    *,
    base_damage: float,
    main_stat: float,
    expertise_percent: float,
    crit_percent: float,
) -> float:
    """Expected damage under the grievous-crit formula (crit_multiplier=1.0).

    Valid when crit_percent >= 1.0 (grievous range), which makes the crit roll
    deterministic — actual damage equals this formula exactly.
    """
    assert crit_percent >= 1, f"The formula is only appropriate for grievous crits but {crit_percent = }"
    return base_damage * main_stat / 1000 * (1 + expertise_percent) * (1 + crit_percent)


def compute_expected_damage__with_haste_scaling(
    *,
    base_damage: float,
    main_stat: float,
    expertise_percent: float,
    crit_percent: float,
    haste_percent: float,
) -> float:
    """Expected damage under the grievous-crit formula (crit_multiplier=1.0).

    Valid when crit_percent >= 1.0 (grievous range), which makes the crit roll
    deterministic — actual damage equals this formula exactly.
    """
    assert crit_percent >= 1, f"The formula is only appropriate for grievous crits but {crit_percent = }"
    return base_damage * main_stat / 1000 * (1 + expertise_percent) * (1 + crit_percent) * (1 + haste_percent)
