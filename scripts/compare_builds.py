from dataclasses import replace
from fellowship_sim.elarion.rotations.chrono_barrage import ChronoBarrage
from fellowship_sim.elarion.rotations.hwa import HwaSimple
from plotly.offline.offline import plot
from fellowship_sim.elarion.rotations.void_barrage import VoidBarrage
from fellowship_sim.simulation.metrics import *
from fellowship_sim.elarion.builds import (
    ElarionSetupBasic,
    BARRAGE_BUILD__NO_IHB,
    ElarionSetup10b6r6p,
    ElarionSetupAngryMultiplierStack,
    ElarionSetupAngryThreeSet,
    ElarionShimmer,
)
from fellowship_sim.elarion.setup_effect import ElarionTalentName
from fellowship_sim.elarion.effect import CelestialImpetusProc, CelestialImpetusAura
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.rotations.void_barrage_method import VoidBarrageMethod
from fellowship_sim.simulation import RepetitionResult, Rotation, run_k
from fellowship_sim.simulation.plots import show_comparison, show_grouped_comparison
from fellowship_sim.base_classes import RawStatsFromScores
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.scenarios import (
    Scenario,
    boss_fight_scenario,
    multiple_identical_packs_scenario,
    single_uniform_pack_scenario,
)

NUM_REPS = 100
SEED = 12345

TTL_JITTER = 0.10  # Randomize time to live by 10%

AOE_DURATION = 360

AOE_INITIAL_SPIRIT_POINTS = 130
AOE_DELAY_SINCE_LAST_FIGHT = 10
AOE_SPIRIT_SCORE = 30 / 4 / 120 * AOE_DURATION  # Assume we clear 20 points of kill score every 2 minutes

BOSS_DURATION = 360  # seconds
BOSS_INITIAL_SPIRIT_POINTS = 130
BOSS_DELAY_SINCE_LAST_FIGHT = 15  # seconds; forwarded to PPM last_time_since_proc to start the fight "hot"
BOSS_SPIRIT_SCORE = 14 * 4  # Sinthara

HIGH_HP_UPTIME = 0.85


scenarios: dict[str, Scenario] = {
    "trash12__single_uniform_pack": single_uniform_pack_scenario(
        note="",
        num_enemies=12,
        duration=AOE_DURATION,
        ttl_jitter=TTL_JITTER,
        delay_since_last_fight=AOE_DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=AOE_INITIAL_SPIRIT_POINTS,
        total_spirit_score=AOE_SPIRIT_SCORE,
    ),
    "trash8__single_uniform_pack": single_uniform_pack_scenario(
        note="",
        num_enemies=8,
        duration=AOE_DURATION,
        ttl_jitter=TTL_JITTER,
        delay_since_last_fight=AOE_DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=AOE_INITIAL_SPIRIT_POINTS,
        total_spirit_score=AOE_SPIRIT_SCORE,
    ),
    "trash4__single_uniform_pack": single_uniform_pack_scenario(
        note="",
        num_enemies=4,
        duration=AOE_DURATION,
        ttl_jitter=TTL_JITTER,
        delay_since_last_fight=AOE_DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=AOE_INITIAL_SPIRIT_POINTS,
        total_spirit_score=AOE_SPIRIT_SCORE,
    ),
    "boss": boss_fight_scenario(
        duration=BOSS_DURATION,
        ttl_jitter=TTL_JITTER,
        delay_since_last_fight=BOSS_DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=BOSS_INITIAL_SPIRIT_POINTS,
        spirit_score=BOSS_SPIRIT_SCORE,
    ),
}

BASIC_BARRAGE_BUILD: list[ElarionTalentName] = [
    "Piercing Seekers",
    "Fusillade",
    "Lunar Fury",
    "Lunarlight Affinity",
    "Fervent Supremacy",
    "Impending Heartseeker",
    "Last Lights",
]


