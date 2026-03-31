from dataclasses import dataclass, field

from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.base_classes.events import AbilityDamage, EventBus


@dataclass(kw_only=True)
class DamageMetrics:
    """Accumulates damage split by target role over one simulation run."""

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
