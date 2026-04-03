import itertools
import re
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

_entity_id_counter = itertools.count(1)


@dataclass(kw_only=True)
class DamageTracker:
    _by_source: dict[str, float] = field(default_factory=dict)

    def _register_damage(self, source_name: str, amount: float) -> None:
        self._by_source[source_name] = self._by_source.get(source_name, 0.0) + amount

    @property
    def total(self) -> float:
        return sum(self._by_source.values())

    @property
    def by_source(self) -> dict[str, float]:
        return dict(self._by_source)


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
            self.damage_tracker._register_damage(type(event.damage_source).__name__, event.damage)

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

    healthpoints: float = field(default=300_000.0, init=False)
    stats: FinalStats = field(init=False)
    abilities: list[Ability] = field(default_factory=list)

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

    def _recalculate_stats(self) -> None:
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

    def _recalculate_cdr_multipliers(self) -> None:
        """Recompute cached CDR multipliers for all abilities.

        Call this whenever haste changes (via recalculate_stats) or when an effect
        that subscribes to ComputeCooldownReduction is added or removed.
        """
        for ability in self.abilities:
            ability._recalculate_cdr_multiplier()
