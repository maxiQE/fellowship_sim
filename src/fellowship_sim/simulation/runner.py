import contextlib
import time
from dataclasses import dataclass

from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.base import FightOver, Rotation
from fellowship_sim.simulation.metrics import DamageMetrics, MetricsResult
from fellowship_sim.simulation.scenarios import Scenario


@dataclass(kw_only=True)
class RepetitionResult:
    k: int
    metrics: MetricsResult
    total_wall_time: float = 0.0  # seconds of real time for all k runs
    mean_wall_time: float = 0.0  # seconds per repetition

    def __str__(self) -> str:
        lines = [
            f"Repetitions : {self.k}",
            str(self.metrics),
            f"Wall time   : {self.total_wall_time:.3f}s total  ({self.mean_wall_time * 1000:.1f} ms/rep)",
        ]
        return "\n".join(lines)


def run_once(
    scenario: Scenario,
    rotation: Rotation,
    setup: ElarionSetup,
    seed: int | None = None,
) -> DamageMetrics:
    state, elarion = scenario.generate_new_scenario(setup, rng_seed=seed)
    metrics = DamageMetrics(_main=state.enemies[0], _bus=state.bus)

    with contextlib.suppress(FightOver):
        rotation.run(elarion)

    return metrics


def run_k(
    k: int,
    scenario: Scenario,
    rotation: Rotation,
    setup: ElarionSetup,
    base_seed: int | None = None,
) -> RepetitionResult:
    seeds = [None if base_seed is None else base_seed + i for i in range(k)]
    rep_times: list[float] = []
    results: list[DamageMetrics] = []
    for s in seeds:
        t0 = time.perf_counter()
        results.append(run_once(scenario=scenario, rotation=rotation, setup=setup, seed=s))
        rep_times.append(time.perf_counter() - t0)

    total_wall = sum(rep_times)

    return RepetitionResult(
        k=k,
        metrics=DamageMetrics.compute_metrics(results=results, fight_duration=scenario.duration),
        total_wall_time=total_wall,
        mean_wall_time=total_wall / k,
    )
