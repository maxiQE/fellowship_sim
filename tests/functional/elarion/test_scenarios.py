import pytest

from fellowship_sim.base_classes import AbilityDamage, Gem, RawStatsFromPercents
from fellowship_sim.base_classes.entity import Entity
from fellowship_sim.base_classes.events import UnitDestroyed
from fellowship_sim.elarion import Talent
from fellowship_sim.elarion.ability import ElarionAbility
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.gems import (
    AdrenalineRush,
    AdrenalineRushBuff,
    FirstStrikeBuff,
    HarmoniousSoul,
    HarmoniousSoulBuff,
)
from fellowship_sim.simulation.scenarios import (
    boss_fight_scenario,
    generate_new_scenario,
    multiple_identical_packs_scenario,
)
from tests.conftest import FixedRNG

# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------

_SETUP = ElarionSetup(
    raw_stats=RawStatsFromPercents(
        main_stat=1000.0,
    ),
    talents=[
        Talent.PIERCING_SEEKERS,
        Talent.FUSILLADE,
        Talent.LUNAR_FURY,
        Talent.LUNARLIGHT_AFFINITY,
        Talent.FERVENT_SUPREMACY,
        Talent.IMPENDING_HEARTSEEKER,
        Talent.LAST_LIGHTS,
    ],
    sets=["Death's Grasp"],
    gem_power={
        Gem.RED: 1458,  # red 6: MightOfTheMinotaur L2 (+9% main stat above 80% HP)
        Gem.PURPLE: 1458,  # purple 6: SealedFate L2, KillerInstinct L1, BlessingOfTheDeathdealer L1
        Gem.WHITE: 120,  # white 1 : on UnitDestroyed, gain HarmoniousSoulBuff
    },
)

# Damage = ability.average_damage * (main_stat / 1000) * (1 + expertise_percent).
# No expertise in this setup; main_stat = (1000 + 15) * 1.09 at full player HP
# (MightOfTheMinotaur L2 active above 80% player HP; ChampionsHeart L1 adds 15 flat).
# Player HP stays 1.0 throughout all tests, so this scale is constant.
_EXPECTED_MAIN_STAT = (1000 + 15) * 1.09
_STAT_SCALE = _EXPECTED_MAIN_STAT / 1000

_EPSILON = 0.01


