from fellowship_sim.simulation.metrics import DETAILED_METRICS
from fellowship_sim.elarion.builds import (
    ElarionSetupBasic,
    BARRAGE_BUILD__NO_IHB,
    ElarionSetup10b6r6p,
    ElarionSetupAngryMultiplierStack,
    ElarionSetupAngryThreeSet,
)
from fellowship_sim.elarion.setup_effect import ElarionTalentName
from fellowship_sim.elarion.effect import CelestialImpetusProc, CelestialImpetusAura
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.rotations.neck_barrage_priority_list_method import NeckBarragePriorityListMethod
from fellowship_sim.elarion.rotations.neck_barrage import NeckBarragePriorityList
from fellowship_sim.simulation import RepetitionResult, Rotation, run_k
from fellowship_sim.simulation.plots import show_comparison, show_grouped_comparison
from fellowship_sim.base_classes import RawStatsFromScores
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.scenarios import TrashAOEFightScenario, BossFightScenario, Scenario


NUM_REPS = 100
SEED = 12345


DURATION = 130  # seconds
AOE_INITIAL_SPIRIT_POINTS = 130
BOSS_INITIAL_SPIRIT_POINTS = 130
DELAY_SINCE_LAST_FIGHT = 15  # seconds; forwarded to PPM last_time_since_proc
SPIRIT_POINT_PER_S = 0.5

HIGH_HP_UPTIME = 0.7


scenarios: dict[str, Scenario] = {
    "trash12": TrashAOEFightScenario(
        note="",
        num_enemies=12,
        duration=DURATION,
        bonus_spirit_point_per_s=SPIRIT_POINT_PER_S,
        delay_since_last_fight=DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=AOE_INITIAL_SPIRIT_POINTS,
    ),
    # "trash8": TrashAOEFightScenario(
    #     note="",
    #     num_enemies=12,
    #     duration=DURATION,
    #     bonus_spirit_point_per_s=SPIRIT_POINT_PER_S,
    #     delay_since_last_fight=DELAY_SINCE_LAST_FIGHT,
    #     initial_spirit_points=AOE_INITIAL_SPIRIT_POINTS,
    # ),
    "boss_fight": BossFightScenario(
        note="full resource",
        duration=DURATION,
        bonus_spirit_point_per_s=SPIRIT_POINT_PER_S,
        delay_since_last_fight=DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=BOSS_INITIAL_SPIRIT_POINTS,
    ),
}

main_stat = 2444.0
crit_score = 484
expertise_score = 1154
haste_score = 1971
spirit_score = 901

STATS = RawStatsFromScores(
    main_stat=main_stat,
    crit_score=crit_score,
    expertise_score=expertise_score,
    haste_score=haste_score,
    spirit_score=spirit_score,
)

setups = {
    "visions__basic__drakheim_set": ElarionSetupBasic(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
    ),
    "visions__10b_6r_6p_no_set": ElarionSetup10b6r6p(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
    ),
    "visions__basic__execute_set": ElarionSetupBasic(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[  # Replace Drakheim by execute set
            "Death's Grasp",
        ],
    ),
    "visions__basic__torment": ElarionSetupBasic(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[  # Replace Drakheim by torment
            "Torment of Bael'Aurum",
        ],
    ),
    "visions__basic__haste_proc": ElarionSetupBasic(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[  # Replace Drakheim by Dark Prophecy (haste proc)
            "Dark Prophecy",
        ],
    ),
    "visions__basic__cithrel": ElarionSetupBasic(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[  # Replace Drakheim by Draconic Might (Cithrel)
            "Draconic Might",
        ],
    ),
    "visions__angry__drak_torment": ElarionSetupAngryMultiplierStack(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
    ),
    "visions__angry__drak_execute": ElarionSetupAngryMultiplierStack(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[
            "Drakheim's Absolution",
            "Death's Grasp",
        ],
    ),
    "visions__angry__cithrel_execute": ElarionSetupAngryMultiplierStack(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[
            "Draconic Might",
            "Death's Grasp",
        ],
    ),
    "visions__angry_3_set__drak_torment_execute": ElarionSetupAngryThreeSet(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[
            "Drakheim's Absolution",
            "Torment of Bael'Aurum",
            "Death's Grasp",
        ],
    ),
    "visions__angry_3_set__drak_torment_haste": ElarionSetupAngryThreeSet(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[
            "Drakheim's Absolution",
            "Torment of Bael'Aurum",
            "Dark Prophecy",
        ],
    ),
    "visions__angry_3_set__drak_torment_cithrel": ElarionSetupAngryThreeSet(
        raw_stats=STATS,
        high_hp_uptime=HIGH_HP_UPTIME,
        sets=[
            "Drakheim's Absolution",
            "Torment of Bael'Aurum",
            "Draconic Might",
        ],
    ),
}

rotations: dict[str, Rotation] = {
    "maxi_smart__basic": NeckBarragePriorityList(),
}


# For all triplets: scenario, setup, rotation, run NUM_REPS repetitions
# Then report the comparison in stdout

all_results: dict[tuple[str, str, str], RepetitionResult] = {}

for scenario_name, scenario in scenarios.items():
    for setup_name, setup in setups.items():
        for rotation_name, rotation in rotations.items():
            print()
            print(f"### {scenario_name:>20} - {setup_name} - {rotation_name:<20} ###")
            print(str(setup))
            result = run_k(
                k=NUM_REPS,
                scenario=scenario,
                rotation=rotation,
                setup=setup,
                base_seed=SEED,
                # metrics=DETAILED_METRICS,  # Uncomment this line for detailed information
            )
            print(result)
            all_results[(scenario_name, setup_name, rotation_name)] = result

# Compare setup + rotation on each scenario
show_comparison(
    all_results=all_results,
    scenario_names=list(scenarios.keys()),
    setup_names=list(setups.keys()),
    rotation_names=list(rotations.keys()),
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
