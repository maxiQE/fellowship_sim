import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from fellowship_sim.base_classes import Entity, create_standard_damage
from fellowship_sim.base_classes.ability import (
    Ability,
    CastReturnCode,
    can_cast_check,
)
from fellowship_sim.base_classes.effect import Effect
from fellowship_sim.base_classes.events import Resource, ResourceSpent
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.rime import rime_config
from fellowship_sim.rime.effect import (
    BurstingIceEffect,
    FlightOfTheNavirEffect,
    FrostwyrmsSpiteEffect,
    GlacialAssaultAura,
    IceBlitzBuff,
    IcyFlowEffect,
    NavirsKeeper,
    SoulfrostTorrentEffect,
    WintersBlessingBuff,
    WrathOfWinterEffect,
)

if TYPE_CHECKING:
    from .entity import Rime  # noqa: F401


@dataclass(kw_only=True, repr=False)
class RimeAbility(Ability["Rime"]):
    """Base class for all Rime abilities.

    Declares orb-cost
    """

    base_orb_cost: int = field(default=0, init=False)

    delay_until_hit: float = field(default=rime_config.RIME_ABILITY_DELAY_UNTIL_HIT)  # Flight time of the missile

    @can_cast_check
    def _orbs(self) -> CastReturnCode:
        return CastReturnCode.OK if self.owner.winter_orbs >= self.orb_cost else CastReturnCode.INSUFFICENT_RESOURCES

    @property
    def orb_cost(self) -> int:
        return self.base_orb_cost

    def _pay_cost_for_cast(self, target: Entity) -> None:
        """Add to pay for orb cost"""
        super()._pay_cost_for_cast(target)

        self._pay_orb_cost(target)

    def _pay_orb_cost(self, target: Entity) -> None:
        orb_cost = self.orb_cost
        if orb_cost:
            self.owner._change_orbs(-orb_cost)

            state = self.owner.state
            state.bus.emit(
                ResourceSpent(
                    ability=self,
                    owner=self.owner,
                    target=target,
                    resource_type=Resource.WINTER_ORBS,
                    resource_amount=orb_cost,
                )
            )


