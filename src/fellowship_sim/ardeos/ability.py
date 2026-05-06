import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fellowship_sim.ardeos import ardeos_config
from fellowship_sim.ardeos.effect import (
    CracklingInfernoBurnDoT,
    EngulfingFlamesDoT,
    FireBallDoT,
    FireFrogsDoT,
    IncinerateDoT,
    SearingBlazeDoT,
    WildfireEffect,
)
from fellowship_sim.base_classes import (
    AbilityDamage,
    CastReturnCode,
    DoTEffect,
    Effect,
    Entity,
    create_standard_damage,
)
from fellowship_sim.base_classes.ability import Ability, can_cast_check
from fellowship_sim.base_classes.timed_events import GenericTimedEvent

if TYPE_CHECKING:
    from fellowship_sim.ardeos.entity import Ardeos  # noqa: F401


@dataclass(kw_only=True, repr=False)
class ArdeosAbility(Ability["Ardeos"]):
    pass


@dataclass(kw_only=True, repr=False)
class Apocalypse(ArdeosAbility):
    average_damage: float = field(
        default=(ardeos_config.APOCALYPSE_DAMAGE_MIN + ardeos_config.APOCALYPSE_DAMAGE_MAX) / 2, init=False
    )
    base_cast_time: float = field(default=ardeos_config.APOCALYPSE_CAST_TIME, init=False)
    base_player_downtime: float = field(default=ardeos_config.APOCALYPSE_CAST_TIME, init=False)

    num_secondary_targets: int = field(default=ardeos_config.APOCALYPSE_NUM_SECONDARY_TARGETS, init=False)
    num_targets_softcap: int = field(default=ardeos_config.APOCALYPSE_TARGETS_SOFTCAP, init=False)


@dataclass(kw_only=True, repr=False)
class Detonate(ArdeosAbility):
    base_cast_time: float = field(default=0.0, init=False)
    base_player_downtime: float = field(default=ardeos_config.DETONATE_PLAYER_DOWNTIME, init=False)
    has_unhasted_cast_time: bool = field(default=True, init=False)

    detonate_window_size: float = field(default=ardeos_config.DETONATE_WINDOW_SIZE, init=False)
    num_detonate_attacks: int = field(default=ardeos_config.DETONATE_NUM_ATTACKS, init=False)

    ember_cost: int = field(default=1, init=False)

    ardeos_dot_types: frozenset[type[DoTEffect]] = field(
        default_factory=lambda: frozenset({
            SearingBlazeDoT,
            EngulfingFlamesDoT,
            IncinerateDoT,
            FireBallDoT,
            FireFrogsDoT,
            CracklingInfernoBurnDoT,
        }),
        init=False,
    )

    @can_cast_check
    def _embers(self) -> CastReturnCode:
        return CastReturnCode.OK if self.owner.embers >= self.ember_cost else CastReturnCode.INSUFFICENT_RESOURCES

    def _pay_cost_for_cast(self, target: Entity) -> None:
        """Add to pay for orb cost"""
        super()._pay_cost_for_cast(target)

        self.owner._spend_ember(self.ember_cost, ability=self)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten: special damage formula."""
        state = self.owner.state

        for enemy in state.enemies:
            total_damage = 0
            for effect in enemy.effects:
                if isinstance(effect, DoTEffect) and type(effect) in self.ardeos_dot_types:
                    snapshot = effect.average_tick_damage_snapshot
                    total_damage += snapshot.average_damage / effect.tick_interval * self.detonate_window_size

            attack_damage = total_damage / self.num_detonate_attacks
            for _ in range(self.num_detonate_attacks):
                splash = AbilityDamage(
                    damage_source=self,
                    owner=self.owner,
                    target=enemy,
                    is_crit=False,
                    is_grievous_crit=False,
                    damage=attack_damage,
                    is_secondary=True,
                )
                self.owner.state.bus.emit(splash)


@dataclass(kw_only=True, repr=False)
class EngulfingFlames(ArdeosAbility):
    tick_damage: float = field(
        default=(ardeos_config.ENGULFING_FLAMES_DAMAGE_MIN + ardeos_config.ENGULFING_FLAMES_DAMAGE_MAX) / 2,
        init=False,
    )

    duration: float = field(default=ardeos_config.ENGULFING_FLAMES_DURATION, init=False)
    tick_duration: float = field(default=ardeos_config.ENGULFING_FLAMES_TICK_INTERVAL, init=False)

    cinder_per_tick: int = field(default=ardeos_config.ENGULFING_FLAMES_CINDER_TICK_AMOUNT, init=False)
    cinder_tick_duration: float = field(default=ardeos_config.ENGULFING_FLAMES_TICK_INTERVAL, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten: apply debuff."""
        self._apply_engulfing_flames(target)

    def _apply_engulfing_flames(self, target: Entity) -> None:
        target.effects.add(EngulfingFlamesDoT(owner=self.owner, duration=self.duration))


