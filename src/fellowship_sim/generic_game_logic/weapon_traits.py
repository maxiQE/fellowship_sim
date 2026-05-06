import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, Literal, cast

from loguru import logger

from fellowship_sim.base_classes import (
    Ability,
    Buff,
    CritScoreAdditive,
    DoTEffect,
    Entity,
    ExpertiseScoreAdditive,
    HasteScoreAdditive,
    HeroicTrait,
    MainStatAdditiveMultiplierCharacter,
    MasterTrait,
    Player,
    SpiritScoreAdditive,
    StatModifier,
    WeaponAbility,
    create_standard_damage,
)
from fellowship_sim.base_classes.effect import AccumulatorEffect, Effect
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    AbilityPeriodicDamage,
    SnapshotCreation,
    SpiritProc,
    UltimateCast,
)
from fellowship_sim.base_classes.real_ppm import RealPPM
from fellowship_sim.base_classes.setup import SetupContext, SetupEffectLate
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.generic_game_logic import generic_config
from fellowship_sim.generic_game_logic.gems import FirstStrike, HarmoniousSoulBuff
from fellowship_sim.generic_game_logic.weapon_abilities import CurseOfAnzhyr

# ---------------------------------------------------------------------------
# AmethystSplinters
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class AmethystSplintersDoT(AccumulatorEffect):
    name: str = field(default="amethyst_splinters_dot", init=False)
    duration: float = field(default=generic_config.AMETHYST_SPLINTERS_DOT_DURATION, init=False)
    base_tick_interval: float = field(default=generic_config.AMETHYST_SPLINTERS_DOT_BASE_TICK_TIME, init=False)
    does_partial_final_tick: bool = field(default=True, init=False)


@dataclass(kw_only=True, repr=False)
class AmethystSplintersAura(Effect):
    """Permanent weapon trait aura applied to the caster.

    On any crit: applies AmethystSplintersDoT to the target.
    damage_ratio scales with trait_level (1-4): 7 / 8 / 9 / 10 %.
    """

    owner: Player

    name: str = field(default="amethyst_splinters", init=False)
    trait_level: int = 4

    _ratio_table: ClassVar[list[float]] = generic_config.AMETHYST_SPLINTERS_DAMAGE_RATIO_TABLE

    base_num_ticks: int = field(default=4, init=False)

    @property
    def damage_ratio(self) -> float:
        return self._ratio_table[self.trait_level - 1]

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage_dealt, owner=self)
        self.owner.state.bus.subscribe(AbilityPeriodicDamage, self._on_damage_dealt, owner=self)

    def _on_damage_dealt(self, event: AbilityDamage | AbilityPeriodicDamage) -> None:
        if not event.is_crit:
            return

        average_damage = event.damage * self.damage_ratio / self.base_num_ticks
        event.target.effects.add(AmethystSplintersDoT(average_damage=average_damage, owner=self.owner))
        logger.debug("Amethyst Splinters proc: DoT → {} (average_damage={:.0f})", event.target, average_damage)


# ---------------------------------------------------------------------------
# DiamondStrike
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DiamondStrikeEcho(Effect):
    """Stacking debuff applied to targets hit by DiamondStrike.

    Each stack increases the damage of the next DiamondStrike hit on this target by +40%.
    Max 5 stacks; each new application renews the 20s duration and adds a stack (default fuse).
    """

    name: str = field(default="diamond_strike_echo", init=False)
    duration: float = field(default=generic_config.DIAMOND_STRIKE_ECHO_DURATION, init=False)
    max_stacks: int = field(default=generic_config.DIAMOND_STRIKE_ECHO_MAX_STACKS, init=False)


