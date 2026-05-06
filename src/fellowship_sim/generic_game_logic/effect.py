from dataclasses import dataclass, field

from fellowship_sim.base_classes import Buff, CritPercentAdditive, HastePercentAdditive
from fellowship_sim.base_classes.effect import Effect
from fellowship_sim.base_classes.entity import Player
from fellowship_sim.base_classes.stats import StatModifier
from fellowship_sim.base_classes.timed_events import GenericTimedEvent

from . import generic_config


@dataclass(kw_only=True, repr=False)
class UltimatumAffix(Effect):
    """Heroes' ability cooldowns are reduced by 10%."""

    owner: Player

    name: str = field(default="ultimatum_affix", init=False)
    cdr: float = field(default=generic_config.ULTIMATUM_AFFIX_CDR, init=False)

    def on_add(self) -> None:
        self.owner.cooldown_reduction *= 1 - self.cdr


@dataclass(kw_only=True, repr=False)
class CritBonus20Percent(Buff):
    """+20% critical chance. Provided by storm shield affix."""

    owner: Player

    name: str = field(default="crit_bonus_20_percent", init=False)
    crit_bonus: float = field(default=generic_config.CRIT_BONUS_20_PERCENT_VALUE, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [CritPercentAdditive(value=self.crit_bonus)]


@dataclass(kw_only=True, repr=False)
class HasteBonus20Percent(Buff):
    """+20% haste percent. Provided by Shadow Lord or Empowered affixes."""

    owner: Player

    name: str = field(default="haste_bonus_20_percent", init=False)
    haste_bonus: float = field(default=generic_config.HASTE_BONUS_20_PERCENT_VALUE, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [HastePercentAdditive(value=self.haste_bonus)]


@dataclass(kw_only=True, repr=False)
class MeteorRainAffix(Effect):
    """Increased spirit generation: +2 spirit per meteor every N seconds."""

    owner: Player

    meteor_strike_interval_min: float = field(default=generic_config.METEOR_RAIN_INTERVAL_MIN, init=False)
    meteor_strike_interval_max: float = field(default=generic_config.METEOR_RAIN_INTERVAL_MAX, init=False)
    spirit_per_meteor: float = field(default=generic_config.METEOR_RAIN_SPIRIT_PER_METEOR, init=False)
    number_of_meteor: int = field(default=generic_config.METEOR_RAIN_NUMBER_OF_METEORS, init=False)

    def on_add(self) -> None:
        self.schedule_next_meteor_fall()

    def schedule_next_meteor_fall(self) -> None:
        interval = self.meteor_strike_interval_min + self.owner.state.rng.random() * (
            self.meteor_strike_interval_max - self.meteor_strike_interval_min
        )
        self.owner.state.schedule(
            time_delay=interval,
            callback=GenericTimedEvent(name="meteor_rain", callback=self.meteor_fall),
        )

    def meteor_fall(self) -> None:
        self.owner.spirit_points += self.spirit_per_meteor * self.number_of_meteor

        self.schedule_next_meteor_fall()
