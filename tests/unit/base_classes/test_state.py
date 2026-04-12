# Unit tests for base_classes/state.py

import threading

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.state import get_state


class FixedRNG:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


class TestStateSelectTargets:
    def test_select_targets_empty_pool_returns_empty(self) -> None:
        state = State(rng=FixedRNG(0.0))
        enemy = Enemy(state=state)
        targets = state.select_targets(main_target=enemy, num=3)
        assert targets == []

    def test_select_targets_excludes_main_target(self) -> None:
        state = State(rng=FixedRNG(0.0))
        enemies = [Enemy(state=state), Enemy(state=state), Enemy(state=state)]
        targets = state.select_targets(main_target=enemies[0], num=3)
        assert enemies[0] not in targets
        assert enemies[1] in targets
        assert enemies[2] in targets

    def test_select_targets_highest_priority_selected(self) -> None:
        state = State(rng=FixedRNG(0.0))
        enemy_a, enemy_b, enemy_c = Enemy(state=state), Enemy(state=state), Enemy(state=state)

        priority_map = {id(enemy_a): 2.0, id(enemy_b): 1.0, id(enemy_c): 0.0}
        targets = state.select_targets(
            main_target=None,
            num=2,
            priority_func=lambda e: priority_map[id(e)],
        )

        assert enemy_a in targets
        assert enemy_b in targets
        assert enemy_c not in targets

    @pytest.mark.parametrize(
        "rng_val,expected_idx",
        [
            (0.0, 0),
            (0.5, 1),
            (0.99, 2),
        ],
    )
    def test_select_targets_tie_breaking_uses_rng(self, rng_val: float, expected_idx: int) -> None:
        """When all enemies have equal priority, selection is random (RNG-controlled)."""
        state = State(rng=FixedRNG(rng_val))
        enemies = [Enemy(state=state), Enemy(state=state), Enemy(state=state)]
        targets = state.select_targets(main_target=None, num=1)
        assert targets == [enemies[expected_idx]]


class TestStateContextVar:
    def test_thread_isolation(self) -> None:
        """States constructed in separate threads don't interfere with each other."""
        barrier = threading.Barrier(2)
        results: list[State | None] = [None, None]

        def run_a() -> None:
            state = State(rng=FixedRNG(0.0))
            Enemy(state=state)
            barrier.wait()
            results[0] = get_state()

        def run_b() -> None:
            state = State(rng=FixedRNG(0.0))
            Enemy(state=state)
            barrier.wait()
            results[1] = get_state()

        t1 = threading.Thread(target=run_a)
        t2 = threading.Thread(target=run_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results[0] is not None
        assert results[1] is not None
        assert results[0] is not results[1]

    def test_deactivate_clears_state(self) -> None:
        """deactivate() clears the active state; get_state() raises afterward."""
        state = State(rng=FixedRNG(0.0))
        Enemy(state=state)

        assert get_state() is state
        state.deactivate()
        with pytest.raises(RuntimeError):
            get_state()
