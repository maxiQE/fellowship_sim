from fellowship_sim.base_classes import base_config

# ---------------------------------------------------------------------------
# Rime entity
# ---------------------------------------------------------------------------
RIME_MAX_WINTER_ORBS = 5
RIME_MAX_ANIMA = 9
RIME_SPIRIT_POINT_GAIN_ON_PROC = 2
RIME_BIRDS_PER_ORB_GAINED = 3

# ---------------------------------------------------------------------------
# Rime base ability
# ---------------------------------------------------------------------------
RIME_ABILITY_DELAY_UNTIL_HIT = 0.5

# ---------------------------------------------------------------------------
# Frost Bolt
# ---------------------------------------------------------------------------
FROST_BOLT_DAMAGE_MIN = 2106
FROST_BOLT_DAMAGE_MAX = 2574
FROST_BOLT_CAST_TIME = base_config.GCD_DURATION

# ---------------------------------------------------------------------------
# Glacial Blast
# ---------------------------------------------------------------------------
GLACIAL_BLAST_ORB_COST = 2
GLACIAL_BLAST_DAMAGE_MIN = 10_693
GLACIAL_BLAST_DAMAGE_MAX = 13_069
GLACIAL_BLAST_CAST_TIME = 2.0
GLACIAL_BLAST_WRATH_OF_WINTER_CAST_TIME = 0.0
GLACIAL_BLAST_WRATH_OF_WINTER_PLAYER_DOWNTIME = base_config.GCD_DURATION
GLACIAL_BLAST_ICY_FLOW_CAST_TIME_REDUCTION = 0.5
GLACIAL_BLAST_GLACIAL_ASSAULT_CAST_TIME = 0.0
GLACIAL_BLAST_GLACIAL_ASSAULT_PLAYER_DOWNTIME = base_config.GCD_DURATION
GLACIAL_BLAST_GLACIAL_ASSAULT_ORB_COST = 0

# ---------------------------------------------------------------------------
# Ice Comet
# ---------------------------------------------------------------------------
ICE_COMET_ORB_COST = 2
ICE_COMET_DAMAGE_MIN = 4_261
ICE_COMET_DAMAGE_MAX = 5_208
ICE_COMET_NUM_SECONDARY_TARGETS = 20
ICE_COMET_NUM_TARGETS_SOFTCAP = 12
ICE_COMET_ICY_FLOW_MINIMUM_DELAY = 0.05
ICE_COMET_ICY_FLOW_DELAY_REDUCTION = 0.5

# ---------------------------------------------------------------------------
# Freezing Torrent
# ---------------------------------------------------------------------------
FREEZING_TORRENT_COOLDOWN = 15.0
FREEZING_TORRENT_CHANNEL_DURATION = 2.0
FREEZING_TORRENT_DAMAGE_MIN = 1_405
FREEZING_TORRENT_DAMAGE_MAX = 1_718
FREEZING_TORRENT_TICK_TIME = 0.4
FREEZING_TORRENT_PARTIAL_CLIP_THRESHOLD = 0.2

# ---------------------------------------------------------------------------
# Cold Snap
# ---------------------------------------------------------------------------
COLD_SNAP_DAMAGE_MIN = 3_283
COLD_SNAP_DAMAGE_MAX = 4_012
COLD_SNAP_COOLDOWN = 12.0
COLD_SNAP_MAX_CHARGES = 2

# ---------------------------------------------------------------------------
# Bursting Ice
# ---------------------------------------------------------------------------
BURSTING_ICE_COOLDOWN = 10.0
BURSTING_ICE_CAST_TIME = 2.0
BURSTING_ICE_DURATION = 3.0
BURSTING_ICE_DAMAGE_MIN = 520
BURSTING_ICE_DAMAGE_MAX = 635
BURSTING_ICE_NUM_SECONDARY_TARGETS = 18
BURSTING_ICE_NUM_TARGETS_SOFTCAP = 12
BURSTING_ICE_TICK_TIME = 0.5

# ---------------------------------------------------------------------------
# Winters Blessing (ability)
# ---------------------------------------------------------------------------
WINTERS_BLESSING_COOLDOWN = 60.0

# ---------------------------------------------------------------------------
# Ice Blitz (ability)
# ---------------------------------------------------------------------------
ICE_BLITZ_COOLDOWN = 120.0

# ---------------------------------------------------------------------------
# Flight of the Navir (ability)
# ---------------------------------------------------------------------------
FLIGHT_OF_THE_NAVIR_COOLDOWN = 60.0
FLIGHT_OF_THE_NAVIR_BIRD_DAMAGE_MIN = 612
FLIGHT_OF_THE_NAVIR_BIRD_DAMAGE_MAX = 748

# ---------------------------------------------------------------------------
# Wrath of Winter (ability)
# ---------------------------------------------------------------------------
WRATH_OF_WINTER_CAST_TIME = base_config.GCD_DURATION

# ---------------------------------------------------------------------------
# Winters Blessing buff
# ---------------------------------------------------------------------------
WINTERS_BLESSING_BUFF_DURATION = 20.0
WINTERS_BLESSING_BUFF_SPIRIT = 0.20

# ---------------------------------------------------------------------------
# Ice Blitz buff
# ---------------------------------------------------------------------------
ICE_BLITZ_BUFF_DURATION = 20.0
ICE_BLITZ_BUFF_DAMAGE_MULTIPLIER = 1.20

# ---------------------------------------------------------------------------
# Wrath of Winter effect
# ---------------------------------------------------------------------------
WRATH_OF_WINTER_EFFECT_DURATION = 20.0
WRATH_OF_WINTER_EFFECT_DAMAGE_MULTIPLIER = 1.20
WRATH_OF_WINTER_ORB_GENERATION_INTERVAL = 4.0
WRATH_OF_WINTER_ORB_GENERATION_COUNT = 1

