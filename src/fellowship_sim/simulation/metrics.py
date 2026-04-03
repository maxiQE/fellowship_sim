import math
from dataclasses import dataclass, field

from fellowship_sim.base_classes import WeaponAbility
from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    EventBus,
    SpiritProc,
    UltimateCast,
)


@dataclass(kw_only=True)
class MeanStd:
    mean: float
    stderr: float

    def __str__(self) -> str:
        return f"{self.mean:,.1f} ± {self.stderr:,.1f}"


@dataclass(kw_only=True)
class MetricsResult:
    total: MeanStd
    main: MeanStd
    secondary: MeanStd
    total_dps: MeanStd
    main_dps: MeanStd
    secondary_dps: MeanStd
    ults_cast: MeanStd
    weapon_ability_casts: MeanStd
    spirit_procs: MeanStd
    top_sources_total: list[tuple[str, int]]
    top_sources_main: list[tuple[str, int]]
    top_sources_secondary: list[tuple[str, int]]

    def __str__(self) -> str:
        show_secondary = self.secondary.mean > 0.0
        show_total = self.total.mean == 0.0 or abs(self.total.mean - self.main.mean) / self.total.mean > 0.001
        lines = []
        if show_total:
            lines.append(
                f"Total       : {self.total.mean:>12,.1f}  ± {self.total.stderr:>12,.1f}  ({self.total_dps} dps)"
            )
        lines.append(f"Main target : {self.main.mean:>12,.1f}  ± {self.main.stderr:>12,.1f}  ({self.main_dps} dps)")
        if show_secondary:
            lines.append(
                f"Secondary   : {self.secondary.mean:>12,.1f}  ± {self.secondary.stderr:>12,.1f}  ({self.secondary_dps} dps)"
            )
        lines.append(f"Ults        : {self.ults_cast}")
        lines.append(f"Weapon ABs  : {self.weapon_ability_casts}")
        lines.append(f"Spirit procs: {self.spirit_procs}")
        if show_total:
            lines.append(f"Sources (total) : {'  '.join(f'{n} {p}%' for n, p in self.top_sources_total)}")
        lines.append(f"Sources (main)  : {'  '.join(f'{n} {p}%' for n, p in self.top_sources_main)}")
        if show_secondary:
            lines.append(f"Sources (sec)   : {'  '.join(f'{n} {p}%' for n, p in self.top_sources_secondary)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-run collectors
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class _DamageSplitCollector:
    total_damage: float = field(default=0.0, init=False)
    main_damage: float = field(default=0.0, init=False)
    secondary_damage: float = field(default=0.0, init=False)
    _main: Entity = field(repr=False)
    _bus: EventBus = field(repr=False)

    def __post_init__(self) -> None:
        self._bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        self.total_damage += event.damage
        if event.target is self._main:
            self.main_damage += event.damage
        else:
            self.secondary_damage += event.damage


@dataclass(kw_only=True)
class _CastCountCollector:
    ult_count: int = field(default=0, init=False)
    weapon_cast_count: int = field(default=0, init=False)
    spirit_proc_count: int = field(default=0, init=False)
    _bus: EventBus = field(repr=False)

    def __post_init__(self) -> None:
        self._bus.subscribe(UltimateCast, self._on_ult, owner=self)
        self._bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)
        self._bus.subscribe(SpiritProc, self._on_spirit, owner=self)

    def _on_ult(self, event: UltimateCast) -> None:
        self.ult_count += 1

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        if isinstance(event.ability, WeaponAbility):
            self.weapon_cast_count += 1

    def _on_spirit(self, event: SpiritProc) -> None:
        self.spirit_proc_count += 1


@dataclass(kw_only=True)
class _DamageSourceCollector:
    _main: Entity = field(repr=False)
    _bus: EventBus = field(repr=False)
    _total_by_source: dict[str, float] = field(default_factory=dict, init=False)
    _main_by_source: dict[str, float] = field(default_factory=dict, init=False)
    _secondary_by_source: dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        name = type(event.damage_source).__name__
        self._total_by_source[name] = self._total_by_source.get(name, 0.0) + event.damage
        if event.target is self._main:
            self._main_by_source[name] = self._main_by_source.get(name, 0.0) + event.damage
        else:
            self._secondary_by_source[name] = self._secondary_by_source.get(name, 0.0) + event.damage


# ---------------------------------------------------------------------------
# Combining container
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class DamageMetrics:
    """Accumulates all metrics for one simulation run."""

    _main: Entity = field(repr=False)
    _bus: EventBus = field(repr=False)
    _damage_split: _DamageSplitCollector = field(init=False)
    _cast_counts: _CastCountCollector = field(init=False)
    _damage_sources: _DamageSourceCollector = field(init=False)

    def __post_init__(self) -> None:
        self._damage_split = _DamageSplitCollector(_main=self._main, _bus=self._bus)
        self._cast_counts = _CastCountCollector(_bus=self._bus)
        self._damage_sources = _DamageSourceCollector(_main=self._main, _bus=self._bus)

    @staticmethod
    def _mean_stderr(vals: list[float]) -> MeanStd:
        n = len(vals)
        mean = sum(vals) / n
        if n < 2:
            return MeanStd(mean=mean, stderr=0.0)
        variance = sum((v - mean) ** 2 for v in vals) / (n - 1)
        return MeanStd(mean=mean, stderr=math.sqrt(variance / n))

    @staticmethod
    def _top_sources(source_dicts: list[dict[str, float]]) -> list[tuple[str, int]]:
        all_keys: set[str] = set()
        for d in source_dicts:
            all_keys.update(d.keys())
        avg: dict[str, float] = {
            key: sum(d.get(key, 0.0) for d in source_dicts) / len(source_dicts) for key in all_keys
        }
        total = sum(avg.values())
        if total == 0.0:
            return []
        top = sorted(avg.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return [(name, int(dmg / total * 100)) for name, dmg in top]

    @classmethod
    def compute_metrics(cls, results: list["DamageMetrics"], fight_duration: float) -> MetricsResult:
        total = cls._mean_stderr([r._damage_split.total_damage for r in results])
        main = cls._mean_stderr([r._damage_split.main_damage for r in results])
        secondary = cls._mean_stderr([r._damage_split.secondary_damage for r in results])
        return MetricsResult(
            total=total,
            main=main,
            secondary=secondary,
            total_dps=MeanStd(mean=total.mean / fight_duration, stderr=total.stderr / fight_duration),
            main_dps=MeanStd(mean=main.mean / fight_duration, stderr=main.stderr / fight_duration),
            secondary_dps=MeanStd(mean=secondary.mean / fight_duration, stderr=secondary.stderr / fight_duration),
            ults_cast=cls._mean_stderr([float(r._cast_counts.ult_count) for r in results]),
            weapon_ability_casts=cls._mean_stderr([float(r._cast_counts.weapon_cast_count) for r in results]),
            spirit_procs=cls._mean_stderr([float(r._cast_counts.spirit_proc_count) for r in results]),
            top_sources_total=cls._top_sources([r._damage_sources._total_by_source for r in results]),
            top_sources_main=cls._top_sources([r._damage_sources._main_by_source for r in results]),
            top_sources_secondary=cls._top_sources([r._damage_sources._secondary_by_source for r in results]),
        )
