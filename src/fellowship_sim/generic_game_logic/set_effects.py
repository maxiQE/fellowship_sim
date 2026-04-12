"""Set bonus effects — permanent or proc auras applied during setup."""

from dataclasses import dataclass, field
from typing import Literal

from fellowship_sim.base_classes import Player
from fellowship_sim.base_classes.effect import Buff, Effect
from fellowship_sim.base_classes.events import (
    AbilityDamage,
    PreDamageSnapshotUpdate,
    UltimateCast,
)
from fellowship_sim.base_classes.real_ppm import RealPPM
from fellowship_sim.base_classes.stats import (
    CritPercentAdditive,
    ExpertisePercentAdditive,
    HastePercentAdditive,
    MainStatAdditiveMultiplierCharacter,
    MainStatTrueMultiplierCharacter,
    SpiritPercentAdditive,
    StatModifier,
)

# ---------------------------------------------------------------------------
# Dark Prophecy (2-piece)
# 0.8 rPPM (haste-scaled) on damage → +25% haste for 20s
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DarkProphecyBuff(Buff):
    """+25% Haste for 20s, applied by DarkProphecy on proc."""

    name: str = field(default="dark_prophecy_buff", init=False)
    duration: float = field(default=20.0, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [HastePercentAdditive(value=0.25)]


@dataclass(kw_only=True, repr=False)
class DarkProphecy(Effect):
    """Proc aura: 0.8 rPPM (NOT haste-scaled??) on damage → DarkProphecyBuff (+25% haste, 20s)."""

    owner: Player

    name: str = field(default="dark_prophecy", init=False)

    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=0.8,
            is_haste_scaled=False,
            is_crit_scaled=False,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if not self._rppm.check():
            return
        self.owner.effects.add(DarkProphecyBuff(owner=self.owner))


# ---------------------------------------------------------------------------
# Draconic Might (2-piece)
# 0.9 rPPM (crit-scaled) on crit → +18% main stat for 14s
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DraconicMightBuff(Buff):
    """+18% Main Stat for 14s, applied by DraconicMight on crit proc."""

    name: str = field(default="draconic_might_buff", init=False)
    duration: float = field(default=14.0, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatAdditiveMultiplierCharacter(value=0.18)]


@dataclass(kw_only=True, repr=False)
class DraconicMight(Effect):
    """Proc aura: 0.9 rPPM (crit-scaled) on critical strikes → DraconicMightBuff (+18% main stat, 14s)."""

    owner: Player

    name: str = field(default="draconic_might", init=False)

    _rppm: RealPPM = field(init=False)

    def __post_init__(self) -> None:
        self._rppm = RealPPM(
            base_ppm=0.9,
            is_haste_scaled=False,
            is_crit_scaled=True,
            owner=self.owner,
        )

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(AbilityDamage, self._on_damage, owner=self)

    def _on_damage(self, event: AbilityDamage) -> None:
        if not event.is_crit:
            return
        if not self._rppm.check():
            return
        self.owner.effects.add(DraconicMightBuff(owner=self.owner))


# ---------------------------------------------------------------------------
# Death's Grasp (2-piece)
# +3% Spirit; +15% damage to low-health targets (<= 30% HP)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DeathsGrasp(Buff):
    """+3% Spirit; +15% damage dealt to targets at <= 30% HP."""

    name: str = field(default="deaths_grasp", init=False)

    low_health_threshold: float = 0.30
    damage_bonus: float = 0.15

    def stat_modifiers(self) -> list[StatModifier]:
        return [SpiritPercentAdditive(value=0.03)]

    def on_add(self) -> None:
        super().on_add()
        self.owner.state.bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        if event.target.percent_hp <= self.low_health_threshold:
            event.snapshot = event.snapshot.scale_average_damage(1.0 + self.damage_bonus)


# ---------------------------------------------------------------------------
# Drakheim's Absolution
# Spirit ability cast → +20% main stat for 20s
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class DrakheimsAbsolutionBuff(Buff):
    """+20% Main stat for 20s, applied by DrakheimsAbsolution on spirit ability cast."""

    name: str = field(default="drakheims_absolution", init=False)
    duration: float = field(default=20.0, init=False)
    max_stacks: int = field(default=5, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatTrueMultiplierCharacter(multiplier=1.20)]


@dataclass(kw_only=True, repr=False)
class DrakheimsAbsolution(Effect):
    """Permanent aura: spirit ability cast (UltimateCast) → DrakheimsAbsolutionBuff."""

    name: str = field(default="drakheims_absolution_aura", init=False)

    def on_add(self) -> None:
        self.owner.state.bus.subscribe(UltimateCast, self._on_ultimate, owner=self)

    def _on_ultimate(self, event: UltimateCast) -> None:
        self.owner.effects.add(DrakheimsAbsolutionBuff(owner=self.owner))


# ---------------------------------------------------------------------------
# Eldrin Deceit (2-piece)
# +3% Critical Strike Chance
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class EldrinDeceit(Buff):
    """+3% Critical Strike Chance."""

    name: str = field(default="eldrin_deceit", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [CritPercentAdditive(value=0.03)]


# ---------------------------------------------------------------------------
# Haunting Lament (2-piece)
# +3% Spirit
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class HauntingLament(Buff):
    """+3% Spirit."""

    name: str = field(default="haunting_lament", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [SpiritPercentAdditive(value=0.03)]


# ---------------------------------------------------------------------------
# Sin Warding (2-piece)
# +3% Expertise; +5% Max Health (HP component not simulated)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class SinWarding(Buff):
    """+3% Expertise. (+5% Max Health — not simulated.)"""

    name: str = field(default="sin_warding", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [ExpertisePercentAdditive(value=0.03)]


# ---------------------------------------------------------------------------
# Sinthara's Veil (2-piece)
# +3% Spirit; +10% magic damage reduction (not simulated)
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class SintharasVeil(Buff):
    """+3% Spirit. (+10% magic damage reduction — not simulated.)"""

    name: str = field(default="sintharas_veil", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [SpiritPercentAdditive(value=0.03)]


# ---------------------------------------------------------------------------
# Torment of Bael'Aurum (2-piece)
# +4% Main Stat
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class TormentOfBaelAurum(Buff):
    """+4% Main Stat."""

    name: str = field(default="torment_of_baelaurum", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [MainStatTrueMultiplierCharacter(multiplier=1.04)]


# ---------------------------------------------------------------------------
# Tuzari Grace (2-piece)
# +3% Haste
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class TuzariGrace(Buff):
    """+3% Haste."""

    name: str = field(default="tuzari_grace", init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [HastePercentAdditive(value=0.03)]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SetEffectName = Literal[
    "Dark Prophecy",
    "Draconic Might",
    "Death's Grasp",
    "Drakheim's Absolution",
    "Eldrin Deceit",
    "Haunting Lament",
    "Sin Warding",
    "Sinthara's Veil",
    "Torment of Bael'Aurum",
    "Tuzari Grace",
]

_SET_EFFECTS: dict[SetEffectName, type[Effect]] = {
    "Dark Prophecy": DarkProphecy,
    "Draconic Might": DraconicMight,
    "Death's Grasp": DeathsGrasp,
    "Drakheim's Absolution": DrakheimsAbsolution,
    "Eldrin Deceit": EldrinDeceit,
    "Haunting Lament": HauntingLament,
    "Sin Warding": SinWarding,
    "Sinthara's Veil": SintharasVeil,
    "Torment of Bael'Aurum": TormentOfBaelAurum,
    "Tuzari Grace": TuzariGrace,
}