@dataclass(kw_only=True, repr=False)
class FireBall(ArdeosAbility):
    average_damage: float = field(
        default=(ardeos_config.FIREBALL_DAMAGE_MIN + ardeos_config.FIREBALL_DAMAGE_MAX) / 2, init=False
    )
    num_secondary_targets: int = field(default=ardeos_config.FIREBALL_NUM_SECONDARY_TARGETS, init=False)
    num_targets_softcap: int = field(default=ardeos_config.FIREBALL_TARGETS_SOFTCAP, init=False)


@dataclass(kw_only=True, repr=False)
class FireFrogs(ArdeosAbility):
    average_damage: float = field(
        default=(ardeos_config.FIREFROGS_DAMAGE_MIN + ardeos_config.FIREFROGS_DAMAGE_MAX) / 2, init=False
    )

    delay_until_hit: float = field(default=0.35, init=False)

    frog_count: int = field(default=ardeos_config.FIREFROGS_FROG_COUNT, init=False)
    toad_count: int = field(default=0, init=False)
    frog_to_toad_conversion_chance: float = field(default=0.0, init=False)
    frog_leap_count: int = field(default=ardeos_config.FIREFROGS_FROG_LEAP_COUNT, init=False)

    fire_toad_damage_multiplier: float = field(default=8.0, init=False)
    fire_toad_num_secondary_targets: int = field(default=19, init=False)
    fire_toad_num_targets_softcap: int = field(default=1, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten: special attack logic for frogs."""
        for _ in range(self.frog_count):
            self._frog_attack(target)

        for _ in range(self.toad_count):
            self._toad_attack(target)

    def _frog_attack(self, main_target: Entity) -> None:
        """Spawn a frog then perform all its leaps."""
        state = self.owner.state
        roll = state.rng.random() if self.frog_to_toad_conversion_chance else 1.0

        if roll < self.frog_to_toad_conversion_chance:
            return self._toad_attack(main_target)

        else:
            for idx in range(self.frog_leap_count):
                # First leap goes to main target, else random
                target = main_target if idx == 0 else state.select_targets(main_target=None, num=1)[0]

                # +- 10% from (1; 2; 3; 4) * delay_until_hit
                delay_until_hit = (0.9 + 0.2 * state.rng.random()) * (idx + 1) * self.delay_until_hit

                create_standard_damage(
                    self.owner.state,
                    self,
                    self.owner,
                    target,
                    base_damage=self.average_damage,
                    delay_until_hit=delay_until_hit,
                )

    def _toad_attack(self, target: Entity) -> None:
        """Spawn a toad then perform its single leap attack.

        Attack the target and all enemies near it for 800% fire frog damage.
        """
        base_damage = self.average_damage * self.fire_toad_damage_multiplier
        create_standard_damage(
            self.owner.state,
            self,
            self.owner,
            target,
            base_damage=base_damage,
            delay_until_hit=self.delay_until_hit,
            num_secondary_targets=self.fire_toad_num_secondary_targets,
            num_targets_softcap=self.fire_toad_num_targets_softcap,
        )


@dataclass(kw_only=True, repr=False)
class Incinerate(ArdeosAbility):
    average_damage: float = field(
        default=(ardeos_config.INCINERATE_DAMAGE_MIN + ardeos_config.INCINERATE_DAMAGE_MAX) / 2, init=False
    )
    num_secondary_targets: int = field(default=19, init=False)
    num_targets_softcap: int = field(default=8, init=False)

    base_cast_time: float = field(default=ardeos_config.INCINERATE_CAST_TIME, init=False)
    base_player_downtime: float = field(default=ardeos_config.INCINERATE_CHANNEL_TIME, init=False)
    tick_interval: float = field(default=0.5, init=False)

    is_ultimate_ability: bool = field(default=True, init=False)

    @property
    def cast_time(self) -> float:
        """Overwritten: cast-time is hasted, but channel is not."""
        return self.base_cast_time / (1 + self.owner.stats.haste_percent)

    @property
    def channel_time(self) -> float:
        return self.base_player_downtime

    @property
    def player_downtime(self) -> float:
        """Time during which player cannot take another action.

        Overwritten: cast-time is hasted, but channel is not."""
        return self.base_cast_time / (1 + self.owner.stats.haste_percent) + self.channel_time

    def _do_cast(self, target: "Entity") -> None:
        """Overwritten for channel logic."""
        state = self.owner.state

        base_tick_interval = self.tick_interval

        haste = self.owner.stats.haste_percent
        tick_interval = base_tick_interval / (1 + haste)
        epsilon = 0.001
        num_ticks = math.floor(self.channel_time / tick_interval + epsilon)

        partial_size = (self.channel_time - num_ticks * tick_interval) / tick_interval

        num_ticks += 1

        # special to incinerate: partials above the minimum size get pushed to full ticks
        partial_size = 1 if partial_size >= 0.05 else 0

        def _next_tick() -> None:
            self._schedule_next_tick(
                target=target,
                tick_interval=tick_interval,
                hit_counter=0,
                total_count=num_ticks,
                partial_size=partial_size,
                partial_time=state.time + self.channel_time,
            )

        # NB: incinerate has immediate damage tick
        state.schedule(time_delay=0, callback=GenericTimedEvent(name="incinerate tick", callback=_next_tick))

    def tick_damage(self, target: Entity) -> None:
        """Do the direct damage attack on all targets."""
        create_standard_damage(
            state=self.owner.state,
            damage_source=self,
            owner=self.owner,
            target=target,
            base_damage=self.average_damage,
            num_secondary_targets=self.num_secondary_targets,
            num_targets_softcap=self.num_targets_softcap,
            delay_until_hit=0,
        )

    def _schedule_next_tick(
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
                f"Unexpected behavior in incinerate: partial time f{partial_time} is earlier than current time {state.time}"
            )

        self.tick_damage(target=target)

        def _next_tick() -> None:
            self._schedule_next_tick(
                target=target,
                tick_interval=tick_interval,
                hit_counter=hit_counter + 1,
                total_count=total_count,
                partial_size=partial_size,
                partial_time=partial_time,
            )

        if hit_counter < total_count - 1:
            state.schedule(
                time_delay=tick_interval, callback=GenericTimedEvent(name="incinerate tick", callback=_next_tick)
            )

        elif hit_counter == total_count - 1 and partial_size > 0:
            state.schedule(
                time_delay=partial_time - state.time,
                callback=GenericTimedEvent(name="incinerate tick", callback=_next_tick),
            )


@dataclass(kw_only=True, repr=False)
class InfernalWave(ArdeosAbility):
    average_damage: float = field(
        default=(ardeos_config.INFERNAL_WAVE_DAMAGE_MIN + ardeos_config.INFERNAL_WAVE_DAMAGE_MAX) / 2, init=False
    )

    base_cast_time: float = field(default=ardeos_config.INFERNAL_WAVE_CAST_TIME, init=False)
    base_player_downtime: float = field(default=ardeos_config.INFERNAL_WAVE_CAST_TIME, init=False)

    cinder_gain_on_cast: int = field(default=40, init=False)

    def _do_cast(self, target: Entity) -> None:
        super()._do_cast(target)

        self.owner._change_cinder(self.cinder_gain_on_cast)


@dataclass(kw_only=True, repr=False)
class Pyromania(ArdeosAbility):
    base_cast_time: float = field(default=0, init=False)
    base_player_downtime: float = field(default=0, init=False)

    base_cooldown: float = field(default=ardeos_config.PYROMANIA_COOLDOWN, init=False)
    num_secondary_targets: int = field(default=ardeos_config.PYROMANIA_NUM_SECONDARY_TARGETS, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten: special logic to apply debuff."""
        self.owner.engulfing_flames._apply_engulfing_flames(target)

        other_enemies = [enemy for enemy in self.owner.state.enemies if enemy is not target]
        other_enemies.sort(key=lambda e: (e.effects.has(EngulfingFlamesDoT), -e.percent_hp))

        for secondary_target in other_enemies[: self.num_secondary_targets]:
            self.owner.engulfing_flames._apply_engulfing_flames(secondary_target)


@dataclass(kw_only=True, repr=False)
class SearingBlaze(ArdeosAbility):
    base_cast_time: float = field(default=0, init=False)
    base_player_downtime: float = field(default=ardeos_config.SEARING_BLAZE_PLAYER_DOWNTIME, init=False)

    tick_damage: float = field(
        default=(ardeos_config.SEARING_BLAZE_DAMAGE_MIN + ardeos_config.SEARING_BLAZE_DAMAGE_MAX) / 2, init=False
    )

    duration: float = field(default=ardeos_config.SEARING_BLAZE_DURATION, init=False)
    tick_duration: float = field(default=ardeos_config.SEARING_BLAZE_TICK_INTERVAL, init=False)

    cinder_per_tick: int = field(default=ardeos_config.SEARING_BLAZE_CINDER_TICK_AMOUNT, init=False)
    cinder_tick_duration: float = field(default=ardeos_config.SEARING_BLAZE_TICK_INTERVAL, init=False)
    is_agonizing_blaze: bool = field(default=False, init=False)

    def _do_cast(self, target: Entity) -> None:
        """Overwritten: apply debuff."""
        self._apply_searing_blaze(target)

    def _apply_searing_blaze(self, target: Entity) -> None:
        target.effects.add(SearingBlazeDoT(owner=self.owner, is_agonizing_blaze=self.is_agonizing_blaze))


@dataclass(kw_only=True, repr=False)
class Wildfire(ArdeosAbility):
    base_cast_time: float = field(default=0, init=False)
    base_player_downtime: float = field(default=0, init=False)

    base_cooldown: float = field(default=ardeos_config.WILDFIRE_COOLDOWN, init=False)

    effect_list: list[type[Effect]] = field(default_factory=lambda: [WildfireEffect], init=False)