SKYWARD_EXPANSE_BARRAGE: list[ElarionTalentName] = [
    "Piercing Seekers",
    "Fusillade",
    "Lunar Fury",
    "Lunarlight Affinity",
    "Fervent Supremacy",
    # "Impending Heartseeker",
    "Last Lights",
    "Skyward Munitions",  #
    "Focused Expanse",  #
]

SKYWARD_STARS_BARRAGE: list[ElarionTalentName] = [
    "Piercing Seekers",
    "Fusillade",
    "Lunar Fury",
    "Lunarlight Affinity",
    "Fervent Supremacy",
    # "Impending Heartseeker",
    "Last Lights",
    "Skyward Munitions",  #
    "Repeating Stars",  #
]

SKYWARD_SKYLIT_BARRAGE: list[ElarionTalentName] = [
    "Piercing Seekers",
    "Fusillade",
    "Lunar Fury",
    "Lunarlight Affinity",
    "Fervent Supremacy",
    # "Impending Heartseeker",
    "Last Lights",
    "Skyward Munitions",  #
    "Skylit Grace",  #
]


main_stat = 2444.0

# 20/20/25/30
crit_score = 900
expertise_score = 1100
haste_score = 1655
spirit_score = 855

STATS = RawStatsFromScores(
    main_stat=main_stat,
    crit_score=crit_score,
    expertise_score=expertise_score,
    haste_score=haste_score,
    spirit_score=spirit_score,
)

angry__drak_execute__void = ElarionSetupAngryMultiplierStack(
    raw_stats=STATS,
    high_hp_uptime=HIGH_HP_UPTIME,
    sets=[
        "Drakheim's Absolution",
        "Death's Grasp",
        # "Torment of Bael'Aurum",
    ],
)

angry__drak_execute__chrono = replace(angry__drak_execute__void, weapon_ability="Chronoshift")


setups = {
    "chrono": {
        "ihb__angry__drak_execute__splinters_seized": replace(
            angry__drak_execute__chrono,
            master_trait="Amethyst Splinters",
            heroic_traits=[
                "Willful Momentum",
                "Seized Opportunity",
            ],
        ),
        "ihb__angry__drak_execute__seized": replace(
            angry__drak_execute__chrono,
            heroic_traits=[
                "Willful Momentum",
                "Seized Opportunity",
            ],
        ),
        "ihb__angry__drak_execute__kindling": replace(
            angry__drak_execute__chrono,
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
        ),
        "sm_fe__angry__drak_execute__seized": replace(
            angry__drak_execute__chrono,
            talents=SKYWARD_EXPANSE_BARRAGE,
            heroic_traits=[
                "Willful Momentum",
                "Seized Opportunity",
            ],
        ),
        "sm_sg__angry__drak_execute__seized": replace(
            angry__drak_execute__chrono,
            talents=SKYWARD_SKYLIT_BARRAGE,
            heroic_traits=[
                "Willful Momentum",
                "Seized Opportunity",
            ],
        ),
    },
    "chrono__send_grace": {
        "sm_sg__angry__drak_execute__seized": replace(
            angry__drak_execute__chrono,
            talents=SKYWARD_SKYLIT_BARRAGE,
            heroic_traits=[
                "Willful Momentum",
                "Seized Opportunity",
            ],
        ),
    },
    "void_dont_sync_grace": {
        "ihb__angry__drak_execute__inspired": angry__drak_execute__void,
    },
    "void_fast_ult": {
        "ihb__angry__drak_execute__kindling": replace(
            angry__drak_execute__void,
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
        ),
        "ihb__BOOTS_angry__drak_execute__kindling": replace(
            angry__drak_execute__void,
            legendary="Cloak",
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
        ),
    },
    "void_sync_all": {
        "ihb__angry_drak_execute__splinters_kindling": replace(
            angry__drak_execute__void,
            master_trait="Amethyst Splinters",
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
        ),
        "ihb__BOOTS_angry_drak_execute__splinters_kindling": replace(
            angry__drak_execute__void,
            legendary="Cloak",
            master_trait="Amethyst Splinters",
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
        ),
        "ihb__no_set_10b6r6p__splinters_kindling": replace(
            angry__drak_execute__void,
            master_trait="Amethyst Splinters",
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
            num_sets=0,
            sets=[],
            gem_power={
                "blue__saphire": 2754,
                "red__ruby": 1296,
                "purple__amethyst": 1206,
            },
        ),
        "ihb__angry__drak_execute__inspired": angry__drak_execute__void,
        "ihb__angry__drak_execute__kindling": replace(
            angry__drak_execute__void,
            heroic_traits=[
                "Willful Momentum",
                "Kindling",
            ],
        ),
        "sm_sg__angry__drak_execute__inspired": replace(
            angry__drak_execute__void,
            talents=SKYWARD_SKYLIT_BARRAGE,
        ),
    },
}

