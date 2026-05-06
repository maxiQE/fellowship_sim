"""Simple Elarion simulation runthrough.

Tweak the globals below to change log verbosity and encounter size, then run:
    python scripts/simple_example__barrage.py
"""

import random

from loguru import logger

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

character_setup = ElarionSetup(
    initial_spirit_points=100,
    # 20/20/25/30
    raw_stats=RawStatsFromScores(
        main_stat=2444.0,
        crit_score=900,
        expertise_score=1100,
        haste_score=1655,
        spirit_score=855,
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

elarion.skystrider_supremacy.cast(main_target)
elarion.skystrider_grace.cast(main_target)
elarion.event_horizon.cast(main_target)

elarion.voidbringers_touch.cast(main_target)

elarion.lunarlight_mark.cast(main_target)
elarion.heartseeker_barrage.cast(main_target)

elarion.volley.cast(main_target)

elarion.highwind_arrow.cast(main_target)

assert elarion.multishot.empowered_by() == Talent.FERVENT_SUPREMACY, "Multishot is not empowered by Fervent Supremacy"
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
