import contextlib
import time
from dataclasses import dataclass

from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.base import FightOver, Rotation
from fellowship_sim.simulation.metrics import (
    DEFAULT_METRICS,
    MeanStd,
    Metric,
    MetricsResult,
    Probe,
    ScalarMetric,
    TextMetric,
)
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
    probe_types: set[type[Probe]] | None = None,
) -> dict[type[Probe], Probe]:
    state, elarion = scenario.generate_new_scenario(setup, rng_seed=seed)

    probes: dict[type[Probe], Probe] = {}
    for pt in probe_types or set():
        probe = pt()
        probe.attach(bus=state.bus, enemies=state.enemies)
        probes[pt] = probe

    with contextlib.suppress(FightOver):
        rotation.run(elarion)

    return probes


def run_k(
    k: int,
    scenario: Scenario,
    rotation: Rotation,
    setup: ElarionSetup,
    base_seed: int | None = None,
    metrics: list[Metric] = DEFAULT_METRICS,
) -> RepetitionResult:
    probe_types: set[type[Probe]] = {m.probe_type for m in metrics}
    seeds = [None if base_seed is None else base_seed + i for i in range(k)]
    rep_times: list[float] = []
    all_run_probes: list[dict[type[Probe], Probe]] = []

    for s in seeds:
        t0 = time.perf_counter()
        all_run_probes.append(
            run_once(scenario=scenario, rotation=rotation, setup=setup, seed=s, probe_types=probe_types)
        )
        rep_times.append(time.perf_counter() - t0)

    total_wall = sum(rep_times)

    scalars: dict[str, MeanStd] = {}
    texts: dict[str, str] = {}
    for metric in metrics:
        run_probe_list = [run[metric.probe_type] for run in all_run_probes]
        if isinstance(metric, ScalarMetric):
            scalars[metric.name] = metric.aggregate(run_probe_list, scenario.duration)
        elif isinstance(metric, TextMetric):
            texts[metric.name] = metric.render(run_probe_list, scenario.duration)

    st_suppressed = frozenset(m.name for m in metrics if not m.show_on_st)

    return RepetitionResult(
        k=k,
        metrics=MetricsResult(
            scalars=scalars,
            texts=texts,
            is_single_target=scenario.num_enemies == 1,
            st_suppressed=st_suppressed,
        ),
        total_wall_time=total_wall,
        mean_wall_time=total_wall / k,
    )