@dataclass(kw_only=True, repr=False)
class DiamondStrike(Effect):
    """Permanent weapon trait aura.

    Each time the owner deals damage, there is an rPPM chance to fire a DiamondStrike hit:
      - base damage scaled by main_stat / expertise
      - multiplied by (1 + k x 0.35) where k = HarmoniousSoul buff stacks on caster
      - multiplied by (1 + s x 0.40) where s = DiamondStrikeEcho stacks on target
    After the hit, DiamondStrikeEcho (1 stack) is applied to the target.

    rPPM per level: 5.0 / 5.5 / 6.1 / 6.7  (haste-scaled)
    Base damage per level: 1480 / 1780 / 2000 / 2370
    """

    owner: Player

    name: str = field(default="diamond_strike", init=False)
    trait_level: int = 4

    _ppm_table: ClassVar[list[float]] = generic_config.DIAMOND_STRIKE_PPM_TABLE
    _base_dmg_table: ClassVar[list[float]] = generic_config.DIAMOND_STRIKE_BASE_DAMAGE_TABLE

    _rppm: RealPPM = field(init=False)
    hs_damage_bonus: float = field(
        default=generic_config.DIAMOND_STRIKE_BONUS_DAMAGE_PER_HARMONIOUS_SOUL_STACK, init=False
    )
    echo_damage_bonus: float = field(
        default=generic_config.DIAMOND_STRIKE_BONUS_DAMAGE_PER_ECHO_STACK, init=False
    )

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=self._ppm_table[self.trait_level - 1],
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if isinstance(event.damage_source, DiamondStrike):
            return

        if not self._rppm.check():
            return

        state = self.owner.state
        state.schedule(
            time_delay=0.0,
            callback=GenericTimedEvent(
                name="diamond_strike proc", callback=lambda: self._fire(self.owner, event.target)
            ),
        )

    def _fire(self, char: Player, target: Entity) -> None:
        unscaled_base_damage = self._base_dmg_table[self.trait_level - 1]

        # HarmoniousSoul stacks on caster
        hs = char.effects.get(HarmoniousSoulBuff)
        n_h_soul = hs.stacks if hs is not None else 0

        # DiamondStrikeEcho stacks on target
        echo = target.effects.get(DiamondStrikeEcho)
        n_echo = echo.stacks if echo is not None else 0

        base_damage = (
            unscaled_base_damage
            * (1 + n_h_soul * self.hs_damage_bonus)
            * (1 + n_echo * self.echo_damage_bonus)
        )

        logger.debug(
            "Diamond Strike proc: unscaled base={:.0f} harmonious soul count={} diamond strike echo count={} → base damage={:.0f} on {}",
            unscaled_base_damage,
            n_h_soul,
            n_echo,
            base_damage,
            target,
        )
        create_standard_damage(self.owner.state, self, char, target, base_damage)
        target.effects.add(DiamondStrikeEcho(owner=self.owner))


# ---------------------------------------------------------------------------
# EmeraldJudgement
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class EmeraldJudgement(Effect):
    """Permanent weapon trait aura.

    On damage: rPPM 2.0 (all levels, haste-scaled) chance to fire a direct hit.
    If the caster has FirstStrike active, applies the FirstStrike buff.

    rPPM: 2.0 (all levels)
    Base damage per level: 6000 / 7000 / 8000 / 9000
    """

    owner: Player

    name: str = field(default="emerald_judgement", init=False)
    trait_level: int = 4

    _base_dmg_table: ClassVar[list[float]] = generic_config.EMERALD_JUDGEMENT_BASE_DAMAGE_TABLE

    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=generic_config.EMERALD_JUDGEMENT_PPM,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if not self._rppm.check():
            return
        char = self.owner
        if not isinstance(char, Player):
            return
        target = event.target
        state = self.owner.state
        state.schedule(
            time_delay=0.0,
            callback=GenericTimedEvent(name="emerald_judgement proc", callback=lambda: self._fire(char, target)),
        )

    def _fire(self, char: Player, target: Entity) -> None:
        # Reset FirstStrike so the hit triggers the buff
        fs = char.effects.get(FirstStrike)
        if fs is not None:
            fs.apply_first_strike()

        base_damage = self._base_dmg_table[self.trait_level - 1]
        create_standard_damage(self.owner.state, self, char, target, base_damage)