@dataclass(kw_only=True, repr=False)
class FrostBolt(RimeAbility):
    """Hurl a bolt of frost magic at target enemy, dealing 2,106 - 2,574 damage."""

    average_damage: float = field(
        default=(rime_config.FROST_BOLT_DAMAGE_MIN + rime_config.FROST_BOLT_DAMAGE_MAX) / 2, init=False
    )
    base_cast_time: float = field(default=rime_config.FROST_BOLT_CAST_TIME, init=False)
    base_player_downtime: float = field(default=rime_config.FROST_BOLT_CAST_TIME, init=False)

    anima_gain: int = field(default=1, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten to add +1 anima to cast."""
        super()._do_cast(target)

        self.owner._change_anima(self.anima_gain)


@dataclass(kw_only=True, repr=False)
class GlacialBlast(RimeAbility):
    """Hurl a mass of ice at target enemy, dealing 10,693 - 13,069 damage."""

    _base_orb_cost: int = field(default=rime_config.GLACIAL_BLAST_ORB_COST, init=False)

    average_damage: float = field(
        default=(rime_config.GLACIAL_BLAST_DAMAGE_MIN + rime_config.GLACIAL_BLAST_DAMAGE_MAX) / 2, init=False
    )
    base_cast_time: float = field(default=rime_config.GLACIAL_BLAST_CAST_TIME, init=False)
    base_player_downtime: float = field(default=rime_config.GLACIAL_BLAST_CAST_TIME, init=False)

    winterswrath_cast_time: float = field(default=rime_config.GLACIAL_BLAST_WRATH_OF_WINTER_CAST_TIME, init=False)
    winterswrath_player_downtime: float = field(
        default=rime_config.GLACIAL_BLAST_WRATH_OF_WINTER_PLAYER_DOWNTIME, init=False
    )

    glacial_assault_cast_time: float = field(default=rime_config.GLACIAL_BLAST_GLACIAL_ASSAULT_CAST_TIME, init=False)
    glacial_assault_player_downtime: float = field(
        default=rime_config.GLACIAL_BLAST_GLACIAL_ASSAULT_PLAYER_DOWNTIME, init=False
    )
    glacial_assault_orb_cost: int = field(default=rime_config.GLACIAL_BLAST_GLACIAL_ASSAULT_ORB_COST, init=False)
    icy_flow_cast_time_reduction: float = field(
        default=rime_config.GLACIAL_BLAST_ICY_FLOW_CAST_TIME_REDUCTION, init=False
    )

    def is_empowered(self) -> bool:
        glacial_assault = self.owner.effects.get(GlacialAssaultAura)
        return (
            self.owner.effects.has(WrathOfWinterEffect)
            or self.owner.effects.has(IcyFlowEffect)
            or (glacial_assault is not None and glacial_assault.is_ready)
        )

    def empowered_by(self) -> str:
        active: list[str] = []
        if self.owner.effects.has(WrathOfWinterEffect):
            active.append("Wrath of Winter")
        if self.owner.effects.has(IcyFlowEffect):
            active.append("Icy Flow")
        glacial_assault = self.owner.effects.get(GlacialAssaultAura)
        if glacial_assault is not None and glacial_assault.is_ready:
            active.append("Glacial Assault")
        return ", ".join(active) if active else "Not empowered"

    @property
    def base_orb_cost(self) -> int:
        """Overwritten base field to make it dynamic depending on GlacialAssault."""

        glacial_assault = self.owner.effects.get(GlacialAssaultAura)
        if glacial_assault is not None and glacial_assault.is_ready:
            return self.glacial_assault_orb_cost
        else:
            return self._base_orb_cost

    @property
    def cast_time(self) -> float:
        if self.owner.effects.has(WrathOfWinterEffect):
            return self.winterswrath_cast_time
        glacial_assault = self.owner.effects.get(GlacialAssaultAura)
        if glacial_assault is not None and glacial_assault.is_ready:
            return self.glacial_assault_cast_time
        if self.owner.effects.has(IcyFlowEffect):
            return (self.base_cast_time - self.icy_flow_cast_time_reduction) / (
                1 + self.owner.stats.haste_percent
            )
        return super().cast_time

    @property
    def player_downtime(self) -> float:
        if self.owner.effects.has(WrathOfWinterEffect):
            return self.winterswrath_player_downtime
        glacial_assault = self.owner.effects.get(GlacialAssaultAura)
        if glacial_assault is not None and glacial_assault.is_ready:
            return self.glacial_assault_player_downtime
        if self.owner.effects.has(IcyFlowEffect):
            return (self.base_player_downtime - self.icy_flow_cast_time_reduction) / (
                1 + self.owner.stats.haste_percent
            )
        return super().player_downtime


@dataclass(kw_only=True, repr=False)
class IceComet(RimeAbility):
    """Unleash a large Ice Comet from above target enemy to crash down on them, dealing 4,261 - 5,208 damage to all enemies caught in the impact radius."""

    base_orb_cost: float = field(default=rime_config.ICE_COMET_ORB_COST, init=False)

    average_damage: float = field(
        default=(rime_config.ICE_COMET_DAMAGE_MIN + rime_config.ICE_COMET_DAMAGE_MAX) / 2, init=False
    )
    num_secondary_targets: int = field(default=rime_config.ICE_COMET_NUM_SECONDARY_TARGETS, init=False)
    num_targets_softcap: int = field(default=rime_config.ICE_COMET_NUM_TARGETS_SOFTCAP, init=False)

    minimum_delay_until_hit: float = field(default=rime_config.ICE_COMET_ICY_FLOW_MINIMUM_DELAY, init=False)
    icy_flow_delay_reduction: float = field(default=rime_config.ICE_COMET_ICY_FLOW_DELAY_REDUCTION, init=False)

    has_avalanche_talent: bool = field(default=False, init=False)
    avalanche_2_hit_chance: float = field(default=rime_config.AVALANCHE_2_HIT_CHANCE, init=False)
    avalanche_3_hit_chance: float = field(default=rime_config.AVALANCHE_3_HIT_CHANCE, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten for avalanche talent which can proc multiple IceComet attacks."""
        state = self.owner.state

        number_of_hits = 1

        if self.has_avalanche_talent:
            roll = state.rng.random()
            if roll < self.avalanche_3_hit_chance:
                number_of_hits = 3
            elif roll < self.avalanche_3_hit_chance + self.avalanche_2_hit_chance:
                number_of_hits = 2

        for hit_number in range(1, number_of_hits + 1):
            delay_until_hit = self.delay_until_hit * hit_number
            if hit_number == 1 and self.owner.effects.has(IcyFlowEffect):
                delay_until_hit = max(
                    self.minimum_delay_until_hit, delay_until_hit - self.icy_flow_delay_reduction
                )

            create_standard_damage(
                state,
                self,
                self.owner,
                target,
                self.average_damage,
                delay_until_hit=delay_until_hit,
                main_damage_multiplier=self.main_damage_multiplier,
                num_secondary_targets=self.num_secondary_targets,
                num_targets_softcap=self.num_targets_softcap,
                secondary_damage_multiplier=self.secondary_damage_multiplier,
            )


@dataclass(kw_only=True, repr=False)
class FreezingTorrent(RimeAbility):
    """Flay your target with a beam of frost energy, dealing 1,405 - 1,718 damage every 0.4 seconds for 2 seconds while channeling."""

    base_cooldown: float = field(default=rime_config.FREEZING_TORRENT_COOLDOWN, init=False)
    base_player_downtime: float = field(default=rime_config.FREEZING_TORRENT_CHANNEL_DURATION, init=False)

    average_damage: float = field(
        default=(rime_config.FREEZING_TORRENT_DAMAGE_MIN + rime_config.FREEZING_TORRENT_DAMAGE_MAX) / 2, init=False
    )

    has_unhasted_cast_time: bool = field(default=True, init=False)
    base_tick_interval: float = field(default=rime_config.FREEZING_TORRENT_TICK_TIME, init=False)
    soulfrost_speed_multiplier: float = field(default=rime_config.SOULFROST_TORRENT_FT_SPEED_MULTIPLIER, init=False)
    partial_clip_threshold: float = field(default=rime_config.FREEZING_TORRENT_PARTIAL_CLIP_THRESHOLD, init=False)

    @property
    def channel_time(self) -> float:
        return self.base_player_downtime

    def is_empowered(self) -> bool:
        return self.owner.effects.has(SoulfrostTorrentEffect)

    def empowered_by(self) -> Literal["Soulfrost Torrent", "Not empowered"]:
        if self.owner.effects.has(SoulfrostTorrentEffect):
            return "Soulfrost Torrent"
        else:
            return "Not empowered"

    def _do_cast(self, target: Entity) -> None:
        """Overwritten to implement channel logic, with partial."""
        state = self.owner.state

        base_tick_interval = self.base_tick_interval

        soulfrost_torrent = self.owner.effects.get(SoulfrostTorrentEffect)
        if soulfrost_torrent is not None:
            base_tick_interval /= self.soulfrost_speed_multiplier
            state.schedule(
                time_delay=self.channel_time,
                callback=GenericTimedEvent(name="Remove soulfrost torrent", callback=soulfrost_torrent.remove),
            )

        haste = self.owner.stats.haste_percent
        tick_interval = base_tick_interval / (1 + haste)
        epsilon = 0.001
        num_ticks = math.floor(self.channel_time / tick_interval + epsilon)

        partial_size = (self.channel_time - num_ticks * tick_interval) / tick_interval

        num_ticks += 1

        # special to freezing torrent: small partial are clipped
        partial_size = partial_size if partial_size >= self.partial_clip_threshold else 0

        # shaving a slight amount off tick_interval to ensure that when player is available, all shots have been fired
        tick_interval *= 0.999

        def _next_channel_tick() -> None:
            self._schedule_channel_attack(
                target=target,
                tick_interval=tick_interval,
                hit_counter=0,
                total_count=num_ticks,
                partial_size=partial_size,
                partial_time=state.time + self.channel_time,
            )

        # NB: freezing torrent has immediate damage tick
        state.schedule(
            time_delay=0, callback=GenericTimedEvent(name="freezing torrent tick", callback=_next_channel_tick)
        )

    def _schedule_channel_attack(
        self,
        target: Entity,
        tick_interval: float,
        hit_counter: int,
        total_count: int,
        partial_size: float,
        partial_time: float,
    ) -> None:
        state = self.owner.state
        if state.time > partial_time:
            raise Exception(  # noqa: TRY002, TRY003
                f"Unexpected behavior in freezing torrent: partial time f{partial_time} is earlier than current time {state.time}"
            )

        if hit_counter < total_count:  # noqa: SIM108
            base_damage = self.average_damage
        else:
            base_damage = self.average_damage * partial_size

        if base_damage < 1e-6:
            return

        create_standard_damage(
            state=state,
            damage_source=self,
            owner=self.owner,
            target=target,
            base_damage=base_damage,
            num_secondary_targets=self.num_secondary_targets,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
            delay_until_hit=0,
        )

        def _next_channel_tick() -> None:
            self._schedule_channel_attack(
                target=target,
                tick_interval=tick_interval,
                hit_counter=hit_counter + 1,
                total_count=total_count,
                partial_size=partial_size,
                partial_time=partial_time,
            )

        if hit_counter < total_count - 1:
            state.schedule(
                time_delay=tick_interval, callback=GenericTimedEvent(name="barrage tick", callback=_next_channel_tick)
            )

        elif hit_counter == total_count - 1 and partial_size > 0:
            state.schedule(
                time_delay=partial_time - state.time,
                callback=GenericTimedEvent(name="barrage tick", callback=_next_channel_tick),
            )


@dataclass(kw_only=True, repr=False)
class ColdSnap(RimeAbility):
    """Assault the target with extreme cold, dealing 3,283 - 4,012 damage."""

    average_damage: float = field(
        default=(rime_config.COLD_SNAP_DAMAGE_MIN + rime_config.COLD_SNAP_DAMAGE_MAX) / 2, init=False
    )

    base_cooldown: float = field(default=rime_config.COLD_SNAP_COOLDOWN, init=False)

    max_charges: int = field(default=rime_config.COLD_SNAP_MAX_CHARGES, init=False)
    initial_charges: int = field(default=rime_config.COLD_SNAP_MAX_CHARGES, init=False)
    has_hasted_cda: bool = field(default=True, init=False)

    orb_gain: int = field(default=1, init=False)
    frostwyrms_spite_damage_bonus: float = field(
        default=rime_config.FROSTWYRMS_SPITE_DAMAGE_BONUS_PER_STACK, init=False
    )

    def is_empowered(self) -> bool:
        return self.owner.effects.has(NavirsKeeper) or self.empowered_by__frostwyrms_spite_instance() is not None

    def empowered_by(self) -> Literal["Navir's Keeper", "Frostwyrm's Spite", "Not empowered"]:
        if self.owner.effects.has(NavirsKeeper):
            return "Navir's Keeper"
        if self.empowered_by__frostwyrms_spite_instance() is not None:
            return "Frostwyrm's Spite"
        return "Not empowered"

    def empowered_by__navirs_keeper_instance(self) -> NavirsKeeper | None:
        return self.owner.effects.get(NavirsKeeper)

    def empowered_by__frostwyrms_spite_instance(self) -> FrostwyrmsSpiteEffect | None:
        return self.owner.effects.get(FrostwyrmsSpiteEffect)

    def _pay_cost_for_cast(self, target: Entity) -> None:
        """Overwritten: if empowered by navirs keeper, consume that instead of a normal charge."""
        navirs_keeper = self.empowered_by__navirs_keeper_instance()

        if navirs_keeper is not None:
            navirs_keeper.stacks -= 1
            if navirs_keeper.stacks == 0:
                navirs_keeper.remove()
            return

        else:
            super()._pay_cost_for_cast(target)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten to:
        - handle FrostwyrmsSpite explosion and additional base damage.
        - add "+1 winter orb" effect.
        """

        state = self.owner.state

        base_damage = self.average_damage

        frostwyrms_spite = self.empowered_by__frostwyrms_spite_instance()

        if frostwyrms_spite is not None:
            base_damage *= 1 + self.frostwyrms_spite_damage_bonus * frostwyrms_spite.stacks
            frostwyrms_spite._do_pulse(base_damage, target)

        create_standard_damage(
            state,
            self,
            self.owner,
            target,
            base_damage,
            delay_until_hit=self.delay_until_hit,
            main_damage_multiplier=self.main_damage_multiplier,
            num_secondary_targets=self.num_secondary_targets,
            num_targets_softcap=self.num_targets_softcap,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
        )

        self.owner._change_orbs(self.orb_gain)


@dataclass(kw_only=True, repr=False)
class BurstingIce(RimeAbility):
    """Conjures an icy crystal inside a target that pulses frost damage, dealing 520 - 635 every 0.5 seconds for 3 seconds to the target and nearby enemies."""

    base_cooldown: float = field(default=rime_config.BURSTING_ICE_COOLDOWN, init=False)

    base_cast_time: float = field(default=rime_config.BURSTING_ICE_CAST_TIME, init=False)
    base_player_downtime: float = field(default=rime_config.BURSTING_ICE_CAST_TIME, init=False)

    average_damage: float = field(
        default=(rime_config.BURSTING_ICE_DAMAGE_MIN + rime_config.BURSTING_ICE_DAMAGE_MAX) / 2, init=False
    )
    num_secondary_targets: int = field(default=rime_config.BURSTING_ICE_NUM_SECONDARY_TARGETS, init=False)
    num_targets_softcap: int = field(default=rime_config.BURSTING_ICE_NUM_TARGETS_SOFTCAP, init=False)

    tick_time: float = field(default=rime_config.BURSTING_ICE_TICK_TIME, init=False)
    duration: float = field(default=rime_config.BURSTING_ICE_DURATION, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten to remove damage and apply effect."""
        tick_interval = self.tick_time / (1 + self.owner.stats.haste_percent)

        target.effects.add(
            BurstingIceEffect(
                owner=self.owner,
                ability=self,
                tick_interval=tick_interval,
                duration=self.duration,
            )
        )

    def _do_pulse_and_anima(self, target: Entity) -> None:
        self.owner._change_anima(+1)
        self._do_pulse(target)

    def _do_pulse(self, target: Entity) -> None:
        state = self.owner.state
        create_standard_damage(
            state,
            self,
            self.owner,
            target,
            self.average_damage,
            main_damage_multiplier=self.main_damage_multiplier,
            num_secondary_targets=self.num_secondary_targets,
            num_targets_softcap=self.num_targets_softcap,
            secondary_damage_multiplier=self.secondary_damage_multiplier,
        )


@dataclass(kw_only=True, repr=False)
class WintersBlessing(RimeAbility):
    """Your Spirit is increased by 20% for 20 seconds and 30% of all damage you deal is replicated as healing divided equally between all allies."""

    base_cast_time: float = field(default=0, init=False)
    base_player_downtime: float = field(default=0, init=False)

    base_cooldown: float = field(default=rime_config.WINTERS_BLESSING_COOLDOWN, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [WintersBlessingBuff], init=False)


@dataclass(kw_only=True, repr=False)
class IceBlitz(RimeAbility):
    """You enter a state of focused casting for 20 seconds, causing you to deal 20% more damage for the duration."""

    base_cast_time: float = field(default=0, init=False)
    base_player_downtime: float = field(default=0, init=False)

    base_cooldown: float = field(default=rime_config.ICE_BLITZ_COOLDOWN, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [IceBlitzBuff], init=False)


@dataclass(kw_only=True, repr=False)
class FlightOfTheNavir(RimeAbility):
    """Summon 5 Frost Swallows to circle above Rime for 20 seconds.

    Your Cold Snap and Freezing Torrent command the frost swallows to swoop down on enemies, each dealing 612 - 748 damage to their target."""

    average_damage: float = field(
        default=(rime_config.FLIGHT_OF_THE_NAVIR_BIRD_DAMAGE_MIN + rime_config.FLIGHT_OF_THE_NAVIR_BIRD_DAMAGE_MAX) / 2,
        init=False,
    )

    base_cast_time: float = field(default=0, init=False)
    base_player_downtime: float = field(default=0, init=False)

    base_cooldown: float = field(default=rime_config.FLIGHT_OF_THE_NAVIR_COOLDOWN, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [FlightOfTheNavirEffect], init=False)

    has_navirs_keeper: bool = field(default=False, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten to not apply damage."""
        for effect_constructor in self.effect_list:
            self.owner.effects.add(effect_constructor(owner=self.owner))

        if self.has_navirs_keeper:
            self.owner.effects.add(NavirsKeeper(owner=self.owner))

    def _do_bird_attack(self, n_birds: int) -> None:
        for _ in range(n_birds):
            state = self.owner.state
            target = state.select_targets(
                main_target=None,
                num=1,
            )
            create_standard_damage(
                state,
                self,
                self.owner,
                target[0],
                self.average_damage,
                main_damage_multiplier=self.main_damage_multiplier,
                num_secondary_targets=self.num_secondary_targets,
                num_targets_softcap=self.num_targets_softcap,
                secondary_damage_multiplier=self.secondary_damage_multiplier,
            )


@dataclass(kw_only=True, repr=False)
class WrathOfWinter(RimeAbility):
    """Invoke the spirits of the frozen tundra for 20 seconds, granting you 1 Winter Orb every 4 seconds.
    You deal +20% increased damage and your Glacial Blast ability is instant cast while Wrath of Winter is active."""

    base_cast_time: float = field(default=rime_config.WRATH_OF_WINTER_CAST_TIME, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [WrathOfWinterEffect], init=False)

    is_ultimate_ability: bool = field(default=True, init=False)