class TestScenarios:
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
    ) -> None:
        """Cast ability twice (once above, once below the crit threshold) and assert damage."""

        # Roll just above threshold → no crit
        rng.value = expected_crit_chance + bonus_crit + _EPSILON
        elarion._change_focus(+100)
        ability._add_charge()
        ability.cast(target)
        elarion.wait(0.01)
        assert not damage_list[-1].is_crit
        assert damage_list[-1].damage == pytest.approx(bonus_damage * _STAT_SCALE * ability.average_damage)

        # Roll just below threshold → crit
        rng.value = expected_crit_chance + bonus_crit - _EPSILON
        elarion._change_focus(+100)
        ability._add_charge()
        ability.cast(target)
        assert damage_list[-1].is_crit
        assert damage_list[-1].damage == pytest.approx(bonus_damage * _STAT_SCALE * 2 * 1.03 * ability.average_damage)

    def test_aoe_scenario__only_big(self) -> None:
        """Test the AOE scenario with a single big enemy (duration=100 for simple HP math).

        Gem / set interactions verified at three HP thresholds:
          - >50%: SealedFate L2 active (+0.15 crit)
          - 50%:  SealedFate deactivates (HP ≤ 0.5 guard)
          - <30%: Death's Grasp active (+1.15× damage), Last Lights active (+0.30 crit)
        """
        scenario = multiple_identical_packs_scenario(
            pack_duration=100,
            num_big=1,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=None,
            initial_spirit_points=0,
        )
        state, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=42)

        rng = FixedRNG(value=1.0)
        state.rng = rng

        target = state.enemies[0]
        damage_list: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, lambda e: damage_list.append(e) if e.target is target else None)

        base_crit = elarion.stats.crit_percent

        expected_crit_chance_list: list[tuple[ElarionAbility, float]] = [
            (elarion.celestial_shot, base_crit),
            (elarion.multishot, base_crit),
            (elarion.heartseeker_barrage, base_crit + 0.2),  # +0.20 from Fusillade
        ]

        # Sanity checks at t=0
        assert elarion.percent_hp == pytest.approx(1.0)
        assert elarion.stats.main_stat == pytest.approx(_EXPECTED_MAIN_STAT)
        assert target.percent_hp == pytest.approx(1.0)

        # Phase 1 — enemy HP > 50% (SealedFate L2 active: +0.15 crit)
        bonus_crit = 0.15
        bonus_damage = 1.0

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert target.percent_hp > 0.5  # Phase 1 casts take ~11s; HP ≈ 0.89

        # HP progression: enemy HP decreases linearly as 1 - t/100.
        # Verified at t=20 (HP=0.8) and t=50 (HP=0.5) after Phase 1 is complete.
        elarion.wait(20 - state.time)
        assert target.percent_hp == pytest.approx(0.8)

        elarion.wait(50 - state.time)
        assert target.percent_hp == pytest.approx(0.5)

        # Phase 2 — enemy HP = 50% (SealedFate deactivates at HP ≤ 0.5)
        bonus_crit = 0.0
        bonus_damage = 1.0

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert 0.3 < target.percent_hp < 0.5  # Phase 2 casts advance time ~11s past t=50

        # Phase 3 — enemy HP < 30% (Death's Grasp +1.15×, Last Lights +0.30 crit)
        elarion.wait(80 - state.time)
        assert target.percent_hp == pytest.approx(0.2)

        bonus_crit = 0.30  # Last Lights (<30% HP)
        bonus_damage = 1.15  # Death's Grasp (≤30% HP)

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert target.percent_hp < 0.3

    @pytest.mark.parametrize(
        "num_enemies, num_enemies_medium, num_enemies_small",
        [
            (10, 4, 4),
            (6, 2, 2),
        ],
    )
    def test_aoe_scenario__mixed_health(
        self, num_enemies: int, num_enemies_medium: int, num_enemies_small: int
    ) -> None:
        """Test the AOE scenario with a single big enemy (duration=100 for simple HP math).

        Gem / set interactions verified at three HP thresholds:
          - >50%: SealedFate L2 active (+0.15 crit)
          - 50%:  SealedFate deactivates (HP ≤ 0.5 guard)
          - <30%: Death's Grasp active (+1.15× damage), Last Lights active (+0.30 crit)
        """
        scenario = multiple_identical_packs_scenario(
            pack_duration=100,
            num_big=num_enemies - num_enemies_medium - num_enemies_small,
            num_medium=num_enemies_medium,
            num_small=num_enemies_small,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=None,
            initial_spirit_points=0,
        )
        state, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=42)

        rng = FixedRNG(value=1.0)
        state.rng = rng

        unit_destroyd_list = []
        state.bus.subscribe(UnitDestroyed, unit_destroyd_list.append)

        assert state.main_target.time_to_live == 100

        assert sorted([e.time_to_live for e in state.enemies], reverse=True) == [e.time_to_live for e in state.enemies]

        assert (
            len([e for e in state.enemies if e.time_to_live == 100])
            == num_enemies - num_enemies_medium - num_enemies_small
        )
        assert len([e for e in state.enemies if e.time_to_live == 75]) == num_enemies_medium
        assert len([e for e in state.enemies if e.time_to_live == 50]) == num_enemies_small

        enemies_medium = [e for e in state.enemies if e.time_to_live == 75]

        target = state.enemies[0]
        damage_list: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, lambda e: damage_list.append(e) if e.target is target else None)

        base_crit = elarion.stats.crit_percent

        expected_crit_chance_list: list[tuple[ElarionAbility, float]] = [
            (elarion.celestial_shot, base_crit),
            (elarion.multishot, base_crit),
        ]

        # Sanity checks at t=0
        assert elarion.percent_hp == pytest.approx(1.0)
        assert elarion.stats.main_stat == pytest.approx(_EXPECTED_MAIN_STAT)
        assert target.percent_hp == pytest.approx(1.0)

        elarion.wait(40)

        target = state.enemies[-1]
        assert target.time_to_live == 50
        assert target.percent_hp == pytest.approx(0.2)

        assert not elarion.effects.has(HarmoniousSoulBuff)

        # Target is in execute range: bonus crit from LL and bonus damage from execute set
        bonus_crit = 0.30
        bonus_damage = 1.15

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert target.percent_hp < 0.3

        elarion.wait(51 - state.time)

        w1_effect = elarion.effects.get(HarmoniousSoulBuff)

        assert len(unit_destroyd_list) == num_enemies_small
        assert elarion.effects.has(HarmoniousSoul)
        assert w1_effect is not None
        assert w1_effect.stacks == num_enemies_small

        elarion.wait(70 - state.time)

        assert not target.is_alive
        assert state.enemies[-1] is not target
        assert state.enemies[-1].is_alive
        assert state.enemies[-1] is enemies_medium[-1]
        assert state.enemies[-1].percent_hp == pytest.approx(5 / 75)

        assert state.main_target.percent_hp == pytest.approx(30 / 100)

        elarion.wait(78 - state.time)

        w1_effect = elarion.effects.get(HarmoniousSoulBuff)

        assert len(unit_destroyd_list) == num_enemies_small + num_enemies_medium
        assert elarion.effects.has(HarmoniousSoul)
        assert w1_effect is not None
        assert w1_effect.stacks == max(0, num_enemies_small - 5) + num_enemies_medium

    def test_adrenaline_rush__mixed_health_scenario(self) -> None:
        """Check that AR correctly goes up on AOE damage in the mixed_health_scenario."""
        scenario = multiple_identical_packs_scenario(
            pack_duration=100,
            num_big=4,
            num_medium=4,
            num_small=4,
            num_packs=1,
            pack_interval=0.0,
            delay_since_last_fight=None,
            initial_spirit_points=0,
        )
        state, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=42)

        elarion.effects.add(AdrenalineRush(owner=elarion))

        rng = FixedRNG(value=1.0)
        state.rng = rng

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert not elarion.effects.has(AdrenalineRushBuff)

        elarion.wait(35 - state.time)

        assert any(e.percent_hp < 0.3 for e in state.enemies)

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert elarion.effects.has(AdrenalineRushBuff)

        elarion.wait(55 - state.time)

        assert any(e.percent_hp < 0.3 for e in state.enemies)

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert elarion.effects.has(AdrenalineRushBuff)

    def test_scenarios_with_multiple_packs(self) -> None:
        """Functional test for scenario with multiple packs.

        NB: use a pack with only big mobs.

        - check that character cannot act during time window between packs.
        - check that mobs are reset with new IDs.
        - proc yellow1 during pack 1 execute.
        - proc white 1 on unit death at pack end.
        - proc green 1 at the beginning of pack2.
        """
        num_enemies = 12
        pack_duration = 100
        pack_interval = 19
        scenario = multiple_identical_packs_scenario(
            pack_duration=pack_duration,
            num_big=num_enemies,
            num_packs=3,
            pack_interval=pack_interval,
            delay_since_last_fight=None,
            initial_spirit_points=0,
        )
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(main_stat=1000.0),
            gem_power={
                Gem.YELLOW: 120,  # yellow 1: when damaging an enemy in execute range, gain a haste bonus AdrenalineRushBuff
                Gem.GREEN: 120,  # green 1: when damaging an enemy for the first time, gain an expertise buff FirstStrikeBuff
                Gem.WHITE: 120,  # white 1 : on UnitDestroyed, gain HarmoniousSoulBuff
            },
        )
        state, elarion = generate_new_scenario(scenario=scenario, setup=setup, rng_seed=42)

        rng = FixedRNG(value=1.0)
        state.rng = rng

        # first attack procs FirstStrikeBuff; all enemies are tagged
        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert elarion.effects.has(FirstStrikeBuff)
        assert not elarion.effects.has(AdrenalineRushBuff)

        # wait for first strike to expire
        elarion.wait(20)

        assert not elarion.effects.has(FirstStrikeBuff)
        assert not elarion.effects.has(AdrenalineRushBuff)

        # second attack does not proc FirstStrikeBuff; enemies have already been tagged
        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert not elarion.effects.has(FirstStrikeBuff)
        assert not elarion.effects.has(AdrenalineRushBuff)

        # Move to execute phase
        elarion.wait(pack_duration * 0.8 - state.time)

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert elarion.effects.has(AdrenalineRushBuff)

        # Move to just before end of pack
        elarion.wait(pack_duration - 1 - state.time)

        assert not elarion.effects.has(HarmoniousSoulBuff)

        # Crosses the end-of-pack timing
        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert state.time == pack_duration + pack_interval

        hs = elarion.effects.get(HarmoniousSoulBuff)
        assert hs is not None
        assert hs.stacks == min(hs.max_stacks, num_enemies) - pack_interval // HarmoniousSoulBuff.duration

        assert not elarion.effects.has(FirstStrikeBuff)
        assert not elarion.effects.has(AdrenalineRushBuff)

        # first attack on second pack
        elarion.multishot.charges = 5
        elarion.multishot.cast(state.main_target)

        assert elarion.effects.has(FirstStrikeBuff)
        assert not elarion.effects.has(AdrenalineRushBuff)

    def test_boss_fight_scenario(self) -> None:
        """Test the boss fight scenario (duration=100 for simple HP math).

        BlessingOfTheConqueror L1 (+5% damage) applies throughout (boss fight flag).
        Combined with Death's Grasp at HP ≤ 30%: 1.05 × 1.15 = 1.2075× damage.
        """
        scenario = boss_fight_scenario(
            duration=100,
            delay_since_last_fight=None,
            initial_spirit_points=0,
        )
        state, elarion = generate_new_scenario(scenario=scenario, setup=_SETUP, rng_seed=42)

        rng = FixedRNG(value=1.0)
        state.rng = rng

        target = state.enemies[0]
        damage_list: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, lambda e: damage_list.append(e) if e.target is target else None)

        base_crit = elarion.stats.crit_percent

        expected_crit_chance_list: list[tuple[ElarionAbility, float]] = [
            (elarion.celestial_shot, base_crit),
            (elarion.multishot, base_crit),
            (elarion.heartseeker_barrage, base_crit + 0.2),  # +0.20 from Fusillade
        ]

        # Sanity checks at t=0
        assert elarion.percent_hp == pytest.approx(1.0)
        assert elarion.stats.main_stat == pytest.approx(_EXPECTED_MAIN_STAT)
        assert target.percent_hp == pytest.approx(1.0)

        # Phase 1 — enemy HP > 50%
        # SealedFate L2: +0.15 crit; BlessingOfTheConqueror L1: +5% damage (boss fight)
        bonus_crit = 0.15
        bonus_damage = 1.05  # BlessingOfTheConqueror L1

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert target.percent_hp > 0.5

        # HP progression
        elarion.wait(20 - state.time)
        assert target.percent_hp == pytest.approx(0.8)

        elarion.wait(50 - state.time)
        assert target.percent_hp == pytest.approx(0.5)

        # Phase 2 — enemy HP = 50% (SealedFate deactivates; BlessingOfTheConqueror remains)
        bonus_crit = 0.0
        bonus_damage = 1.05  # BlessingOfTheConqueror L1 still active

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert 0.3 < target.percent_hp < 0.5

        # Phase 3 — enemy HP < 30%
        # BlessingOfTheConqueror L1 × Death's Grasp: 1.05 × 1.15 damage
        # Last Lights: +0.30 crit
        elarion.wait(80 - state.time)
        assert target.percent_hp == pytest.approx(0.2)

        bonus_crit = 0.30
        bonus_damage = 1.05 * 1.15  # BlessingOfTheConqueror L1 × Death's Grasp

        for ability, expected_crit_chance in expected_crit_chance_list:
            self._cast_and_check(
                ability=ability,
                target=target,
                elarion=elarion,
                damage_list=damage_list,
                rng=rng,
                expected_crit_chance=expected_crit_chance,
                bonus_crit=bonus_crit,
                bonus_damage=bonus_damage,
            )

        assert elarion.percent_hp == pytest.approx(1.0)
        assert target.percent_hp < 0.3
