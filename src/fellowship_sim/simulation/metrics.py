import math
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import cast

from fellowship_sim.base_classes import Effect, WeaponAbility
from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    EffectApplied,
    EffectRefreshed,
    EffectRemoved,
    EventBus,
    SpiritProc,
    UltimateCast,
)
from fellowship_sim.base_classes.state import get_state

# ---------------------------------------------------------------------------
# MeanStd
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class MeanStd:
    mean: float
    stderr: float

    def __str__(self) -> str:
        return f"{self.mean:,.1f} ± {self.stderr:,.1f}"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def mean_stderr(vals: list[float]) -> MeanStd:
    n = len(vals)
    if n == 0:
        raise ValueError("Can't compute the mean and stderr of an empty list")  # noqa: TRY003

    mean = sum(vals) / n
    if n < 2:
        return MeanStd(mean=mean, stderr=0.0)
    variance = sum((v - mean) ** 2 for v in vals) / (n - 1)
    return MeanStd(mean=mean, stderr=math.sqrt(variance / n))


def _format_damage_source_contribution(source_dicts: list[dict[str, float]]) -> str:
    number_of_displayed_values = 5

    all_keys: set[str] = set()
    for d in source_dicts:
        all_keys.update(d.keys())
    avg: dict[str, float] = {key: sum(d.get(key, 0.0) for d in source_dicts) / len(source_dicts) for key in all_keys}
    total = sum(avg.values())
    if total == 0.0:
        return ""
    top = sorted(avg.items(), key=lambda kv: kv[1], reverse=True)[:number_of_displayed_values]
    return "  ".join(f"{name} {int(dmg / total * 100)}%" for name, dmg in top)


def _format_ability_cast_count(cast_count_dicts: list[dict[str, int]]) -> str:
    all_keys: set[str] = set()
    for d in cast_count_dicts:
        all_keys.update(d.keys())
    avg: dict[str, float] = {
        key: sum(d.get(key, 0) for d in cast_count_dicts) / len(cast_count_dicts) for key in all_keys
    }
    total = sum(avg.values())
    avg = {
        "Total": total,
        **{key: avg[key] for key in sorted(avg.keys())},
    }
    return "  ".join(f"{key} {value:.1f}" for key, value in avg.items())


def _format_buff_uptime(probes: "list[BuffUptimeProbe]", duration: float) -> str:
    all_keys: set[str] = set()
    for probe in probes:
        all_keys.update(probe.total_uptime_dict.keys())
    parts: list[str] = []
    for name in sorted(all_keys):
        avg_uptime = sum(probe.total_uptime_dict.get(name, 0.0) for probe in probes) / len(probes)
        avg_count = sum(probe.buff_count_dict.get(name, 0.0) for probe in probes) / len(probes)
        parts.append(f"{name} ({avg_count}) {avg_uptime / duration * 100:.0f}%")
    return "  ".join(parts)


def _format_source_details(probes: "list[DamageSourceProbe]") -> str:
    all_keys: set[str] = set()
    for probe in probes:
        all_keys.update(probe.avg_damage_by_source.keys())
    parts: list[str] = []
    for name in sorted(all_keys):
        count = sum(probe.count_by_source.get(name, 0) for probe in probes) / len(probes)
        avg_dmg = sum(probe.avg_damage_by_source.get(name, 0.0) for probe in probes) / len(probes)
        crit_rate = sum(probe.crit_rate_by_source.get(name, 0.0) for probe in probes) / len(probes)
        gcrit_rate = sum(probe.grievous_crit_rate_by_source.get(name, 0.0) for probe in probes) / len(probes)
        parts.append(
            f"{name} ({count:.0f}): {avg_dmg:,.0f}  {crit_rate * 100:.0f}% crit"
            + (f" {gcrit_rate * 100:.0f}% grievous" if gcrit_rate > 0 else "")
        )
    return "  ||  ".join(parts)


