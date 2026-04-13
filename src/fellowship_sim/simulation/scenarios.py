import contextlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from fellowship_sim.base_classes.entity import Enemy
from fellowship_sim.base_classes.state import State, StateInformation, get_state
from fellowship_sim.base_classes.timed_events import FightDowntimeEnd, FightDowntimeStart, FightOverTimedEvent
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup


@dataclass(kw_only=True)
class EnemySpec:
    time_to_live: float
    is_boss: bool = False
    ttl_jitter: float = 0.0  # uniform ± fraction; 0 = deterministic
    spirit_score: float = 0


@dataclass(kw_only=True)
class PackSpec:
    enemies: list[EnemySpec]
    time_to_next_pack: float | None  # None → last pack; seconds of downtime otherwise

    def __post_init__(self) -> None:
        ttls = [e.time_to_live for e in self.enemies]
        if ttls != sorted(ttls, reverse=True):
            raise ValueError("PackSpec enemies must be ordered by time_to_live descending")  # noqa: TRY003
        boss_ttl = max((e.time_to_live for e in self.enemies if e.is_boss), default=None)
        if boss_ttl is not None:
            max_non_boss_ttl = max((e.time_to_live for e in self.enemies if not e.is_boss), default=0.0)
            if max_non_boss_ttl > boss_ttl:
                raise ValueError("Non-boss enemies cannot have a longer ttl than boss enemies")  # noqa: TRY003


@dataclass(kw_only=True)
class Scenario:
    note: str = ""
    packs: list[PackSpec]
    delay_since_last_fight: float | None
    is_ult_authorized: bool
    initial_spirit_points: float
    finalize_character: Callable[[Elarion], None] | None = field(default=None, repr=False)

    @property
    def duration(self) -> float:
        total = 0.0
        for pack in self.packs:
            total += max(e.time_to_live for e in pack.enemies)
            if pack.time_to_next_pack is not None:
                total += pack.time_to_next_pack
        return total

    @property
    def num_enemies(self) -> int:
        return len(self.packs[0].enemies)

    def __str__(self) -> str:
        fields = ", ".join([
            f"duration={self.duration}",
            f"initial_spirit_points={self.initial_spirit_points}",
            f"delay_since_last_fight={self.delay_since_last_fight}",
        ])
        return f"Scenario ({self.note}) ({fields})"


def _spawn_pack(pack: PackSpec, state: State) -> None:
    for idx, spec in enumerate(pack.enemies):
        Enemy(
            state=state,
            time_to_live=spec.time_to_live,
            is_boss=spec.is_boss,
            is_main=idx == 0,
            spirit_score=spec.spirit_score,
        )


def _randomize_pack_health(pack: PackSpec, rng: random.Random) -> PackSpec:
    enemies = [
        EnemySpec(
            time_to_live=spec.time_to_live * (1.0 + rng.uniform(-spec.ttl_jitter, spec.ttl_jitter)),
            is_boss=spec.is_boss,
            ttl_jitter=spec.ttl_jitter,
        )
        for spec in pack.enemies
    ]
    return PackSpec(
        enemies=sorted(enemies, key=lambda e: e.time_to_live, reverse=True), time_to_next_pack=pack.time_to_next_pack
    )


def generate_new_scenario(
    scenario: Scenario,
    setup: ElarionSetup,
    rng_seed: float | None,
) -> tuple[State, Elarion]:
    with contextlib.suppress(RuntimeError):
        get_state().deactivate()

    ttl_rng = random.Random(x=rng_seed)
    randomized_packs = [_randomize_pack_health(pack=pack, rng=ttl_rng) for pack in scenario.packs]

    state = State(
        rng=random.Random(x=rng_seed),
        information=StateInformation(
            delay_since_last_fight=scenario.delay_since_last_fight,
            is_ult_authorized=scenario.is_ult_authorized,
        ),
    )

    _spawn_pack(pack=randomized_packs[0], state=state)

    current_time = 0.0
    for idx, pack in enumerate(randomized_packs):
        pack_duration = max(e.time_to_live for e in pack.enemies)
        pack_end = current_time + pack_duration
        current_time = pack_end

        if pack.time_to_next_pack is None:
            break

        next_pack_start = pack_end + pack.time_to_next_pack
        current_time = next_pack_start

        next_randomized_pack = randomized_packs[idx + 1]
        state.schedule(pack_end, FightDowntimeStart(name=f"Pack {idx + 1} end"))
        state.schedule(
            next_pack_start,
            FightDowntimeEnd(
                name=f"Pack {idx + 2} start",
                callback=lambda p=next_randomized_pack, s=state: _spawn_pack(pack=p, state=s),
            ),
        )

    state.schedule(current_time, FightOverTimedEvent())

    elarion = setup.finalize(state)
    elarion.spirit_points = 0
    elarion._change_spirit_points(scenario.initial_spirit_points)

    if scenario.finalize_character is not None:
        scenario.finalize_character(elarion)

    return state, elarion


