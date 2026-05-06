import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

from fellowship_sim.base_classes import Ability, Entity, RealPPM, create_standard_damage
from fellowship_sim.base_classes.effect import Buff, Effect
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    PreDamageSnapshotUpdate,
    Resource,
    ResourceChanged,
    ResourceSpent,
    SpiritProc,
)
from fellowship_sim.base_classes.stats import (
    CritMultiplierMultiplicativeCharacter,
    SpiritPercentAdditive,
    StatModifier,
)
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.rime import rime_config

if TYPE_CHECKING:
    from .ability import BurstingIce
    from .entity import Rime


@dataclass(kw_only=True, repr=False)
class WintersBlessingBuff(Buff):
    """+20% spirit for 20 s."""

    owner: "Rime" = field(init=True)

    name: str = field(default="winters_blessing", init=False)
    duration: float = field(default=rime_config.WINTERS_BLESSING_BUFF_DURATION, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [SpiritPercentAdditive(value=rime_config.WINTERS_BLESSING_BUFF_SPIRIT)]


@dataclass(kw_only=True, repr=False)
class IceBlitzBuff(Effect):
    """+20% damage for 20 s."""

    owner: "Rime" = field(init=True)

    name: str = field(default="ice_blitz", init=False)
    duration: float = field(default=rime_config.ICE_BLITZ_BUFF_DURATION, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        event.snapshot = event.snapshot.scale_average_damage(rime_config.ICE_BLITZ_BUFF_DAMAGE_MULTIPLIER)
        logger.trace("Ice Blitz: damage x1.20")


@dataclass(kw_only=True, repr=False)
class WrathOfWinterEffect(Effect):
    """+20% damage for 20 s."""

    owner: "Rime" = field(init=True)

    name: str = field(default="wrath_of_winter", init=False)
    duration: float = field(default=rime_config.WRATH_OF_WINTER_EFFECT_DURATION, init=False)

    orb_generation_interval: float = field(default=rime_config.WRATH_OF_WINTER_ORB_GENERATION_INTERVAL, init=False)
    orb_generation_count: int = field(default=rime_config.WRATH_OF_WINTER_ORB_GENERATION_COUNT, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

        for idx in range(0, math.floor(self.duration / self.orb_generation_interval) + 1):
            self.owner.state.schedule(
                idx * self.orb_generation_interval,
                GenericTimedEvent(name="Wrath of Winter orb generation", callback=self._add_orb),
            )

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        event.snapshot = event.snapshot.scale_average_damage(rime_config.WRATH_OF_WINTER_EFFECT_DAMAGE_MULTIPLIER)
        logger.trace("Wrath of Winter: damage x1.20")

    def _add_orb(self) -> None:
        logger.trace(f"Wrath of Winter: add {self.orb_generation_count} orb")
        self.owner._change_orbs(self.orb_generation_count)


@dataclass(kw_only=True, repr=False)
class FlightOfTheNavirEffect(Effect):
    """5 Frost Swallows circle for 20 s; each Cold Snap / Freezing Torrent commands them to swoop."""

    owner: "Rime" = field(init=True)

    name: str = field(default="flight_of_the_navir", init=False)
    duration: float = field(default=rime_config.FLIGHT_OF_THE_NAVIR_EFFECT_DURATION, init=False)

    n_birds: int = field(default=rime_config.FLIGHT_OF_THE_NAVIR_N_BIRDS, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast_success, owner=self)

    def _on_cast_success(self, event: AbilityCastSuccess) -> None:
        from .ability import ColdSnap, FreezingTorrent

        if not isinstance(event.ability, (ColdSnap, FreezingTorrent)):
            return

        self.owner.flight_of_the_navir._do_bird_attack(self.n_birds)


@dataclass(kw_only=True, repr=False)
class BurstingIceEffect(Effect):
    ability: "BurstingIce" = field(init=True)
    tick_interval: float = field(init=True)
    duration: float = field(init=True)

    has_winters_embrace: bool = field(init=True)

    def on_add(self) -> None:
        state = self.owner.state

        logger.debug(
            f"bursting ice effect created with: duration={self.duration}s; tick interval={self.tick_interval}s"
        )

        if self.has_winters_embrace:
            self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

        state.schedule(
            time_delay=self.tick_interval, callback=GenericTimedEvent(name="bursting ice tick", callback=self._do_tick)
        )

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import BurstingIce

        if not isinstance(event.damage_source, BurstingIce):
            event.snapshot = event.snapshot.scale_average_damage(rime_config.WINTERS_EMBRACE_DAMAGE_MULTIPLIER)
            logger.trace("Winter's Embrace: damage x1.20")

    def _do_tick(self) -> None:
        if self.attached_to is None:
            return

        state = self.owner.state

        self.ability._do_pulse_and_anima(target=self.attached_to)

        state.schedule(
            time_delay=self.tick_interval, callback=GenericTimedEvent(name="bursting ice tick", callback=self._do_tick)
        )


# Sprit effect


@dataclass(kw_only=True, repr=False)
class RimeSpiritProcAura(Effect):
    """Permanent aura on Rime.

    - Any orb-spending ability can trigger a spirit proc.
    - Proc chance is character.stats.spirit_proc_chance (simple rng roll).
    - On proc:
        - refunds the orb cost of the triggering ability.
        - gain 2 spirit points
    """

    owner: "Rime" = field(init=True)

    name: str = field(default="rime_spirit_effect", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(ResourceSpent, self._on_resource_spent, owner=self)

    def _on_resource_spent(self, event: ResourceSpent) -> None:
        if event.resource_type != Resource.WINTER_ORBS:
            return

        state = self.owner.state

        proc_chance = self.owner.stats.spirit_proc_chance

        undulating_spirit = self.owner.effects.get(UndulatingSpritEffect)

        if undulating_spirit is not None:
            proc_chance = 1
            undulating_spirit.remove()

        roll = state.rng.random() if proc_chance > 0 else 0.0
        logger.trace(f"{proc_chance = }, {roll = } in spirit_proc)")
        if proc_chance == 0.0 or roll >= proc_chance:
            return

        ability = event.ability
        resource_amount = event.resource_amount
        state.schedule(
            time_delay=0.0,
            callback=GenericTimedEvent(
                name="spirit_effect proc", callback=lambda: self._resolve_proc(ability, resource_amount)
            ),
        )

        logger.debug(f"spirit proc triggered by {event.ability}")

    def _resolve_proc(self, ability: Ability, resource_amount: int) -> None:
        logger.debug(f"spirit proc resolving: refund {resource_amount} focus")
        state = self.owner.state

        state.bus.emit(SpiritProc(ability=ability, owner=self.owner, resource_amount=resource_amount))

        # Gain 1 spirit point
        self.owner.spirit_points = min(
            self.owner.spirit_points + self.owner.spirit_point_gain_on_proc, self.owner.max_spirit_points
        )

        # Refund focus
        self.owner._change_orbs(resource_amount)


# ---------------------------------------------------------------------------
# Talent effects
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class ChillingFinesse(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="chilling_finesse", init=False)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        bus.subscribe(AbilityCastSuccess, self._on_cast_success, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FreezingTorrent

        if not isinstance(event.damage_source, FreezingTorrent) or event.is_secondary:
            return
        self.owner.bursting_ice._reduce_cooldown(rime_config.CHILLING_FINESSE_BURSTING_ICE_CDR)
        logger.trace(
            f"Chilling Finesse: FT tick → Bursting Ice CD -{rime_config.CHILLING_FINESSE_BURSTING_ICE_CDR:.1f}s"
        )

    def _on_cast_success(self, event: AbilityCastSuccess) -> None:
        from .ability import ColdSnap

        if not isinstance(event.ability, ColdSnap):
            return
        self.owner.freezing_torrent._reduce_cooldown(rime_config.CHILLING_FINESSE_FREEZING_TORRENT_CDR)
        logger.trace(
            f"Chilling Finesse: Cold Snap → Freezing Torrent CD -{rime_config.CHILLING_FINESSE_FREEZING_TORRENT_CDR:.1f}s"
        )


@dataclass(kw_only=True, repr=False)
class Burstbolter(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="burstbolter", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FrostBolt

        if not isinstance(event.damage_source, FrostBolt) or event.is_secondary:
            return
        self.owner._change_anima(rime_config.BURSTBOLTER_ANIMA_GAIN)
        self.owner.bursting_ice._do_pulse(event.target)
        logger.trace("Burstbolter: Frost Bolt → +2 anima + Bursting Ice pulse")


@dataclass(kw_only=True, repr=False)
class IcyFlowAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="icy_flow_aura", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast_success, owner=self)

    def _on_cast_success(self, event: AbilityCastSuccess) -> None:
        from .ability import ColdSnap

        if not isinstance(event.ability, ColdSnap):
            return
        self.owner.effects.add(IcyFlowEffect(owner=self.owner))
        logger.debug("Icy Flow: Cold Snap → IcyFlowEffect granted")


@dataclass(kw_only=True, repr=False)
class IcyFlowEffect(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="icy_flow", init=False)
    duration: float = field(default=rime_config.ICY_FLOW_EFFECT_DURATION, init=False)
    stacks: int = field(default=rime_config.ICY_FLOW_EFFECT_MAX_STACKS, init=False)
    max_stacks: int = field(default=rime_config.ICY_FLOW_EFFECT_MAX_STACKS, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import GlacialBlast, IceComet

        if not isinstance(event.damage_source, (GlacialBlast, IceComet)) or event.is_secondary:
            return
        event.snapshot = event.snapshot.add_crit_percent(rime_config.ICY_FLOW_EFFECT_CRIT_BONUS)
        self.stacks -= 1
        logger.trace(
            "Icy Flow: +{:.0%} crit on {} ({} charges left)",
            rime_config.ICY_FLOW_EFFECT_CRIT_BONUS,
            type(event.damage_source).__name__,
            self.stacks,
        )

        if self.stacks <= 0:
            self.remove()


@dataclass(kw_only=True, repr=False)
class BitingColdBuff(Buff):
    owner: "Rime" = field(init=True)

    name: str = field(default="biting_cold", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [CritMultiplierMultiplicativeCharacter(multiplier=rime_config.BITING_COLD_BUFF_CRIT_MULTIPLIER)]


@dataclass(kw_only=True, repr=False)
class WisdomOfTheNorth(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="wisdom_of_the_north", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(ResourceSpent, self._on_resource_spent, owner=self)

    def _on_resource_spent(self, event: ResourceSpent) -> None:
        if event.resource_type != Resource.WINTER_ORBS:
            return
        cdr = rime_config.WISDOM_OF_THE_NORTH_CDR_PER_ORB * event.resource_amount
        self.owner.ice_blitz._reduce_cooldown(cdr)
        self.owner.flight_of_the_navir._reduce_cooldown(cdr)
        self.owner.winters_blessing._reduce_cooldown(cdr)
        logger.trace(f"Wisdom of the North: {event.resource_amount} orb(s) spent → -{cdr:.1f}s on Ice Blitz/FotN/WB")


@dataclass(kw_only=True, repr=False)
class GlacialAssaultAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="glacial_assault_aura", init=False)
    stacks: int = field(default=0, init=False)
    max_stacks: int = field(default=rime_config.GLACIAL_ASSAULT_MAX_STACKS, init=False)

    damage_echo_fraction: float = field(default=rime_config.GLACIAL_ASSAULT_DAMAGE_ECHO_FRACTION, init=False)

    num_secondary_targets: int = field(default=rime_config.GLACIAL_ASSAULT_NUM_SECONDARY_TARGETS, init=False)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityCastSuccess, self._on_cast_success, owner=self)
        bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    @property
    def is_ready(self) -> bool:
        return self.stacks == self.max_stacks

    def _on_cast_success(self, event: AbilityCastSuccess) -> None:
        from .ability import ColdSnap

        if not isinstance(event.ability, ColdSnap):
            return
        if self.stacks == self.max_stacks:
            return

        self.stacks += 1
        if self.is_ready:
            logger.debug(f"Glacial Assault: {self.stacks}/{self.max_stacks} stacks → Glacial Blast empowered")
        else:
            logger.trace(f"Glacial Assault: {self.stacks}/{self.max_stacks} stacks")

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import GlacialBlast

        if not isinstance(event.damage_source, GlacialBlast):
            return

        if self.is_ready:
            event.snapshot = event.snapshot.scale_average_damage(rime_config.GLACIAL_ASSAULT_DAMAGE_MULTIPLIER)
            logger.trace(
                f"Glacial Assault: +{rime_config.GLACIAL_ASSAULT_DAMAGE_MULTIPLIER - 1:.0%} damage → stacks reset"
            )

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import GlacialBlast

        if not isinstance(event.damage_source, GlacialBlast) or event.is_secondary:
            return

        if self.is_ready:
            base_damage = self.damage_echo_fraction * event.damage

            for target in self.owner.state.select_targets(main_target=event.target, num=self.num_secondary_targets):
                event = AbilityDamage(
                    damage_source=self,
                    owner=self.owner,
                    target=target,
                    is_crit=False,
                    is_grievous_crit=False,
                    damage=base_damage,
                    is_secondary=True,
                )
                self.owner.state.bus.emit(event)

            self.stacks = 0


@dataclass(kw_only=True, repr=False)
class NavirsKeeper(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="navirs_keeper", init=False)
    duration: float = field(default=rime_config.NAVIRS_KEEPER_DURATION, init=False)
    stacks: int = field(default=rime_config.NAVIRS_KEEPER_MAX_STACKS, init=False)
    max_stacks: int = field(default=rime_config.NAVIRS_KEEPER_MAX_STACKS, init=False)


@dataclass(kw_only=True, repr=False)
class FrostweaversWrathEffect(Effect):
    """Next Glacial Blast or Ice Comet gains +100% additional crit chance. Consumed on hit."""

    owner: "Rime" = field(init=True)

    name: str = field(default="frostweavers_wrath", init=False)
    duration: float = field(default=rime_config.FROSTWEAVERS_WRATH_EFFECT_DURATION, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import GlacialBlast, IceComet

        if not isinstance(event.damage_source, (GlacialBlast, IceComet)) or event.is_secondary:
            return
        event.snapshot = event.snapshot.add_crit_percent(rime_config.FROSTWEAVERS_WRATH_CRIT_BONUS)
        logger.trace(
            f"Frostweaver's Wrath: +{rime_config.FROSTWEAVERS_WRATH_CRIT_BONUS:.0%} crit on {type(event.damage_source).__name__}"
        )
        self.remove()


@dataclass(kw_only=True, repr=False)
class FrostweaversWrathAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="frostweavers_wrath_aura", init=False)
    proc_chance: float = field(default=rime_config.FROSTWEAVERS_WRATH_PROC_CHANCE, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(ResourceChanged, self._on_resource_changed, owner=self)

    def _on_resource_changed(self, event: ResourceChanged) -> None:
        if event.resource_type != Resource.WINTER_ORBS or event.resource_amount <= 0:
            return
        roll = self.owner.state.rng.random()
        if roll < self.proc_chance:
            self.owner.effects.add(FrostweaversWrathEffect(owner=self.owner))
            logger.debug(f"Frostweaver's Wrath: proc ({roll:.3f} < {self.proc_chance:.2f}) → effect granted")
        else:
            logger.trace(f"Frostweaver's Wrath: no proc ({roll:.3f} >= {self.proc_chance:.2f})")


@dataclass(kw_only=True, repr=False)
class CascadingBliz(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="cascading_bliz", init=False)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(ResourceChanged, self._on_resource_changed, owner=self)
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_resource_changed(self, event: ResourceChanged) -> None:
        if event.resource_type != Resource.ANIMA or event.resource_amount <= 0:
            return
        if not self.owner.effects.has(IceBlitzBuff):
            return
        self.owner.flight_of_the_navir._do_bird_attack(n_birds=1)
        logger.trace("Cascading Bliz: anima generated + Ice Blitz active → 1 bird attack")

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FlightOfTheNavir

        if not isinstance(event.damage_source, FlightOfTheNavir) or event.is_secondary:
            return
        ice_blitz_buff = self.owner.effects.get(IceBlitzBuff)
        if ice_blitz_buff is None:
            return
        ice_blitz_buff.duration += rime_config.CASCADING_BLIZ_ICE_BLITZ_EXTENSION
        ice_blitz_buff._schedule_expiry()
        logger.trace(f"Cascading Bliz: FotN hit → Ice Blitz +{rime_config.CASCADING_BLIZ_ICE_BLITZ_EXTENSION:.1f}s")


@dataclass(kw_only=True, repr=False)
class UndulatingSpritEffect(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="undulating_spirit", init=False)
    duration: float = field(default=rime_config.UNDULATING_SPIRIT_EFFECT_DURATION, init=False)


@dataclass(kw_only=True, repr=False)
class UndulatingSpiritAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="undulating_spirit_aura", init=False)
    proc_chance: float = field(default=rime_config.UNDULATING_SPIRIT_PROC_CHANCE, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast_success, owner=self)

    def _on_cast_success(self, event: AbilityCastSuccess) -> None:
        roll = self.owner.state.rng.random()
        if roll < self.proc_chance:
            self.owner.effects.add(UndulatingSpritEffect(owner=self.owner))
            logger.debug(f"Undulating Spirit: proc ({roll:.3f} < {self.proc_chance:.2f}) → effect granted")


@dataclass(kw_only=True, repr=False)
class SoulfrostTorrentEffect(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="soulfrost_torrent", init=False)
    duration: float = field(default=rime_config.SOULFROST_TORRENT_EFFECT_DURATION, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        from .ability import FreezingTorrent

        if not isinstance(event.damage_source, FreezingTorrent):
            return
        event.snapshot = event.snapshot.add_crit_percent(rime_config.SOULFROST_TORRENT_CRIT_BONUS)
        logger.trace("Soulfrost Torrent: FT hit → +100% crit chance")


@dataclass(kw_only=True, repr=False)
class SoulfrostTorrentAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="soulfrost_torrent_aura", init=False)
    real_ppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self.real_ppm = RealPPM(
            base_ppm=rime_config.SOULFROST_TORRENT_AURA_PPM,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast_success, owner=self)

    def _on_cast_success(self, event: AbilityCastSuccess) -> None:
        if self.real_ppm.check():
            self.owner.effects.add(SoulfrostTorrentEffect(owner=self.owner))
            logger.debug("Soulfrost Torrent: PPM proc → effect granted")


@dataclass(kw_only=True, repr=False)
class FrostwyrmsSpiteEffect(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="frostwyrms_spite", init=False)
    duration: float = field(default=rime_config.FROSTWYRMS_SPITE_EFFECT_DURATION, init=False)
    max_stacks: int = field(default=rime_config.FROSTWYRMS_SPITE_EFFECT_MAX_STACKS, init=False)

    base_num_secondary_targets: int = field(default=rime_config.FROSTWYRMS_SPITE_NUM_SECONDARY_TARGETS, init=False)
    num_targets_softcap: int = field(default=rime_config.FROSTWYRMS_SPITE_NUM_TARGETS_SOFTCAP, init=False)

    @property
    def num_secondary_targets(self) -> int:
        return min(self.stacks, self.base_num_secondary_targets)

    def _do_pulse(self, base_damage: float, target: Entity) -> None:
        create_standard_damage(
            self.owner.state,
            damage_source=self,
            owner=self.owner,
            target=target,
            base_damage=base_damage,
            delay_until_hit=0,
            main_damage_multiplier=0,
            num_secondary_targets=self.num_secondary_targets,
            num_targets_softcap=self.num_targets_softcap,
        )


@dataclass(kw_only=True, repr=False)
class FrostwyrmsSpiteAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="frostwyrms_spite_aura", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FreezingTorrent

        if not isinstance(event.damage_source, FreezingTorrent) or event.is_secondary:
            return
        self.owner.effects.add(FrostwyrmsSpiteEffect(owner=self.owner))
        logger.trace("Frostwyrm's Spite: FT tick → +1 stack")


@dataclass(kw_only=True, repr=False)
class CoalescingFrostEffect(Effect):
    owner: "Rime" = field(init=True)
    stacks: int = field(default=1, init=True)

    name: str = field(default="coalescing_frost", init=False)
    duration: float = field(default=rime_config.COALESCING_FROST_DURATION, init=False)
    max_stacks: int = field(default=rime_config.COALESCING_FROST_MAX_STACKS, init=False)

    average_damage: float = field(default=rime_config.COALESCING_FROST_AVERAGE_DAMAGE, init=False)
    num_secondary_targets: int = field(default=rime_config.COALESCING_FROST_NUM_SECONDARY_TARGETS, init=False)
    num_targets_softcap: int = field(default=rime_config.COALESCING_FROST_NUM_TARGETS_SOFTCAP, init=False)

    def on_remove(self, *, is_remove_from_expiration: bool = False) -> None:
        if not is_remove_from_expiration or self.attached_to is None:
            return
        create_standard_damage(
            state=self.owner.state,
            damage_source=self,
            owner=self.owner,
            target=self.attached_to,
            base_damage=self.average_damage * self.stacks,
            delay_until_hit=0,
            num_secondary_targets=self.num_secondary_targets,
            num_targets_softcap=self.num_targets_softcap,
        )


@dataclass(kw_only=True, repr=False)
class CoalescingFrostAura(Effect):
    owner: "Rime" = field(init=True)

    name: str = field(default="coalescing_frost_aura", init=False)
    crit_extra_stack_chance: float = field(default=rime_config.COALESCING_FROST_CRIT_EXTRA_STACK_CHANCE, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        from .ability import FreezingTorrent

        if not isinstance(event.damage_source, FreezingTorrent) or event.is_secondary:
            return
        stacks = 2 if event.is_crit and self.owner.state.rng.random() < self.crit_extra_stack_chance else 1
        event.target.effects.add(CoalescingFrostEffect(owner=self.owner, stacks=stacks))
        logger.trace(f"Coalescing Frost: FT tick → +{stacks} stack(s) on {event.target}")
