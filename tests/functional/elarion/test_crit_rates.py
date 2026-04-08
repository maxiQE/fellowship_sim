"""Functional tests for per-ability crit rates.

Marked slow — each test runs hundreds of simulated fights.
Run selectively with: pytest -m slow

Methodology
-----------
Crit rolls are pooled across all repetitions to reduce variance before comparing
observed rates against theoretical values derived from elarion.stats.crit_percent.

Bonus-crit effects present in the BASIC_BARRAGE_BUILD (minus Last Lights):

  HeartseekerBarrage       : +0.20  (Fusillade talent)
  LunarlightSalvo          : +0.40  (Lunarlight Affinity talent)
  LunarlightExplosion      : +0.40  (Lunarlight Affinity talent)
  VoidbringersTouchEffect  : +1.00  (always crits — debuff explosion mechanic)

All other sources use the unmodified base crit rate from stats.
Last Lights (+0.30 when target HP < 30%) is deliberately excluded from the talent
build so plain-ability assertions do not need to account for HP-conditional crit.
"""

from collections import defaultdict
from typing import cast

import pytest

from fellowship_sim.base_classes import RawStatsFromPercents
from fellowship_sim.elarion.rotations.neck_barrage import NeckBarragePriorityList
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.metrics import DamageSourceProbe
from fellowship_sim.simulation.runner import run_once
from fellowship_sim.simulation.scenarios import BossFightScenario, Scenario, TrashAOEFightScenario

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NUM_REPS = 1000
_SEED = 42
_N_SIGMA = 3

_DURATION = 130  # seconds
_DELAY = 15  # seconds since last fight

_STATS = RawStatsFromPercents(
    main_stat=1000,
    crit_percent=0.15,  # -> 20% crit rate when accounting for base
)


_SETUP = ElarionSetup(
    raw_stats=_STATS,
    talents=[
        "Piercing Seekers",
        "Fusillade",
        "Lunar Fury",
        "Lunarlight Affinity",
        "Fervent Supremacy",
        "Impending Heartseeker",
        # "Last Lights",
    ],
    weapon_ability="Voidbringer's Touch",
)

_ROTATION = NeckBarragePriorityList()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def st_scenario() -> BossFightScenario:
    return BossFightScenario(
        duration=_DURATION,
        bonus_spirit_point_per_s=0.5,
        delay_since_last_fight=_DELAY,
        initial_spirit_points=130,
    )


