from fellowship_sim.base_classes import base_config

# ---------------------------------------------------------------------------
# Searing Blaze
# ---------------------------------------------------------------------------
SEARING_BLAZE_DAMAGE_MIN: float = 612
SEARING_BLAZE_DAMAGE_MAX: float = 749
SEARING_BLAZE_TICK_INTERVAL: float = 2.0
SEARING_BLAZE_DURATION: float = 24.0
SEARING_BLAZE_CINDER_TICK_INTERVAL: float = 2.0
SEARING_BLAZE_CINDER_TICK_AMOUNT: int = 1
SEARING_BLAZE_PLAYER_DOWNTIME: float = base_config.GCD_DURATION
SEARING_BLAZE_PANDEMIC_FRACTION: float = 0.30
AGONIZING_BLAZE_DAMAGE_PER_STACK: float = 0.04
AGONIZING_BLAZE_MAX_STACKS: int = 10

# ---------------------------------------------------------------------------
# Engulfing Flames
# ---------------------------------------------------------------------------
ENGULFING_FLAMES_DAMAGE_MIN: float = 1556
ENGULFING_FLAMES_DAMAGE_MAX: float = 1901
ENGULFING_FLAMES_TICK_INTERVAL: float = 1.5
ENGULFING_FLAMES_DURATION: float = 9.0
ENGULFING_FLAMES_CINDER_TICK_AMOUNT: int = 5
ENGULFING_FLAMES_COOLDOWN: float = 20.0

# ---------------------------------------------------------------------------
# Fire Ball DoT
# ---------------------------------------------------------------------------
FIREBALL_DOT_TICK_INTERVAL: float = 2.0
FIREBALL_DOT_DURATION: float = 12.0
FIREBALL_DOT_DAMAGE_FRACTION: float = 0.20
FIREBALL_DOT_CINDER_CHANCE: float = 0.5
FIREBALL_DOT_CINDER_AMOUNT: int = 2

# ---------------------------------------------------------------------------
# Fire Frogs DoT
# ---------------------------------------------------------------------------
FIREFROGS_DOT_TICK_INTERVAL: float = 3.0
FIREFROGS_DOT_DURATION: float = 12.0
FIREFROGS_DOT_DAMAGE_FRACTION: float = 1.0

# ---------------------------------------------------------------------------
# Crackling Inferno DoT
# ---------------------------------------------------------------------------
CRACKLING_INFERNO_DOT_TICK_INTERVAL: float = 3.0
CRACKLING_INFERNO_DOT_DURATION: float = 24.0
CRACKLING_INFERNO_DOT_DAMAGE_FRACTION: float = 0.60

# ---------------------------------------------------------------------------
# Incinerate DoT
# ---------------------------------------------------------------------------
INCINERATE_DOT_DAMAGE_MIN: float = 369
INCINERATE_DOT_DAMAGE_MAX: float = 451
INCINERATE_DOT_TICK_INTERVAL: float = 3.0
INCINERATE_DOT_DURATION: float = 12.0
INCINERATE_DOT_DAMAGE_BONUS_PER_STACK: float = 0.30
INCINERATE_DOT_MAX_STACKS: int = 50

# ---------------------------------------------------------------------------
# Apocalypse
# ---------------------------------------------------------------------------
APOCALYPSE_DAMAGE_MIN: float = 19_827
APOCALYPSE_DAMAGE_MAX: float = 24_233
APOCALYPSE_CAST_TIME: float = 3.0
APOCALYPSE_COOLDOWN: float = 60.0
APOCALYPSE_NUM_SECONDARY_TARGETS: int = 1000  # infinity
APOCALYPSE_TARGETS_SOFTCAP: int = 1

# ---------------------------------------------------------------------------
# Detonate
# ---------------------------------------------------------------------------
DETONATE_PLAYER_DOWNTIME: float = 1.0
DETONATE_WINDOW_SIZE: float = 2.5
DETONATE_NUM_ATTACKS: int = 3

# ---------------------------------------------------------------------------
# Fire Ball
# ---------------------------------------------------------------------------
FIREBALL_DAMAGE_MIN: float = 5_540
FIREBALL_DAMAGE_MAX: float = 6_771
FIREBALL_COOLDOWN: float = 30.0
FIREBALL_CHARGES: int = 2
FIREBALL_NUM_SECONDARY_TARGETS: int = 1000  # infinity
FIREBALL_TARGETS_SOFTCAP: int = 5

