from fellowship_sim.base_classes import base_config

# ---------------------------------------------------------------------------
# Elarion entity
# ---------------------------------------------------------------------------
ELARION_MAX_FOCUS = 100.0
ELARION_FOCUS_REGEN_RATE = 5.0
ELARION_SPIRIT_POINT_GAIN_ON_PROC = 1

# ---------------------------------------------------------------------------
# Focused Shot
# ---------------------------------------------------------------------------
FOCUSED_SHOT_DAMAGE_MIN = 1212
FOCUSED_SHOT_DAMAGE_MAX = 1481
FOCUSED_SHOT_CAST_TIME = base_config.GCD_DURATION
FOCUSED_SHOT_FOCUS_GAIN = 20

# ---------------------------------------------------------------------------
# Celestial Shot
# ---------------------------------------------------------------------------
CELESTIAL_SHOT_DAMAGE_MIN = 2591
CELESTIAL_SHOT_DAMAGE_MAX = 3166
CELESTIAL_SHOT_FOCUS_COST = 15

# ---------------------------------------------------------------------------
# Multishot
# ---------------------------------------------------------------------------
MULTISHOT_DAMAGE_MIN = 2173
MULTISHOT_DAMAGE_MAX = 2655
MULTISHOT_MAX_CHARGES = 5
MULTISHOT_FOCUS_COST = 20
MULTISHOT_NUM_SECONDARY_TARGETS = 11
MULTISHOT_NUM_TARGETS_SOFTCAP = 15
MULTISHOT_EMPOWERED_MIN_ARROWS = 3
MULTISHOT_EMPOWERED_FOCUS_COST_DIVISOR = 2

# ---------------------------------------------------------------------------
# Highwind Arrow
# ---------------------------------------------------------------------------
HIGHWIND_ARROW_COOLDOWN = 15.0
HIGHWIND_ARROW_CAST_TIME = 2.0
HIGHWIND_ARROW_DAMAGE_MIN = 8370
HIGHWIND_ARROW_DAMAGE_MAX = 10230
HIGHWIND_ARROW_MAX_CHARGES = 3
HIGHWIND_ARROW_FOCUS_COST = 30
HIGHWIND_ARROW_NUM_SECONDARY_TARGETS = 2
HIGHWIND_ARROW_SECONDARY_DAMAGE_MULTIPLIER = 0.7
HIGHWIND_ARROW_FC_DAMAGE_MULTIPLIER = 2.0
HIGHWIND_ARROW_FC_NUM_SECONDARY_TARGETS = 7
HIGHWIND_ARROW_RW_PLAYER_DOWNTIME = 1.5
HIGHWIND_ARROW_RW_DAMAGE_MULTIPLIER = 1.5
HIGHWIND_ARROW_MULTISHOT_CHARGE_MIN_ENEMIES = 3

# ---------------------------------------------------------------------------
# Volley
# ---------------------------------------------------------------------------
VOLLEY_COOLDOWN = 30.0
VOLLEY_DAMAGE_MIN = 977
VOLLEY_DAMAGE_MAX = 1195
VOLLEY_FOCUS_COST = 30
VOLLEY_NUM_SECONDARY_TARGETS = 11
VOLLEY_NUM_TARGETS_SOFTCAP = 15
VOLLEY_DURATION = 8.0 + 1e-9  # epsilon ensures tick breakpoints are hit exactly
VOLLEY_TICK_TIME = 1.0

# ---------------------------------------------------------------------------
# Heartseeker Barrage
# ---------------------------------------------------------------------------
HEARTSEEKER_BARRAGE_COOLDOWN = 20.0
HEARTSEEKER_BARRAGE_CHANNEL_DURATION = 2.0
HEARTSEEKER_BARRAGE_DAMAGE_MIN = 1124
HEARTSEEKER_BARRAGE_DAMAGE_MAX = 1373
HEARTSEEKER_BARRAGE_TICK_TIME = 0.2
HEARTSEEKER_BARRAGE_DELAY_UNTIL_HIT = 0.01
HEARTSEEKER_BARRAGE_FOCUS_COST = 30
HEARTSEEKER_BARRAGE_IMPENDING_STEP = 0.1

