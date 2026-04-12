import contextlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import cast

import pytest

from fellowship_sim.base_classes import AbilityDamage, Enemy, RawStatsFromPercents, State, StateInformation
from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.base_classes.state import get_state
from fellowship_sim.elarion.ability import ElarionAbility
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.rotations.neck_barrage_priority_list_method import NeckBarragePriorityListMethod
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.simulation.metrics import DamageSourceProbe
from fellowship_sim.simulation.runner import run_once
from fellowship_sim.simulation.scenarios import BossFightScenario, Scenario, TrashAOEFightScenario
from tests.conftest import FixedRNG

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


_SETUP_NO_LL = ElarionSetup(
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


_SETUP_WITH_LL = ElarionSetup(
    raw_stats=_STATS,
    talents=[
        "Piercing Seekers",
        "Fusillade",
        "Lunar Fury",
        "Lunarlight Affinity",
        "Fervent Supremacy",
        "Impending Heartseeker",
        "Last Lights",
    ],
    weapon_ability="Voidbringer's Touch",
)

_ROTATION = NeckBarragePriorityListMethod()


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
        pack_duration=_DURATION,
        bonus_spirit_point_per_s=0.5,
        delay_since_last_fight=_DELAY,
        initial_spirit_points=130,
    )


@dataclass(kw_only=True)
class OnlyExecuteScenario(Scenario):
    note: str = field(default="", init=False)
    duration: float = field(default=120, init=False)
    num_enemies: int = field(default=1, init=False)
    bonus_spirit_point_per_s: float = field(default=0.5, init=False)
    delay_since_last_fight: float = field(default=0.5, init=False)
    initial_spirit_points: float = field(default=130, init=False)

    is_ult_authorized: bool = field(default=True, init=True, repr=False)

    _description: str = field(default="ST, only execute phase", init=False, repr=False)
    is_boss_fight: bool = field(default=False, init=False, repr=False)

    def generate_new_scenario(self, setup: ElarionSetup, rng_seed: float | None) -> tuple[State, Elarion]:
        """Overwritten to set time_to_live to infinity and enemy.percent_hp to 0.2"""
        with contextlib.suppress(RuntimeError):
            get_state().deactivate()

        state = State(
            rng=random.Random(x=rng_seed),
            information=StateInformation(
                is_boss_fight=self.is_boss_fight,
                duration=self.duration,
                delay_since_last_fight=self.delay_since_last_fight,
                is_ult_authorized=self.is_ult_authorized,
            ),
        )
        enemies = [Enemy(state=state, time_to_live=float("inf")) for _ in range(self.num_enemies)]
        for enemy in enemies:
            enemy.percent_hp = 0.2

        elarion = setup.finalize(state)

        # Avoid having spirit go over max
        elarion.spirit_points = 0
        elarion._change_spirit_points(self.initial_spirit_points)

        elarion.spirit_point_per_s = self.bonus_spirit_point_per_s

        if self.finalize_character is not None:
            self.finalize_character(elarion)

        return state, elarion


@pytest.fixture
def execute_scenario() -> OnlyExecuteScenario:
    return OnlyExecuteScenario()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_pooled_crit_rates(scenario: Scenario, setup: ElarionSetup) -> dict[str, tuple[float, float]]:
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
            setup=setup,
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


def _base_crit(scenario: Scenario, setup: ElarionSetup) -> float:
    """Return the base crit_percent from a freshly initialised Elarion."""
    _, elarion = scenario.generate_new_scenario(setup=setup, rng_seed=0)
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


