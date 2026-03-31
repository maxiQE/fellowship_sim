# Top-level fixtures shared across all test types (unit, integration, functional)

from collections.abc import Callable

import pytest

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion


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


@pytest.fixture
def state_no_procs__st() -> State:
    entity = Entity()
    return State(enemies=[entity], rng=FixedRNG(value=0.0)).activate()


@pytest.fixture
def state_always_procs__st() -> State:
    entity = Entity()
    return State(enemies=[entity], rng=FixedRNG(value=1.0)).activate()


@pytest.fixture
def unit_elarion__zero_stats(state_no_procs__st: State) -> Elarion:
    player = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
    state_no_procs__st.character = player
    return player


@pytest.fixture
def setup_hasted_elarion(state_no_procs__st: State) -> Callable[..., Elarion]:
    def _factory(*, haste: float) -> Elarion:
        player = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=haste))
        state_no_procs__st.character = player
        return player

    return _factory
