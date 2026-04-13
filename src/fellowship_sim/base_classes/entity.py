import itertools
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from loguru import logger

from . import base_config
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
    from .state import State
    from .stats import MutableStats


_entity_id_counter = itertools.count(1)

DAMAGE_TRACKER_BIN_SIZE: Final[float] = 10.0


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
    bin_key_size: float = field(default=DAMAGE_TRACKER_BIN_SIZE, init=True)

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
        """Total damage dealt across all sources."""
        return sum(record.total for record in self._by_source.values())

    @property
    def by_source(self) -> dict[str, DamageRecord]:
        """Damage records keyed by ability class name."""
        return dict(self._by_source)

    @property
    def by_time_bin(self) -> dict[int, dict[str, DamageRecord]]:
        """Damage records grouped by time bin (bin_key_size seconds each), then by source."""
        return {k: dict(v) for k, v in self._by_time_bin.items()}

    @property
    def total_by_time_bin(self) -> dict[int, float]:
        """Total damage per time bin, summed across all sources."""
        return {k: sum(r.total for r in v.values()) for k, v in self._by_time_bin.items()}


@dataclass(kw_only=True)
class Entity:
    state: "State"
    effects: EffectCollection = field(default_factory=EffectCollection)
    percent_hp: float = field(default=1.0)
    is_alive: bool = field(default=True, init=False)
    is_main: bool = field(default=False)
    damage_tracker: DamageTracker = field(default_factory=DamageTracker)
    id: int = field(default_factory=lambda: next(_entity_id_counter), init=False)

    def __post_init__(self) -> None:
        self.effects._entity = self

    def kill(self) -> None:
        """Mark this entity as dead, remove all its effects, and emit UnitDestroyed."""
        from fellowship_sim.base_classes.events import UnitDestroyed

        if not self.is_alive:
            logger.error(f"Double-death on {self = }")
            return

        self.is_alive = False

        # NB: list(self.effects) to copy; otherwise, the iterand changes size
        for effect in list(self.effects):
            if effect.attached_to is not None:
                effect.remove()

        self.state.bus.emit(UnitDestroyed(entity=self))

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
    is_boss: bool = field(default=False, init=True)
    spirit_score: float = field(default=0, init=True)

    def __post_init__(self) -> None:
        from fellowship_sim.base_classes.timed_events import UnitDeathTimedEvent

        super().__post_init__()

        self.state.add_enemy(self)

        if math.isfinite(self.time_to_live):
            self.state.schedule(self.time_to_live, UnitDeathTimedEvent(entity=self, callback=self.kill))

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

        self.state.add_character(self)

        # Initialize self.stats from init field self.raw_stats
        self._recalculate_stats()

    def wait(self, duration: float) -> None:
        """Take no action for the specified duration.

        Args:
            duration: Seconds to wait.
        """
        from .timed_events import PlayerAvailableAgain, PlayerUnavailable

        state = self.state

        state.schedule(time_delay=0, callback=PlayerUnavailable())
        state.schedule(time_delay=duration, callback=PlayerAvailableAgain())

        state.step()

    def _tick(self, dt: float) -> None:
        super()._tick(dt)
        self._spirit_regen(dt)

    @property
    def spirit_regen_rate(self) -> float:
        time_based_regen_rate: int | float = (
            base_config.SPIRIT_PER_SECOND * (1 + self.stats.spirit_percent) * self.max_spirit_points / 100
        )

        enemy_hp_loss_spirit_regen_rate = 0
        for enemy in self.state.enemies:
            enemy_hp_loss_spirit_regen_rate += 1 / enemy.time_to_live * enemy.spirit_score / 4

        total_spirit_rate = time_based_regen_rate + enemy_hp_loss_spirit_regen_rate
        return total_spirit_rate

    def _spirit_regen(self, dt: float) -> None:
        total_spirit_increase = self.spirit_regen_rate * dt
        self._change_spirit_points(total_spirit_increase)

    def _change_spirit_points(self, change: float) -> None:
        """Adjust spirit_points by change, clamped to [0, max_spirit_points]."""
        self.spirit_points = max(0, min(self.max_spirit_points, self.spirit_points + change))

    def _recalculate_stats(self) -> "MutableStats":
        """Recompute stats by firing ComputeFinalStats and applying collected modifiers."""
        from .events import ComputeFinalStats

        event = ComputeFinalStats(owner=self, raw_stats=self.raw_stats)
        self.state.bus.emit(event)
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