# ---------------------------------------------------------------------------
# Flight of the Navir effect
# ---------------------------------------------------------------------------
FLIGHT_OF_THE_NAVIR_EFFECT_DURATION = 20.0
FLIGHT_OF_THE_NAVIR_N_BIRDS = 5


WINTERS_EMBRACE_DAMAGE_MULTIPLIER = 1.20

# ---------------------------------------------------------------------------
# Burstbolter talent
# ---------------------------------------------------------------------------
BURSTBOLTER_ANIMA_GAIN = 2

# ---------------------------------------------------------------------------
# Chilling Finesse talent
# ---------------------------------------------------------------------------
CHILLING_FINESSE_BURSTING_ICE_CDR = 0.3
CHILLING_FINESSE_FREEZING_TORRENT_CDR = 1.5

# ---------------------------------------------------------------------------
# Icy Flow talent
# ---------------------------------------------------------------------------
ICY_FLOW_EFFECT_DURATION = 8.0
ICY_FLOW_EFFECT_MAX_STACKS = 2
ICY_FLOW_EFFECT_CRIT_BONUS = 0.30

# ---------------------------------------------------------------------------
# Biting Cold talent
# ---------------------------------------------------------------------------
BITING_COLD_BUFF_CRIT_MULTIPLIER = 1.10

# ---------------------------------------------------------------------------
# Wisdom of the North talent
# ---------------------------------------------------------------------------
WISDOM_OF_THE_NORTH_CDR_PER_ORB = 0.3

# ---------------------------------------------------------------------------
# Avalanche talent
# ---------------------------------------------------------------------------
AVALANCHE_2_HIT_CHANCE = 0.15
AVALANCHE_3_HIT_CHANCE = 0.07

# ---------------------------------------------------------------------------
# Glacial Assault talent
# ---------------------------------------------------------------------------
GLACIAL_ASSAULT_MAX_STACKS = 4
GLACIAL_ASSAULT_DAMAGE_MULTIPLIER = 1.40
GLACIAL_ASSAULT_DAMAGE_ECHO_FRACTION = 0.1
GLACIAL_ASSAULT_NUM_SECONDARY_TARGETS = 19

# ---------------------------------------------------------------------------
# Navir's Keeper
# ---------------------------------------------------------------------------
NAVIRS_KEEPER_DURATION = 10.0
NAVIRS_KEEPER_MAX_STACKS = 2

# ---------------------------------------------------------------------------
# Frostweaver's Wrath
# ---------------------------------------------------------------------------
FROSTWEAVERS_WRATH_EFFECT_DURATION = 12.0
FROSTWEAVERS_WRATH_PROC_CHANCE = 0.17
FROSTWEAVERS_WRATH_CRIT_BONUS = 1.0

# ---------------------------------------------------------------------------
# Cascading Bliz
# ---------------------------------------------------------------------------
CASCADING_BLIZ_ICE_BLITZ_EXTENSION = 0.2

# ---------------------------------------------------------------------------
# Undulating Spirit
# ---------------------------------------------------------------------------
UNDULATING_SPIRIT_EFFECT_DURATION = 10.0
UNDULATING_SPIRIT_PROC_CHANCE = 0.10

# ---------------------------------------------------------------------------
# Soulfrost Torrent
# ---------------------------------------------------------------------------
SOULFROST_TORRENT_EFFECT_DURATION = 18.0
SOULFROST_TORRENT_AURA_PPM = 1.5
SOULFROST_TORRENT_CRIT_BONUS = 1.0
SOULFROST_TORRENT_FT_SPEED_MULTIPLIER = 1.4

# ---------------------------------------------------------------------------
# Frostwyrm's Spite
# ---------------------------------------------------------------------------
FROSTWYRMS_SPITE_EFFECT_DURATION = 15.0
FROSTWYRMS_SPITE_EFFECT_MAX_STACKS = 30
FROSTWYRMS_SPITE_NUM_SECONDARY_TARGETS = 20
FROSTWYRMS_SPITE_NUM_TARGETS_SOFTCAP = 3
FROSTWYRMS_SPITE_DAMAGE_BONUS_PER_STACK = 0.2

# ---------------------------------------------------------------------------
# Coalescing Frost
# ---------------------------------------------------------------------------
COALESCING_FROST_DURATION = 3.0
COALESCING_FROST_MAX_STACKS = 30
COALESCING_FROST_AVERAGE_DAMAGE = 520
COALESCING_FROST_NUM_SECONDARY_TARGETS = 20
COALESCING_FROST_NUM_TARGETS_SOFTCAP = 10
COALESCING_FROST_CRIT_EXTRA_STACK_CHANCE = 0.50

# ---------------------------------------------------------------------------
# Supreme Torrent talent
# ---------------------------------------------------------------------------
SUPREME_TORRENT_CHANNEL_DURATION = 2.8

# ---------------------------------------------------------------------------
# Greater Glacial Blast talent
# ---------------------------------------------------------------------------
GREATER_GLACIAL_BLAST_CAST_TIME = 2.5
GREATER_GLACIAL_BLAST_DAMAGE_BONUS = 0.4

# ---------------------------------------------------------------------------
# Legendary: Boots
# ---------------------------------------------------------------------------
LEGENDARY_BOOTS_BURSTING_ICE_DURATION_BONUS = 2.0

# ---------------------------------------------------------------------------
# Legendary: Neck
# ---------------------------------------------------------------------------
LEGENDARY_NECK_BOOSTED_SPIRIT_POINT_GAIN_ON_PROC = 3
