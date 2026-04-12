import contextlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from fellowship_sim.base_classes.entity import Enemy
from fellowship_sim.base_classes.state import State, StateInformation, get_state
from fellowship_sim.base_classes.timed_events import FightDowntimeEnd, FightDowntimeStart
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

    def generate_enemies(self, state: State) -> list[Enemy]:
        return [Enemy(state=state, time_to_live=self.duration) for _ in range(self.num_enemies)]

    def add_events(self, state: State) -> None:
        pass

    def generate_new_scenario(self, setup: ElarionSetup, rng_seed: float | None) -> tuple[State, Elarion]:
        with contextlib.suppress(RuntimeError):
            get_state().deactivate()

        state = State(
            rng=random.Random(x=rng_seed),
            information=StateInformation(
                is_boss_fight=self.is_boss_fight,
                duration=self.duration,
                delay_since_last_fight=self.delay_since_last_fight,
                is_ult_authorized=self.is_ult_authorized,
            ),
        )
        self.generate_enemies(state=state)

        self.add_events(state=state)

        elarion = setup.finalize(state)

        # Avoid having spirit go over max
        elarion.spirit_points = 0
        elarion._change_spirit_points(self.initial_spirit_points)

        elarion.spirit_point_per_s = self.bonus_spirit_point_per_s

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
    duration: float = field(init=False)
    pack_duration: float  # seconds
    num_enemies: int
    num_enemies_medium: int = field(default=0, init=True)
    num_enemies_small: int = field(default=0, init=True)
    num_packs: int = field(default=1, init=True)
    pack_interval_s: float = field(default=15.0, init=True)
    bonus_spirit_point_per_s: float
    delay_since_last_fight: float | None  # None for first fight
    initial_spirit_points: float

    enemy_health_ratio: tuple[float, float, float] = field(default_factory=lambda: (1, 0.75, 0.50), init=True)

    is_ult_authorized: bool = field(default=True, init=True, repr=False)

    _description: str = field(default="Trash fight", init=False, repr=False)
    is_boss_fight: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.duration = self.pack_duration * self.num_packs + self.pack_interval_s * (self.num_packs - 1)

        if self.num_enemies_big <= 0:
            raise ValueError(  # noqa: TRY003
                f"Number of big enemies should be at least 1 but got {self.num_enemies_big}; ({self.num_enemies = }, {self.num_enemies_medium = }, {self.num_enemies_small = })"
            )

        if self.pack_interval_s < 0.0:
            raise ValueError(f"Pack interval duration should be positive; got {self.pack_interval_s}")  # noqa: TRY003

    def __str__(self) -> str:
        fields = ", ".join([
            f"duration={self.duration}",
            f"bonus_spirit_point_per_s={self.bonus_spirit_point_per_s}",
            f"initial_spirit_points={self.initial_spirit_points}",
            f"delay_since_last_fight={self.delay_since_last_fight}",
        ])
        return (
            self._description
            + f" [{self.num_enemies_big, self.num_enemies_medium, self.num_enemies_small}]"
            + f" ({self.note})"
            + f" ({fields})"
        )

    @property
    def num_enemies_big(self) -> int:
        return self.num_enemies - self.num_enemies_medium - self.num_enemies_small

    def generate_enemies(self, state: State) -> list[Enemy]:
        """Overwritten to handle the diversity of time to live"""
        enemies: list[Enemy] = []
        for num, multiplier in zip(
            [self.num_enemies_big, self.num_enemies_medium, self.num_enemies_small],
            self.enemy_health_ratio,
            strict=True,
        ):
            enemies += [Enemy(state=state, time_to_live=self.duration * multiplier) for _ in range(num)]
        return enemies

    def add_events(self, state: State) -> None:
        if self.num_packs > 1:
            for idx in range(1, self.num_packs):
                pack_end_time = idx * self.pack_duration
                next_pack_start_time = pack_end_time + self.pack_interval_s
                state.schedule(
                    pack_end_time,
                    FightDowntimeStart(
                        name=f"Pack {idx} end",
                    ),
                )
                state.schedule(
                    next_pack_start_time,
                    FightDowntimeEnd(
                        name=f"Pack {idx + 1} start",
                        callback=lambda: self.generate_enemies(state),
                    ),
                )