def boss_fight_scenario(
    *,
    duration: float,
    delay_since_last_fight: float | None,
    spirit_score: float = 56,  # Sinthara has 56 score
    initial_spirit_points: float = 130,
    ttl_jitter: float = 0.0,
    note: str = "",
    finalize_character: Callable[[Elarion], None] | None = None,
) -> Scenario:
    return Scenario(
        note=note,
        packs=[
            PackSpec(
                enemies=[EnemySpec(time_to_live=duration, is_boss=True, ttl_jitter=ttl_jitter)], time_to_next_pack=None
            )
        ],
        delay_since_last_fight=delay_since_last_fight,
        is_ult_authorized=True,
        initial_spirit_points=initial_spirit_points,
        finalize_character=finalize_character,
    )


def single_uniform_pack_scenario(
    *,
    duration: float,
    num_enemies: int,
    delay_since_last_fight: float | None,
    initial_spirit_points: float,
    total_spirit_score: float = 60,
    is_ult_authorized: bool = True,
    ttl_jitter: float = 0.0,
    note: str = "",
) -> Scenario:
    enemies = [
        EnemySpec(time_to_live=duration, ttl_jitter=ttl_jitter, spirit_score=total_spirit_score / num_enemies)
        for _ in range(num_enemies)
    ]
    return Scenario(
        note=note,
        packs=[PackSpec(enemies=enemies, time_to_next_pack=None)],
        delay_since_last_fight=delay_since_last_fight,
        is_ult_authorized=is_ult_authorized,
        initial_spirit_points=initial_spirit_points,
    )


def multiple_identical_packs_scenario(
    *,
    pack_duration: float,
    pack_interval: float,
    num_packs: int,
    num_big: int,
    num_medium: int = 0,
    num_small: int = 0,
    medium_ttl_ratio: float = 0.75,
    small_ttl_ratio: float = 0.50,
    ttl_jitter: float = 0.0,
    spirit_score: float = 60,
    delay_since_last_fight: float | None,
    initial_spirit_points: float,
    is_ult_authorized: bool = True,
    note: str = "",
) -> Scenario:
    num_enemies = num_big + num_medium + num_small
    enemies = (
        [
            EnemySpec(time_to_live=pack_duration, ttl_jitter=ttl_jitter, spirit_score=spirit_score / num_enemies)
            for _ in range(num_big)
        ]
        + [
            EnemySpec(
                time_to_live=pack_duration * medium_ttl_ratio,
                ttl_jitter=ttl_jitter,
                spirit_score=spirit_score / num_enemies,
            )
            for _ in range(num_medium)
        ]
        + [
            EnemySpec(
                time_to_live=pack_duration * small_ttl_ratio,
                ttl_jitter=ttl_jitter,
                spirit_score=spirit_score / num_enemies,
            )
            for _ in range(num_small)
        ]
    )
    pack_specs = [
        PackSpec(enemies=enemies, time_to_next_pack=pack_interval if i < num_packs - 1 else None)
        for i in range(num_packs)
    ]
    return Scenario(
        note=note,
        packs=pack_specs,
        delay_since_last_fight=delay_since_last_fight,
        is_ult_authorized=is_ult_authorized,
        initial_spirit_points=initial_spirit_points,
    )
