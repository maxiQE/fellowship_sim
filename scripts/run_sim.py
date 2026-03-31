"""Run k repetitions of a scenario with a given rotation and character stats.

Usage examples:
    python scripts/run_sim.py --scenario single --k 100 --main-stat 2444 --crit 0.15 --haste 0.30
    python scripts/run_sim.py --scenario four   --k 200 --main-stat 2444 --crit 0.15 --haste 0.30 --seed 42
    python scripts/run_sim.py --scenario twelve --k 50  --main-stat 2444 --crit 0.15
"""

import argparse

from fellowship_sim import configure_logging
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.rotations.hwa_priority_list import HighwindArrowPriorityList
from fellowship_sim.simulation import FourTargets3Min, Rotation, SingleTarget3Min, TwelveTargets3Min, run_k
from fellowship_sim.simulation.scenarios import _FixedDurationScenario

SCENARIOS: dict[str, type[_FixedDurationScenario]] = {
    "single": SingleTarget3Min,
    "four": FourTargets3Min,
    "twelve": TwelveTargets3Min,
}

ROTATIONS: dict[str, type[Rotation]] = {
    "hwa": HighwindArrowPriorityList,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Elarion simulation runner")
    p.add_argument(
        "--scenario",
        choices=list(SCENARIOS),
        default="single",
        help="Fight scenario (default: single)",
    )
    p.add_argument(
        "--rotation",
        choices=list(ROTATIONS),
        default="hwa",
        help="Rotation to evaluate (default: hwa)",
    )
    p.add_argument("--k", type=int, default=100, help="Number of repetitions (default: 100)")
    p.add_argument("--main-stat", type=float, default=2444, dest="main_stat")
    p.add_argument("--crit", type=float, default=0.2, dest="crit_percent", help="Crit chance [0–1]")
    p.add_argument("--haste", type=float, default=0.2, dest="haste_percent", help="Haste [0–1]")
    p.add_argument("--expertise", type=float, default=0.2, dest="expertise_percent")
    p.add_argument("--spirit", type=float, default=0.2, dest="spirit_percent")
    p.add_argument("--initial-focus", type=float, default=100.0, dest="initial_focus")
    p.add_argument("--seed", type=int, default=12345, help="Base RNG seed for reproducibility")
    p.add_argument("--log-level", default="WARNING", dest="log_level")
    return p


def main() -> None:
    args = build_parser().parse_args()

    configure_logging(level=args.log_level)

    raw_stats = RawStatsFromPercents(
        main_stat=args.main_stat,
        crit_percent=args.crit_percent,
        haste_percent=args.haste_percent,
        expertise_percent=args.expertise_percent,
        spirit_percent=args.spirit_percent,
    )

    scenario = SCENARIOS[args.scenario]()
    rotation = ROTATIONS[args.rotation]()

    print(f"Scenario  : {scenario.description}")
    print(f"Rotation  : {type(rotation).__name__}")
    print(f"Stats     : main={args.main_stat}, crit={args.crit_percent}, haste={args.haste_percent}")
    print(f"Focus     : {args.initial_focus}")
    print()

    result = run_k(
        k=args.k,
        scenario=scenario,
        rotation=rotation,
        raw_stats=raw_stats,
        initial_focus=args.initial_focus,
        base_seed=args.seed,
    )
    print(result)


if __name__ == "__main__":
    main()
