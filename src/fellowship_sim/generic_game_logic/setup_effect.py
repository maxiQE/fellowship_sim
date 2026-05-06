"""Generic weapon trait setup effects — applied once after character initialisation."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Generic, TypeVar, get_args, overload

from loguru import logger

from fellowship_sim.base_classes import Effect, Gem, HeroicTrait, MasterTrait, RawStatsFromScores, State, Weapon
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.setup import SetupContext, SetupEffect, SetupEffectEarly, SetupEffectLate
from fellowship_sim.base_classes.stats import RawStats
from fellowship_sim.generic_game_logic import generic_config
from fellowship_sim.generic_game_logic.buff import BaseCritPercent, RandomizePlayerPercentHP, SpiritOfHeroismAura
from fellowship_sim.generic_game_logic.gems import (
    AdrenalineRush,
    AncientsWisdom,
    BerserkersZeal,
    BlessingOfTheArtisan,
    BlessingOfTheCommander,
    BlessingOfTheConqueror,
    BlessingOfTheDeathdealer,
    BlessingOfTheVirtuoso,
    ChampionsHeart,
    FelineGrace,
    FirstStrike,
    GemOvercap,
    HarmoniousSoul,
    KillerInstinct,
    MightOfTheMinotaur,
    MysticsIntuition,
    OraclesForesight,
    ReapersReprieve,
    ResonatingSoul,
    RoguesResurgence,
    SealedFate,
    SentinelsBastion,
    StoicsTeachings,
    TacticiansAcumen,
    ThiefsAlacrity,
    TitansBlood,
    TranquilResolve,
    UnyieldingVitality,
    VanguardsResolve,
)
from fellowship_sim.generic_game_logic.set_effects import (
    _SET_EFFECTS,
    SetEffectName,
)
from fellowship_sim.generic_game_logic.weapon_abilities import WeaponAbilitySetupEffectDict
from fellowship_sim.generic_game_logic.weapon_traits import _HEROIC_TRAITS, _MASTER_TRAITS


class TalentBuild[T]:
    """Immutable ordered talent list supporting + (append) and - (remove) operators."""

    def __init__(self, talents: list[T]) -> None:
        self._talents: list[T] = list(talents)

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> list[T]: ...
    def __getitem__(self, index: int | slice) -> T | list[T]:
        return self._talents[index]

    def __len__(self) -> int:
        return len(self._talents)

    def __iter__(self) -> Iterator[T]:
        return iter(self._talents)

    def __add__(self, talent: T) -> "TalentBuild[T]":
        return TalentBuild([*self._talents, talent])

    def __sub__(self, talent: T) -> "TalentBuild[T]":
        return TalentBuild([t for t in self._talents if t != talent])

    def __repr__(self) -> str:
        return f"TalentBuild({self._talents!r})"


_UNLOCK_THRESHOLDS: list[int] = generic_config.GEM_UNLOCK_THRESHOLDS
_LEVELUP_THRESHOLDS: list[int] = generic_config.GEM_LEVELUP_THRESHOLDS
_OVERCAP_THRESHOLD: int = generic_config.GEM_OVERCAP_THRESHOLD


@dataclass(kw_only=True)
class DefaultEffectSetup(SetupEffectEarly[Player]):
    """Add the default +5% crit and SpiritOfHeroismAura effects."""

    def apply(self, character: Player, context: SetupContext) -> None:
        """Add BaseCritPercent and SpiritOfHeroismAura; store the aura in context for downstream setup effects."""
        soh_aura = SpiritOfHeroismAura(owner=character)
        character.effects.add(BaseCritPercent(owner=character))
        character.effects.add(soh_aura)

        if context.spirit_of_heroism_aura:
            raise Exception("Trying to override already existing spirit_of_heroism_aura on context")  # noqa: TRY002, TRY003
        context.spirit_of_heroism_aura = soh_aura

        character._recalculate_stats()


@dataclass(kw_only=True)
class WeaponMasterTraitSelection(SetupEffectLate[Player]):
    """Apply up to one weapon master trait to the character."""

    master_trait: MasterTrait
    trait_level: int = 4

    def __str__(self) -> str:
        level_str = "" if self.trait_level == 4 else f" (lv.{self.trait_level})"
        return f"Master Trait: {self.master_trait}{level_str}"

    def apply(self, character: Player, context: SetupContext) -> None:
        setup = _MASTER_TRAITS[self.master_trait](trait_level=self.trait_level)
        setup.apply(character, context)
        logger.debug(f"setup: weapon master trait '{self.master_trait}' (level {self.trait_level}) applied")


@dataclass(kw_only=True)
class WeaponHeroicTraitSelection(SetupEffectLate[Player]):
    """Apply up to two weapon heroic traits to the character."""

    heroic_traits: list[HeroicTrait] = field(default_factory=list)
    trait_level: int = 4

    def __post_init__(self) -> None:
        if len(self.heroic_traits) > 2:
            raise ValueError(f"Up to 2 heroic traits allowed, got {len(self.heroic_traits)}")  # noqa: TRY003

    def __str__(self) -> str:
        level_str = "" if self.trait_level == 4 else f" (lv.{self.trait_level})"
        return f"Heroic Traits: {', '.join(self.heroic_traits)}{level_str}"

    def apply(self, character: Player, context: SetupContext) -> None:
        for name in self.heroic_traits:
            setup = _HEROIC_TRAITS[name](trait_level=self.trait_level)
            setup.apply(character, context)
            logger.debug(f"setup: weapon heroic trait '{name}' (level {self.trait_level}) applied")


@dataclass(kw_only=True)
class SetEffectSelection(SetupEffectLate[Player]):
    """Apply one or more set bonus effects to the character."""

    sets: list[SetEffectName]

    def __str__(self) -> str:
        return f"Sets: {', '.join(self.sets)}"

    def apply(self, character: Player, context: SetupContext) -> None:
        for name in self.sets:
            character.effects.add(_SET_EFFECTS[name](owner=character))
            logger.debug(f"setup: set effect '{name}' applied")


@dataclass(kw_only=True)
class RandomizePlayerPercentHPSetup(SetupEffectLate[Player]):
    """Setup effect to randomly shift player HP from 100% to low_hp_percent."""

    high_hp_uptime: float = field(default=generic_config.RANDOMIZE_PLAYER_HP_DEFAULT_HIGH_UPTIME, init=True)

    def __str__(self) -> str:
        return f"High HP uptime: {100 * self.high_hp_uptime:.0f}%"

    def apply(self, character: Player, context: SetupContext) -> None:
        if self.high_hp_uptime < 1.0:
            character.effects.add(RandomizePlayerPercentHP(owner=character, high_hp_uptime=self.high_hp_uptime))
            logger.debug("setup: 'randomize player percent hp' applied")
        else:
            logger.warning(
                "setup: 'randomize player percent hp' NOT APPLIED because requested uptime of 100% disables it. Set to `None` to disable this warning."
            )


@dataclass(kw_only=True)
class _GenericGemSetupEffectLate(SetupEffectLate[Player]):
    """Common protocol for all gem setup-effects."""

    is_level_2: bool = False


@dataclass(kw_only=True)
class BlessingOfTheVirtuosoSetup(_GenericGemSetupEffectLate):
    """Yellow gem (slot 5): permanent +3%/+9% haste buff; sets spirit_of_heroism_aura.blessing_of_the_virtuoso_level.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    def apply(self, character: "Player", context: SetupContext) -> None:

        aura = context.spirit_of_heroism_aura
        if aura is None:
            raise RuntimeError(  # noqa: TRY003
                "BlessingOfTheVirtuosoSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )

        aura.blessing_of_the_virtuoso_level = 2 if self.is_level_2 else 1
        character.effects.add(BlessingOfTheVirtuoso(is_level_2=self.is_level_2, owner=character))

        logger.debug(
            "gem setup: Blessing of the Virtuoso level {} (virtuoso level={}, haste=+{}%)",
            2 if self.is_level_2 else 1,
            aura.blessing_of_the_virtuoso_level,
            9 if self.is_level_2 else 3,
        )


@dataclass(kw_only=True)
class AncestralSurgeSetup(_GenericGemSetupEffectLate):
    """Blue gem (slot 4): +10/+30 max spirit; sets spirit_of_heroism_aura.ancestral_surge_level.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    def apply(self, character: Player, context: SetupContext) -> None:
        """Increase max_spirit_points and set spirit_of_heroism_aura.ancestral_surge_level."""
        bonus = (
            generic_config.ANCESTRAL_SURGE_MAX_SPIRIT_BONUS_L2
            if self.is_level_2
            else generic_config.ANCESTRAL_SURGE_MAX_SPIRIT_BONUS_L1
        )
        character.max_spirit_points += bonus
        level = 2 if self.is_level_2 else 1
        aura = context.spirit_of_heroism_aura
        if aura is None:
            raise RuntimeError(  # noqa: TRY003
                "AncestralSurgeSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )
        aura.ancestral_surge_level = level
        logger.debug(f"gem setup: Ancestral Surge level {level} (+{bonus} max spirit)")


@dataclass(kw_only=True)
class BlessingOfTheProphetSetup(_GenericGemSetupEffectLate):
    """Blue gem (slot 5): SpiritOfHeroism +6s/+18s duration; spirit_ability_cost -5/-15.

    Requires SpiritOfHeroismAuraSetup to have run first (raises RuntimeError otherwise).
    """

    def apply(self, character: Player, context: SetupContext) -> None:
        """Extend SOH duration and reduce spirit_ability_cost on the character."""
        duration_bonus = (
            generic_config.BLESSING_OF_THE_PROPHET_SOH_DURATION_BONUS_L2
            if self.is_level_2
            else generic_config.BLESSING_OF_THE_PROPHET_SOH_DURATION_BONUS_L1
        )
        cost_reduction = (
            generic_config.BLESSING_OF_THE_PROPHET_SPIRIT_COST_REDUCTION_L2
            if self.is_level_2
            else generic_config.BLESSING_OF_THE_PROPHET_SPIRIT_COST_REDUCTION_L1
        )
        aura = context.spirit_of_heroism_aura
        if aura is None:
            raise RuntimeError(  # noqa: TRY003
                "BlessingOfTheProphetSetup requires SpiritOfHeroismAura to be present in SetupContext. "
                "Ensure SpiritOfHeroismAuraSetup (timing=EARLY) is included in setup_effects_late."
            )
        aura.soh_duration += duration_bonus
        character.spirit_ability_cost -= cost_reduction
        logger.debug(
            "gem setup: Blessing of the Prophet level {} (+{:.0f}s spirit of heroism duration, -{:.0f} spirit cost)",
            2 if self.is_level_2 else 1,
            duration_bonus,
            cost_reduction,
        )


# NB: all gem effects have the is_level_2 keyword argument
_GEM_EFFECTS: dict[str, list[type[_GenericGemSetupEffectLate] | type[Effect]]] = {
    "red__ruby": [
        MightOfTheMinotaur,
        ChampionsHeart,
        UnyieldingVitality,
        TitansBlood,
        BlessingOfTheConqueror,
    ],
    "purple__amethyst": [
        SealedFate,
        BerserkersZeal,
        ReapersReprieve,
        KillerInstinct,
        BlessingOfTheDeathdealer,
    ],
    "yellow__topaz": [
        AdrenalineRush,
        ThiefsAlacrity,
        RoguesResurgence,
        FelineGrace,
        BlessingOfTheVirtuosoSetup,
    ],
    "green__emerald": [
        FirstStrike,
        VanguardsResolve,
        SentinelsBastion,
        TacticiansAcumen,
        BlessingOfTheCommander,
    ],
    "blue__saphire": [
        AncestralSurgeSetup,
        MysticsIntuition,
        ResonatingSoul,
        OraclesForesight,
        BlessingOfTheProphetSetup,
    ],
    "white__diamond": [
        HarmoniousSoul,
        StoicsTeachings,
        TranquilResolve,
        AncientsWisdom,
        BlessingOfTheArtisan,
    ],
}


@dataclass(kw_only=True)
class GemSetupEffect(SetupEffectLate[Player]):
    """Apply gem effects to a character based on gem color and power.

    Unlock thresholds (one effect per step): 120, 240, 480, 720, 960.
    Level-up thresholds (effects leveled in order): 1200, 1560, 1920, 2280, 2640.
    Power above 2640 generates a GemOvercap bonus: k * 0.005% main stat where k = power - 2640.
    """

    gem_power: dict[Gem, int]

    total_gem_power: int = field(default=generic_config.GEM_TOTAL_MAX_POWER, init=True)
    gem_trait_level: dict[Gem, tuple[int, int]] = field(init=False)
    overcap_power: int = field(init=False)

    def __post_init__(self) -> None:
        total_gem_power = sum(self.gem_power.values())
        if total_gem_power > self.total_gem_power:
            raise ValueError(f"Configured gem power {total_gem_power} exceeds maximum {self.total_gem_power}")  # noqa: TRY003
        self.gem_trait_level = {
            gem_color: (
                sum(1 for t in _UNLOCK_THRESHOLDS if power >= t),
                sum(1 for t in _LEVELUP_THRESHOLDS if power >= t),
            )
            for gem_color, power in self.gem_power.items()
        }
        self.overcap_power = sum(
            power - _OVERCAP_THRESHOLD for gem_color, power in self.gem_power.items() if power > _OVERCAP_THRESHOLD
        )

    def __str__(self) -> str:
        trait_level_info = []
        for gem_color in Gem:
            if gem_color not in self.gem_power:
                continue
            num_unlocked, num_leveled = self.gem_trait_level[gem_color]
            total_trait_level = num_unlocked + num_leveled
            prefix = gem_color.split("__")[0][0]
            trait_level_info.append((total_trait_level, prefix))

        # Sort by total_trait_level, ignore color to keep order unchanged
        trait_level_info.sort(key=lambda tup: tup[0], reverse=True)

        trait_level_info = [f"{total_trait_level}{prefix}" for total_trait_level, prefix in trait_level_info]

        power_level_info = sorted(
            [(power, gem_color.split("__")[0][0]) for gem_color, power in self.gem_power.items()],
            key=lambda tup: tup[0],
            reverse=True,
        )

        return f"Gems: {' '.join(trait_level_info)} (+{self.overcap_power}) [{', '.join(f'{p}{c}' for p, c in power_level_info)}]"

    def apply(self, character: Player, context: SetupContext) -> None:
        for gem_color in self.gem_power:
            effects = _GEM_EFFECTS[gem_color]
            num_unlocked, num_leveled = self.gem_trait_level[gem_color]

            for i, effect_cls in enumerate(effects[:num_unlocked]):
                is_level_2 = i < num_leveled
                if issubclass(effect_cls, _GenericGemSetupEffectLate):
                    effect_cls(is_level_2=is_level_2).apply(character, context)
                else:
                    # NB: all gem effects have the is_level_2 keyword argument
                    character.effects.add(effect_cls(is_level_2=is_level_2, owner=character))  # ty:ignore[unknown-argument]

                gem_label = gem_color.replace("__", ": ").replace("_", " ")
                effect_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", effect_cls.__name__)
                logger.debug(
                    "gem setup: {} {} (level {})",
                    gem_label,
                    effect_label,
                    2 if is_level_2 else 1,
                )

        if self.overcap_power > 0:
            character.effects.add(GemOvercap(overcap=self.overcap_power, owner=character))


# ---------------------------------------------------------------------------
# Generic player setup orchestrator
# ---------------------------------------------------------------------------

_P = TypeVar("_P", bound=Player)


@dataclass(kw_only=True)
class PlayerSetup(Generic[_P]):  # noqa: UP046
    """Generic base for all character setup orchestrators.

    Subclasses must:
    - declare valid_weapon_abilities as field(init=False) listing the weapons
      valid for that character;
    - implement _create_character(state) returning the concrete Player subtype.
    """

    raw_stats: RawStats
    initial_spirit_points: float = 100

    weapon_ability: Weapon | None = None
    master_trait: MasterTrait | None = None
    master_trait_level: int = 4
    heroic_traits: list[HeroicTrait] | None = None
    heroic_trait_level: int = 4
    sets: list[SetEffectName] | None = None
    gem_power: dict[Gem, int] | None = None
    total_gem_power: int | None = None
    high_hp_uptime: float | None = None

    total_talent_points = generic_config.TOTAL_TALENT_POINTS

    # Declared without default: each subclass overrides with field(init=False, default_factory=...)
    # listing only the weapons valid for that specific character.
    valid_weapon_abilities: frozenset[Weapon]

    total_gem_power_default: list[int] = field(default_factory=lambda: [5256, 4608, 3876, 3066, 2256], init=False)
    setup_effect_list: list[SetupEffect[Player]] = field(init=False)
    num_sets: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        num_sets = len(self.sets) if self.sets is not None else 0
        if self.total_gem_power is None:
            if num_sets >= len(self.total_gem_power_default):
                raise ValueError(  # noqa: TRY003
                    f"too many sets equipped ({num_sets} > 4); sets: {self.sets}"
                )
            resolved_gem_power = self.total_gem_power_default[num_sets]
        else:
            resolved_gem_power = self.total_gem_power

        if self.num_sets is not None and num_sets != self.num_sets:
            logger.warning(
                f"Character setup has default number of sets: {self.num_sets} but only {num_sets} were chosen."
                " This probably indicates a mistake during setup configuration."
                " You can remove this warning by setting num_sets = None during call."
            )

        try:
            self._validate_inputs()
            self.setup_effect_list = self._build_setup_effect_list(resolved_gem_power=resolved_gem_power)
        except ValueError as e:
            raise ValueError(f"{type(self).__name__} configuration error: {e}") from e  # noqa: TRY003

    def _validate_inputs(self) -> None:
        if self.weapon_ability is not None and self.weapon_ability not in self.valid_weapon_abilities:
            raise ValueError(  # noqa: TRY003
                f"invalid weapon_ability {self.weapon_ability!r}; must be one of {sorted(self.valid_weapon_abilities)}"
            )
        if self.sets is not None:
            invalid_sets = [s for s in self.sets if s not in get_args(SetEffectName)]
            if invalid_sets:
                raise ValueError(  # noqa: TRY003
                    f"invalid sets {invalid_sets!r}; must be one of {get_args(SetEffectName)}"
                )
        if self.high_hp_uptime is not None and not (0 <= self.high_hp_uptime <= 1.0):
            raise ValueError(  # noqa: TRY003
                f"invalid high_hp_uptime: {self.high_hp_uptime}; must be between 0.0 and 1.0"
            )

    def _character_default_setup_effects(self) -> list[SetupEffect[Player]]:
        """Always-active permanent effects, applied first. Override in subclasses."""
        return []

    def _character_pre_generic_setup_effects(self) -> list[SetupEffect[Player]]:
        """Character-specific effects before weapon/trait/gem/set effects. Override in subclasses."""
        return []

    def _build_setup_effect_list(self, *, resolved_gem_power: int) -> list[SetupEffect[Player]]:
        effects: list[SetupEffect[Player]] = [
            DefaultEffectSetup(),
            *self._character_default_setup_effects(),
            *self._character_pre_generic_setup_effects(),
        ]
        if self.weapon_ability is not None:
            effects.append(WeaponAbilitySetupEffectDict[self.weapon_ability]())
        if self.master_trait is not None:
            effects.append(
                WeaponMasterTraitSelection(master_trait=self.master_trait, trait_level=self.master_trait_level)
            )
        if self.heroic_traits is not None:
            effects.append(
                WeaponHeroicTraitSelection(heroic_traits=self.heroic_traits, trait_level=self.heroic_trait_level)
            )
        if self.gem_power is not None:
            effects.append(GemSetupEffect(gem_power=self.gem_power, total_gem_power=resolved_gem_power))
        if self.sets is not None:
            effects.append(SetEffectSelection(sets=self.sets))
        if self.high_hp_uptime is not None:
            effects.append(RandomizePlayerPercentHPSetup(high_hp_uptime=self.high_hp_uptime))
        return effects

    def __str__(self) -> str:
        state = State()
        character = self.finalize(state)
        info_lines: list[str] = []
        info_lines.append(f"Final main stat: {character.stats.main_stat}")
        if isinstance(character.raw_stats, RawStatsFromScores):
            mutable_stats = character._recalculate_stats()
            scores = "Scores (Raw -> Final): "
            scores += f"{character.raw_stats.crit_score} -> {mutable_stats.crit_score}\t"
            scores += f"{character.raw_stats.expertise_score} -> {mutable_stats.expertise_score}\t"
            scores += f"{character.raw_stats.haste_score} -> {mutable_stats.haste_score}\t"
            scores += f"{character.raw_stats.spirit_score} -> {mutable_stats.spirit_score}"
            info_lines.append(scores)
            bonus_percent = "Bonus percent: "
            bonus_percent += f"{100 * mutable_stats.crit_percent:.0f}%\t"
            bonus_percent += f"{100 * mutable_stats.expertise_percent:.0f}%\t"
            bonus_percent += f"{100 * mutable_stats.haste_percent:.0f}%\t"
            bonus_percent += f"{100 * mutable_stats.spirit_percent:.0f}%"
            info_lines.append(bonus_percent)
        stats = f"Final percent: {100 * character.stats.crit_percent:<4.2f}%\t{100 * character.stats.expertise_percent:<4.2f}%\t{100 * character.stats.haste_percent:<4.2f}%\t{100 * character.stats.spirit_percent:<4.2f}%"
        derived = f"Spirit proc chance={100 * character.stats.spirit_proc_chance:<4.2f}, crit multiplier={character.stats.crit_multiplier:<4.2f}"
        info_lines += [stats, derived]
        n_base = 1 + len(self._character_default_setup_effects())
        info_lines += [str(elem) for elem in self.setup_effect_list[n_base:]]
        state.deactivate()
        return "\n".join(info_lines)

    def _create_character(self, state: State) -> "_P":
        raise NotImplementedError

    def finalize(self, state: State) -> "_P":
        character = self._create_character(state)
        character.spirit_points = self.initial_spirit_points
        context = SetupContext()
        for setup_effect in self.setup_effect_list:
            setup_effect.apply(character, context)
        character._recalculate_stats()
        return character
