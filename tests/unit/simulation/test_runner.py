# Unit tests for simulation/runner.py

from collections.abc import Iterator
from dataclasses import dataclass, field

from fellowship_sim.base_classes.ability import Ability
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.state import State, get_state
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.runner import run_k, run_once
from fellowship_sim.simulation.scenarios import BossFightScenario, Scenario

# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

_SETUP = ElarionSetup(raw_stats=RawStatsFromPercents(main_stat=1000.0))

_SCENARIO = BossFightScenario(
    duration=10.0,
    bonus_spirit_point_per_s=0.0,
    delay_since_last_fight=None,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubDamageSource:
    """Minimal stand-in for Ability[Player] | Effect, sufficient to construct AbilityDamage.

    AbilityDamage only uses type(damage_source).__name__ for bookkeeping — no interface
    is required beyond that.
    """

    def __str__(self) -> str:
        return "stub"


@dataclass(kw_only=True)
class _SeedCapturingScenario:
    """Wraps a Scenario and records every rng_seed passed to generate_new_scenario."""

    _inner: Scenario
    seeds_seen: list[int | None] = field(default_factory=list)
    last_state: State | None = field(default=None, init=False)

    @property
    def duration(self) -> float:
        return self._inner.duration

    @property
    def num_enemies(self) -> int:
        return self._inner.num_enemies

    def generate_new_scenario(self, setup: ElarionSetup, rng_seed: int | None) -> tuple[State, Elarion]:
        self.seeds_seen.append(rng_seed)
        state, elarion = self._inner.generate_new_scenario(setup, rng_seed=rng_seed)
        self.last_state = state
        return state, elarion


@dataclass(kw_only=True)
class _StateCapturingRotation(Rotation):
    """Records the active State on each __call__, then immediately terminates."""

    captured_states: list[State] = field(default_factory=list)

    def __call__(self, elarion: Elarion) -> Iterator[Ability | None]:
        self.captured_states.append(get_state())
        yield from ()


@dataclass(kw_only=True)
class _DamageAndExitRotation(Rotation):
    """Records initial enemy damage total, applies 1 000 damage to it, then terminates.

    Designed to be used across k runs: each run sees the enemy's damage_tracker.total
    before doing anything, then leaves the enemy with 1 000 damage so the next run
    can verify it starts fresh.
    """

    initial_totals: list[float] = field(default_factory=list)

    def __call__(self, elarion: Elarion) -> Iterator[Ability | None]:
        state = get_state()
        enemy = state.enemies[0]
        self.initial_totals.append(enemy.damage_tracker.total)
        # Constructing AbilityDamage registers the damage on enemy.damage_tracker immediately
        # via its __post_init__ → target._take_damage(self).
        AbilityDamage(
            damage_source=_StubDamageSource(),  # ty:ignore[invalid-argument-type]
            owner=elarion,
            target=enemy,
            damage=1_000.0,
            is_crit=False,
            is_grievous_crit=False,
        )
        yield from ()


# ---------------------------------------------------------------------------
# Tests — run_once
# ---------------------------------------------------------------------------


class TestRunOnce:
    """run_once: single execution; seed forwarding and state/rotation contract."""

    def test_seed_forwarded_to_scenario(self) -> None:
        """The seed passed to run_once reaches generate_new_scenario unchanged."""
        scenario = _SeedCapturingScenario(_inner=_SCENARIO)
        run_once(scenario=scenario, rotation=_StateCapturingRotation(), setup=_SETUP, seed=99)  # ty:ignore[invalid-argument-type]
        assert scenario.seeds_seen == [99]

    def test_active_state_during_rotation_is_from_scenario(self) -> None:
        """The State that is active when the rotation runs is the one generate_new_scenario returned.

        Verifies that run_once does not silently replace or deactivate the state between
        setup and execution.
        """
        scenario = _SeedCapturingScenario(_inner=_SCENARIO)
        rotation = _StateCapturingRotation()
        run_once(scenario=scenario, rotation=rotation, setup=_SETUP, seed=0)  # ty:ignore[invalid-argument-type]
        assert rotation.captured_states[0] is scenario.last_state


# ---------------------------------------------------------------------------
# Tests — run_k
# ---------------------------------------------------------------------------


class TestRunK:
    """run_k: k-repetition loop; isolation, seed sequencing, and reset guarantees."""

    def test_seeds_are_sequential(self) -> None:
        """Each run receives seed = base_seed + i (i = 0 … k-1), in order."""
        scenario = _SeedCapturingScenario(_inner=_SCENARIO)
        run_k(k=3, scenario=scenario, rotation=_StateCapturingRotation(), setup=_SETUP, base_seed=10, metrics=[])  # ty:ignore[invalid-argument-type]
        assert scenario.seeds_seen == [10, 11, 12]

    def test_each_run_gets_fresh_state(self) -> None:
        """Each of the k runs operates on a distinct State instance."""
        rotation = _StateCapturingRotation()
        run_k(k=2, scenario=_SCENARIO, rotation=rotation, setup=_SETUP, base_seed=0, metrics=[])
        assert rotation.captured_states[0] is not rotation.captured_states[1]

    def test_enemy_damage_starts_at_zero_each_run(self) -> None:
        """Enemy damage_tracker.total is 0 at the start of every run, regardless of damage done in prior runs.

        _DamageAndExitRotation puts 1 000 damage on the enemy each call.
        The next call must still see 0, proving generate_new_scenario creates a fresh enemy.
        """
        rotation = _DamageAndExitRotation()
        run_k(k=3, scenario=_SCENARIO, rotation=rotation, setup=_SETUP, base_seed=0, metrics=[])
        assert rotation.initial_totals == [0.0, 0.0, 0.0]

    def test_enemy_objects_are_distinct_across_runs(self) -> None:
        """The enemy object in run N is not the same Python object as in run N+1.

        A shared object would mean damage and effects from one run could bleed into the next.
        """
        rotation = _StateCapturingRotation()
        run_k(k=2, scenario=_SCENARIO, rotation=rotation, setup=_SETUP, base_seed=0, metrics=[])
        assert rotation.captured_states[0].enemies[0] is not rotation.captured_states[1].enemies[0]