class TestCritRatesBarrageBuild:
    @pytest.mark.slow
    def test_crit_rates_single_target(self, st_scenario: Scenario) -> None:
        """Observed crit rates per ability should match the values predicted by stats."""
        base_crit = _base_crit(scenario=st_scenario, setup=_SETUP_NO_LL)
        observed = _collect_pooled_crit_rates(scenario=st_scenario, setup=_SETUP_NO_LL)

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

    @pytest.mark.slow
    def test_crit_rates_aoe(self, aoe_scenario: Scenario) -> None:
        """Same assertions as the ST test but in a multi-target scenario.

        DamageSourceProbe aggregates hits across all enemies, so crit rates
        are weighted by the actual hit distribution.
        """
        base_crit = _base_crit(scenario=aoe_scenario, setup=_SETUP_NO_LL)
        observed = _collect_pooled_crit_rates(scenario=aoe_scenario, setup=_SETUP_NO_LL)

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

    @pytest.mark.slow
    def test_crit_rates_single_target_with_last_lights(self, execute_scenario: Scenario) -> None:
        """Observed crit rates per ability should match the values predicted by stats."""
        base_crit = _base_crit(scenario=execute_scenario, setup=_SETUP_WITH_LL)
        # Last lights: +30% crit chance
        base_crit += 0.30

        observed = _collect_pooled_crit_rates(scenario=execute_scenario, setup=_SETUP_WITH_LL)

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

    def _cast_and_check(
        self,
        *,
        ability: ElarionAbility,
        target: Entity,
        elarion: Elarion,
        damage_list: list[AbilityDamage],
        rng: FixedRNG,
        expected_crit_chance: float,
        bonus_crit: float,
        bonus_damage: float,
        secondary_damage_list: list[AbilityDamage] | None = None,
        secondary_crit_threshold: float | None = None,
    ) -> None:
        """Cast ability twice (once above, once below the crit threshold) and assert damage.

        main_stat=1000 in all callers, so damage = bonus_damage * ability.average_damage (scale=1.0).
        If secondary_damage_list and secondary_crit_threshold are provided, the secondary hit on the
        fixed-health enemy is also asserted (used for multishot).
        """
        _epsilon = 0.01

        def _check_secondary() -> None:
            if secondary_damage_list is None or secondary_crit_threshold is None:
                return
            secondary_is_crit = rng.value < secondary_crit_threshold
            assert secondary_damage_list[-1].is_crit == secondary_is_crit
            assert secondary_damage_list[-1].damage == pytest.approx(
                (2 * 1.03 if secondary_is_crit else 1.0) * ability.average_damage
            )

        # Roll just above threshold → no crit
        rng.value = expected_crit_chance + bonus_crit + _epsilon
        elarion._change_focus(+100)
        ability._add_charge()
        ability.cast(target)
        elarion.wait(0.01)
        assert not damage_list[-1].is_crit
        assert damage_list[-1].damage == pytest.approx(bonus_damage * ability.average_damage)
        _check_secondary()

        # Roll just below threshold → crit
        rng.value = expected_crit_chance + bonus_crit - _epsilon
        elarion._change_focus(+100)
        ability._add_charge()
        ability.cast(target)
        assert damage_list[-1].is_crit
        assert damage_list[-1].damage == pytest.approx(bonus_damage * 2 * 1.03 * ability.average_damage)
        _check_secondary()

    @pytest.mark.parametrize("crit_percent", [0.05, 0.15, 0.30])
    def test_crit_rates__execute_damage__manual(self, crit_percent: float) -> None:
        """A lower-level functional test for crit rates.

        - Setup a single-target scenario with an enemy with constant HP.
        - Set enemy hp to high.
        - Test the crit-rate by fixing the rng for various abilities.
        - Set enemy hp to mid.
        - Test the crit-rate again.
        - Set enemy hp to low.
        - Test the crit rate again.
        """
        rng = FixedRNG(value=1.0)
        state = State(rng=rng)
        enemy_scaling_health = Enemy(state=state, time_to_live=100)
        enemy_fixed_health = Enemy(state=state, time_to_live=float("inf"))
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=crit_percent,
            ),
            talents=[
                # "Piercing Seekers",
                "Fusillade",
                "Lunar Fury",
                "Lunarlight Affinity",
                "Fervent Supremacy",
                "Impending Heartseeker",
                "Last Lights",
            ],
            sets=["Death's Grasp"],
            gem_power={
                "purple__amethyst": 1458,  # purple 6
            },
        )
        elarion = setup.finalize(state)

        target_damage_list: list[AbilityDamage] = []
        fixed_health_damage_list: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: target_damage_list.append(e) if e.target is target else fixed_health_damage_list.append(e),
        )

        base_crit = elarion.stats.crit_percent
        # SealedFate L2 always active on enemy_fixed_health: its HP never drops below 50%
        fixed_crit_threshold = base_crit + 0.15

        expected_crit_chance_list: list[tuple[ElarionAbility, float]] = [
            (elarion.celestial_shot, base_crit),
            (elarion.multishot, base_crit),
            (elarion.heartseeker_barrage, base_crit + 0.2),
        ]

        # high HP — SealedFate L2 active on target (+0.15 crit)
        assert target.percent_hp > 0.5
        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=target_damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=0.15,
                bonus_damage=1.0,
                secondary_damage_list=fixed_health_damage_list if ability is elarion.multishot else None,
                secondary_crit_threshold=fixed_crit_threshold if ability is elarion.multishot else None,
            )
        assert target.percent_hp > 0.5

        # middle HP — SealedFate deactivates (HP ≤ 0.5)
        elarion.wait(55 - state.time)
        assert 0.3 < target.percent_hp < 0.5
        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=target_damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=0.0,
                bonus_damage=1.0,
                secondary_damage_list=fixed_health_damage_list if ability is elarion.multishot else None,
                secondary_crit_threshold=fixed_crit_threshold if ability is elarion.multishot else None,
            )
        assert 0.3 < target.percent_hp < 0.5

        # low HP — Death's Grasp +1.15× damage, Last Lights +0.30 crit
        elarion.wait(80 - state.time)
        assert target.percent_hp < 0.3
        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=target_damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=0.3,
                bonus_damage=1.15,
                secondary_damage_list=fixed_health_damage_list if ability is elarion.multishot else None,
                secondary_crit_threshold=fixed_crit_threshold if ability is elarion.multishot else None,
            )
        assert target.percent_hp < 0.3
