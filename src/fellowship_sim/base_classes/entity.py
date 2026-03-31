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

    def __str__(self) -> str:
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(self).__name__)
        return f"{name}({self.id}, dmg taken={self.damage_tracker.total:.0f})"

    def __repr__(self) -> str:
        return str(self)

    def _take_damage(self, event: "AbilityDamage | AbilityPeriodicDamage") -> None:
        self.damage_tracker._register_damage(type(event.damage_source).__name__, event.damage)


@dataclass(kw_only=True, repr=False)
class Player(Entity):
    raw_stats: RawStats
    healthpoints: float = 300_000.0
    stats: FinalStats = field(init=False)
    abilities: list[Ability] = field(default_factory=list)
    spirit_points: float = 0.0
    max_spirit_points: float = 100.0
    spirit_ability_cost: float = 100.0

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
        pass

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
