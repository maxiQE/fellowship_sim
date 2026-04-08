from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from fellowship_sim.base_classes import Ability, Player


# ---------------------------------------------------------------------------
# Score-to-percent conversion (authoritative location)
# ---------------------------------------------------------------------------


def secondary_stat_percent_from_score(score: float) -> float:
    """Convert a secondary-stat score to a percent fraction.

    Affine by parts:
      0-589    -> 0-10%   (100% efficiency)
      589-898  -> 10-15%  (95% efficiency)
      898-1242 -> 15-20%  (85.5% efficiency)
      1242-1647-> 20-25%  (72.675% efficiency)
      1647+    -> 25%+    (58.2% efficiency)
    """
    thresholds = [589, 898, 1242, 1647]
    if score < thresholds[0]:
        return score / thresholds[0] * 0.1
    elif score < thresholds[1]:
        return 0.1 + (score - thresholds[0]) / (thresholds[1] - thresholds[0]) * 0.05
    elif score < thresholds[2]:
        return 0.15 + (score - thresholds[1]) / (thresholds[2] - thresholds[1]) * 0.05
    elif score < thresholds[3]:
        return 0.2 + (score - thresholds[2]) / (thresholds[3] - thresholds[2]) * 0.05
    else:
        return 0.25 + (score - thresholds[3]) * 0.009901 / 100


# ---------------------------------------------------------------------------
# Stat system: RawStats / MutableStats / FinalStats / StatModifier
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, frozen=True)
class FinalStats:
    """Immutable stats — result of collating RawStats and all active effect modifiers."""

    main_stat: float
    crit_percent: float
    expertise_percent: float
    haste_percent: float
    spirit_percent: float
    crit_multiplier: float

    def __str__(self) -> str:
        return f"stats(main={self.main_stat:.0f}, haste={self.haste_percent:.1%}, crit={self.crit_percent:.1%})"

    def __repr__(self) -> str:
        return str(self)

    @property
    def spirit_proc_chance(self) -> float:
        return self.spirit_percent / (1 + self.spirit_percent)


@dataclass(kw_only=True)
class MutableStats:
    """Mutable accumulator seeded from RawStats; StatModifiers apply here before finalization.

    Score fields receive additive score modifiers; percent fields receive additive percent
    modifiers.  ``finalize()`` converts scores to percents (via the rating curve) and sums
    them with the direct percent fields to produce an immutable FinalStats.
    """

    base_main_stat: float
    crit_score: float
    expertise_score: float
    haste_score: float
    spirit_score: float
    crit_percent: float
    expertise_percent: float
    haste_percent: float
    spirit_percent: float
    crit_multiplier: float

    main_stat_additive_bonus: float = field(default=0, init=False)
    main_stat_additive_multiplier: float = field(default=1.0, init=False)  # Bucket 2 !!
    main_stat_true_multiplier: float = field(default=1.0, init=False)

    @property
    def main_stat(self) -> float:
        return (
            (self.base_main_stat + self.main_stat_additive_bonus)
            * self.main_stat_additive_multiplier
            * self.main_stat_true_multiplier
        )

    def finalize(self) -> FinalStats:
        return FinalStats(
            main_stat=self.main_stat,
            crit_percent=self.crit_percent + secondary_stat_percent_from_score(self.crit_score),
            expertise_percent=self.expertise_percent + secondary_stat_percent_from_score(self.expertise_score),
            haste_percent=self.haste_percent + secondary_stat_percent_from_score(self.haste_score),
            spirit_percent=self.spirit_percent + secondary_stat_percent_from_score(self.spirit_score),
            crit_multiplier=self.crit_multiplier,
        )


def _require_non_negative(value: float | int, name: str) -> None:
    if value < 0:
        msg = f"{name} must be >= 0, got {value}"
        raise ValueError(msg)


@dataclass(kw_only=True, frozen=True)
class StatModifier(ABC):
    """Unified modifier applied to MutableStats — covers both score and percent adjustments."""

    @abstractmethod
    def apply(self, stats: MutableStats) -> None: ...


@dataclass(kw_only=True, frozen=True)
class MainStatAdditiveCharacter(StatModifier):
    value: int

    def apply(self, stats: MutableStats) -> None:
        stats.main_stat_additive_bonus += self.value


@dataclass(kw_only=True, frozen=True)
class MainStatAdditiveMultiplierCharacter(StatModifier):
    value: float

    def apply(self, stats: MutableStats) -> None:
        stats.main_stat_additive_multiplier += self.value


@dataclass(kw_only=True, frozen=True)
class MainStatTrueMultiplierCharacter(StatModifier):
    multiplier: float

    def apply(self, stats: MutableStats) -> None:
        stats.main_stat_true_multiplier *= self.multiplier


@dataclass(kw_only=True, frozen=True)
class CritMultiplierMultiplicativeCharacter(StatModifier):
    multiplier: float

    def apply(self, stats: MutableStats) -> None:
        stats.crit_multiplier *= self.multiplier


@dataclass(kw_only=True, frozen=True)
class CritPercentAdditive(StatModifier):
    value: float

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.crit_percent += self.value


@dataclass(kw_only=True, frozen=True)
class ExpertisePercentAdditive(StatModifier):
    value: float

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.expertise_percent += self.value


@dataclass(kw_only=True, frozen=True)
class HastePercentAdditive(StatModifier):
    value: float

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.haste_percent += self.value


@dataclass(kw_only=True, frozen=True)
class SpiritPercentAdditive(StatModifier):
    value: float

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.spirit_percent += self.value


