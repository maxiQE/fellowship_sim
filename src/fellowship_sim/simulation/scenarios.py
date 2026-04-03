import contextlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from fellowship_sim.base_classes.entity import Enemy
from fellowship_sim.base_classes.state import State, StateInformation, get_state
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup


@dataclass(kw_only=True)
class Scenario:
    """Scenario base class."""

    note: str = field(default="", init=True, repr=False)
    _description: str = field(repr=False)  # Overall description
    duration: float  # seconds
    num_enemies: int
    bonus_spirit_point_per_s: float
    initial_spirit_points: float
    is_ult_authorized: bool
    delay_since_last_fight: float | None  # None for first fight
    is_boss_fight: bool

    finalize_character: Callable[[Elarion], None] | None = None

    def __str__(self) -> str:
        fields = ", ".join([
            f"duration={self.duration}",
            f"bonus_spirit_point_per_s={self.bonus_spirit_point_per_s}",
            f"initial_spirit_points={self.initial_spirit_points}",
            f"delay_since_last_fight={self.delay_since_last_fight}",
        ])
        return self._description + f" ({self.note})" + f" ({fields})"

    def generate_new_scenario(self, setup: ElarionSetup, rng_seed: float | None) -> tuple[State, Elarion]:
        with contextlib.suppress(RuntimeError):
            get_state().deactivate()

        state = State(
            enemies=[Enemy(time_to_live=self.duration) for _ in range(self.num_enemies)],
            rng=random.Random(x=rng_seed),
            information=StateInformation(
                is_boss_fight=self.is_boss_fight,
                duration=self.duration,
                delay_since_last_fight=self.delay_since_last_fight,
                is_ult_authorized=self.is_ult_authorized,
            ),
        )

        elarion = setup.finalize(state)

        # Avoid having spirit go over max
        elarion.spirit_points = 0
        elarion._change_spirit_points(self.initial_spirit_points)

        if self.finalize_character is not None:
            self.finalize_character(elarion)

        return state, elarion


@dataclass(kw_only=True)
class BossFightScenario(Scenario):
    note: str = field(default="", init=True, repr=False)
    duration: float  # seconds
    bonus_spirit_point_per_s: float
    delay_since_last_fight: float | None  # None for first fight

    initial_spirit_points: float = field(default=130, init=True, repr=True)

    _description: str = field(default="Boss fight", init=False, repr=False)
    num_enemies: int = field(default=1, init=False, repr=False)
    is_ult_authorized: bool = field(default=True, init=False, repr=False)
    is_boss_fight: bool = field(default=True, init=False, repr=False)


@dataclass(kw_only=True)
class TrashAOEFightScenario(Scenario):
    note: str = field(default="", init=True, repr=False)
    duration: float  # seconds
    num_enemies: int
    bonus_spirit_point_per_s: float
    delay_since_last_fight: float | None  # None for first fight
    initial_spirit_points: float

    is_ult_authorized: bool = field(default=True, init=True, repr=False)

    _description: str = field(default="Trash fight", init=False, repr=False)
    is_boss_fight: bool = field(default=False, init=False, repr=False)

    def __str__(self) -> str:
        fields = ", ".join([
            f"duration={self.duration}",
            f"bonus_spirit_point_per_s={self.bonus_spirit_point_per_s}",
            f"initial_spirit_points={self.initial_spirit_points}",
            f"delay_since_last_fight={self.delay_since_last_fight}",
        ])
        return self._description + f" [{self.num_enemies}]" + f" ({self.note})" + f" ({fields})"
