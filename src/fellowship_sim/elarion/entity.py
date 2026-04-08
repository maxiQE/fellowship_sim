from dataclasses import dataclass, field

from loguru import logger

from fellowship_sim.base_classes import Ability, Player
from fellowship_sim.elarion.effect import CelestialImpetusProc

from .ability import (
    CelestialShot,
    EventHorizon,
    FocusedShot,
    HeartseekerBarrage,
    HighwindArrow,
    LunarlightExplosion,
    LunarlightMark,
    LunarlightSalvo,
    Multishot,
    SkystriderGrace,
    SkystriderSupremacy,
    Volley,
)


@dataclass(kw_only=True, repr=False)
class Elarion(Player):
    focus: float = field(default=100.0, init=True)
    max_focus: float = field(default=100.0, init=False)
    focus_regen_rate: float = field(default=5.0 / 1.5, init=False)  # focus per second at zero haste

    has_increased_proc_chance_barrage: bool = field(default=False, init=False)
    has_increased_proc_chance_volley: bool = field(default=False, init=False)

    event_horizon__reduce_focust_cost: bool = field(default=False, init=False)

    abilities: list[Ability] = field(default_factory=list, init=False)

    lunarlight_mark: "LunarlightMark" = field(init=False)
    _lunarlight_salvo: "LunarlightSalvo" = field(init=False)
    _lunarlight_explosion: "LunarlightExplosion" = field(init=False)
    focused_shot: "FocusedShot" = field(init=False)
    celestial_shot: "CelestialShot" = field(init=False)
    multishot: "Multishot" = field(init=False)
    highwind_arrow: "HighwindArrow" = field(init=False)
    volley: "Volley" = field(init=False)
    heartseeker_barrage: "HeartseekerBarrage" = field(init=False)
    skystrider_grace: "SkystriderGrace" = field(init=False)
    event_horizon: "EventHorizon" = field(init=False)
    skystrider_supremacy: "SkystriderSupremacy" = field(init=False)

    @property
    def celestial_impetus_stacks(self) -> int:
        ci_proc_effect = self.effects.get(CelestialImpetusProc)
        return ci_proc_effect.stacks if ci_proc_effect is not None else 0

    def __str__(self) -> str:
        spirit_info = f"spirit={self.spirit_points}/{self.max_spirit_points}"
        if self.spirit_points >= self.spirit_ability_cost:
            spirit_info = "** " + spirit_info + " **"
        return f"Elarion(focus={self.focus:.1f}, {spirit_info}, effects={len(self.effects)})"

    def _tick(self, dt: float) -> None:
        super()._tick(dt)

        gain = self.focus_regen_rate * (1 + self.stats.haste_percent) * dt
        self._change_focus(gain)
        logger.trace(f"focus regen: +{gain:.2f} -> {self.focus:.1f}/{self.max_focus}")

    def __post_init__(self) -> None:
        super().__post_init__()

        self.lunarlight_mark = LunarlightMark(owner=self)
        self._lunarlight_salvo = LunarlightSalvo(owner=self)
        self._lunarlight_explosion = LunarlightExplosion(owner=self)
        self.focused_shot = FocusedShot(owner=self)
        self.celestial_shot = CelestialShot(owner=self)
        self.multishot = Multishot(owner=self)
        self.highwind_arrow = HighwindArrow(owner=self)
        self.volley = Volley(owner=self)
        self.heartseeker_barrage = HeartseekerBarrage(owner=self)
        self.skystrider_grace = SkystriderGrace(owner=self)
        self.event_horizon = EventHorizon(owner=self)
        self.skystrider_supremacy = SkystriderSupremacy(owner=self)

        self.abilities = [
            self.lunarlight_mark,
            self.focused_shot,
            self.celestial_shot,
            self.multishot,
            self.highwind_arrow,
            self.volley,
            self.heartseeker_barrage,
            self.skystrider_grace,
            self.event_horizon,
            self.skystrider_supremacy,
        ]

        self._recalculate_stats()

    def _change_focus(self, change: float) -> None:
        new_focus = self.focus + change
        if new_focus < 0:
            # This indicates that a validation has gone completely wrong
            raise ValueError(f"Negative focus after change: {new_focus}")  # noqa: TRY003

        self.focus = min(new_focus, self.max_focus)
