"""Simple Elarion simulation runthrough.

Tweak the globals below to change log verbosity and encounter size, then run:
    python scripts/simple_example__barrage.py
"""

import random

from loguru import logger

from fellowship_sim import configure_logging
from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromScores
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Levels
# TRACE | DEBUG : for debugging
# INFO: show damage
# SUCCESS: show important effects
# WARNING | ERROR: show problems

LOG_LEVEL = "INFO"
NUM_TARGETS = 5
SEED = 1234

character_setup = ElarionSetup(
    initial_spirit_points=100,
    raw_stats=RawStatsFromScores(
        main_stat=2444.0,
        crit_score=1125,
        expertise_score=1125,
        haste_score=1125,
        spirit_score=1125,
    ),
    legendary="Neck",
    weapon_ability="Voidbringer's Touch",
    master_trait="Amethyst Splinters",
    heroic_traits=[
        "Willful Momentum",
        "Inspired Allegiance",
    ],
    talents=[
        "Piercing Seekers",
        "Fusillade",
        "Lunar Fury",
        "Lunarlight Affinity",
        "Fervent Supremacy",
        "Impending Heartseeker",
        "Last Lights",
    ],
    gem_power={
        # 10b, 6r, 6p
        "blue__saphire": 2664,
        "red__ruby": 1212,
        "purple__amethyst": 1212,
    },
    sets=[
        # "Drakheim's Absolution",
    ],
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

if NUM_TARGETS <= 0:
    raise ValueError(f"Configuration error: the number of targets is negative {NUM_TARGETS}")

configure_logging(LOG_LEVEL)
state = State(rng=random.Random(x=SEED))
enemies: list[Enemy] = [Enemy(state=state) for _ in range(NUM_TARGETS)]

elarion: Elarion = character_setup.finalize(state)

main_target = enemies[0]

# ---------------------------------------------------------------------------
# Ability sequence
# ---------------------------------------------------------------------------

elarion.skystrider_supremacy.cast(main_target)
elarion.skystrider_grace.cast(main_target)
elarion.event_horizon.cast(main_target)

elarion.voidbringers_touch.cast(main_target)

elarion.lunarlight_mark.cast(main_target)
elarion.heartseeker_barrage.cast(main_target)

elarion.volley.cast(main_target)

elarion.highwind_arrow.cast(main_target)

assert elarion.multishot.empowered_by() == "Fervent Supremacy", "Multishot is not empowered by Fervent Supremacy"
elarion.multishot.cast(main_target)
elarion.multishot.cast(main_target)
elarion.multishot.cast(main_target)
elarion.multishot.cast(main_target)

# ---------------------------------------------------------------------------
# Damage report
# ---------------------------------------------------------------------------

logger.success("Total damage dealt to each enemy:")
for enemy in state.enemies:
    logger.success(f"Enemy {enemy.id} - {enemy.damage_tracker.total:.0f}")

logger.success("Damage breakdown for main target")
for key, value in main_target.damage_tracker.by_source.items():
    logger.success(f"{key} : {value.total:.0f}")
