# Unit tests for base_classes/real_ppm.py

import pytest

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.real_ppm import RealPPM
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion


class FixedRNG:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


_BASE_PPM = 6.0
_INTERVAL = 60.0 / _BASE_PPM  # 10.0 seconds


def _setup_rppm(
    *,
    is_haste_scaled: bool = False,
    is_crit_scaled: bool = False,
    haste: float = 0.0,
    crit: float = 0.0,
    rng_value: float = 0.0,
) -> tuple[RealPPM, State]:
    entity = Entity()
    state = State(enemies=[entity], rng=FixedRNG(rng_value)).activate()
    player = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=haste, crit_percent=crit))
    state.character = player
    rppm = RealPPM(
        base_ppm=_BASE_PPM,
        is_haste_scaled=is_haste_scaled,
        is_crit_scaled=is_crit_scaled,
        owner=player,
    )
    return rppm, state


def test_first_check_never_procs() -> None:
    """On the very first check, interval_since_last_proc=0 → proc_chance=0 → no proc."""
    rppm, _ = _setup_rppm()
    assert not rppm.check()


def test_proc_chance_is_one_after_full_interval() -> None:
    """After a full proc interval has elapsed since the last attempt, proc_chance = 1.0."""
    rppm, state = _setup_rppm()
    rppm.check()  # sets last_attempt_time = 0.0
    state.advance_time(_INTERVAL)
    assert rppm.proc_chance == pytest.approx(1.0)


def test_proc_chance_linear_at_half_interval() -> None:
    rppm, state = _setup_rppm()
    rppm.check()  # sets last_attempt_time = 0.0
    state.advance_time(_INTERVAL / 2)
    assert rppm.proc_chance == pytest.approx(0.5)


def test_check_updates_last_attempt_on_miss() -> None:
    """check() records the attempt time even when the roll fails."""
    rppm, state = _setup_rppm()
    state.advance_time(5.0)
    rppm.check()  # proc_chance=0 → no proc, but last_attempt_time must be set
    assert rppm.last_attempt_time == pytest.approx(5.0)


def test_haste_scaling_shortens_proc_interval() -> None:
    rppm, _ = _setup_rppm(is_haste_scaled=True, haste=0.2)
    expected_interval = 60.0 / (_BASE_PPM * 1.2)
    assert rppm.current_proc_interval == pytest.approx(expected_interval)


def test_crit_scaling_shortens_proc_interval() -> None:
    rppm, _ = _setup_rppm(is_crit_scaled=True, crit=0.1)
    expected_interval = 60.0 / (_BASE_PPM * 1.1)
    assert rppm.current_proc_interval == pytest.approx(expected_interval)
