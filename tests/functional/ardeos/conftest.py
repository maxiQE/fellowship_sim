import pytest

from fellowship_sim.ardeos.entity import Ardeos
from fellowship_sim.ardeos.setup import ArdeosSetup
from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from tests.conftest import SequenceRNG


def build_ardeos(
    state: State,
    *,
    haste_percent: float | None = None,
    spirit_percent: float | None = None,
    expertise_percent: float | None = None,
    crit_percent: float | None = None,
    main_stat: float | None = None,
) -> Ardeos:
    return ArdeosSetup(
        raw_stats=RawStatsFromPercents(
            main_stat=main_stat if main_stat is not None else 1000.0,
            haste_percent=haste_percent if haste_percent is not None else 0.0,
            spirit_percent=spirit_percent if spirit_percent is not None else 0.0,
            expertise_percent=expertise_percent if expertise_percent is not None else 0.0,
            crit_percent=crit_percent if crit_percent is not None else 0.0,
        ),
    ).finalize(state=state)


@pytest.fixture
def rng() -> SequenceRNG:
    return SequenceRNG(values=[1.0])


@pytest.fixture
def state(rng: SequenceRNG) -> State:
    s = State(rng=rng)
    Enemy(state=s)
    return s


@pytest.fixture(params=[0.0, 0.1, 0.2])
def ardeos(state: State, request: pytest.FixtureRequest) -> Ardeos:
    return build_ardeos(state=state, haste_percent=float(request.param))