# ---------------------------------------------------------------------------
# Lunarlight Mark (ability)
# ---------------------------------------------------------------------------
LUNARLIGHT_MARK_COOLDOWN = 30.0
LUNARLIGHT_MARK_NUM_SECONDARY_TARGETS = 11
LUNARLIGHT_MARK_STACKS = 3

# ---------------------------------------------------------------------------
# Lunarlight Salvo / Explosion (shared damage values)
# ---------------------------------------------------------------------------
LUNARLIGHT_SALVO_DAMAGE_MIN = 2033
LUNARLIGHT_SALVO_DAMAGE_MAX = 2485
LUNARLIGHT_EXPLOSION_NUM_SECONDARY_TARGETS = 11

# ---------------------------------------------------------------------------
# Skystrider Grace (ability)
# ---------------------------------------------------------------------------
SKYSTRIDER_GRACE_COOLDOWN = 120.0

# ---------------------------------------------------------------------------
# Event Horizon (ability)
# ---------------------------------------------------------------------------
EVENT_HORIZON_CAST_TIME = 0.7
EVENT_HORIZON_FOCUS_COST_MULTIPLIER = 0.5

# ---------------------------------------------------------------------------
# Skystrider Supremacy (ability)
# ---------------------------------------------------------------------------
SKYSTRIDER_SUPREMACY_COOLDOWN = 40.0

# ---------------------------------------------------------------------------
# Skystrider Grace buff
# ---------------------------------------------------------------------------
SKYSTRIDER_GRACE_BUFF_DURATION = 20.0
SKYSTRIDER_GRACE_BUFF_HASTE = 0.30

# ---------------------------------------------------------------------------
# Event Horizon buff
# ---------------------------------------------------------------------------
EVENT_HORIZON_BUFF_DURATION = 20.0
EVENT_HORIZON_BUFF_DAMAGE_MULTIPLIER = 1.20
EVENT_HORIZON_HWA_CDR_ON_BARRAGE = 0.5
EVENT_HORIZON_BARRAGE_CDR_ON_VOLLEY = 1.0

# ---------------------------------------------------------------------------
# Skystrider Supremacy buff
# ---------------------------------------------------------------------------
SKYSTRIDER_SUPREMACY_BUFF_DURATION = 4.0

# ---------------------------------------------------------------------------
# Fervent Supremacy buff
# ---------------------------------------------------------------------------
FERVENT_SUPREMACY_COOLDOWN_REDUCTION = 15.0
FERVENT_SUPREMACY_BUFF_DURATION = 15.0
FERVENT_SUPREMACY_BUFF_STACKS = 4
FERVENT_SUPREMACY_BUFF_BONUS_DAMAGE = 0.25

# ---------------------------------------------------------------------------
# Empowered Multishot Charge buff
# ---------------------------------------------------------------------------
EMPOWERED_MULTISHOT_CHARGE_BUFF_DURATION = 15.0
EMPOWERED_MULTISHOT_CHARGE_BUFF_STACKS = 1
EMPOWERED_MULTISHOT_CHARGE_BUFF_MAX_STACKS = 2

# ---------------------------------------------------------------------------
# Celestial Impetus
# ---------------------------------------------------------------------------
CELESTIAL_IMPETUS_PROC_DURATION = 15.0
CELESTIAL_IMPETUS_PROC_MAX_STACKS = 2
CELESTIAL_IMPETUS_AURA_MAIN_TARGET_MARK_COUNT = 3
CELESTIAL_IMPETUS_AURA_PPM = 2.0

# ---------------------------------------------------------------------------
# Lunarlight Mark effect
# ---------------------------------------------------------------------------
LUNARLIGHT_MARK_EFFECT_DURATION = 15.0
LUNARLIGHT_MARK_EFFECT_MAX_STACKS = 20
LUNARLIGHT_MARK_EFFECT_EXPLOSION_CHANCE = 0.20
LUNARLIGHT_MARK_CRIT_PROC_CHANCE = 0.5
LUNARLIGHT_MARK_NORMAL_PROC_CHANCE = 0.25
LUNARLIGHT_MARK_TALENTED_PROC_CHANCE_MULTIPLIER = 2  # Talented volley and barrage proc chance multiplier