# ---------------------------------------------------------------------------
# SapphireAurastone
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class SapphireAurastoneSetup(SetupEffectLate[Player]):
    """Master weapon trait setup: adds SapphireAurastone aura and sets spirit_of_heroism_aura.sapphire_aurastone_level.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    trait_level: int = 4

    def apply(self, character: "Player", context: SetupContext) -> None:
        soh_aura = context.spirit_of_heroism_aura
        if soh_aura is None:
            raise RuntimeError(  # noqa: TRY003
                "SapphireAurastoneSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )
        soh_aura.sapphire_aurastone_level = self.trait_level
        logger.debug(
            f"setup: Sapphire Aurastone added; spirit of heroism aurastone level={soh_aura.sapphire_aurastone_level}",
        )


@dataclass(kw_only=True, repr=False)
class SapphireAurastonePulse(Effect):
    """Active while Spirit of Heroism is up (grafted on by SpiritOfHeroism).

    Accumulates a fraction of all damage dealt by the owner and pulses the
    total equally to all enemies every 3 seconds.
    Remaining accumulated damage is dealt when the effect is removed.

    ratio: fraction of damage to accumulate (from SapphireAurastone.ratio).
    """

    name: str = field(default="sapphire_aurastone_pulse", init=False)

    trait_level: int
    ratio: float = field(init=False)

    pulse_interval: float = field(default=generic_config.SAPPHIRE_AURASTONE_PULSE_INTERVAL, init=False)

    accumulated: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.ratio = generic_config.SAPPHIRE_AURASTONE_RATIO_TABLE[self.trait_level - 1]

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        bus.subscribe(AbilityPeriodicDamage, self._on_periodic_damage, owner=self)
        state = self.owner.state
        state.schedule(
            time_delay=self.pulse_interval,
            callback=GenericTimedEvent(name="sapphire_aurastone pulse", callback=self._pulse),
        )

    def _on_damage(self, event: AbilityDamage) -> None:
        self.accumulated += event.damage * self.ratio

    def _on_periodic_damage(self, event: AbilityPeriodicDamage) -> None:
        self.accumulated += event.damage * self.ratio

    def _pulse(self) -> None:
        if self.attached_to is None:
            return
        enemies = self.owner.state.enemies
        if enemies and self.accumulated > 1e-9:
            per_enemy = self.accumulated / len(enemies)
            logger.debug("sapphire_aurastone pulse: {:.0f} total ({:.0f}/enemy)", self.accumulated, per_enemy)
            char = self.owner
            for enemy in list(enemies):
                self.owner.state.bus.emit(
                    AbilityDamage(
                        damage_source=self,
                        owner=char,
                        target=enemy,
                        is_crit=False,
                        is_grievous_crit=False,
                        damage=per_enemy,
                    )
                )
            self.accumulated = 0.0
        state = self.owner.state
        state.schedule(
            time_delay=self.pulse_interval,
            callback=GenericTimedEvent(name="sapphire_aurastone pulse", callback=self._pulse),
        )

    def on_remove(self, *, is_remove_from_expiration: bool = False) -> None:
        if self.accumulated < 1e-9 or self.attached_to is None:
            return
        enemies = self.owner.state.enemies
        if not enemies:
            return
        per_enemy = self.accumulated / len(enemies)
        logger.debug("sapphire_aurastone final pulse: {:.0f} total ({:.0f}/enemy)", self.accumulated, per_enemy)
        char = self.owner
        for enemy in list(enemies):
            self.owner.state.bus.emit(
                AbilityDamage(
                    damage_source=self,
                    owner=char,
                    target=enemy,
                    is_crit=False,
                    is_grievous_crit=False,
                    damage=per_enemy,
                )
            )
        self.accumulated = 0.0


# ---------------------------------------------------------------------------
# VisionsOfGrandeur
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class VisionsOfGrandeur(Effect):
    """Permanent weapon trait aura.

    - Weapon ability cast: grant SP = sp_rate x ability.base_cooldown / 30.
    - Spirit ability cast (UltimateCast): reset all equipped weapon ability cooldowns.

    SP rate per level: 2.0 / 2.4 / 2.8 / 3.2
    """

    owner: Player

    name: str = field(default="visions_of_grandeur", init=False)
    trait_level: int = 4

    _sp_rate_table: ClassVar[list[float]] = generic_config.VISIONS_OF_GRANDEUR_SP_RATE_TABLE
    sp_cdr_normalization: float = field(
        default=generic_config.VISIONS_OF_GRANDEUR_SP_CDR_NORMALIZATION, init=False
    )

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)
        bus.subscribe(UltimateCast, self._on_ultimate, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        from fellowship_sim.base_classes.ability import WeaponAbility

        if not isinstance(event.ability, WeaponAbility):
            return
        sp_rate = self._sp_rate_table[self.trait_level - 1]
        sp = sp_rate * event.ability.base_cooldown / self.sp_cdr_normalization
        char = self.owner
        char.spirit_points = min(char.spirit_points + sp, char.max_spirit_points)

        ability_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(event.ability).__name__)
        logger.debug(
            "Visions of Grandeur: {} cast → +{:.2f} SP (now {:.1f})",
            ability_label,
            sp,
            char.spirit_points,
        )

    def _on_ultimate(self, event: UltimateCast) -> None:
        from fellowship_sim.base_classes.ability import WeaponAbility

        char = self.owner
        for ability in char.abilities:
            if isinstance(ability, WeaponAbility):
                ability._reset_cooldown()
                logger.debug(f"Visions of Grandeur: {ability} CD reset on ultimate cast")


@dataclass(kw_only=True, repr=False)
class BraveMachinations(Effect):
    """Heroic weapon trait aura on the caster.

    Each weapon ability hit gains +crit chance.
    The first crit from any given weapon ability cast reduces that ability's
    remaining cooldown by 30%.  Further crits from the same cast are ignored.

    Crit bonus per level: 20 / 24 / 28 / 32 %
    """

    name: str = field(default="brave_machinations", init=False)
    trait_level: int = 4

    _crit_bonus_table: ClassVar[list[float]] = generic_config.BRAVE_MACHINATIONS_CRIT_BONUS_TABLE

    # Epoch tracking: incremented on each weapon-ability cast; CDR fires once per epoch.
    _cast_epoch: int = field(default=0, init=False)
    _cdr_epoch: int = field(default=-1, init=False)
    cdr_on_crit: float = field(default=generic_config.BRAVE_MACHINATIONS_CDR_ON_CRIT, init=False)

    @property
    def crit_bonus(self) -> float:
        return self._crit_bonus_table[self.trait_level - 1]

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)
        bus.subscribe(SnapshotCreation, self._on_pre_damage, owner=self)
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        bus.subscribe(AbilityPeriodicDamage, self._on_periodic_damage, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        if isinstance(event.ability, WeaponAbility):
            self._cast_epoch += 1

    def _on_pre_damage(self, event: SnapshotCreation) -> None:
        if isinstance(event.damage_source, (WeaponAbility, CurseOfAnzhyr)):
            event.snapshot = event.snapshot.add_crit_percent(self.crit_bonus)

    def _apply_cdr(self, ability: Ability) -> None:
        if self._cdr_epoch == self._cast_epoch:
            return  # already triggered CDR this cast
        self._cdr_epoch = self._cast_epoch
        ability._remove_cooldown_multiplicative(self.cdr_on_crit)

        ability_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(ability).__name__)
        logger.debug(
            "Brave Machinations: crit → {} cooldown -30% (now {:.1f}s)",
            ability_label,
            ability.cooldown,
        )

    def _on_damage(self, event: AbilityDamage) -> None:
        if not event.is_crit:
            return

        if isinstance(event.damage_source, WeaponAbility):
            self._apply_cdr(event.damage_source)

    def _on_periodic_damage(self, event: AbilityPeriodicDamage) -> None:
        if not event.is_crit:
            return

        if isinstance(event.damage_source, CurseOfAnzhyr):
            self._apply_cdr(event.owner.icicles_of_anzhyr)  # ty:ignore[unresolved-attribute]


@dataclass(kw_only=True, repr=False)
class HeroicBrand(Effect):
    """Heroic weapon trait aura on the caster.

    All weapon ability hits deal increased damage.

    Damage bonus per level: +50 / +60 / +70 / +80 %
    """

    name: str = field(default="heroic_brand", init=False)
    trait_level: int = 4

    _dmg_bonus_table: ClassVar[list[float]] = generic_config.HEROIC_BRAND_DAMAGE_BONUS_TABLE

    @property
    def damage_multiplier(self) -> float:
        return 1.0 + self._dmg_bonus_table[self.trait_level - 1]

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SnapshotCreation, self._on_snapshot_create, owner=self)

    def _on_snapshot_create(self, event: SnapshotCreation) -> None:
        if not isinstance(event.damage_source, WeaponAbility):
            return
        event.snapshot = event.snapshot.scale_average_damage(self.damage_multiplier)

        source_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", type(event.damage_source).__name__)
        logger.trace(
            "Heroic Brand: {} x{:.2f} on {}",
            source_label,
            self.damage_multiplier,
        )


# ---------------------------------------------------------------------------
# RubyStorm (master)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class RubyStorm(Effect):
    """Master weapon trait aura on the caster.

    On ability damage (1.3 rPPM, haste-scaled): spawns a Ruby Storm that
    hits all enemies for ratio * caster.healthpoints damage.

    Damage per level: 6.5 / 7.8 / 9.1 / 10.4 % of max health.
    """

    owner: Player

    name: str = field(default="ruby_storm", init=False)
    trait_level: int = 4

    _ratio_table: ClassVar[list[float]] = generic_config.RUBY_STORM_DAMAGE_RATIO_TABLE
    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=generic_config.RUBY_STORM_PPM,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    @property
    def ratio(self) -> float:
        return self._ratio_table[self.trait_level - 1]

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if not self._rppm.check():
            return
        char = self.owner
        if not isinstance(char, Player):
            return
        base_damage = self.ratio * char.healthpoints
        state = self.owner.state
        logger.debug(
            "Ruby Storm: proc {:.0f} dmg (up to 8 enemies, {:.1f}% of {:.0f} HP)",
            base_damage,
            self.ratio * 100,
            char.healthpoints,
        )
        create_standard_damage(
            state,
            self,
            char,
            event.target,
            base_damage,
            num_secondary_targets=generic_config.RUBY_STORM_MAX_SECONDARY_TARGETS,
            is_scaled_by_main_stat=False,
        )


# ---------------------------------------------------------------------------
# MartialInitiative (master)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class MartialInitiativeBuff(Buff):
    """+10% Main Stat for a weapon-ability-scaled duration. (+15% Damage Reduction not simulated.)"""

    name: str = field(default="martial_initiative_buff", init=False)
    duration: float = field(default=6.0, init=True)  # overridden at application time

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatAdditiveMultiplierCharacter(value=generic_config.MARTIAL_INITIATIVE_MAIN_STAT_BONUS)]


@dataclass(kw_only=True, repr=False)
class MartialInitiative(Effect):
    """Master weapon trait aura on the caster.

    On weapon ability cast: applies +10% Main Stat for
    duration_ratio * ability.base_cooldown seconds.  +15% Damage Reduction not simulated.

    Duration ratio per level: 20 / 24 / 28 / 32 % of base cooldown.
    """

    name: str = field(default="martial_initiative", init=False)
    trait_level: int = 4

    _duration_ratio_table: ClassVar[list[float]] = generic_config.MARTIAL_INITIATIVE_DURATION_RATIO_TABLE

    @property
    def duration_ratio(self) -> float:
        return self._duration_ratio_table[self.trait_level - 1]

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        if not isinstance(event.ability, WeaponAbility):
            return
        duration = self.duration_ratio * event.ability.base_cooldown
        self.owner.effects.add(MartialInitiativeBuff(duration=duration, owner=self.owner))
        logger.debug(
            "Martial Initiative: buff {:.1f}s ({:.0f}% of {:.0f}s CD)",
            duration,
            self.duration_ratio * 100,
            event.ability.base_cooldown,
        )


# ---------------------------------------------------------------------------
# HiddenPower / PowerRevealed (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class PowerRevealedBuff(Buff):
    """+X% Main Stat for 15s, granted when HiddenPower reaches 5 stacks."""

    name: str = field(default="power_revealed", init=False)
    duration: float = field(default=generic_config.HIDDEN_POWER_REVEALED_BUFF_DURATION, init=False)
    trait_level: int = 4

    _main_stat_table: ClassVar[list[float]] = generic_config.HIDDEN_POWER_MAIN_STAT_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatAdditiveMultiplierCharacter(value=0.0 + self._main_stat_table[self.trait_level - 1])]


@dataclass(kw_only=True, repr=False)
class HiddenPower(Effect):
    """Heroic weapon trait aura on the caster.

    Ability damage (2.6 rPPM, haste-scaled) grants 1 stack for 60s.
    At 5 stacks they are consumed and PowerRevealed is applied for 15s.
    Cannot gain stacks while PowerRevealed is active.

    Main Stat bonus per level: 7.5 / 9 / 10.5 / 12 %.
    """

    owner: Player

    name: str = field(default="hidden_power", init=False)
    trait_level: int = 4

    _STACK_DURATION: ClassVar[float] = generic_config.HIDDEN_POWER_STACK_DURATION
    _MAX_STACKS: ClassVar[int] = generic_config.HIDDEN_POWER_MAX_STACKS

    _stacks: int = field(default=0, init=False)
    _decay_generation: int = field(default=0, init=False)
    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=generic_config.HIDDEN_POWER_PPM,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityCastSuccess, self._try_gain_stack, owner=self)

    def _try_gain_stack(self, event: AbilityCastSuccess) -> None:
        if not self._rppm.check():
            return
        if self.owner.effects.has(PowerRevealedBuff):
            return

        self._stacks += 1
        self._decay_generation += 1  # invalidate pending decays
        gen = self._decay_generation
        state = self.owner.state
        state.schedule(
            time_delay=self._STACK_DURATION,
            callback=GenericTimedEvent(name="hidden_power stack decay", callback=lambda g=gen: self._decay_stack(g)),
        )
        logger.debug(f"Hidden Power: stack {self._stacks} gained")
        if self._stacks >= self._MAX_STACKS:
            self._decay_generation += 1  # invalidate pending decays
            self._stacks = 0
            self.owner.effects.add(PowerRevealedBuff(trait_level=self.trait_level, owner=self.owner))
            logger.debug("Hidden Power: 5 stacks consumed → power revealed")

    def _decay_stack(self, gen: int) -> None:
        if gen != self._decay_generation:
            return
        if self._stacks > 0:
            self._stacks -= 1
            logger.debug(f"Hidden Power: stack decayed ({self._stacks} remaining)")


# ---------------------------------------------------------------------------
# HuntersFocus (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class HuntersFocusBuff(Buff):
    """Haste Rating buff from HuntersFocus, stacking up to 5 times."""

    owner: Player

    name: str = field(default="hunters_focus_buff", init=False)
    duration: float = field(default=generic_config.HUNTERS_FOCUS_BUFF_DURATION, init=False)
    trait_level: int = 4

    max_stacks: int = field(default=generic_config.HUNTERS_FOCUS_MAX_STACKS, init=False)

    _haste_table: ClassVar[list[int]] = generic_config.HUNTERS_FOCUS_HASTE_PER_STACK_TABLE

    @property
    def haste_per_stack(self) -> int:
        return self._haste_table[self.trait_level - 1]

    def stat_modifiers(self) -> list[StatModifier]:
        return [HasteScoreAdditive(value=self.haste_per_stack * self.stacks)]


@dataclass(kw_only=True, repr=False)
class HuntersFocus(Effect):
    """Heroic weapon trait aura on the caster.

    Targeted offensive ability casts grant +X Haste Rating for 8s,
    stacking up to 5 times.  All stacks are lost if a targeted offensive
    ability is used on a different enemy.

    Haste Rating per stack per level: 20 / 32 / 43 / 55.
    """

    owner: Player

    name: str = field(default="hunters_focus", init=False)
    trait_level: int = 4

    _focus_target: "Entity | None" = field(default=None, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        if event.target is event.owner:
            return  # self-targeted ability — not a "targeted offensive" cast

        if self._focus_target is not None and event.target is not self._focus_target:
            existing = self.owner.effects.get(HuntersFocusBuff)
            if existing is not None:
                existing.remove()
            logger.debug("Hunter's Focus: target changed, stacks reset")

        self._focus_target = event.target
        self.owner.effects.add(HuntersFocusBuff(trait_level=self.trait_level, owner=self.owner))


# ---------------------------------------------------------------------------
# InspiredAllegiance (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class InspiredAllegianceBuff(Buff):
    """Haste Rating buff applied to self by InspiredAllegiance proc."""

    name: str = field(default="inspired_allegiance_buff", init=False)
    duration: float = field(default=generic_config.INSPIRED_ALLEGIANCE_BUFF_DURATION, init=False)
    trait_level: int = 4

    _haste_table: ClassVar[list[int]] = generic_config.INSPIRED_ALLEGIANCE_HASTE_SCORE_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [HasteScoreAdditive(value=self._haste_table[self.trait_level - 1])]


@dataclass(kw_only=True, repr=False)
class InspiredAllegiance(Effect):
    """Heroic weapon trait aura on the caster.

    Ability damage (1.2 rPPM, haste-scaled): reduces all weapon ability
    cooldowns by X seconds and grants +Y Haste Rating for 8s.
    Ally Haste buff not simulated.

    CDR per level: 2 / 3 / 4 / 5 s.  Haste Rating per level: 85 / 85 / 85 / 127.
    """

    owner: Player

    name: str = field(default="inspired_allegiance", init=False)
    trait_level: int = 4

    _cdr_table: ClassVar[list[float]] = generic_config.INSPIRED_ALLEGIANCE_CDR_TABLE
    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=generic_config.INSPIRED_ALLEGIANCE_PPM,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    @property
    def cdr_seconds(self) -> float:
        return self._cdr_table[self.trait_level - 1]

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        bus.subscribe(AbilityPeriodicDamage, self._on_periodic_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        self._try_proc()

    def _on_periodic_damage(self, event: AbilityPeriodicDamage) -> None:
        self._try_proc()

    def _try_proc(self) -> None:
        if not self._rppm.check():
            return
        for ability in self.owner.abilities:
            if isinstance(ability, WeaponAbility):
                ability._remove_cooldown(self.cdr_seconds)
        self.owner.effects.add(InspiredAllegianceBuff(trait_level=self.trait_level, owner=self.owner))
        logger.debug("Inspired Allegiance: proc → -{:.0f}s CDR, +haste buff", self.cdr_seconds)


# ---------------------------------------------------------------------------
# Kindling (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class KindlingDoT(DoTEffect):
    """Fire DoT applied by the Kindling proc."""

    name: str = field(default="kindling_dot", init=False)

    average_damage: float = field(init=True)

    duration: float = field(default=generic_config.KINDLING_DOT_DURATION, init=False)
    base_tick_interval: float = field(default=generic_config.KINDLING_DOT_TICK_DURATION, init=False)


@dataclass(kw_only=True, repr=False)
class Kindling(Effect):
    """Heroic weapon trait aura on the caster.

    Damage events (2.1 rPPM, haste-scaled) apply KindlingDot to the target,
    dealing ratio * main_stat total fire damage over 9s (3 base ticks).
    Healing/cauterize component not simulated.

    Damage ratio per level: 644 / 770 / 931 / 1120 % of primary stat.
    """

    owner: Player

    name: str = field(default="kindling", init=False)
    trait_level: int = 4

    _ratio_table: ClassVar[list[float]] = generic_config.KINDLING_DAMAGE_RATIO_TABLE
    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=generic_config.KINDLING_PPM,
            is_haste_scaled=True,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        self.owner.state.bus.subscribe(AbilityPeriodicDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage | AbilityPeriodicDamage) -> None:
        if isinstance(event.damage_source, (Kindling, KindlingDoT)):
            return

        if self._rppm is None or not self._rppm.check():
            return

        average_damage = self._ratio_table[self.trait_level - 1] * 1000
        event.target.effects.add(KindlingDoT(owner=self.owner, average_damage=average_damage))
        logger.debug(f"Kindling: proc on {event.target} average damage={average_damage:.0f}")


# ---------------------------------------------------------------------------
# Navigator's Intuition (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class NavigatorsIntuitionBuff(Buff):
    """Highest secondary stat gains +X rating for 30s."""

    name: str = field(default="navigators_intuition_buff", init=False)
    duration: float = field(default=generic_config.NAVIGATORS_INTUITION_BUFF_DURATION, init=False)
    trait_level: int = 4

    stat: Literal["crit", "haste", "expertise", "spirit"] = "crit"

    _rating_table: ClassVar[list[int]] = generic_config.NAVIGATORS_INTUITION_RATING_TABLE

    @property
    def rating(self) -> int:
        return self._rating_table[self.trait_level - 1]

    def stat_modifiers(self) -> list[StatModifier]:
        rating = self.rating
        if self.stat == "crit":
            return [CritScoreAdditive(value=rating)]
        elif self.stat == "haste":
            return [HasteScoreAdditive(value=rating)]
        elif self.stat == "expertise":
            return [ExpertiseScoreAdditive(value=rating)]
        else:
            return [SpiritScoreAdditive(value=rating)]


@dataclass(kw_only=True, repr=False)
class NavigatorsIntuition(Effect):
    """Heroic weapon trait aura on the caster.

    Offensive ability casts have a 20% flat chance to grant +X of the highest
    secondary stat for 30s.  Internal cooldown: 90s.

    Rating per level: 276 / 414 / 552 / 690.
    """

    owner: Player

    name: str = field(default="navigators_intuition", init=False)
    trait_level: int = 4

    _PROC_CHANCE: ClassVar[float] = generic_config.NAVIGATORS_INTUITION_PROC_CHANCE
    _ICD: ClassVar[float] = generic_config.NAVIGATORS_INTUITION_ICD

    _next_available: float = field(default=0.0, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityCastSuccess, self._on_cast, owner=self)

    def _on_cast(self, event: AbilityCastSuccess) -> None:
        if event.target is self.owner:
            return

        state = self.owner.state
        if state.time < self._next_available:
            return
        if state.rng.random() >= self._PROC_CHANCE:
            return
        self._next_available = state.time + self._ICD
        stat = self._highest_secondary_stat(self.owner)
        self.owner.effects.add(NavigatorsIntuitionBuff(trait_level=self.trait_level, stat=stat, owner=self.owner))
        logger.debug(f"Navigator's Intuition: proc → +{self.rating_label} {stat} for 30s")

    @property
    def rating_label(self) -> int:
        return NavigatorsIntuitionBuff._rating_table[self.trait_level - 1]

    @staticmethod
    def _highest_secondary_stat(char: Player) -> Literal["crit", "haste", "expertise", "spirit"]:
        """Return 'crit', 'haste', 'expertise', or 'spirit' — whichever is highest."""
        stats = char.stats
        candidates = {
            "crit": stats.crit_score,
            "haste": stats.haste_score,
            "expertise": stats.expertise_score,
            "spirit": stats.spirit_score,
        }
        return cast("Literal['crit', 'haste', 'expertise', 'spirit']", max(candidates, key=lambda k: candidates[k]))


@dataclass(kw_only=True, repr=False)
class PatientSoul(Buff):
    """+X% expertise score; permanent buff."""

    name: str = field(default="patient_soul_buff", init=False)

    trait_level: int = 4

    _expertise_score_table: ClassVar[list[int]] = generic_config.PATIENT_SOUL_EXPERTISE_SCORE_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [ExpertiseScoreAdditive(value=self._expertise_score_table[self.trait_level - 1])]


# ---------------------------------------------------------------------------
# Seized Opportunity (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class SeizedOpportunityBuff(Buff):
    """+X Critical Strike Rating for 12s."""

    name: str = field(default="seized_opportunity_buff", init=False)
    duration: float = field(default=generic_config.SEIZED_OPPORTUNITY_BUFF_DURATION, init=False)
    trait_level: int = 4

    _rating_table: ClassVar[list[int]] = generic_config.SEIZED_OPPORTUNITY_CRIT_SCORE_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [CritScoreAdditive(value=self._rating_table[self.trait_level - 1])]


@dataclass(kw_only=True, repr=False)
class SeizedOpportunity(Effect):
    """Heroic weapon trait aura on the caster.

    Every 20 critical strikes grant +X Critical Strike Rating for 12s.
    Crit count is frozen while SeizedOpportunityBuff is active.

    Crit Rating per level: 112 / 168 / 224 / 280.
    """

    name: str = field(default="seized_opportunity", init=False)
    trait_level: int = 4

    _CRITS_REQUIRED: ClassVar[int] = generic_config.SEIZED_OPPORTUNITY_CRITS_REQUIRED

    _crit_count: int = field(default=0, init=False)

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        bus.subscribe(AbilityPeriodicDamage, self._on_periodic_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if event.is_crit:
            self._count_crit()

    def _on_periodic_damage(self, event: AbilityPeriodicDamage) -> None:
        if event.is_crit:
            self._count_crit()

    def _count_crit(self) -> None:
        if self.owner.effects.has(SeizedOpportunityBuff):
            return
        self._crit_count += 1
        if self._crit_count >= self._CRITS_REQUIRED:
            self._crit_count = 0
            self.owner.effects.add(SeizedOpportunityBuff(trait_level=self.trait_level, owner=self.owner))
            logger.debug("Seized Opportunity: 20 crits → buff applied")


# ---------------------------------------------------------------------------
# Vengeful Soul (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class VengefulSoulBuff(Buff):
    """+X% Main Stat for 6s."""

    name: str = field(default="vengeful_soul_buff", init=False)
    duration: float = field(default=generic_config.VENGEFUL_SOUL_BUFF_DURATION, init=False)
    trait_level: int = 4

    _main_stat_table: ClassVar[list[float]] = generic_config.VENGEFUL_SOUL_MAIN_STAT_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatAdditiveMultiplierCharacter(value=0.0 + self._main_stat_table[self.trait_level - 1])]


@dataclass(kw_only=True, repr=False)
class VengefulSoul(Effect):
    """Heroic weapon trait aura on the caster.

    Critical strikes have a chance (2.0 rPPM, crit-scaled) to increase
    Main Stat by X% for 6s.  Healing below 50% HP not simulated.

    Main Stat bonus per level: 4 / 4.8 / 5.6 / 6.4 %.
    """

    owner: Player

    name: str = field(default="vengeful_soul", init=False)
    trait_level: int = 4

    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=generic_config.VENGEFUL_SOUL_PPM,
            is_haste_scaled=True,
            is_crit_scaled=True,
            owner=self.owner,
        )

    def on_add(self) -> None:
        bus = self.owner.state.bus
        bus.subscribe(AbilityDamage, self._on_damage, owner=self)
        bus.subscribe(AbilityPeriodicDamage, self._on_periodic_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if not event.is_crit:
            return
        self._try_proc()

    def _on_periodic_damage(self, event: AbilityPeriodicDamage) -> None:
        if not event.is_crit:
            return
        self._try_proc()

    def _try_proc(self) -> None:
        if not self._rppm.check():
            return

        self.owner.effects.add(VengefulSoulBuff(trait_level=self.trait_level, owner=self.owner))
        logger.debug(
            "Vengeful Soul: proc → +{:.1f}% main stat for 6s",
            VengefulSoulBuff._main_stat_table[self.trait_level - 1] * 100,
        )


# ---------------------------------------------------------------------------
# Willful Momentum (heroic)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class WillfulMomentumMainStatBuff(Buff):
    """+X% Main Stat for 4s, triggered by WillfulMomentum on SpiritProc."""

    name: str = field(default="willful_momentum_main_stat_buff", init=False)
    duration: float = field(default=generic_config.WILLFUL_MOMENTUM_MAIN_STAT_BUFF_DURATION, init=False)
    trait_level: int = 4

    _main_stat_table: ClassVar[list[float]] = generic_config.WILLFUL_MOMENTUM_MAIN_STAT_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatAdditiveMultiplierCharacter(value=self._main_stat_table[self.trait_level - 1])]


@dataclass(kw_only=True, repr=False)
class WillfulMomentum(Buff):
    """Heroic weapon trait permanent aura on the caster.

    Provides +X Spirit Rating passively.
    On SpiritProc (spirit refund): grants +Y% Main Stat for 4s.

    Spirit Rating per level: 59 / 89 / 118 / 148.
    Main Stat bonus per level: 3 / 3.6 / 4.2 / 4.8 %.
    """

    name: str = field(default="willful_momentum", init=False)
    trait_level: int = 4

    _spirit_rating_table: ClassVar[list[int]] = generic_config.WILLFUL_MOMENTUM_SPIRIT_RATING_TABLE

    def stat_modifiers(self) -> list[StatModifier]:
        return [SpiritScoreAdditive(value=self._spirit_rating_table[self.trait_level - 1])]

    def on_add(self) -> None:
        super().on_add()
        self.owner.state.bus.subscribe(SpiritProc, self._on_spirit_proc, owner=self)

    def _on_spirit_proc(self, event: SpiritProc) -> None:
        self.owner.effects.add(WillfulMomentumMainStatBuff(trait_level=self.trait_level, owner=self.owner))
        logger.debug("Willful Momentum: spirit proc → main stat buff")


# ---------------------------------------------------------------------------
# Trait name types and registries
# ---------------------------------------------------------------------------



def _wrap(cls: type) -> Callable[[int], SetupEffectLate[Player]]:
    """Return a factory that wraps a trait Effect class in a SetupEffectLate."""

    def factory(trait_level: int = 4) -> SetupEffectLate[Player]:
        class _TraitSetup(SetupEffectLate[Player]):
            def apply(self, character: Player, context: SetupContext) -> None:
                character.effects.add(cls(trait_level=trait_level, owner=character))

        return _TraitSetup()

    return factory


_MASTER_TRAITS: dict[MasterTrait, Callable[..., SetupEffectLate[Player]]] = {
    MasterTrait.AMETHYST_SPLINTERS: _wrap(AmethystSplintersAura),
    MasterTrait.BRAVE_MACHINATIONS: _wrap(BraveMachinations),
    MasterTrait.DIAMOND_STRIKE: _wrap(DiamondStrike),
    MasterTrait.EMERALD_JUDGEMENT: _wrap(EmeraldJudgement),
    MasterTrait.HEROIC_BRAND: _wrap(HeroicBrand),
    MasterTrait.MARTIAL_INITIATIVE: _wrap(MartialInitiative),
    MasterTrait.RUBY_STORM: _wrap(RubyStorm),
    MasterTrait.SAPPHIRE_AURASTONE: SapphireAurastoneSetup,
    MasterTrait.VISIONS_OF_GRANDEUR: _wrap(VisionsOfGrandeur),
}

_HEROIC_TRAITS: dict[HeroicTrait, Callable[..., SetupEffectLate[Player]]] = {
    HeroicTrait.HIDDEN_POWER: _wrap(HiddenPower),
    HeroicTrait.HUNTERS_FOCUS: _wrap(HuntersFocus),
    HeroicTrait.INSPIRED_ALLEGIANCE: _wrap(InspiredAllegiance),
    HeroicTrait.KINDLING: _wrap(Kindling),
    HeroicTrait.NAVIGATORS_INTUITION: _wrap(NavigatorsIntuition),
    HeroicTrait.PATIENT_SOUL: _wrap(PatientSoul),
    HeroicTrait.SEIZED_OPPORTUNITY: _wrap(SeizedOpportunity),
    HeroicTrait.VENGEFUL_SOUL: _wrap(VengefulSoul),
    HeroicTrait.WILLFUL_MOMENTUM: _wrap(WillfulMomentum),
}
