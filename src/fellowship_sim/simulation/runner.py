import contextlib
import time
from dataclasses import dataclass

from fellowship_sim.base_classes.entity import Player
from fellowship_sim.generic_game_logic.setup_effect import PlayerSetup
from fellowship_sim.simulation.base import FightOver, Rotation
from fellowship_sim.simulation.metrics import (
    DEFAULT_METRICS,
    MeanStd,
    Metric,
    MetricsResult,
    Probe,
    ScalarMetric,
    TextMetric,
    mean_stderr,
)
from fellowship_sim.simulation.scenarios import Scenario, generate_new_scenario


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


def run_once[P: Player](
    scenario: Scenario,
    rotation: Rotation[P],
    setup: PlayerSetup[P],
    seed: int | None = None,
    probe_types: set[type[Probe]] | None = None,
) -> tuple[dict[type[Probe], Probe], float]:
    """Run a single simulation, collect probes, and return them.

    Initializes the scenario and character, attaches probes, runs the rotation
    until FightOver, then removes all remaining effects.

    Args:
        scenario: The fight scenario (duration, enemies, spirit income).
        rotation: Callable that yields abilities for the player to cast.
        setup: Character build (stats, talents, gear).
        seed: RNG seed for reproducibility; None for random.
        probe_types: Set of Probe subclasses to attach; defaults to empty.

    Returns:
        Dict mapping each Probe type to its populated instance.
        Duration of the scenario.
    """
    state, player = generate_new_scenario(scenario=scenario, setup=setup, rng_seed=seed)

    probes: dict[type[Probe], Probe] = {}
    for pt in probe_types or set():
        probe = pt()
        probe.attach(bus=state.bus, enemies=state.enemies)
        probes[pt] = probe

    with contextlib.suppress(FightOver):
        for ability in rotation(player):
            if ability is not None:
                ability.cast(state.main_target)

    for entity in [*state.enemies, player]:
        for effect in list(entity.effects):
            if effect.attached_to:
                effect.remove()

    return probes, state.time


def run_k[P: Player](
    k: int,
    scenario: Scenario,
    rotation: Rotation[P],
    setup: PlayerSetup[P],
    base_seed: int | None = None,
    metrics: list[Metric] = DEFAULT_METRICS,
) -> RepetitionResult:
    """Run k independent simulations and aggregate results into a RepetitionResult.

    Args:
        k: Number of repetitions.
        scenario: The fight scenario.
        rotation: Callable that yields abilities for the player to cast.
        setup: Character build.
        base_seed: Base RNG seed; each rep uses base_seed+i. None for random.
        metrics: List of ScalarMetric/TextMetric to compute; defaults to DEFAULT_METRICS.

    Returns:
        RepetitionResult with aggregated scalars, texts, and wall-time stats.
    """
    probe_types: set[type[Probe]] = {m.probe_type for m in metrics}
    seeds = [None if base_seed is None else base_seed + i for i in range(k)]
    rep_times: list[float] = []
    all_run_probes: list[dict[type[Probe], Probe]] = []
    duration_list: list[float] = []

    for s in seeds:
        t0 = time.perf_counter()
        probes, duration = run_once(scenario=scenario, rotation=rotation, setup=setup, seed=s, probe_types=probe_types)
        all_run_probes.append(probes)
        duration_list.append(duration)
        rep_times.append(time.perf_counter() - t0)

    total_wall = sum(rep_times)

    scalars: dict[str, MeanStd] = {}
    texts: dict[str, str] = {}
    for metric in metrics:
        run_probe_list = [run[metric.probe_type] for run in all_run_probes]
        if isinstance(metric, ScalarMetric):
            scalars[metric.name] = mean_stderr(metric.aggregate(run_probe_list, duration_list))
        elif isinstance(metric, TextMetric):
            texts[metric.name] = metric.render(run_probe_list, duration_list)

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