# ---------------------------------------------------------------------------
# MetricsResult
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class MetricsResult:
    scalars: dict[str, MeanStd]
    texts: dict[str, str]
    is_single_target: bool
    st_suppressed: frozenset[str]  # metric names with show_on_st=False

    def __str__(self) -> str:
        lines: list[str] = []
        for name, ms in self.scalars.items():
            if self.is_single_target and name in self.st_suppressed:
                continue
            lines.append(f"{name:<24}: {ms}")
        for name, text in self.texts.items():
            if self.is_single_target and name in self.st_suppressed:
                continue
            if text:
                lines.append(f"{name:<24}: {text}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


class Probe(ABC):
    @abstractmethod
    def attach(self, bus: EventBus, enemies: Sequence[Entity]) -> None: ...


@dataclass(kw_only=True)
class DamageSplitProbe(Probe):
    """Reads damage totals directly from each enemy's DamageTracker after the run."""

    _enemies: Sequence[Entity] = field(default_factory=list, init=False)

    def attach(self, bus: EventBus, enemies: Sequence[Entity]) -> None:
        self._enemies = enemies

    @property
    def main_damage(self) -> float:
        return self._enemies[0].damage_tracker.total

    @property
    def secondary_damage(self) -> float:
        return sum(e.damage_tracker.total for e in self._enemies[1:])

    @property
    def total_damage(self) -> float:
        return sum(e.damage_tracker.total for e in self._enemies)


@dataclass(kw_only=True)
class BuffUptimeProbe(Probe):
    """Subscribes to effect added and removed. Deduces buff uptime."""

    last_uptime_dict: dict[str, float] = field(default_factory=dict, init=False)
    uptime_intervals_dict: dict[str, list[tuple[float, float]]] = field(
        default_factory=lambda: defaultdict(list), init=False
    )
    buff_count_dict: dict[str, int] = field(default_factory=lambda: defaultdict(lambda: 0), init=False)

    def attach(self, bus: EventBus, enemies: Sequence[Entity]) -> None:
        bus.subscribe(EffectApplied, self._on_apply, owner=self)
        bus.subscribe(EffectRefreshed, self._on_apply, owner=self)
        bus.subscribe(EffectRemoved, self._on_removed, owner=self)

    def effect_key(self, effect: Effect) -> str:
        return effect.name

    def _on_apply(self, event: EffectApplied) -> None:
        state = get_state()
        if event.target != state.character:
            return

        key = self.effect_key(event.effect)
        self.last_uptime_dict[key] = state.time
        self.buff_count_dict[key] += 1

    def _on_renew(self, event: EffectRefreshed) -> None:
        state = get_state()
        if event.target != state.character:
            return

        key = self.effect_key(event.effect)
        self.buff_count_dict[key] += 1

    def _on_removed(self, event: EffectRemoved) -> None:
        state = get_state()
        if event.target != state.character:
            return

        key = self.effect_key(event.effect)
        if key not in self.last_uptime_dict:
            if not math.isinf(event.effect.duration):
                raise Exception(f"Finite duration effect {event.effect} was not found in self.last_uptime_dict")  # noqa: TRY002, TRY003
            return

        interval = self.last_uptime_dict[key], state.time
        self.uptime_intervals_dict[key].append(interval)

        del self.last_uptime_dict[key]

    @property
    def total_uptime_dict(self) -> dict[str, float]:
        return {
            key: sum(stop - start for start, stop in intervals) for key, intervals in self.uptime_intervals_dict.items()
        }


@dataclass(kw_only=True)
class CastCountProbe(Probe):
    """Subscribes to cast/spirit events; counts are not on the entity."""

    ult_count: int = field(default=0, init=False)
    weapon_cast_count: int = field(default=0, init=False)
    spirit_proc_count: int = field(default=0, init=False)
    ability_cast_count: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int), init=False)

    def attach(self, bus: EventBus, enemies: Sequence[Entity]) -> None:
        bus.subscribe(UltimateCast, self._on_ult, owner=self)
        bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)
        bus.subscribe(SpiritProc, self._on_spirit, owner=self)

    def _on_ult(self, event: UltimateCast) -> None:
        self.ult_count += 1

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        if isinstance(event.ability, WeaponAbility):
            self.weapon_cast_count += 1
        self.ability_cast_count[str(event.ability)] += 1

    def _on_spirit(self, event: SpiritProc) -> None:
        self.spirit_proc_count += 1


