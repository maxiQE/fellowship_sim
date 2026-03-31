"""Simulation configuration constants."""

from fellowship_sim.elarion.buff import EventHorizonBuff, SkystriderGraceBuff
from fellowship_sim.elarion.effect import ImpendingHeartseeker, LunarlightMarkEffect

# Effect names that trigger debug-level logging when applied, refreshed, or removed.
# Add entries here to trace a specific effect's lifecycle in the logs.

IMPORTANT_EFFECTS: list[str] = [
    # Self buffs
    ImpendingHeartseeker.name,
    EventHorizonBuff.name,
    SkystriderGraceBuff.name,
    # Enemy debuffs
    LunarlightMarkEffect.name,
]
