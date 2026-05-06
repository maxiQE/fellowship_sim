"""Simple Elarion simulation runthrough.

Tweak the globals below to change log verbosity and encounter size, then run:
    python -i scripts/interactive_example__barrage.py
"""

import random

from fellowship_sim import configure_logging
from fellowship_sim.base_classes import Enemy, Gem, HeroicTrait, Legendary, MasterTrait, State, Weapon
from fellowship_sim.base_classes.stats import RawStatsFromScores
from fellowship_sim.elarion import Talent
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup

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

main_stat = 2444.0
# 20/20/25/30
crit_score = 900
expertise_score = 1100
haste_score = 1655
spirit_score = 855

character_setup = ElarionSetup(
    initial_spirit_points=100,
    raw_stats=RawStatsFromScores(
        main_stat=main_stat,
        crit_score=crit_score,
        expertise_score=expertise_score,
        haste_score=haste_score,
        spirit_score=spirit_score,
    ),
    legendary=Legendary.NECK,
    weapon_ability=Weapon.VOIDBRINGERS_TOUCH,
    master_trait=MasterTrait.VISIONS_OF_GRANDEUR,
    heroic_traits=[
        HeroicTrait.WILLFUL_MOMENTUM,
        HeroicTrait.INSPIRED_ALLEGIANCE,
    ],
    talents=[
        Talent.PIERCING_SEEKERS,
        Talent.FUSILLADE,
        Talent.LUNAR_FURY,
        Talent.LUNARLIGHT_AFFINITY,
        Talent.FERVENT_SUPREMACY,
        Talent.IMPENDING_HEARTSEEKER,
        Talent.LAST_LIGHTS,
    ],
    gem_power={
        # 10b, 6r, 6p
        Gem.BLUE: 2664,
        Gem.RED: 1212,
        Gem.PURPLE: 1212,
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

# No ability sequence !
# Run this with the command below and manually select the actions
# `python -i scripts/interactive_example__barrage.py`
