from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from loguru import logger

from fellowship_sim.base_classes import SetupEffectEarly, SetupEffectLate, base_config
from fellowship_sim.base_classes.setup import SetupContext
from fellowship_sim.rime import rime_config

from .effect import (
    BitingColdBuff,
    Burstbolter,
    CascadingBliz,
    ChillingFinesse,
    CoalescingFrostAura,
    FrostweaversWrathAura,
    FrostwyrmsSpiteAura,
    GlacialAssaultAura,
    IcyFlowAura,
    RimeSpiritProcAura,
    SoulfrostTorrentAura,
    UndulatingSpiritAura,
    WisdomOfTheNorth,
)

if TYPE_CHECKING:
    from .entity import Rime


# ---------------------------------------------------------------------------
# Always-active default effects
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class RimeDefaultEffectSetup(SetupEffectEarly["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(RimeSpiritProcAura(owner=character))


# ---------------------------------------------------------------------------
# Talent setups
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class ChillingFinesseSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(ChillingFinesse(owner=character))
        logger.debug("setup: Chilling Finesse added")


@dataclass(kw_only=True)
class WintersEmbraceEffectSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.bursting_ice.has_winters_embrace = True
        logger.debug("setup: Winter's Embrace → bursting_ice flag set")


@dataclass(kw_only=True)
class GlacialAssaultSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(GlacialAssaultAura(owner=character))
        logger.debug("setup: Glacial Assault added")


@dataclass(kw_only=True)
class BurstbolterSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(Burstbolter(owner=character))
        logger.debug("setup: Burstbolter added")


@dataclass(kw_only=True)
class SupremeTorrentEffectSetup(SetupEffectLate["Rime"]):
    torrent_new_duration: float = field(default=rime_config.SUPREME_TORRENT_CHANNEL_DURATION, init=False)

    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.freezing_torrent.base_player_downtime = self.torrent_new_duration
        logger.debug(f"setup: Supreme Torrent → FT duration = {self.torrent_new_duration:.1f}s")


@dataclass(kw_only=True)
class NavirsKeeperSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.flight_of_the_navir.has_navirs_keeper = True
        logger.debug("setup: Navir's Keeper → FotN flag set")


@dataclass(kw_only=True)
class IcyFlowSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(IcyFlowAura(owner=character))
        logger.debug("setup: Icy Flow added")


@dataclass(kw_only=True)
class AvalancheSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.ice_comet.has_avalanche_talent = True
        logger.debug("setup: Avalanche → ice_comet flag set")


@dataclass(kw_only=True)
class CoalescingFrostSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(CoalescingFrostAura(owner=character))
        logger.debug("setup: Coalescing Frost added")


@dataclass(kw_only=True)
class TundraGuardSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        pass  # defensive talent, not simulated


@dataclass(kw_only=True)
class GreaterGlacialBlastEffectSetup(SetupEffectLate["Rime"]):
    gb_new_cast_time: float = field(default=rime_config.GREATER_GLACIAL_BLAST_CAST_TIME, init=False)
    gb_bonus_damage: float = field(default=rime_config.GREATER_GLACIAL_BLAST_DAMAGE_BONUS, init=False)

    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.glacial_blast.base_cast_time = self.gb_new_cast_time
        character.glacial_blast.base_player_downtime = self.gb_new_cast_time
        character.glacial_blast.main_damage_multiplier *= 1 + self.gb_bonus_damage
        logger.debug(
            f"setup: Greater Glacial Blast → cast time {self.gb_new_cast_time:.1f}s, damage ×{character.glacial_blast.main_damage_multiplier:.2f}"
        )


@dataclass(kw_only=True)
class MagicWardSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        pass  # defensive talent, not simulated


@dataclass(kw_only=True)
class CascadingBlitzSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(CascadingBliz(owner=character))
        logger.debug("setup: Cascading Blitz added")


@dataclass(kw_only=True)
class FrostweaversWrathSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(FrostweaversWrathAura(owner=character))
        logger.debug("setup: Frostweaver's Wrath added")


@dataclass(kw_only=True)
class SoulfrostTorrentSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(SoulfrostTorrentAura(owner=character))
        logger.debug("setup: Soulfrost Torrent added")


@dataclass(kw_only=True)
class BitingColdSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(BitingColdBuff(owner=character))
        logger.debug("setup: Biting Cold added")


@dataclass(kw_only=True)
class SpiritedFortitudeSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        pass  # defensive talent, not simulated


@dataclass(kw_only=True)
class WisdomOfTheNorthSetup(SetupEffectLate["Rime"]):
    def apply(self, character: "Rime", context: SetupContext) -> None:
        character.effects.add(WisdomOfTheNorth(owner=character))
        logger.debug("setup: Wisdom of the North added")


# ---------------------------------------------------------------------------
# Legendary selection
# ---------------------------------------------------------------------------

RimeLegendaryName = Literal["Neck", "Boots", "Cloak"]


@dataclass(kw_only=True)
class RimeLegendarySelection(SetupEffectLate["Rime"]):
    selected_legendary: RimeLegendaryName

    def __str__(self) -> str:
        return f"Legendary: {self.selected_legendary}"

    def apply(self, character: "Rime", context: SetupContext) -> None:
        if self.selected_legendary == "Neck":
            self._apply_neck(character)
        elif self.selected_legendary == "Boots":
            self._apply_boots(character)
        elif self.selected_legendary == "Cloak":
            self._apply_cloak(character)

    def _apply_neck(self, character: "Rime") -> None:
        character.effects.add(UndulatingSpiritAura(owner=character))
        character.spirit_point_gain_on_proc = rime_config.LEGENDARY_NECK_BOOSTED_SPIRIT_POINT_GAIN_ON_PROC
        logger.debug("legendary (Neck): Undulating Spirit Aura added")

    def _apply_boots(self, character: "Rime") -> None:
        character.bursting_ice.duration += rime_config.LEGENDARY_BOOTS_BURSTING_ICE_DURATION_BONUS
        logger.debug(f"legendary (Boots): Bursting Ice duration → {character.bursting_ice.duration:.0f}s")

    def _apply_cloak(self, character: "Rime") -> None:
        character.effects.add(FrostwyrmsSpiteAura(owner=character))
        logger.debug("legendary (Cloak): Frostwyrm's Spite Aura added")


# ---------------------------------------------------------------------------
# Talent selection
# ---------------------------------------------------------------------------

RimeTalentName = Literal[
    # cost 2
    "Chilling Finesse",
    "Winter's Embrace",
    "Glacial Assault",
    # cost 1
    "Burstbolter",
    "Supreme Torrent",
    "Navir's Keeper",
    # cost 2
    "Icy Flow",
    "Avalanche",
    "Coalescing Frost",
    # cost 1
    "Tundra Guard",
    "Greater Glacial Blast",
    "Magic Ward",
    # cost 3
    "Cascading Blitz",
    "Frostweaver's Wrath",
    "Soulfrost Torrent",
    # cost 1
    "Biting Cold",
    "Spirited Fortitude",
    "Wisdom of the North",
]

_TALENT_COSTS: dict[str, int] = {
    "Chilling Finesse": 2,
    "Winter's Embrace": 2,
    "Glacial Assault": 2,
    "Burstbolter": 1,
    "Supreme Torrent": 1,
    "Navir's Keeper": 1,
    "Icy Flow": 2,
    "Avalanche": 2,
    "Coalescing Frost": 2,
    "Tundra Guard": 1,
    "Greater Glacial Blast": 1,
    "Magic Ward": 1,
    "Cascading Blitz": 3,
    "Frostweaver's Wrath": 3,
    "Soulfrost Torrent": 3,
    "Biting Cold": 1,
    "Spirited Fortitude": 1,
    "Wisdom of the North": 1,
}

_TALENT_SETUP: dict[RimeTalentName, type[SetupEffectLate["Rime"]]] = {  # type: ignore[valid-type]
    "Chilling Finesse": ChillingFinesseSetup,
    "Winter's Embrace": WintersEmbraceEffectSetup,
    "Glacial Assault": GlacialAssaultSetup,
    "Burstbolter": BurstbolterSetup,
    "Supreme Torrent": SupremeTorrentEffectSetup,
    "Navir's Keeper": NavirsKeeperSetup,
    "Icy Flow": IcyFlowSetup,
    "Avalanche": AvalancheSetup,
    "Coalescing Frost": CoalescingFrostSetup,
    "Tundra Guard": TundraGuardSetup,
    "Greater Glacial Blast": GreaterGlacialBlastEffectSetup,
    "Magic Ward": MagicWardSetup,
    "Cascading Blitz": CascadingBlitzSetup,
    "Frostweaver's Wrath": FrostweaversWrathSetup,
    "Soulfrost Torrent": SoulfrostTorrentSetup,
    "Biting Cold": BitingColdSetup,
    "Spirited Fortitude": SpiritedFortitudeSetup,
    "Wisdom of the North": WisdomOfTheNorthSetup,
}


@dataclass(kw_only=True)
class RimeTalentSelection(SetupEffectLate["Rime"]):
    """Apply a list of talent names, validating the total point cost.

    Raises ValueError if the selected talents exceed total_talent_points.
    """

    talents: list[RimeTalentName] = field(default_factory=list)
    total_talent_points: int = base_config.MAX_TALENT_POINTS

    def __post_init__(self) -> None:
        total_cost = sum(_TALENT_COSTS[t] for t in self.talents)
        if total_cost > self.total_talent_points:
            raise ValueError(  # noqa: TRY003
                f"Talent selection costs {total_cost} points but only {self.total_talent_points} are available "
                f"(talents: {self.talents})"
            )
        logger.debug(f"setup: {total_cost}/{self.total_talent_points} talent points used")

    def __str__(self) -> str:
        return f"Talents: {', '.join(self.talents)}"

    def apply(self, character: "Rime", context: SetupContext) -> None:
        for talent in self.talents:
            _TALENT_SETUP[talent]().apply(character, context)
            logger.debug(f"setup: talent '{talent}' applied ({_TALENT_COSTS[talent]} pts)")
