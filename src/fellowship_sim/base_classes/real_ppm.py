from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .state import get_state

if TYPE_CHECKING:
    from .entity import Player


@dataclass(kw_only=True)
class RealPPM:
    """Real Procs Per Minute mechanic.

    Proc probability scales linearly with time since the last proc:
    after one full proc interval the chance reaches 100%.
    Optionally scales PPM with the character's haste and/or crit.
    """

    base_ppm: float
    is_haste_scaled: bool
    is_crit_scaled: bool
    owner: "Player"

    # NB: optional value here is very important; the first cast is always a missed proc
    last_attempt_time: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        time_since_last_fight = get_state().information.delay_since_last_fight
        current_time = get_state().time
        self.last_attempt_time = current_time - time_since_last_fight if time_since_last_fight is not None else None

    @property
    def current_ppm(self) -> float:
        ppm = self.base_ppm
        if self.is_haste_scaled:
            ppm *= 1.0 + self.owner.stats.haste_percent
        if self.is_crit_scaled:
            ppm *= 1.0 + self.owner.stats.crit_percent
        return ppm

    @property
    def current_proc_interval(self) -> float:
        """Seconds between guaranteed procs at the current PPM."""
        return 60.0 / self.current_ppm

    @property
    def interval_since_last_proc(self) -> float:
        """Seconds elapsed since the last proc, or 0 if it has never procced."""
        if self.last_attempt_time is None:
            return 0.0
        return get_state().time - self.last_attempt_time

    @property
    def proc_chance(self) -> float:
        return self.interval_since_last_proc / self.current_proc_interval

    def check(self) -> bool:
        """Roll for a proc. Updates last_attempt_time on roll."""
        prob = self.proc_chance
        has_procced = False
        if prob > 0 and get_state().rng.random() < prob:
            has_procced = True

        self.last_attempt_time = get_state().time

        return has_procced