# ---------------------------------------------------------------------------
# Fire Frogs
# ---------------------------------------------------------------------------
FIREFROGS_DAMAGE_MIN: float = 658
FIREFROGS_DAMAGE_MAX: float = 804
FIREFROGS_FROG_COUNT: int = 5
FIREFROGS_FROG_LEAP_COUNT: int = 3
FIREFROGS_COOLDOWN: float = 45.0
FIREFROGS_DELAY_UNTIL_HIT: float = 0.35
FIRE_TOAD_DAMAGE_MULTIPLIER: float = 8.0
FIRE_TOAD_NUM_SECONDARY_TARGETS: int = 19
FIRE_TOAD_NUM_TARGETS_SOFTCAP: int = 1

# ---------------------------------------------------------------------------
# Incinerate
# ---------------------------------------------------------------------------
INCINERATE_DAMAGE_MIN: float = 3_033
INCINERATE_DAMAGE_MAX: float = 3_707
INCINERATE_CAST_TIME: float = 1.5
INCINERATE_CHANNEL_TIME: float = 2.5
INCINERATE_TICK_INTERVAL: float = 0.5
INCINERATE_DELAY_UNTIL_HIT: float = 0.0
INCINERATE_NUM_SECONDARY_TARGETS: int = 19
INCINERATE_TARGETS_SOFTCAP: int = 8

# ---------------------------------------------------------------------------
# Infernal Wave
# ---------------------------------------------------------------------------
INFERNAL_WAVE_DAMAGE_MIN: float = 1_323
INFERNAL_WAVE_DAMAGE_MAX: float = 1_617
INFERNAL_WAVE_CAST_TIME: float = 1.5
INFERNAL_WAVE_CINDER_GAIN: int = 40

# ---------------------------------------------------------------------------
# Pyromania
# ---------------------------------------------------------------------------
PYROMANIA_COOLDOWN: float = 90.0
PYROMANIA_NUM_SECONDARY_TARGETS: int = 2

# ---------------------------------------------------------------------------
# Wildfire
# ---------------------------------------------------------------------------
WILDFIRE_COOLDOWN: float = 45.0
WILDFIRE_DURATION: float = 9.0
WILDFIRE_DOT_TICK_ACCELERATION: float = 0.2

# ---------------------------------------------------------------------------
# Legendaries
# ---------------------------------------------------------------------------
DEVOURING_FLAME_DAMAGE_PER_EF_STACK: float = 0.08
EXPLOSIVO_FIREBALL_CDR: float = 8.0
EXPLOSIVO_MAX_DAMAGE_MULTIPLIER: float = 1.50
CLOAK_TOAD_COUNT: int = 1
CLOAK_TOAD_CONVERSION_CHANCE: float = 0.15

# ---------------------------------------------------------------------------
# Talents
# ---------------------------------------------------------------------------
SLOW_BURN_DOT_DURATION_EXTENSION: float = 0.5
BACKDRAFT_SB_DURATION_EXTENSION: float = 1.5
CRASH_AND_BURN_FIREBALL_CDR: float = 0.1
ROLLING_FLAMES_EF_CDR_PER_SB_TICK: float = 0.25
ROLLING_FLAMES_EF_CDR_PER_IW_CAST: float = 1.0
CRACKLING_INFERNO_IW_CRIT_BONUS: float = 0.20
PYROPHIBIAN_FRENZY_PROC_CHANCE: float = 0.08
SPONTANEOUS_COMBUSTION_BASE_PROC_CHANCE: float = 0.04
SPONTANEOUS_COMBUSTION_CRIT_SCALING: float = 0.2
SPONTANEOUS_COMBUSTION_CRIT_BONUS: float = 1.0
FROG_SQUAD_DAMAGE_BONUS: float = 0.10
FIRESTARTER_DOT_CRIT_BONUS: float = 0.20
FIRESTARTER_ACCUMULATOR_FIXED_CRIT_CHANCE: float = 0.15
INTENSIFYING_INFERNO_DAMAGE_PER_DOT_TYPE: float = 0.15
INCINERATE_HIT_DOT_EXTENSION: float = 1.5
FLARE_UP_ECHO_FRACTION: float = 0.50
REIGN_OF_FIRE_BASE_PPM: float = 1.5
REIGN_OF_FIRE_CRIT_BONUS: float = 1.0
GREAT_BALLS_OF_FIRE_DAMAGE_MULTIPLIER: float = 1.6
UNDYING_FLAME_EF_DURATION_EXTENSION: float = 3.0
UNDYING_FLAME_EF_CHARGES: int = 2