# ---------------------------------------------------------------------------
# Spirit Effect
# ---------------------------------------------------------------------------
SPIRIT_EFFECT_MAIN_TARGET_MARK_COUNT = 5
SPIRIT_EFFECT_SECONDARY_TARGET_MARK_COUNT = 2
SPIRIT_EFFECT_NUM_SECONDARY_TARGETS = 2

# ---------------------------------------------------------------------------
# Final Crescendo
# ---------------------------------------------------------------------------
FINAL_CRESCENDO_MAX_STACKS = 3

# ---------------------------------------------------------------------------
# Resurgent Winds
# ---------------------------------------------------------------------------
RESURGENT_WINDS_DURATION = 15.0
RESURGENT_WINDS_MAX_STACKS = 2

# ---------------------------------------------------------------------------
# Impending Heartseeker
# ---------------------------------------------------------------------------
IMPENDING_HEARTSEEKER_DURATION = 15.0

# ---------------------------------------------------------------------------
# Skylit Grace talent
# ---------------------------------------------------------------------------
SKYLIT_GRACE_CDR_MODIFIER = 1.0

# ---------------------------------------------------------------------------
# Fusillade
# ---------------------------------------------------------------------------
FUSILLADE_CRIT_BONUS = 0.20
FUSILLADE_BARRAGE_CHANNEL_DURATION = 2.5

# ---------------------------------------------------------------------------
# Focused Expanse
# ---------------------------------------------------------------------------
FOCUSED_EXPANSE_PROC_CHANCE = 0.20
FOCUSED_EXPANSE_MS_BONUS_DAMAGE = 0.25

# ---------------------------------------------------------------------------
# Last Lights
# ---------------------------------------------------------------------------
LAST_LIGHTS_HP_THRESHOLD = base_config.LOW_HEALTH_THRESHOLD
LAST_LIGHTS_CRIT_BONUS = 0.30

# ---------------------------------------------------------------------------
# Shimmer
# ---------------------------------------------------------------------------
SHIMMER_DURATION = 9.0
SHIMMER_MAX_STACKS = 2
SHIMMER_DAMAGE_PER_STACK = 0.10

# ---------------------------------------------------------------------------
# Lethal Shots
# ---------------------------------------------------------------------------
LETHAL_SHOTS_PROC_CHANCE = 0.40
LETHAL_SHOTS_CRIT_BONUS = 1.0

# ---------------------------------------------------------------------------
# Lunar Fury
# ---------------------------------------------------------------------------
LUNAR_FURY_DAMAGE_BONUS = 0.30

# ---------------------------------------------------------------------------
# Lunarlight Affinity
# ---------------------------------------------------------------------------
LUNARLIGHT_AFFINITY_CRIT_BONUS = 0.40

# ---------------------------------------------------------------------------
# Skyward Munitions
# ---------------------------------------------------------------------------
SKYWARD_MUNITIONS_CDR = 1.0

# ---------------------------------------------------------------------------
# Repeating Stars
# ---------------------------------------------------------------------------
REPEATING_STARS_VOLLEY_CDR = 0.3

# ---------------------------------------------------------------------------
# Piercing Seekers talent
# ---------------------------------------------------------------------------
PIERCING_SEEKERS_NUM_SECONDARY_TARGETS = 1
PIERCING_SEEKERS_SECONDARY_DAMAGE_MULTIPLIER = 0.7

# ---------------------------------------------------------------------------
# Legendary: Neck; Starstriker's Ascent
# ---------------------------------------------------------------------------
STARSTRIKERS_ASCENT_PROC_CHANCE = 0.50
STARSTRIKERS_ASCENT_IHB_GRANT_DELAY = 0.1

# ---------------------------------------------------------------------------
# Legendary: Boots
# ---------------------------------------------------------------------------
LEGENDARY_BOOTS_VOLLEY_DURATION_BONUS = 2.0
LEGENDARY_BOOTS_MULTISHOT_EXTENDS_DURATION = 0.5