@dataclass(kw_only=True)
class DamageSourceProbe(Probe):
    """Reads per-source damage breakdowns from each enemy's DamageTracker after the run."""

    _enemies: Sequence[Entity] = field(default_factory=list, init=False)

    def attach(self, bus: EventBus, enemies: Sequence[Entity]) -> None:
        self._enemies = enemies

    @property
    def main_by_source(self) -> dict[str, float]:
        return {name: record.total for name, record in self._enemies[0].damage_tracker.by_source.items()}

    @property
    def secondary_by_source(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for enemy in self._enemies[1:]:
            for name, record in enemy.damage_tracker.by_source.items():
                result[name] = result.get(name, 0.0) + record.total
        return result

    @property
    def total_by_source(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for enemy in self._enemies:
            for name, record in enemy.damage_tracker.by_source.items():
                result[name] = result.get(name, 0.0) + record.total
        return result

    def _aggregate_records(self) -> dict[str, tuple[float, int, int, int]]:
        """Returns {source: (total_damage, count, crits, grievous_crits)} summed across all enemies."""
        result: dict[str, tuple[float, int, int, int]] = {}
        for enemy in self._enemies:
            for name, record in enemy.damage_tracker.by_source.items():
                prev = result.get(name, (0.0, 0, 0, 0))
                result[name] = (
                    prev[0] + record.total,
                    prev[1] + record.count,
                    prev[2] + record.crits,
                    prev[3] + record.grievous_crits,
                )
        return result

    @property
    def avg_damage_by_source(self) -> dict[str, float]:
        return {name: total / count for name, (total, count, _, _) in self._aggregate_records().items() if count > 0}

    @property
    def count_by_source(self) -> dict[str, int]:
        return {name: count for name, (_, count, _, _) in self._aggregate_records().items() if count > 0}

    @property
    def crit_rate_by_source(self) -> dict[str, float]:
        return {name: crits / count for name, (_, count, crits, _) in self._aggregate_records().items() if count > 0}

    @property
    def grievous_crit_rate_by_source(self) -> dict[str, float]:
        return {name: gcrits / count for name, (_, count, _, gcrits) in self._aggregate_records().items() if count > 0}


# ---------------------------------------------------------------------------
# Metric types
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class ScalarMetric:
    name: str
    probe_type: type[Probe]
    aggregate: Callable[[list[Probe], float], MeanStd]
    show_on_st: bool = True


@dataclass(kw_only=True)
class TextMetric:
    name: str
    probe_type: type[Probe]
    render: Callable[[list[Probe], float], str]
    show_on_st: bool = True


Metric = ScalarMetric | TextMetric


# ---------------------------------------------------------------------------
# Default metric set
# ---------------------------------------------------------------------------

DEFAULT_METRICS: list[Metric] = [
    ScalarMetric(
        name="total",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).total_damage for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="main",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).main_damage for probe in probe_list
        ]),
    ),
    ScalarMetric(
        name="secondary",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).secondary_damage for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="total_dps",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).total_damage / duration for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="main_dps",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).main_damage / duration for probe in probe_list
        ]),
    ),
    ScalarMetric(
        name="secondary_dps",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).secondary_damage / duration for probe in probe_list
        ]),
        show_on_st=False,
    ),
]


DETAILED_METRICS: list[Metric] = [
    ScalarMetric(
        name="total",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).total_damage for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="main",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).main_damage for probe in probe_list
        ]),
    ),
    ScalarMetric(
        name="secondary",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).secondary_damage for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="total_dps",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).total_damage / duration for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="main_dps",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).main_damage / duration for probe in probe_list
        ]),
    ),
    ScalarMetric(
        name="secondary_dps",
        probe_type=DamageSplitProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            cast(DamageSplitProbe, probe).secondary_damage / duration for probe in probe_list
        ]),
        show_on_st=False,
    ),
    ScalarMetric(
        name="ults_cast",
        probe_type=CastCountProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            float(cast(CastCountProbe, probe).ult_count) for probe in probe_list
        ]),
    ),
    ScalarMetric(
        name="weapon_ability_casts",
        probe_type=CastCountProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            float(cast(CastCountProbe, probe).weapon_cast_count) for probe in probe_list
        ]),
    ),
    ScalarMetric(
        name="spirit_procs",
        probe_type=CastCountProbe,
        aggregate=lambda probe_list, duration: mean_stderr([
            float(cast(CastCountProbe, probe).spirit_proc_count) for probe in probe_list
        ]),
    ),
    TextMetric(
        name="sources_total",
        probe_type=DamageSourceProbe,
        render=lambda probe_list, duration: _format_damage_source_contribution([
            cast(DamageSourceProbe, probe).total_by_source for probe in probe_list
        ]),
        show_on_st=False,
    ),
    TextMetric(
        name="sources_main",
        probe_type=DamageSourceProbe,
        render=lambda probe_list, duration: _format_damage_source_contribution([
            cast(DamageSourceProbe, probe).main_by_source for probe in probe_list
        ]),
    ),
    TextMetric(
        name="sources_secondary",
        probe_type=DamageSourceProbe,
        render=lambda probe_list, duration: _format_damage_source_contribution([
            cast(DamageSourceProbe, probe).secondary_by_source for probe in probe_list
        ]),
        show_on_st=False,
    ),
    TextMetric(
        name="number_of_casts",
        probe_type=CastCountProbe,
        render=lambda probe_list, duration: _format_ability_cast_count([
            cast(CastCountProbe, probe).ability_cast_count for probe in probe_list
        ]),
    ),
    TextMetric(
        name="source_details",
        probe_type=DamageSourceProbe,
        render=lambda probe_list, duration: _format_source_details([
            cast(DamageSourceProbe, probe) for probe in probe_list
        ]),
    ),
    TextMetric(
        name="buff_uptime",
        probe_type=BuffUptimeProbe,
        render=lambda probe_list, duration: _format_buff_uptime(
            [cast(BuffUptimeProbe, probe) for probe in probe_list], duration
        ),
    ),
]
