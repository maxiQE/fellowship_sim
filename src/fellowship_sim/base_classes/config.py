"""Simulation configuration constants."""

from fellowship_sim.base_classes import Effect
from fellowship_sim.elarion.buff import EventHorizonBuff, SkystriderGraceBuff
from fellowship_sim.elarion.effect import ImpendingHeartseeker, VolleyEffect

# Effect names that trigger debug-level logging when applied, refreshed, or removed.
# Add entries here to trace a specific effect's lifecycle in the logs.

IMPORTANT_EFFECTS: list[type[Effect]] = [
    # Self buffs
    ImpendingHeartseeker,
    EventHorizonBuff,
    SkystriderGraceBuff,
    # Enemy debuffs
    # LunarlightMarkEffect,
    VolleyEffect,
]