DESYNC_VOLLEY = True

rotations: dict[str, Rotation] = {
    "void_sync_all": VoidBarrage(sync_grace_in_ult=True, desync_volley_on_aoe=DESYNC_VOLLEY),
    "void_dont_sync_grace": VoidBarrage(sync_grace_in_ult=False, desync_volley_on_aoe=DESYNC_VOLLEY),
    "void_fast_ult": VoidBarrage(can_send_early_ult=True, desync_volley_on_aoe=DESYNC_VOLLEY),
    "chrono": ChronoBarrage(desync_volley_on_aoe=DESYNC_VOLLEY),
    "chrono__send_grace": ChronoBarrage(send_intermediate_grace=True, desync_volley_on_aoe=DESYNC_VOLLEY),
}

# Metrics

GRACE_CASTS = ability_cast_count_metric("Skystrider Grace")

printed_metrics: list[ScalarMetric | TextMetric] = [
    TOTAL_DPS,
    MAIN_DPS,
    SECONDARY_DPS,
    ULTS_CAST,
    GRACE_CASTS,
    WEAPON_ABILITY_CASTS,
    SPIRIT_PROCS,
    SOURCES_TOTAL,
    SOURCES_MAIN,
    SOURCES_SECONDARY,
    NUMBER_OF_CASTS,
    SOURCE_DETAILS,
    BUFF_UPTIME,
]

plotted_metrics: list[ScalarMetric | TextMetric] = [
    TOTAL_DPS,
    MAIN_DPS,
    SECONDARY_DPS,
    ULTS_CAST,
    GRACE_CASTS,
    WEAPON_ABILITY_CASTS,
]

# Run each possible scenario x setup x rotation

all_results: dict[tuple[str, str, str], RepetitionResult] = {}

for scenario_name, scenario in scenarios.items():
    rotation_results = {}
    for rotation_name, rotation in rotations.items():
        for setup_name, setup in setups[rotation_name].items():
            print()
            print(f"### {scenario_name:>20} - {setup_name} - {rotation_name:<20} ###")
            print(str(setup))
            result = run_k(
                k=NUM_REPS,
                scenario=scenario,
                rotation=rotation,
                setup=setup,
                base_seed=SEED,
                metrics=printed_metrics,
            )
            print(result)
            rotation_results[(scenario_name, setup_name, rotation_name)] = result
            all_results[(scenario_name, setup_name, rotation_name)] = result

    if rotation_results:
        # Compare setup + rotation on each scenario
        show_comparison(
            all_results=rotation_results,
            scenario_names=[scenario_name],
            metrics=plotted_metrics,
        )

# # Make a plot to compare between groups of scenarios
# # Uncomment to compare damage between the two cases
# for scenario_group in [
#     ["trash12", "trash8", "boss_fight"],
# ]:
#     show_grouped_comparison(
#         all_results=all_results,
#         scenario_names=scenario_group,
#         setup_names=list(setups.keys()),
#         rotation_names=list(rotations.keys()),
#     )
