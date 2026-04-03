from fellowship_sim.elarion.effect import CelestialImpetusProc, CelestialImpetusAura
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.rotations.neck_barrage_priority_list_angry import NeckBarrageAngryDesyncVolley
from fellowship_sim.elarion.rotations.neck_barrage_priority_list_method import NeckBarragePriorityListMethod
from fellowship_sim.elarion.rotations.hwa_priority_list import HighwindArrowPriorityList
from fellowship_sim.elarion.rotations.neck_barrage import NeckBarragePriorityList
from fellowship_sim.simulation import RepetitionResult, Rotation, run_k
from fellowship_sim.simulation.plots import show_comparison, show_grouped_comparison
from fellowship_sim.base_classes import RawStatsFromScores
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.scenarios import TrashAOEFightScenario, BossFightScenario, Scenario


NUM_REPS = 100
SEED = 12345


DURATION = 120  # seconds
AOE_INITIAL_SPIRIT_POINTS = 100
BOSS_INITIAL_SPIRIT_POINTS = 130
DELAY_SINCE_LAST_FIGHT = 15  # seconds; forwarded to PPM last_time_since_proc


scenarios: dict[str, Scenario] = {
    # "trash8": TrashAOEFightScenario(
    #     note="",
    #     num_enemies=8,
    #     duration=60 * 2,
    #     bonus_spirit_point_per_s=0.5,
    #     delay_since_last_fight=15.0,
    #     initial_spirit_points=100,
    # ),
    "trash12": TrashAOEFightScenario(
        note="",
        num_enemies=12,
        duration=DURATION,
        bonus_spirit_point_per_s=0.5,
        delay_since_last_fight=DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=AOE_INITIAL_SPIRIT_POINTS,
    ),
    "boss_fight": BossFightScenario(
        note="full resource",
        duration=DURATION,
        bonus_spirit_point_per_s=0.5,
        delay_since_last_fight=DELAY_SINCE_LAST_FIGHT,
        initial_spirit_points=BOSS_INITIAL_SPIRIT_POINTS,
    ),
}

main_stat = 2444.0
crit_score = 484
expertise_score = 1154
haste_score = 1971
spirit_score = 901

setups = {
    # "visions__basic__execute_set": ElarionSetup(
    #     # initial_spirit_points=100,    # Ignored by scenario anyway
    #     raw_stats=RawStatsFromScores(
    #         main_stat=main_stat,
    #         crit_score=crit_score,
    #         expertise_score=expertise_score,
    #         haste_score=haste_score,
    #         spirit_score=spirit_score,
    #     ),
    #     legendary="Neck",
    #     weapon_ability="Voidbringer's Touch",
    #     master_trait="Visions Of Grandeur",
    #     heroic_traits=[
    #         "Willful Momentum",
    #         "Inspired Allegiance",
    #     ],
    #     talents=[
    #         "Piercing Seekers",
    #         "Fusillade",
    #         "Lunar Fury",
    #         "Lunarlight Affinity",
    #         "Fervent Supremacy",
    #         "Impending Heartseeker",
    #         "Last Lights",
    #     ],
    #     gem_power={
    #         "blue__saphire": 3402,
    #         "red__ruby": 1206,
    #     },
    #     sets=[
    #         "Death's Grasp",
    #     ],
    #     high_hp_uptime=0.8,
    # ),
    "visions__basic__drakheim_set": ElarionSetup(
        # initial_spirit_points=100,    # Ignored by scenario anyway
        raw_stats=RawStatsFromScores(
            main_stat=main_stat,
            crit_score=crit_score,
            expertise_score=expertise_score,
            haste_score=haste_score,
            spirit_score=spirit_score,
        ),
        legendary="Neck",
        weapon_ability="Voidbringer's Touch",
        master_trait="Visions Of Grandeur",
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
            "blue__saphire": 3402,
            "red__ruby": 1206,
        },
        sets=[
            "Drakheim's Absolution",
        ],
        high_hp_uptime=0.8,
    ),
    # "visions__angry_multiplier_stack": ElarionSetup(
    #     # initial_spirit_points=100,    # Ignored by scenario anyway
    #     raw_stats=RawStatsFromScores(
    #         main_stat=main_stat,
    #         crit_score=crit_score,
    #         expertise_score=expertise_score,
    #         haste_score=haste_score,
    #         spirit_score=spirit_score,
    #     ),
    #     legendary="Neck",
    #     weapon_ability="Voidbringer's Touch",
    #     master_trait="Visions Of Grandeur",
    #     heroic_traits=[
    #         "Willful Momentum",
    #         "Inspired Allegiance",
    #     ],
    #     talents=[
    #         "Piercing Seekers",
    #         "Fusillade",
    #         "Lunar Fury",
    #         "Lunarlight Affinity",
    #         "Fervent Supremacy",
    #         "Impending Heartseeker",
    #         "Last Lights",
    #     ],
    #     gem_power={
    #         "blue__saphire": 3402,
    #         "red__ruby": 1206,
    #     },
    #     sets=[
    #         "Drakheim's Absolution",
    #     ],
    #     high_hp_uptime=0.8,
    # ),
}

rotations: dict[str, Rotation] = {
    "maxi_smart": NeckBarragePriorityList(),
    "method_prio": NeckBarragePriorityListMethod(),
    # "angry_desync_volley": NeckBarrageAngryDesyncVolley(),
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

# # Compare between scenarios
# for scenario_group in [
#     ["trash12", boss_fight"],
# ]:
#     show_grouped_comparison(
#         all_results=all_results,
#         scenario_names=scenario_group,
#         setup_names=list(setups.keys()),
#         rotation_names=list(rotations.keys()),
#     )