@dataclass(kw_only=True, frozen=True)
class CritScoreAdditive(StatModifier):
    value: int

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.crit_score += self.value


@dataclass(kw_only=True, frozen=True)
class ExpertiseScoreAdditive(StatModifier):
    value: int

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.expertise_score += self.value


@dataclass(kw_only=True, frozen=True)
class HasteScoreAdditive(StatModifier):
    value: int

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.haste_score += self.value


@dataclass(kw_only=True, frozen=True)
class SpiritScoreAdditive(StatModifier):
    value: int

    def __post_init__(self) -> None:
        _require_non_negative(self.value, "value")

    def apply(self, stats: MutableStats) -> None:
        stats.spirit_score += self.value


@dataclass(kw_only=True, frozen=True)
class RawStats(ABC):
    """Abstract base: stats from equipped items only — immutable."""

    main_stat: float
    crit_multiplier: float = 1.0

    @abstractmethod
    def to_mutable_stats(self) -> MutableStats: ...


@dataclass(kw_only=True, frozen=True)
class RawStatsFromPercents(RawStats):
    """RawStats expressed directly as percent values."""

    crit_percent: float = 0.0
    expertise_percent: float = 0.0
    haste_percent: float = 0.0
    spirit_percent: float = 0.0

    def __post_init__(self) -> None:
        for name, val in [
            ("crit_percent", self.crit_percent),
            ("expertise_percent", self.expertise_percent),
            ("haste_percent", self.haste_percent),
            ("spirit_percent", self.spirit_percent),
        ]:
            _require_non_negative(val, name)

    def to_mutable_stats(self) -> MutableStats:
        return MutableStats(
            base_main_stat=self.main_stat,
            crit_score=0,
            expertise_score=0,
            haste_score=0,
            spirit_score=0,
            crit_percent=self.crit_percent,
            expertise_percent=self.expertise_percent,
            haste_percent=self.haste_percent,
            spirit_percent=self.spirit_percent,
            crit_multiplier=self.crit_multiplier,
        )


@dataclass(kw_only=True, frozen=True)
class RawStatsFromScores(RawStats):
    """RawStats expressed as secondary-stat scores; converted to percents via the rating curve."""

    crit_score: float = 0
    expertise_score: float = 0
    haste_score: float = 0
    spirit_score: float = 0

    total_score_cap: float = field(default=4510, init=True)

    def __post_init__(self) -> None:
        for name, val in [
            ("crit_score", self.crit_score),
            ("expertise_score", self.expertise_score),
            ("haste_score", self.haste_score),
            ("spirit_score", self.spirit_score),
        ]:
            _require_non_negative(val, name)
        total_score = self.crit_score + self.expertise_score + self.haste_score + self.spirit_score
        if total_score > self.total_score_cap:
            raise ValueError(  # noqa: TRY003
                f"Configuration error: Total stat score {total_score} exceeds budget {self.total_score_cap}"
            )

    def to_mutable_stats(self) -> MutableStats:
        return MutableStats(
            base_main_stat=self.main_stat,
            crit_score=self.crit_score,
            expertise_score=self.expertise_score,
            haste_score=self.haste_score,
            spirit_score=self.spirit_score,
            crit_percent=0.0,
            expertise_percent=0.0,
            haste_percent=0.0,
            spirit_percent=0.0,
            crit_multiplier=self.crit_multiplier,
        )


# ---------------------------------------------------------------------------
# Snapshot stat system (ability cast-time stats)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, frozen=True)
class SnapshotStats:
    average_damage: float
    crit_multiplier: float
    crit_percent: float
    # haste_percent: float

    @classmethod
    def from_ability_and_character(cls, ability: "Ability", character: "Player") -> Self:
        """Derive snapshot from ability and character."""
        return cls(
            average_damage=ability.average_damage
            * character.stats.main_stat
            / 1000
            * (1 + character.stats.expertise_percent),
            crit_multiplier=character.stats.crit_multiplier,
            crit_percent=character.stats.crit_percent,
            # haste_percent=character.stats.haste_percent,
        )

    @classmethod
    def from_base_damage_and_character(
        cls,
        base_damage: float,
        character: "Player",
        *,
        is_scaled_by_expertise: bool = True,
        is_scaled_by_main_stat: bool = True,
    ) -> Self:
        """Derive snapshot from ability and character."""
        return cls(
            average_damage=base_damage
            * ((character.stats.main_stat / 1000) if is_scaled_by_main_stat else 1)
            * ((1 + character.stats.expertise_percent) if is_scaled_by_expertise else 1),
            crit_multiplier=character.stats.crit_multiplier,
            crit_percent=character.stats.crit_percent,
            # haste_percent=character.stats.haste_percent,
        )

    def scale_average_damage(self, multiplier: float) -> "SnapshotStats":
        """Return a new snapshot with average_damage multiplied by multiplier."""
        return SnapshotStats(
            average_damage=self.average_damage * multiplier,
            crit_multiplier=self.crit_multiplier,
            crit_percent=self.crit_percent,
            # haste_percent=self.haste_percent,
        )

    def add_crit_percent(self, delta: float) -> "SnapshotStats":
        """Return a new snapshot with crit_percent increased by delta."""
        return SnapshotStats(
            average_damage=self.average_damage,
            crit_multiplier=self.crit_multiplier,
            crit_percent=self.crit_percent + delta,
            # haste_percent=self.haste_percent,
        )
