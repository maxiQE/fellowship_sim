"""Simple Ardeos simulation runthrough.

Tweak the globals below to change log verbosity and encounter size, then run:
    python scripts/simple_example__ardeos.py
"""

import random

from loguru import logger

from fellowship_sim import configure_logging
from fellowship_sim.base_classes import Enemy, Gem, HeroicTrait, Legendary, MasterTrait, State, Weapon
from fellowship_sim.base_classes.stats import RawStatsFromScores
from fellowship_sim.ardeos import Talent
from fellowship_sim.ardeos.entity import Ardeos
from fellowship_sim.ardeos.setup import ArdeosSetup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Levels
# TRACE | DEBUG : for debugging
# INFO: show damage
# SUCCESS: show important effects
# WARNING | ERROR: show problems

LOG_LEVEL = "INFO"
NUM_TARGETS = 5
SEED = 1234

character_setup = ArdeosSetup(
    raw_stats=RawStatsFromScores(
        main_stat=2444.0,
        crit_score=900,
        expertise_score=1100,
        haste_score=1655,
        spirit_score=855,
    ),
    legendary=Legendary.NECK,
    talents=[
        Talent.BACKDRAFT,
        Talent.CRASH_AND_BURN,
        Talent.SLOW_BURN,
        Talent.UNDYING_FLAME,
        Talent.GREAT_BALLS_OF_FIRE,
        Talent.AGONIZING_BLAZE,
        Talent.ROLLING_FLAMES,
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

ardeos: Ardeos = character_setup.finalize(state)

target = enemies[0]

# ---------------------------------------------------------------------------
# Ability sequence
# ---------------------------------------------------------------------------

while ardeos.embers <= 3:
    ardeos.infernal_wave.cast(target)

ardeos.apocalypse.cast(target)
ardeos.engulfing_flames.cast(target)
ardeos.searing_blaze.cast(target)
ardeos.fire_ball.cast(target)
ardeos.fire_frogs.cast(target)

while ardeos.embers >= 1:
    ardeos.detonate.cast(target)

ardeos.wait(1.0)

# ---------------------------------------------------------------------------
# Damage report
# ---------------------------------------------------------------------------

logger.success("Total damage dealt to each enemy:")
for enemy in state.enemies:
    logger.success(f"Enemy {enemy.id} - {enemy.damage_tracker.total:.0f}")

logger.success("Damage breakdown for main target")
for key, value in target.damage_tracker.by_source.items():
    logger.success(f"{key} : {value.total:.0f}")
