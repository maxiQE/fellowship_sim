import itertools
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

from .ability import (
    WEAPON_ABILITY_NOT_INITIALIZED,
    Ability,
    WeaponAbility,
    WeaponAbilityNotInitialized,
)
from .effect import EffectCollection
from .stats import FinalStats, RawStats

if TYPE_CHECKING:
    from .events import AbilityDamage, AbilityPeriodicDamage
    from .stats import MutableStats


_entity_id_counter = itertools.count(1)


@dataclass(kw_only=True)
class DamageRecord:
    total: float = field(default=0.0, init=False)
    count: int = field(default=0, init=False)
    crits: int = field(default=0, init=False)
    grievous_crits: int = field(default=0, init=False)

    def _add(self, event: "AbilityDamage | AbilityPeriodicDamage") -> None:
        self.total += event.damage
        self.count += 1
        if event.is_crit:
            self.crits += 1
        if event.is_grievous_crit:
            self.grievous_crits += 1


@dataclass(kw_only=True)
class DamageTracker:
    bin_key_size: float = field(default=10.0, init=True)

    _by_source: defaultdict[str, DamageRecord] = field(default_factory=lambda: defaultdict(DamageRecord), init=False)
    _by_time_bin: defaultdict[int, defaultdict[str, DamageRecord]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(DamageRecord)), init=False
    )

    def _register_damage(self, event: "AbilityDamage | AbilityPeriodicDamage") -> None:
        source_name = type(event.damage_source).__name__
        self._by_source[source_name]._add(event)
        self._by_time_bin[int(event.time // self.bin_key_size)][source_name]._add(event)

    @property
    def total(self) -> float:
        return sum(record.total for record in self._by_source.values())

    @property
    def by_source(self) -> dict[str, DamageRecord]:
        return dict(self._by_source)

    @property
    def by_time_bin(self) -> dict[int, dict[str, DamageRecord]]:
        return {k: dict(v) for k, v in self._by_time_bin.items()}

    @property
    def total_by_time_bin(self) -> dict[int, float]:
        return {k: sum(r.total for r in v.values()) for k, v in self._by_time_bin.items()}


@dataclass(kw_only=True)
class Entity:
    effects: EffectCollection = field(default_factory=EffectCollection)
    percent_hp: float = field(default=1.0)
    damage_tracker: DamageTracker = field(default_factory=DamageTracker)
    id: int = field(default_factory=lambda: next(_entity_id_counter), init=False)

    def __post_init__(self) -> None:
        self.effects._entity = self

    @property
    def is_alive(self) -> bool:
        return self.percent_hp > 0

    def __str__(self) -> str:
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(self).__name__)
        return f"{name}({self.id}, dmg taken={self.damage_tracker.total:.0f})"

    def __repr__(self) -> str:
        return str(self)

    def _take_damage(self, event: "AbilityDamage | AbilityPeriodicDamage") -> None:
        if self.is_alive:
            self.damage_tracker._register_damage(event=event)

    def _tick(self, dt: float) -> None:
        pass


@dataclass(kw_only=True)
class Enemy(Entity):
    time_to_live: float = field(default=float("inf"), init=True)

    def _tick(self, dt: float) -> None:
        self.percent_hp -= dt / self.time_to_live


@dataclass(kw_only=True, repr=False)
class Player(Entity):
    raw_stats: RawStats

    stats: FinalStats = field(init=False)

    healthpoints: float = field(default=300_000.0, init=False)
    abilities: list[Ability] = field(default_factory=list, init=False)

    spirit_points: float = field(default=0.0, init=False)
    max_spirit_points: float = field(default=100.0, init=False)
    spirit_ability_cost: float = field(default=100.0, init=False)

    spirit_point_per_s: float = field(default=0.2, init=False)

    # Weapon ability slots — one per available weapon ability type.
    # Unequipped slots hold WEAPON_ABILITY_NOT_INITIALIZED (logs a warning on access).
    weapon_ability: "WeaponAbility | WeaponAbilityNotInitialized" = field(
        default=WEAPON_ABILITY_NOT_INITIALIZED, init=False
    )

    voidbringers_touch: "WeaponAbility | WeaponAbilityNotInitialized" = field(
        default=WEAPON_ABILITY_NOT_INITIALIZED, init=False
    )
    chronoshift: "WeaponAbility | WeaponAbilityNotInitialized" = field(
        default=WEAPON_ABILITY_NOT_INITIALIZED, init=False
    )
    natures_fury: "WeaponAbility | WeaponAbilityNotInitialized" = field(
        default=WEAPON_ABILITY_NOT_INITIALIZED, init=False
    )
    icicles_of_anzhyr: "WeaponAbility | WeaponAbilityNotInitialized" = field(
        default=WEAPON_ABILITY_NOT_INITIALIZED, init=False
    )

    def __post_init__(self) -> None:
        super().__post_init__()

        # Initialize self.stats from init field self.raw_stats
        self._recalculate_stats()

    def wait(self, duration: float) -> None:
        from .state import get_state  # lazy — avoids circular import
        from .timed_events import PlayerAvailableAgain

        state = get_state()
        state.schedule(time_delay=duration, callback=PlayerAvailableAgain())
        state.step()

    def _tick(self, dt: float) -> None:
        super()._tick(dt)
        self._change_spirit_points(self.spirit_point_per_s * dt)

    def _change_spirit_points(self, change: float) -> None:
        self.spirit_points = max(0, min(self.max_spirit_points, self.spirit_points + change))

    def _recalculate_stats(self) -> "MutableStats":
        """Recompute stats by firing ComputeFinalStats and applying collected modifiers."""
        from .events import ComputeFinalStats
        from .state import get_state

        event = ComputeFinalStats(owner=self, raw_stats=self.raw_stats)
        get_state().bus.emit(event)
        mutable = self.raw_stats.to_mutable_stats()
        for modifier in event.modifiers:
            modifier.apply(mutable)
        self.stats = mutable.finalize()
        logger.debug(f"stats recalculated for {self}: {self.stats}")
        self._recalculate_cdr_multipliers()

        return mutable

    def _recalculate_cdr_multipliers(self) -> None:
        """Recompute cached CDR multipliers for all abilities.

        Call this whenever haste changes (via recalculate_stats) or when an effect
        that subscribes to ComputeCooldownReduction is added or removed.
        """
        for ability in self.abilities:
            ability._recalculate_cdr_multiplier()
