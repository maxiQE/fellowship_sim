import contextlib
import math
import random
import time
from dataclasses import dataclass

from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.simulation.base import FightOver, Rotation
from fellowship_sim.simulation.metrics import DamageMetrics
from fellowship_sim.simulation.scenarios import _FixedDurationScenario


@dataclass(kw_only=True)
class RepetitionResult:
    k: int
    mean_total: float
    stderr_total: float
    mean_main: float
    stderr_main: float
    mean_secondary: float
    stderr_secondary: float
    total_wall_time: float = 0.0  # seconds of real time for all k runs
    mean_wall_time: float = 0.0  # seconds per repetition

    def __str__(self) -> str:
        lines = [
            f"Repetitions : {self.k}",
            f"Total       : {self.mean_total:>12,.1f}  ± {self.stderr_total:,.1f}",
            f"Main target : {self.mean_main:>12,.1f}  ± {self.stderr_main:,.1f}",
            f"Secondary   : {self.mean_secondary:>12,.1f}  ± {self.stderr_secondary:,.1f}",
            f"Wall time   : {self.total_wall_time:.3f}s total  ({self.mean_wall_time * 1000:.1f} ms/rep)",
        ]
        return "\n".join(lines)


def run_once(
    scenario: _FixedDurationScenario,
    rotation: Rotation,
    raw_stats: RawStats,
    initial_focus: float = 100.0,
    seed: int | None = None,
) -> DamageMetrics:
    rng = random.Random(seed)  # noqa: S311
    state, elarion = scenario.setup(raw_stats, initial_focus, rng)
    metrics = DamageMetrics(_main=state.enemies[0], _bus=state.bus)
    with contextlib.suppress(FightOver):
        rotation.run(elarion)
    return metrics


def _mean_stderr(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    mean = sum(vals) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in vals) / (n - 1)
    return mean, math.sqrt(variance / n)


def run_k(
    k: int,
    scenario: _FixedDurationScenario,
    rotation: Rotation,
    raw_stats: RawStats,
    initial_focus: float = 100.0,
    base_seed: int | None = None,
) -> RepetitionResult:
    seeds = [None if base_seed is None else base_seed + i for i in range(k)]
    rep_times: list[float] = []
    results: list[DamageMetrics] = []
    for s in seeds:
        t0 = time.perf_counter()
        results.append(run_once(scenario, rotation, raw_stats, initial_focus, seed=s))
        rep_times.append(time.perf_counter() - t0)

    mean_t, se_t = _mean_stderr([r.total_damage for r in results])
    mean_m, se_m = _mean_stderr([r.main_damage for r in results])
    mean_s, se_s = _mean_stderr([r.secondary_damage for r in results])
    total_wall = sum(rep_times)

    return RepetitionResult(
        k=k,
        mean_total=mean_t,
        stderr_total=se_t,
        mean_main=mean_m,
        stderr_main=se_m,
        mean_secondary=mean_s,
        stderr_secondary=se_s,
        total_wall_time=total_wall,
        mean_wall_time=total_wall / k,
    )
