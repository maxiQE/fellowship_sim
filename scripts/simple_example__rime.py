"""Simple Elarion simulation runthrough.

Tweak the globals below to change log verbosity and encounter size, then run:
    python scripts/simple_example__barrage.py
"""

import random

from loguru import logger

from fellowship_sim import configure_logging
from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromScores
from fellowship_sim.rime.entity import Rime
from fellowship_sim.rime.setup import RimeSetup

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

character_setup = RimeSetup(
    initial_spirit_points=130,
    initial_winter_orbs=5,
    raw_stats=RawStatsFromScores(
        main_stat=2444.0,
        crit_score=1198,
        expertise_score=1572,
        haste_score=1239,
        spirit_score=500,
    ),
    legendary="Neck",
    weapon_ability="Chronoshift",
    master_trait="Visions Of Grandeur",
    heroic_traits=[
        "Willful Momentum",
        "Kindling",
    ],
    talents=[
        "Winter's Embrace",
        "Burstbolter",
        "Icy Flow",
        "Avalanche",
        "Greater Glacial Blast",
        "Frostweaver's Wrath",
        "Biting Cold",
        "Wisdom of the North",
    ],
    gem_power={
        # 10b, 7p, 1r
        "blue__saphire": 2664,
        "purple__amethyst": 1620,
        "red__ruby": 162,
    },
    sets=[
        "Drakheim's Absolution",
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

rime: Rime = character_setup.finalize(state)

target = enemies[0]

# ---------------------------------------------------------------------------
# Ability sequence
# ---------------------------------------------------------------------------

rime.wrath_of_winter.cast(target)

rime.chronoshift.cast(target)

print(f"{rime.chronoshift.cooldown = }\t{rime.chronoshift.charges = }\t{rime.chronoshift.can_cast() = }")

rime.wait(40)

print(f"{rime.chronoshift.cooldown = }\t{rime.chronoshift.charges = }\t{rime.chronoshift.can_cast() = }")


# ---------------------------------------------------------------------------
# Damage report
# ---------------------------------------------------------------------------

logger.success("Total damage dealt to each enemy:")
for enemy in state.enemies:
    logger.success(f"Enemy {enemy.id} - {enemy.damage_tracker.total:.0f}")

logger.success("Damage breakdown for main target")
for key, value in target.damage_tracker.by_source.items():
    logger.success(f"{key} : {value.total:.0f}")
