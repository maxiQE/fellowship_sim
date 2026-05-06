from dataclasses import dataclass, field

from loguru import logger

from fellowship_sim.base_classes import Ability, Player
from fellowship_sim.base_classes.events import Resource, ResourceSpent

from .ability import (
    Apocalypse,
    Detonate,
    EngulfingFlames,
    FireBall,
    FireFrogs,
    Incinerate,
    InfernalWave,
    Pyromania,
    SearingBlaze,
    Wildfire,
)


@dataclass(kw_only=True, repr=False)
class Ardeos(Player):
    cinders: int = field(default=0, init=False)
    max_cinders: int = field(default=100)
    embers: int = field(default=0, init=False)
    max_embers: int = field(default=4, init=False)

    def __str__(self) -> str:
        spirit_info = f"spirit={self.spirit_points}/{self.max_spirit_points}"
        if self.spirit_points >= self.spirit_ability_cost:
            spirit_info = "** " + spirit_info + " **"
        return f"Ardeos(embers={self.embers}, cinders={self.cinders}, {spirit_info}, effects={len(self.effects)})"

    def __post_init__(self) -> None:
        super().__post_init__()

        self.apocalypse = Apocalypse(owner=self)
        self.detonate = Detonate(owner=self)
        self.engulfing_flames = EngulfingFlames(owner=self)
        self.fire_ball = FireBall(owner=self)
        self.fire_frogs = FireFrogs(owner=self)
        self.incinerate = Incinerate(owner=self)
        self.infernal_wave = InfernalWave(owner=self)
        self.pyromania = Pyromania(owner=self)
        self.searing_blaze = SearingBlaze(owner=self)
        self.wildfire = Wildfire(owner=self)

        self.abilities = [
            self.apocalypse,
            self.detonate,
            self.engulfing_flames,
            self.fire_ball,
            self.fire_frogs,
            self.incinerate,
            self.infernal_wave,
            self.pyromania,
            self.searing_blaze,
            self.wildfire,
        ]

        self._recalculate_stats()

    def _change_cinder(self, change: int) -> None:
        total = self.cinders + change
        ember_change = total // self.max_cinders
        new_cinder = total % self.max_cinders

        self.cinders = new_cinder
        if ember_change > 0:
            self._gain_ember(ember_change)

        logger.trace(f"Ardeos cinder change: change={change}, new_cinder={new_cinder}, ember_change={ember_change}")

    def _gain_ember(self, change: int) -> None:
        if change <= 0:
            raise ValueError()

        new_ember = min(self.max_embers, self.embers + change)
        self.embers = new_ember

        logger.trace(f"Ardeos ember change: change={change}, new_ember={new_ember}")

    def _spend_ember(self, cost: int, ability: Ability) -> None:
        if cost <= 0:
            raise ValueError()

        self.embers -= cost
        self.state.bus.emit(
            ResourceSpent(
                owner=self,
                ability=ability,
                target=None,
                resource_type=Resource.EMBERS,
                resource_amount=cost,
            )
        )
