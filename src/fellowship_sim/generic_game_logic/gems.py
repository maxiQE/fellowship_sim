"""Gem effects — applied as permanent auras during setup."""

from dataclasses import dataclass, field

from loguru import logger

from fellowship_sim.base_classes import base_config
from fellowship_sim.base_classes.effect import Buff, Effect
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.events import (
    AbilityDamage,
    PreDamageSnapshotUpdate,
    SnapshotCreation,
    UnitDestroyed,
)
from fellowship_sim.base_classes.stats import (
    CritMultiplierMultiplicativeCharacter,
    CritPercentAdditive,
    CritScoreAdditive,
    ExpertisePercentAdditive,
    ExpertiseScoreAdditive,
    HastePercentAdditive,
    HasteScoreAdditive,
    MainStatAdditiveCharacter,
    MainStatAdditiveMultiplierCharacter,
    MainStatTrueMultiplierCharacter,
    SpiritPercentAdditive,
    SpiritScoreAdditive,
    StatModifier,
)
from fellowship_sim.generic_game_logic import generic_config


@dataclass(kw_only=True, repr=False)
class MightOfTheMinotaur(Buff):
    """Passive: +3% primary stat while above 80% health (+9% at level 2)."""

    name: str = field(default="might_of_the_minotaur", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        hp_pct = self.owner.percent_hp
        if hp_pct <= generic_config.MIGHT_OF_THE_MINOTAUR_HP_THRESHOLD:
            return []
        value = (
            generic_config.MIGHT_OF_THE_MINOTAUR_STAT_BONUS_L2
            if self.is_level_2
            else generic_config.MIGHT_OF_THE_MINOTAUR_STAT_BONUS_L1
        )
        return [MainStatAdditiveMultiplierCharacter(value=value)]


@dataclass(kw_only=True, repr=False)
class ChampionsHeart(Buff):
    """+15 primary stat (+45 at level 2). Stamina component ignored."""

    name: str = field(default="champions_heart", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.CHAMPIONS_HEART_STAT_BONUS_L2
            if self.is_level_2
            else generic_config.CHAMPIONS_HEART_STAT_BONUS_L1
        )
        return [MainStatAdditiveCharacter(value=value)]


@dataclass(kw_only=True, repr=False)
class UnyieldingVitality(Effect):
    """Heal 0.7% max HP every 2s in combat. No-op."""

    name: str = field(default="unyielding_vitality", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class TitansBlood(Effect):
    """+4% Stamina. No-op."""

    name: str = field(default="titans_blood", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class BlessingOfTheConqueror(Effect):
    """While in a boss fight: +5% damage/healing/absorption (+15% at level 2)."""

    name: str = field(default="blessing_of_the_conqueror", init=False)
    is_level_2: bool = False

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(SnapshotCreation, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: SnapshotCreation) -> None:
        if not any(enemy.is_boss for enemy in self.owner.state.enemies):
            return
        multiplier = (
            generic_config.BLESSING_OF_THE_CONQUEROR_DAMAGE_MULTIPLIER_L2
            if self.is_level_2
            else generic_config.BLESSING_OF_THE_CONQUEROR_DAMAGE_MULTIPLIER_L1
        )
        event.snapshot = event.snapshot.scale_average_damage(multiplier)


@dataclass(kw_only=True, repr=False)
class SealedFate(Effect):
    """+5% critical strike chance on targets above 50% health (+15% at level 2)."""

    name: str = field(default="sealed_fate", init=False)
    is_level_2: bool = False

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if event.target.percent_hp <= generic_config.SEALED_FATE_HP_THRESHOLD:
            return
        delta = (
            generic_config.SEALED_FATE_CRIT_BONUS_L2 if self.is_level_2 else generic_config.SEALED_FATE_CRIT_BONUS_L1
        )
        event.snapshot = event.snapshot.add_crit_percent(delta)


@dataclass(kw_only=True, repr=False)
class BerserkersZeal(Buff):
    """+100 Critical Strike score (+300 at level 2). Stamina component ignored."""

    name: str = field(default="berserkers_zeal", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.BERSERKERS_ZEAL_CRIT_SCORE_L2
            if self.is_level_2
            else generic_config.BERSERKERS_ZEAL_CRIT_SCORE_L1
        )
        return [CritScoreAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class ReapersReprieve(Effect):
    """On enemy death: heal 12% max HP over 18s. No-op."""

    name: str = field(default="reapers_reprieve", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class KillerInstinct(Buff):
    """+3% critical strike chance (+9% at level 2)."""

    name: str = field(default="killer_instinct", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.KILLER_INSTINCT_CRIT_BONUS_L2
            if self.is_level_2
            else generic_config.KILLER_INSTINCT_CRIT_BONUS_L1
        )
        return [CritPercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class BlessingOfTheDeathdealer(Buff):
    """Critical strikes deal 3% more damage (+9% at level 2)."""

    name: str = field(default="blessing_of_the_deathdealer", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        multiplier = (
            generic_config.BLESSING_OF_THE_DEATHDEALER_CRIT_MULTIPLIER_L2
            if self.is_level_2
            else generic_config.BLESSING_OF_THE_DEATHDEALER_CRIT_MULTIPLIER_L1
        )
        return [CritMultiplierMultiplicativeCharacter(multiplier=multiplier)]


@dataclass(kw_only=True, repr=False)
class AdrenalineRushBuff(Buff):
    """+3% Haste for 10s, applied by AdrenalineRush on low-health targets (+9% at level 2)."""

    name: str = field(default="adrenaline_rush", init=False)
    duration: float = field(default=generic_config.ADRENALINE_RUSH_BUFF_DURATION, init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.ADRENALINE_RUSH_HASTE_BONUS_L2
            if self.is_level_2
            else generic_config.ADRENALINE_RUSH_HASTE_BONUS_L1
        )
        return [HastePercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class AdrenalineRush(Effect):
    """Proc aura: apply AdrenalineRushBuff when damage lands on a target at ≤30% health."""

    name: str = field(default="adrenaline_rush_aura", init=False)
    is_level_2: bool = False

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if event.target.percent_hp > base_config.LOW_HEALTH_THRESHOLD:
            return
        self.owner.effects.add(AdrenalineRushBuff(is_level_2=self.is_level_2, owner=self.owner))


@dataclass(kw_only=True, repr=False)
class ThiefsAlacrity(Buff):
    """+100 Haste score (+300 at level 2). Stamina component ignored."""

    name: str = field(default="thiefs_alacrity", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.THIEFS_ALACRITY_HASTE_SCORE_L2
            if self.is_level_2
            else generic_config.THIEFS_ALACRITY_HASTE_SCORE_L1
        )
        return [HasteScoreAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class RoguesResurgence(Effect):
    """When below 50% health: heal 8% max HP. Once per 20s. No-op."""

    name: str = field(default="rogues_resurgence", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class FelineGrace(Buff):
    """+3% Haste (+9% at level 2)."""

    name: str = field(default="feline_grace", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.FELINE_GRACE_HASTE_BONUS_L2
            if self.is_level_2
            else generic_config.FELINE_GRACE_HASTE_BONUS_L1
        )
        return [HastePercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class BlessingOfTheVirtuoso(Buff):
    """+3% Haste retained from Spirit of Heroism while it is inactive (+9% at level 2)."""

    name: str = field(default="blessing_of_the_virtuoso", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.BLESSING_OF_THE_VIRTUOSO_HASTE_BONUS_L2
            if self.is_level_2
            else generic_config.BLESSING_OF_THE_VIRTUOSO_HASTE_BONUS_L1
        )
        return [HastePercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class FirstStrikeBuff(Buff):
    """+5% Expertise for 15s, granted by FirstStrike on the first hit against a new enemy (+15% at level 2)."""

    name: str = field(default="first_strike_buff", init=False)
    duration: float = field(default=generic_config.FIRST_STRIKE_BUFF_DURATION, init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.FIRST_STRIKE_EXPERTISE_BONUS_L2
            if self.is_level_2
            else generic_config.FIRST_STRIKE_EXPERTISE_BONUS_L1
        )
        return [ExpertisePercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class FirstStrike(Effect):
    """Proc aura: apply FirstStrikeBuff on the first attack against each unique enemy."""

    name: str = field(default="first_strike_aura", init=False)
    is_level_2: bool = False
    _attacked_ids: set[int] = field(default_factory=set, init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if event.target.id in self._attacked_ids:
            return
        self._attacked_ids.add(event.target.id)
        self.owner.effects.add(FirstStrikeBuff(is_level_2=self.is_level_2, owner=self.owner))

    def apply_first_strike(self) -> None:
        """Directly apply (or renew) FirstStrikeBuff, independent of the attacked-ids tracking."""
        self.owner.effects.add(FirstStrikeBuff(is_level_2=self.is_level_2, owner=self.owner))


@dataclass(kw_only=True, repr=False)
class VanguardsResolve(Buff):
    """+100 Expertise score (+300 at level 2). Stamina component ignored."""

    name: str = field(default="vanguards_resolve", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.VANGUARDS_RESOLVE_EXPERTISE_SCORE_L2
            if self.is_level_2
            else generic_config.VANGUARDS_RESOLVE_EXPERTISE_SCORE_L1
        )
        return [ExpertiseScoreAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class SentinelsBastion(Effect):
    """Every 60s: shield absorbing 10% max HP for 60s. No-op."""

    name: str = field(default="sentinels_bastion", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class TacticiansAcumen(Buff):
    """+3% Expertise (+9% at level 2)."""

    name: str = field(default="tacticians_acumen", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.TACTICIANS_ACUMEN_EXPERTISE_BONUS_L2
            if self.is_level_2
            else generic_config.TACTICIANS_ACUMEN_EXPERTISE_BONUS_L1
        )
        return [ExpertisePercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class BlessingOfTheCommander(Effect):
    """Player gains 4% / 12% cooldown reduction."""

    owner: Player

    name: str = field(default="blessing_of_the_commander", init=False)
    is_level_2: bool = False

    def on_add(self) -> None:
        self.owner.cooldown_reduction *= 1 - (
            generic_config.BLESSING_OF_THE_COMMANDER_CDR_L2
            if self.is_level_2
            else generic_config.BLESSING_OF_THE_COMMANDER_CDR_L1
        )


@dataclass(kw_only=True, repr=False)
class MysticsIntuition(Buff):
    """+100 Spirit score (+300 at level 2). Stamina component ignored."""

    name: str = field(default="mystics_intuition", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.MYSTICS_INTUITION_SPIRIT_SCORE_L2
            if self.is_level_2
            else generic_config.MYSTICS_INTUITION_SPIRIT_SCORE_L1
        )
        return [SpiritScoreAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class ResonatingSoul(Effect):
    """No-op."""

    name: str = field(default="resonating_soul", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class OraclesForesight(Buff):
    """+3% Spirit (+9% at level 2)."""

    name: str = field(default="oracles_foresight", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.ORACLES_FORESIGHT_SPIRIT_BONUS_L2
            if self.is_level_2
            else generic_config.ORACLES_FORESIGHT_SPIRIT_BONUS_L1
        )
        return [SpiritPercentAdditive(value=value)]


@dataclass(kw_only=True, repr=False)
class HarmoniousSoulBuff(Buff):
    """Stacking buff: +0.3% Crit/Haste/Expertise/Spirit per stack for 5s, up to 10 stacks (+0.9% at level 2).

    The duration of the buff is renewed each time a new stack is applied.
    On buff expiry, instead of all stacks being removed, only a single one is removed.
    Stats are recalculated on every stack change.
    """

    owner: Player

    name: str = field(default="harmonious_soul", init=False)
    duration: float = field(default=generic_config.HARMONIOUS_SOUL_BUFF_DURATION, init=False)

    is_level_2: bool = field(default=False, init=True)
    max_stacks: int = field(default=generic_config.HARMONIOUS_SOUL_MAX_STACKS, init=False)

    def _expire(self, seq: int) -> None:
        """Overwritten: on expiry, remove a single stack."""
        if seq != self._expiry_seq:
            return  # stale — effect was refreshed or removed since this was scheduled
        logger.trace(f"effect expired: {self}")

        self._decay_one_stack()

    def _decay_one_stack(self) -> None:
        """Remove one stack; if zero remain, remove the buff; otherwise renew duration and reschedule expiry."""
        if self.attached_to is None:
            raise Exception("HarmoniousSoul unattached")  # noqa: TRY002, TRY003

        self.stacks -= 1
        if self.stacks <= 0:
            # NB: self.remove automatically trigger _recalculate_stats
            self.remove()
        else:
            # reset duration and reschedule expiry
            self.duration = HarmoniousSoulBuff.duration
            self._schedule_expiry()
            self.owner._recalculate_stats()

    def stat_modifiers(self) -> list[StatModifier]:
        v = self.stacks * (
            generic_config.HARMONIOUS_SOUL_STAT_BONUS_PER_STACK_L2
            if self.is_level_2
            else generic_config.HARMONIOUS_SOUL_STAT_BONUS_PER_STACK_L1
        )
        return [
            CritPercentAdditive(value=v),
            HastePercentAdditive(value=v),
            ExpertisePercentAdditive(value=v),
            SpiritPercentAdditive(value=v),
        ]


@dataclass(kw_only=True, repr=False)
class HarmoniousSoul(Effect):
    """Proc aura: gain a stack of HarmoniousSoulBuff each time an enemy is defeated."""

    owner: Player

    name: str = field(default="harmonious_soul_aura", init=False)
    is_level_2: bool = False

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(UnitDestroyed, self._on_unit_destroyed, owner=self)

    def _on_unit_destroyed(self, event: UnitDestroyed) -> None:
        if event.entity is self.owner:
            return
        self.owner.effects.add(HarmoniousSoulBuff(is_level_2=self.is_level_2, owner=self.owner))


@dataclass(kw_only=True, repr=False)
class StoicsTeachings(Buff):
    """+25 primary stat (+75 at level 2). Armor component ignored."""

    name: str = field(default="stoics_teachings", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        value = (
            generic_config.STOICS_TEACHINGS_MAIN_STAT_L2
            if self.is_level_2
            else generic_config.STOICS_TEACHINGS_MAIN_STAT_L1
        )
        return [MainStatAdditiveCharacter(value=value)]


@dataclass(kw_only=True, repr=False)
class TranquilResolve(Effect):
    """No-op."""

    name: str = field(default="tranquil_resolve", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class AncientsWisdom(Buff):
    """+3% primary stat (+9% at level 2)."""

    name: str = field(default="ancients_wisdom", init=False)
    is_level_2: bool = False

    def stat_modifiers(self) -> list[StatModifier]:
        multiplier = (
            generic_config.ANCIENTS_WISDOM_MAIN_STAT_MULTIPLIER_L2
            if self.is_level_2
            else generic_config.ANCIENTS_WISDOM_MAIN_STAT_MULTIPLIER_L1
        )
        return [MainStatTrueMultiplierCharacter(multiplier=multiplier)]


@dataclass(kw_only=True, repr=False)
class BlessingOfTheArtisan(Effect):
    """No-op."""

    name: str = field(default="blessing_of_the_artisan", init=False)
    is_level_2: bool = False


@dataclass(kw_only=True, repr=False)
class GemOvercap(Buff):
    """Permanent main stat multiplier from gem power exceeding 2640.

    For overcap k = actual_power - 2640, grants k * 0.005% additional main stat
    (multiplier = 1 + k * 0.00005).
    """

    name: str = field(default="gem_overcap", init=False)
    overcap: int = 0

    def __post_init__(self) -> None:
        if self.overcap <= 0:
            raise ValueError(f"gem overcap should be strictly positive, but got {self.overcap}")  # noqa: TRY003

    def stat_modifiers(self) -> list[StatModifier]:
        return [
            MainStatAdditiveMultiplierCharacter(
                value=self.overcap * generic_config.GEM_OVERCAP_MAIN_STAT_BONUS_PER_POINT
            )
        ]
