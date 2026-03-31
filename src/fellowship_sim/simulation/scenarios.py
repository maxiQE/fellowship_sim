import random

from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.base_classes.state import State
from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.base_classes.timed_events import FightOverTimedEvent
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import create_elarion


class _FixedDurationScenario:
    """Base for scenarios that run for a fixed wall-clock duration against N enemies."""

    description: str = ""
    num_enemies: int
    max_time: float  # seconds

    def setup(
        self,
        raw_stats: RawStats,
        initial_focus: float,
        rng: random.Random,
    ) -> tuple[State, Elarion]:
        enemies = [Entity() for _ in range(self.num_enemies)]
        state = State(enemies=enemies, rng=rng).activate()
        state.schedule(time_delay=self.max_time, callback=FightOverTimedEvent())
        elarion = create_elarion(state=state, raw_stats=raw_stats, initial_focus=initial_focus)
        return state, elarion


class SingleTarget3Min(_FixedDurationScenario):
    description = "1 enemy, 60 s fight"
    num_enemies = 1
    max_time = 180.0


class FourTargets3Min(_FixedDurationScenario):
    description = "4 enemies, 60 s fight"
    num_enemies = 4
    max_time = 180.0


class TwelveTargets3Min(_FixedDurationScenario):
    description = "12 enemies, 60 s fight"
    num_enemies = 12
    max_time = 180.0
