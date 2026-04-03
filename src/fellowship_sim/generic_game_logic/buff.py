"""Generic active buffs shared across character classes."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fellowship_sim.base_classes import Player
from fellowship_sim.base_classes.effect import Buff, Effect
from fellowship_sim.base_classes.events import UltimateCast
from fellowship_sim.base_classes.state import get_state
from fellowship_sim.base_classes.stats import (
    HastePercentAdditive,
    MainStatAdditiveMultiplierCharacter,
    StatModifier,
)
from fellowship_sim.generic_game_logic.weapon_traits import SapphireAurastonePulse

if TYPE_CHECKING:
    from fellowship_sim.base_classes.events import UltimateCast


@dataclass(kw_only=True, repr=False)
class SpiritOfHeroism(Buff):
    """+30% haste (reduced by blessing_of_the_virtuoso_level) for 20s.

    Optionally adds a main-stat multiplier from ancestral_surge_level:
      level 1 → +8% (* 1.08), level 2 → +24% (* 1.24).

    If sapphire_aurastone_level > 0, starts SapphireAurastonePulse
    on activation and removes it on expiry.
    """

    name: str = field(default="spirit_of_heroism", init=False)

    duration: float
    ancestral_surge_level: int  # 0=none, 1=+8% main stat, 2=+24% main stat
    blessing_of_the_virtuoso_level: int  # 0=none, 1=-3% haste, 2=-9% haste
    sapphire_aurastone_level: int  # 0=absent, 1-4=trait level

    def __str__(self) -> str:
        dur = "∞" if self.duration == float("inf") else f"{self.duration:.1f}s"
        extras = []
        if self.ancestral_surge_level > 0:
            extras.append(f"Surge: {self.ancestral_surge_level}")
        if self.sapphire_aurastone_level > 0:
            extras.append(f"Sapphire Aurastone: {self.sapphire_aurastone_level}")
        if self.blessing_of_the_virtuoso_level > 0:
            extras.append(f"Virtuoso: {self.blessing_of_the_virtuoso_level}")
        suffix = f" [{', '.join(extras)}]" if extras else ""
        return f"Spirit of Heroism ({dur}){suffix}"

    def stat_modifiers(self) -> list[StatModifier]:
        haste_reduction = (
            0.09
            if self.blessing_of_the_virtuoso_level == 2
            else 0.03
            if self.blessing_of_the_virtuoso_level == 1
            else 0.0
        )
        modifiers: list[StatModifier] = [HastePercentAdditive(value=0.30 - haste_reduction)]
        if self.ancestral_surge_level == 2:
            modifiers.append(MainStatAdditiveMultiplierCharacter(value=0.24))
        elif self.ancestral_surge_level == 1:
            modifiers.append(MainStatAdditiveMultiplierCharacter(value=0.08))
        return modifiers

    def on_add(self) -> None:
        super().on_add()
        if self.sapphire_aurastone_level > 0:
            from fellowship_sim.generic_game_logic.weapon_traits import (
                SapphireAurastonePulse,
            )

            self.owner.effects.add(SapphireAurastonePulse(trait_level=self.sapphire_aurastone_level, owner=self.owner))

    def on_remove(self) -> None:
        pulse = self.owner.effects.get(SapphireAurastonePulse)
        if pulse is not None:
            pulse.remove()
        super().on_remove()


@dataclass(kw_only=True, repr=False)
class SpiritOfHeroismAura(Effect):
    """Permanent aura to trigger spirit of heroism when ultimate is cast.

    Carries the configuration for the SpiritOfHeroism buff that fires on UltimateCast:
      - soh_duration            base duration of the fired buff (seconds)
      - ancestral_surge_level   0=none, 1=+8% main stat, 2=+24% main stat
      - blessing_of_the_virtuoso_level  0=none, 1=-3% haste, 2=-9% haste
      - sapphire_aurastone_level        0=absent, 1-4=trait level

    Setup effects registered in the NORMAL (or LATE) phase modify these fields via
    SetupContext.spirit_of_heroism_aura, or directly via character.effects.get().
    """

    name: str = field(default="spirit_of_heroism_aura", init=False)
    soh_duration: float = field(default=20.0, init=False)
    ancestral_surge_level: int = field(default=0, init=False)
    blessing_of_the_virtuoso_level: int = field(default=0, init=False)
    sapphire_aurastone_level: int = field(default=0, init=False)

    def on_add(self) -> None:

        get_state().bus.subscribe(UltimateCast, self._on_ultimate_cast, owner=self)

    def _on_ultimate_cast(self, event: "UltimateCast") -> None:
        self.owner.effects.add(
            SpiritOfHeroism(
                owner=self.owner,
                duration=self.soh_duration,
                ancestral_surge_level=self.ancestral_surge_level,
                blessing_of_the_virtuoso_level=self.blessing_of_the_virtuoso_level,
                sapphire_aurastone_level=self.sapphire_aurastone_level,
            )
        )


@dataclass(kw_only=True, repr=False)
class BaseCritPercent(Buff):
    name: str = field(default="base_crit_percent_aura", init=False)
    base_crit_percent: float = field(default=0.05, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        from fellowship_sim.base_classes import CritPercentAdditive

        return [CritPercentAdditive(value=self.base_crit_percent)]


@dataclass(kw_only=True, repr=False)
class RandomizePlayerPercentHP(Effect):
    """Randomly shift player HP from 100% to low_hp_percent.

    This enables effects which depend on player HP.
    """

    owner: Player

    name: str = field(default="randomize_player_percent_hp", init=False)

    high_hp_uptime: float = field(default=0.80, init=True)

    low_hp_percent: float = field(default=0.70, init=True)

    def __post_init__(self) -> None:
        self.schedule_set_hp(to_high=False)

    def set_hp(self, to_high: bool) -> None:
        if to_high:
            self.owner.percent_hp = 1.0
        else:
            self.owner.percent_hp = self.low_hp_percent

        self.owner._recalculate_stats()

        self.schedule_set_hp(to_high=not to_high)

    def schedule_set_hp(self, to_high: bool) -> None:
        from fellowship_sim.base_classes.state import get_state
        from fellowship_sim.base_classes.timed_events import GenericTimedEvent

        state = get_state()

        base = sum(state.rng.random() for _ in range(6))  # mean = 3
        if to_high:
            # Low-HP period duration: mean = 3 s, no scaling needed
            time_delay = base
        else:
            # High-HP period duration: mean = 3 * high_hp_uptime / (1 - high_hp_uptime)
            scale = self.high_hp_uptime / (1.0 - self.high_hp_uptime)
            time_delay = base * scale

        state.schedule(
            time_delay=time_delay,
            callback=GenericTimedEvent(
                name=f"set_hp_{'high' if to_high else 'low'}",
                callback=lambda: self.set_hp(to_high=to_high),
            ),
        )