@pytest.fixture
def aoe_scenario() -> TrashAOEFightScenario:
    return TrashAOEFightScenario(
        num_enemies=12,
        duration=_DURATION,
        bonus_spirit_point_per_s=0.5,
        delay_since_last_fight=_DELAY,
        initial_spirit_points=130,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_pooled_crit_rates(scenario: Scenario) -> dict[str, tuple[float, float]]:
    """Return pooled (rate, standard_error) per damage-source class name.

    Crits and counts are summed across all _NUM_REPS runs so that low-frequency
    abilities still accumulate enough samples for a meaningful comparison.

    Standard error is approximated as p * (1 - p) / sqrt(n), where p is the pooled
    crit rate and n is the total hit count.
    """
    total_count: defaultdict[str, int] = defaultdict(int)
    total_crits: defaultdict[str, int] = defaultdict(int)

    for i in range(_NUM_REPS):
        probes = run_once(
            scenario=scenario,
            rotation=_ROTATION,
            setup=_SETUP,
            seed=_SEED + i,
            probe_types={DamageSourceProbe},
        )
        probe = cast(DamageSourceProbe, probes[DamageSourceProbe])
        for source, count in probe.count_by_source.items():
            total_count[source] += count
            # crit_rate_by_source[source] == crits / count — reconstruct exact int
            total_crits[source] += round(probe.crit_rate_by_source[source] * count)

    result: dict[str, tuple[float, float]] = {}
    for source in total_count:
        n = total_count[source]
        p = total_crits[source] / n
        se = (p * (1 - p) / n) ** 0.5
        result[source] = (p, se)
    return result


def _base_crit(scenario: Scenario) -> float:
    """Return the base crit_percent from a freshly initialised Elarion."""
    _, elarion = scenario.generate_new_scenario(setup=_SETUP, rng_seed=0)
    return elarion.stats.crit_percent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _assert_crit_rate(
    observed: dict[str, tuple[float, float]],
    source: str,
    expected: float,
    label: str,
) -> None:
    """Assert the observed crit rate for *source* is within _N_SIGMA of *expected*.

    Two checks are performed:
    - The 3-sigma interval is narrower than 5% (enough samples were collected).
    - The observed rate is within 3 sigma of the expected value.
    """
    if source not in observed:
        return
    p, se = observed[source]
    interval = _N_SIGMA * se
    assert interval < 0.05, f"{label} {source}: 3σ interval {interval:.3%} ≥ 5% — not enough samples (n too low)"
    assert abs(p - expected) < interval, (
        f"{label} {source}: observed {p:.3%}, expected ~{expected:.3%} (±{interval:.3%})"
    )


@pytest.mark.slow
class TestCritRatesBarrageBuild:
    def test_crit_rates_single_target(self, st_scenario: BossFightScenario) -> None:
        """Observed crit rates per ability should match the values predicted by stats."""
        base_crit = _base_crit(scenario=st_scenario)
        observed = _collect_pooled_crit_rates(scenario=st_scenario)

        # Plain abilities — no bonus crit in this talent build
        for source in ["FocusedShot", "HighwindArrow", "Multishot", "CelestialShot", "VolleyTick"]:
            _assert_crit_rate(observed=observed, source=source, expected=base_crit, label="ST")

        # HeartseekerBarrage: +0.20 from Fusillade
        _assert_crit_rate(
            observed=observed,
            source="HeartseekerBarrage",
            expected=min(1.0, base_crit + 0.20),
            label="ST",
        )

        # LunarlightSalvo and LunarlightExplosion: +0.40 from Lunarlight Affinity
        for source in ["LunarlightSalvo", "LunarlightExplosion"]:
            _assert_crit_rate(
                observed=observed,
                source=source,
                expected=min(1.0, base_crit + 0.40),
                label="ST",
            )

        # VoidbringersTouchEffect explosion always crits (se == 0, skip interval check)
        if "VoidbringersTouchEffect" in observed:
            p, _ = observed["VoidbringersTouchEffect"]
            assert p == pytest.approx(1.0), f"ST VoidbringersTouchEffect: observed {p:.3%}, expected 100%"

    def test_crit_rates_aoe(self, aoe_scenario: TrashAOEFightScenario) -> None:
        """Same assertions as the ST test but in a multi-target scenario.

        DamageSourceProbe aggregates hits across all enemies, so crit rates
        are weighted by the actual hit distribution.
        """
        base_crit = _base_crit(scenario=aoe_scenario)
        observed = _collect_pooled_crit_rates(scenario=aoe_scenario)

        for source in ["FocusedShot", "HighwindArrow", "Multishot", "CelestialShot", "VolleyTick"]:
            _assert_crit_rate(observed=observed, source=source, expected=base_crit, label="AOE")

        _assert_crit_rate(
            observed=observed,
            source="HeartseekerBarrage",
            expected=min(1.0, base_crit + 0.20),
            label="AOE",
        )

        for source in ["LunarlightSalvo", "LunarlightExplosion"]:
            _assert_crit_rate(
                observed=observed,
                source=source,
                expected=min(1.0, base_crit + 0.40),
                label="AOE",
            )

        if "VoidbringersTouchEffect" in observed:
            p, _ = observed["VoidbringersTouchEffect"]
            assert p == pytest.approx(1.0), f"AOE VoidbringersTouchEffect: observed {p:.3%}, expected 100%"
