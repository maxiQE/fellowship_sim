from dataclasses import dataclass, field

from loguru import logger

from fellowship_sim.base_classes import Player
from fellowship_sim.base_classes.events import Resource, ResourceChanged
from fellowship_sim.rime import rime_config

from .ability import (
    BurstingIce,
    ColdSnap,
    FlightOfTheNavir,
    FreezingTorrent,
    FrostBolt,
    GlacialBlast,
    IceBlitz,
    IceComet,
    WintersBlessing,
    WrathOfWinter,
)


@dataclass(kw_only=True, repr=False)
class Rime(Player):
    winter_orbs: int = field(default=0, init=False)
    max_winter_orbs: int = field(default=rime_config.RIME_MAX_WINTER_ORBS, init=False)
    anima: int = field(default=0, init=False)
    max_anima: int = field(default=rime_config.RIME_MAX_ANIMA, init=False)

    spirit_point_gain_on_proc: int = field(default=rime_config.RIME_SPIRIT_POINT_GAIN_ON_PROC, init=False)

    frost_bolt: "FrostBolt" = field(init=False)
    glacial_blast: "GlacialBlast" = field(init=False)
    ice_comet: "IceComet" = field(init=False)
    freezing_torrent: "FreezingTorrent" = field(init=False)
    cold_snap: "ColdSnap" = field(init=False)
    bursting_ice: "BurstingIce" = field(init=False)
    winters_blessing: "WintersBlessing" = field(init=False)
    ice_blitz: "IceBlitz" = field(init=False)
    flight_of_the_navir: "FlightOfTheNavir" = field(init=False)
    wrath_of_winter: "WrathOfWinter" = field(init=False)

    def __str__(self) -> str:
        spirit_info = f"spirit={self.spirit_points}/{self.max_spirit_points}"
        if self.spirit_points >= self.spirit_ability_cost:
            spirit_info = "** " + spirit_info + " **"
        return f"Rime(orbs={self.winter_orbs}, anima={self.anima}, {spirit_info}, effects={len(self.effects)})"

    def __post_init__(self) -> None:
        super().__post_init__()

        self.frost_bolt = FrostBolt(owner=self)
        self.glacial_blast = GlacialBlast(owner=self)
        self.ice_comet = IceComet(owner=self)
        self.freezing_torrent = FreezingTorrent(owner=self)
        self.cold_snap = ColdSnap(owner=self)
        self.bursting_ice = BurstingIce(owner=self)
        self.winters_blessing = WintersBlessing(owner=self)
        self.ice_blitz = IceBlitz(owner=self)
        self.flight_of_the_navir = FlightOfTheNavir(owner=self)
        self.wrath_of_winter = WrathOfWinter(owner=self)

        self.abilities = [
            self.frost_bolt,
            self.glacial_blast,
            self.ice_comet,
            self.freezing_torrent,
            self.cold_snap,
            self.bursting_ice,
            self.winters_blessing,
            self.ice_blitz,
            self.flight_of_the_navir,
            self.wrath_of_winter,
        ]

        self._recalculate_stats()

    @property
    def winters_embrace_duration(self) -> float:
        from .effect import BurstingIceEffect

        if not self.bursting_ice.has_winters_embrace:
            return 0

        bursting_ice_debuffs = [enemy.effects.get(BurstingIceEffect) for enemy in self.state.enemies]
        durations = [effect.duration for effect in bursting_ice_debuffs if effect is not None]
        durations.append(0)
        duration = max(durations)
        return duration

    def _change_orbs(self, change: int) -> None:
        new_orbs = max(0, min(self.max_winter_orbs, self.winter_orbs + change))
        logger.trace(f"Rime orb change: change={change}, old={self.winter_orbs}, new={new_orbs}")
        self.winter_orbs = new_orbs

        if change > 0:
            self.state.bus.emit(
                ResourceChanged(
                    owner=self,
                    resource_type=Resource.WINTER_ORBS,
                    resource_amount=change,
                )
            )
            logger.info(f"Rime orb gain: orbs={self.winter_orbs}")
            n_birds = change * rime_config.RIME_BIRDS_PER_ORB_GAINED
            self.flight_of_the_navir._do_bird_attack(n_birds=n_birds)

    def _change_anima(self, change: int) -> None:
        new_anima = max(0, self.anima + change)
        new_orbs = new_anima // self.max_anima
        new_anima = new_anima % self.max_anima

        if change > 0:
            self.state.bus.emit(
                ResourceChanged(
                    owner=self,
                    resource_type=Resource.ANIMA,
                    resource_amount=change,
                )
            )

        logger.trace(
            f"Rime anima change: change={change}, old_anima={self.anima}, new_anima={new_anima}", new_orbs={new_orbs}
        )

        if new_orbs > 0:
            self._change_orbs(new_orbs)

        self.anima = new_anima
