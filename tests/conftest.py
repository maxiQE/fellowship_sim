from collections.abc import Callable

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion

# Top-level fixtures shared across all test types (unit, integration, functional)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-slow", action="store_true", default=False, help="also run slow tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-slow"):
        return
    skip_slow = pytest.mark.skip(reason="slow test — pass --run-slow to include")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


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
def state_always_procs__st() -> State:
    state = State(rng=FixedRNG(value=0.0))
    Enemy(state=state)
    state.information.delay_since_last_fight = None
    return state


@pytest.fixture
def state_no_procs__st() -> State:
    state = State(rng=FixedRNG(value=1.0))
    Enemy(state=state)
    return state


@pytest.fixture
def unit_elarion__zero_stats(state_always_procs__st: State) -> Elarion:
    return Elarion(state=state_always_procs__st, raw_stats=RawStatsFromPercents(main_stat=1000.0))


@pytest.fixture
def setup_hasted_elarion(state_always_procs__st: State) -> Callable[..., Elarion]:
    def _factory(*, haste: float) -> Elarion:
        return Elarion(state=state_always_procs__st, raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=haste))

    return _factory
