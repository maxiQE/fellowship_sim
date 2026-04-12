"""Integration tests — generic weapon trait mechanics."""

from dataclasses import dataclass

import pytest

from fellowship_sim.base_classes import AbilityPeriodicDamage, Enemy, Player, SnapshotStats, State
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    AbilityDamage,
    PreDamageSnapshotUpdate,
    SpiritProc,
    UltimateCast,
)
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.base_classes.timed_events import GenericTimedEvent
from fellowship_sim.elarion.setup import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch
from fellowship_sim.generic_game_logic.weapon_traits import (
    AmethystSplintersDoT,
    BraveMachinations,
    HeroicBrand,
    HuntersFocus,
    HuntersFocusBuff,
    InspiredAllegianceBuff,
    MartialInitiative,
    MartialInitiativeBuff,
    NavigatorsIntuition,
    NavigatorsIntuitionBuff,
    PowerRevealedBuff,
    SeizedOpportunity,
    SeizedOpportunityBuff,
    VengefulSoulBuff,
    VisionsOfGrandeur,
    WillfulMomentum,
    WillfulMomentumMainStatBuff,
)
from tests.integration.fixtures import FixedRNG


@dataclass(kw_only=True)
class DotScenario:
    id: str
    hits: list[tuple[float, float, float]]  # (time, damage, haste)
    expected: list[tuple[float, float]]  # (time, tick_damage)
    advance_to: float

    @property
    def total_stored(self) -> float:
        return sum(dmg * 0.1 * (1 + h) for _, dmg, h in self.hits)


_D = 10_000.0  # base crit damage used in single-hit scenarios

SCENARIOS = [
    # --- Single-hit ---
    DotScenario(
        id="single_h0.2",
        hits=[(0.0, _D, 0.2)],
        expected=[(5 / 3, 250.0), (10 / 3, 250.0), (5.0, 250.0), (20 / 3, 250.0), (8.0, 200.0)],
        advance_to=8.5,
    ),
    DotScenario(
        id="single_h0.1",
        hits=[(0.0, _D, 0.1)],
        expected=[(20 / 11, 250.0), (40 / 11, 250.0), (60 / 11, 250.0), (80 / 11, 250.0), (8.0, 100.0)],
        advance_to=8.5,
    ),
    DotScenario(
        id="single_h0.3",
        hits=[(0.0, _D, 0.3)],
        expected=[
            (20 / 13, 250.0),
            (40 / 13, 250.0),
            (60 / 13, 250.0),
            (80 / 13, 250.0),
            (100 / 13, 250.0),
            (8.0, 50.0),
        ],
        advance_to=8.5,
    ),
    # --- Two hits, same haste, second hit between ticks ---
    # hit 1 t=0 (stored=1200), tick at 5/3 (→stored=950)
    # hit 2 t=2: stored=1550, num_ticks=1+(10-10/3)/(5/3)=5, tick_damage=310, partial=0
    DotScenario(
        id="fusion_t2_same_haste",
        hits=[(0.0, 10_000.0, 0.2), (2.0, 5_000.0, 0.2)],
        expected=[
            (5 / 3, 250.0),
            (10 / 3, 310.0),
            (5.0, 310.0),
            (20 / 3, 310.0),
            (25 / 3, 310.0),
            (10.0, 310.0),
        ],
        advance_to=11.0,
    ),
    # --- Two hits, same haste, second hit lands on a tick boundary ---
    # hit 1 t=0, 2 ticks fire at 5/3 and 10/3 (stored→700)
    # hit 2 t=4: stored=1300, num_ticks=1+(12-5)/(5/3)=5.2, tick_damage=250, partial=50
    DotScenario(
        id="fusion_t4_same_haste",
        hits=[(0.0, 10_000.0, 0.2), (4.0, 5_000.0, 0.2)],
        expected=[
            (5 / 3, 250.0),
            (10 / 3, 250.0),
            (5.0, 250.0),
            (20 / 3, 250.0),
            (25 / 3, 250.0),
            (10.0, 250.0),
            (35 / 3, 250.0),
            (12.0, 50.0),
        ],
        advance_to=13.0,
    ),
    # --- Four hits, haste changes ---
    # hit 1 t=0 h=0.2 → stored=1200, tick_time=5/3, tick_damage=250
    # tick at 5/3 (250, stored→950)
    # hit 2 t=2 h=0.2 → fuse: stored=1550, ticks=5, tick_damage=310
    # tick at 10/3 (310, stored→1240)
    # hit 3 t=5 h=0.6 (fires before tick at same time via lower seq)
    #   → fuse: stored=1240+3200=4440, tick_time=1.25, next_tick=5
    #   → num_ticks=1+(13-5)/1.25=7.4, tick_damage=600
    # tick at 5 (600, stored→3840), next at 6.25
    # tick at 6.25 (600, stored→3240), next at 7.5
    # hit 4 t=7 h=0.2 → fuse: stored=3240+600=3840, tick_time=5/3, next_tick=7.5
    #   → num_ticks=1+(15-7.5)/(5/3)=5.5, tick_damage=3840/5.5≈698.18, partial≈349.09
    # ticks at 7.5, 55/6, 65/6, 12.5, 85/6 (all 698.18), partial at 15
]

_TD = 3840 / 5.5  # tick_damage for fusion_4hits_haste_change

SCENARIOS.append(
    DotScenario(
        id="fusion_4hits_haste_change",
        hits=[
            (0.0, 10_000.0, 0.2),
            (2.0, 5_000.0, 0.2),
            (5.0, 20_000.0, 0.6),
            (7.0, 5_000.0, 0.2),
        ],
        expected=[
            (5 / 3, 250.0),
            (10 / 3, 310.0),
            (5.0, 600.0),
            (6.25, 600.0),
            (7.5, _TD),
            (55 / 6, _TD),
            (65 / 6, _TD),
            (12.5, _TD),
            (85 / 6, _TD),
            (15.0, _TD / 2),
        ],
        advance_to=16.0,
    )
)


def _make_dot(player: Player, damage: float, haste: float) -> AmethystSplintersDoT:
    return AmethystSplintersDoT(owner=player, stored_damage=damage * 0.1 * (1 + haste), haste_percent=haste)


def _run(scenario: DotScenario) -> list[tuple[float, float]]:
    """Run a scenario and return all (time, damage) DamageDealt events."""
    state = State(rng=FixedRNG(0.0))
    target = Enemy(state=state)
    elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000))

    collected: list[tuple[float, float]] = []
    state.bus.subscribe(AbilityPeriodicDamage, lambda e: collected.append((state.time, e.damage)))

    for hit_time, damage, haste in scenario.hits[1:]:
        dot = _make_dot(elarion, damage, haste)
        state.schedule(
            time_delay=hit_time,
            callback=GenericTimedEvent(name="add dot", callback=lambda d=dot: target.effects.add(d)),
        )

    target.effects.add(_make_dot(elarion, *scenario.hits[0][1:]))
    state.advance_time(scenario.advance_to)
    return collected


# Excludes 0.25, 0.50, 0.75: integer num_ticks → no partial tick → final == first.
_HASTE_WITH_PARTIAL = [0.01, 0.05, 0.10, 0.15, 0.20, 0.30, 0.35, 0.40, 0.45, 0.60, 0.70, 0.80, 0.90]


class TestAmethystSplintersDoT:
    @pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
    def test_scenario(self, scenario: DotScenario) -> None:
        hits = _run(scenario)
        assert len(hits) == len(scenario.expected), "wrong number of ticks"
        for i, (exp_time, exp_dmg) in enumerate(scenario.expected):
            assert hits[i][0] == pytest.approx(exp_time, abs=1e-9), f"tick {i} time"
            assert hits[i][1] == pytest.approx(exp_dmg, rel=1e-6), f"tick {i} damage"
        assert sum(d for _, d in hits) == pytest.approx(scenario.total_stored, rel=1e-6), "total damage"

    @pytest.mark.parametrize("haste", _HASTE_WITH_PARTIAL)
    def test_final_tick_smaller_than_first(self, haste: float) -> None:
        scenario = DotScenario(id="", hits=[(0.0, 10_000.0, haste)], expected=[], advance_to=8.5)
        hits = _run(scenario)
        assert len(hits) >= 2
        assert hits[-1][1] < hits[0][1]


class TestBraveMachinations:
    """BraveMachinations: weapon ability hits gain +crit; first crit per cast reduces CD by 30%."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, BraveMachinations, VoidbringersTouch, Enemy]:
        elarion = unit_elarion__zero_stats
        brave = BraveMachinations(trait_level=4, owner=elarion)
        elarion.effects.add(brave)
        vbt = VoidbringersTouch(owner=elarion)
        return state_always_procs__st, elarion, brave, vbt, state_always_procs__st.enemies[0]

    def test_adds_crit_percent_to_weapon_ability_snapshot(
        self, setup: tuple[State, Elarion, BraveMachinations, VoidbringersTouch, Enemy]
    ) -> None:
        """PreDamageSnapshotUpdate from a weapon ability source gains +32% crit (trait_level=4)."""
        state, elarion, brave, vbt, enemy = setup
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.3, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=vbt, target=enemy, snapshot=snap)
        state.bus.emit(event)
        assert event.snapshot.crit_percent == pytest.approx(0.3 + brave.crit_bonus)

    def test_does_not_add_crit_to_non_weapon_ability_snapshot(
        self, setup: tuple[State, Elarion, BraveMachinations, VoidbringersTouch, Enemy]
    ) -> None:
        """Non-weapon-ability sources are not affected by the crit bonus."""
        state, elarion, brave, vbt, enemy = setup
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.3, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state.bus.emit(event)
        assert event.snapshot.crit_percent == pytest.approx(0.3)

    def test_first_crit_reduces_cooldown_by_30_percent_of_base(
        self, setup: tuple[State, Elarion, BraveMachinations, VoidbringersTouch, Enemy]
    ) -> None:
        """First crit from a weapon ability cast reduces that ability's CD by 30% of its base CD."""
        state, elarion, brave, vbt, enemy = setup
        vbt.cooldown = vbt.base_cooldown
        state.bus.emit(AbilityCastSuccess(ability=vbt, owner=elarion, target=enemy))
        state.bus.emit(
            AbilityDamage(
                damage_source=vbt, owner=elarion, target=enemy, is_crit=True, is_grievous_crit=False, damage=100.0
            )
        )
        assert vbt.cooldown == pytest.approx(vbt.base_cooldown * 0.70)

    def test_cdr_fires_only_once_per_cast(
        self, setup: tuple[State, Elarion, BraveMachinations, VoidbringersTouch, Enemy]
    ) -> None:
        """Second crit from the same weapon ability cast does not apply additional CDR."""
        state, elarion, brave, vbt, enemy = setup
        vbt.cooldown = vbt.base_cooldown
        state.bus.emit(AbilityCastSuccess(ability=vbt, owner=elarion, target=enemy))
        state.bus.emit(
            AbilityDamage(
                damage_source=vbt, owner=elarion, target=enemy, is_crit=True, is_grievous_crit=False, damage=100.0
            )
        )
        cooldown_after_first_crit = vbt.cooldown
        state.bus.emit(
            AbilityDamage(
                damage_source=vbt, owner=elarion, target=enemy, is_crit=True, is_grievous_crit=False, damage=100.0
            )
        )
        assert vbt.cooldown == pytest.approx(cooldown_after_first_crit)


class TestHeroicBrand:
    """HeroicBrand: weapon ability hits deal +50/60/70/80% damage."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, HeroicBrand, VoidbringersTouch, Enemy]:
        elarion = unit_elarion__zero_stats
        brand = HeroicBrand(trait_level=4, owner=elarion)
        elarion.effects.add(brand)
        vbt = VoidbringersTouch(owner=elarion)
        return state_always_procs__st, elarion, brand, vbt, state_always_procs__st.enemies[0]

    def test_scales_weapon_ability_average_damage(
        self, setup: tuple[State, Elarion, HeroicBrand, VoidbringersTouch, Enemy]
    ) -> None:
        """Weapon ability snapshot average_damage is multiplied by 1.80 (trait_level=4)."""
        state, elarion, brand, vbt, enemy = setup
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=vbt, target=enemy, snapshot=snap)
        state.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1000.0 * brand.damage_multiplier)

    def test_does_not_scale_non_weapon_ability_damage(
        self, setup: tuple[State, Elarion, HeroicBrand, VoidbringersTouch, Enemy]
    ) -> None:
        """Non-weapon-ability snapshots are not modified."""
        state, elarion, brand, vbt, enemy = setup
        snap = SnapshotStats(average_damage=1000.0, crit_percent=0.0, crit_multiplier=1.0)
        event = PreDamageSnapshotUpdate(damage_source=elarion.focused_shot, target=enemy, snapshot=snap)
        state.bus.emit(event)
        assert event.snapshot.average_damage == pytest.approx(1000.0)


class TestMartialInitiative:
    """MartialInitiative: weapon ability cast → +10% Main Stat buff for a cooldown-scaled duration."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, MartialInitiative, VoidbringersTouch, Enemy]:
        elarion = unit_elarion__zero_stats
        mi = MartialInitiative(trait_level=4, owner=elarion)
        elarion.effects.add(mi)
        vbt = VoidbringersTouch(owner=elarion)
        return state_always_procs__st, elarion, mi, vbt, state_always_procs__st.enemies[0]

    def test_applies_buff_on_weapon_cast(
        self, setup: tuple[State, Elarion, MartialInitiative, VoidbringersTouch, Enemy]
    ) -> None:
        """Weapon ability cast applies MartialInitiativeBuff to the caster."""
        state, elarion, mi, vbt, enemy = setup
        state.bus.emit(AbilityCastSuccess(ability=vbt, owner=elarion, target=enemy))
        assert elarion.effects.has(MartialInitiativeBuff)

    def test_buff_duration_is_duration_ratio_times_base_cooldown(
        self, setup: tuple[State, Elarion, MartialInitiative, VoidbringersTouch, Enemy]
    ) -> None:
        """Buff duration = duration_ratio × ability.base_cooldown (0.32 × 90 = 28.8s at level 4)."""
        state, elarion, mi, vbt, enemy = setup
        state.bus.emit(AbilityCastSuccess(ability=vbt, owner=elarion, target=enemy))
        buff = elarion.effects.get(MartialInitiativeBuff)
        assert isinstance(buff, MartialInitiativeBuff)
        assert buff.duration == pytest.approx(mi.duration_ratio * vbt.base_cooldown)

    def test_buff_adds_10_percent_main_stat(
        self, setup: tuple[State, Elarion, MartialInitiative, VoidbringersTouch, Enemy]
    ) -> None:
        """MartialInitiativeBuff provides +10% Main Stat."""
        state, elarion, mi, vbt, enemy = setup
        before = elarion.stats.main_stat
        state.bus.emit(AbilityCastSuccess(ability=vbt, owner=elarion, target=enemy))
        assert elarion.stats.main_stat == pytest.approx(before * 1.10)


class TestVisionsOfGrandeur:
    """VisionsOfGrandeur: weapon casts → Spirit Points; spirit casts → reset weapon ability CDs."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, VisionsOfGrandeur, VoidbringersTouch, Enemy]:
        elarion = unit_elarion__zero_stats
        vog = VisionsOfGrandeur(trait_level=4, owner=elarion)
        elarion.effects.add(vog)
        vbt = VoidbringersTouch(owner=elarion)
        elarion.abilities.append(vbt)
        return state_always_procs__st, elarion, vog, vbt, state_always_procs__st.enemies[0]

    def test_weapon_cast_grants_spirit_points(
        self, setup: tuple[State, Elarion, VisionsOfGrandeur, VoidbringersTouch, Enemy]
    ) -> None:
        """Weapon ability cast grants SP = sp_rate × base_cooldown / 30 (3.2 × 90 / 30 = 9.6)."""
        state, elarion, vog, vbt, enemy = setup
        elarion.spirit_points = 0.0
        state.bus.emit(AbilityCastSuccess(ability=vbt, owner=elarion, target=enemy))
        assert elarion.spirit_points == pytest.approx(3.2 * vbt.base_cooldown / 30.0)

    def test_spirit_cast_resets_weapon_ability_cooldowns(
        self, setup: tuple[State, Elarion, VisionsOfGrandeur, VoidbringersTouch, Enemy]
    ) -> None:
        """UltimateCast resets all weapon ability cooldowns to zero."""
        state, elarion, vog, vbt, enemy = setup
        vbt.cooldown = 45.0
        state.bus.emit(UltimateCast(ability=elarion.skystrider_supremacy, owner=elarion, target=enemy))
        assert vbt.cooldown == pytest.approx(0.0)


class TestHuntersFocus:
    """HuntersFocus: stacking haste buff on targeted offensive casts; resets on target change."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, HuntersFocus, Enemy, Enemy]:
        elarion = unit_elarion__zero_stats
        hf = HuntersFocus(trait_level=4, owner=elarion)
        elarion.effects.add(hf)
        enemy1 = state_always_procs__st.enemies[0]
        enemy2 = Enemy(state=state_always_procs__st)
        return state_always_procs__st, elarion, hf, enemy1, enemy2

    def test_applies_haste_buff_on_targeted_cast(
        self, setup: tuple[State, Elarion, HuntersFocus, Enemy, Enemy]
    ) -> None:
        """Targeted ability cast applies HuntersFocusBuff to the caster."""
        state, elarion, hf, enemy1, enemy2 = setup
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy1))
        assert elarion.effects.has(HuntersFocusBuff)

    def test_stacks_on_repeated_casts_same_target(
        self, setup: tuple[State, Elarion, HuntersFocus, Enemy, Enemy]
    ) -> None:
        """Repeated casts against the same target stack the buff up to 5 times."""
        state, elarion, hf, enemy1, enemy2 = setup
        for _ in range(5):
            state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy1))
        buff = elarion.effects.get(HuntersFocusBuff)
        assert isinstance(buff, HuntersFocusBuff)
        assert buff.stacks == 5

    def test_target_change_resets_stacks(self, setup: tuple[State, Elarion, HuntersFocus, Enemy, Enemy]) -> None:
        """Casting on a different enemy removes the existing buff and starts fresh at 1 stack."""
        state, elarion, hf, enemy1, enemy2 = setup
        for _ in range(3):
            state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy1))
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy2))
        buff = elarion.effects.get(HuntersFocusBuff)
        assert isinstance(buff, HuntersFocusBuff)
        assert buff.stacks == 1


class TestNavigatorsIntuition:
    """NavigatorsIntuition: 20% flat chance on offensive cast to buff highest secondary stat; 90s ICD."""

    @pytest.fixture
    def state_spirit_highest(self) -> tuple[State, Elarion, NavigatorsIntuition, Enemy]:
        """Elarion with spirit as the highest secondary stat (30% vs 10% for others)."""
        state = State(rng=FixedRNG(value=0.0))
        enemy = Enemy(state=state)
        elarion = Elarion(
            state=state,
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                spirit_percent=0.30,
                crit_percent=0.10,
                haste_percent=0.10,
                expertise_percent=0.10,
            ),
        )
        ni = NavigatorsIntuition(trait_level=4, owner=elarion)
        elarion.effects.add(ni)
        return state, elarion, ni, enemy

    @pytest.fixture
    def state_haste_highest(self) -> tuple[State, Elarion, NavigatorsIntuition, Enemy]:
        """Elarion with haste as the highest secondary stat (30% vs 10% for others)."""
        state = State(rng=FixedRNG(value=0.0))
        enemy = Enemy(state=state)
        elarion = Elarion(
            state=state,
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                spirit_percent=0.10,
                crit_percent=0.10,
                haste_percent=0.30,
                expertise_percent=0.10,
            ),
        )
        ni = NavigatorsIntuition(trait_level=4, owner=elarion)
        elarion.effects.add(ni)
        return state, elarion, ni, enemy

    def test_buff_applies_to_spirit_when_spirit_is_highest(
        self, state_spirit_highest: tuple[State, Elarion, NavigatorsIntuition, Enemy]
    ) -> None:
        """When spirit is the highest secondary stat, proc buffs spirit rating."""
        state, elarion, ni, enemy = state_spirit_highest
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy))
        buff = elarion.effects.get(NavigatorsIntuitionBuff)
        assert isinstance(buff, NavigatorsIntuitionBuff)
        assert buff.stat == "spirit"

    def test_buff_applies_to_haste_when_haste_is_highest(
        self, state_haste_highest: tuple[State, Elarion, NavigatorsIntuition, Enemy]
    ) -> None:
        """When haste is the highest secondary stat, proc buffs haste rating."""
        state, elarion, ni, enemy = state_haste_highest
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy))
        buff = elarion.effects.get(NavigatorsIntuitionBuff)
        assert isinstance(buff, NavigatorsIntuitionBuff)
        assert buff.stat == "haste"

    def test_icd_blocks_reproccing_within_90s(
        self, state_spirit_highest: tuple[State, Elarion, NavigatorsIntuition, Enemy]
    ) -> None:
        """After a proc, the 90s ICD prevents another proc on the next cast."""
        state, elarion, ni, enemy = state_spirit_highest
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy))
        buff = elarion.effects.get(NavigatorsIntuitionBuff)
        assert isinstance(buff, NavigatorsIntuitionBuff)
        buff.remove()
        # ICD active: _next_available = 90.0, state.time = 0.0
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy))
        assert not elarion.effects.has(NavigatorsIntuitionBuff)

    def test_buff_renewed_after_icd_still_targets_spirit(
        self, state_spirit_highest: tuple[State, Elarion, NavigatorsIntuition, Enemy]
    ) -> None:
        """After the ICD expires, a new proc with spirit still highest again buffs spirit."""
        state, elarion, ni, enemy = state_spirit_highest
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy))
        state.advance_time(90.1)  # first buff expires at t=30, ICD expires at t=90
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=enemy))
        buff = elarion.effects.get(NavigatorsIntuitionBuff)
        assert isinstance(buff, NavigatorsIntuitionBuff)
        assert buff.stat == "spirit"


class TestSeizedOpportunity:
    """SeizedOpportunity: every 20 crits apply +crit buff; crit count frozen while buff is active."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, SeizedOpportunity, Enemy]:
        elarion = unit_elarion__zero_stats
        so = SeizedOpportunity(trait_level=4, owner=elarion)
        elarion.effects.add(so)
        return state_always_procs__st, elarion, so, state_always_procs__st.enemies[0]

    def test_buff_applied_after_20_crits(self, setup: tuple[State, Elarion, SeizedOpportunity, Enemy]) -> None:
        """Exactly 20 critical hits trigger SeizedOpportunityBuff; 19 do not."""
        state, elarion, so, enemy = setup
        for _ in range(19):
            state.bus.emit(
                AbilityDamage(
                    damage_source=elarion.focused_shot,
                    owner=elarion,
                    target=enemy,
                    is_crit=True,
                    is_grievous_crit=False,
                    damage=1.0,
                )
            )
        assert not elarion.effects.has(SeizedOpportunityBuff)
        state.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=enemy,
                is_crit=True,
                is_grievous_crit=False,
                damage=1.0,
            )
        )
        assert elarion.effects.has(SeizedOpportunityBuff)

    def test_crit_count_frozen_while_buff_active(self, setup: tuple[State, Elarion, SeizedOpportunity, Enemy]) -> None:
        """While SeizedOpportunityBuff is active, crits do not increment the counter."""
        state, elarion, so, enemy = setup
        for _ in range(20):
            state.bus.emit(
                AbilityDamage(
                    damage_source=elarion.focused_shot,
                    owner=elarion,
                    target=enemy,
                    is_crit=True,
                    is_grievous_crit=False,
                    damage=1.0,
                )
            )
        assert elarion.effects.has(SeizedOpportunityBuff)
        for _ in range(20):
            state.bus.emit(
                AbilityDamage(
                    damage_source=elarion.focused_shot,
                    owner=elarion,
                    target=enemy,
                    is_crit=True,
                    is_grievous_crit=False,
                    damage=1.0,
                )
            )
        assert so._crit_count == 0


class TestWillfulMomentum:
    """WillfulMomentum: passive +Spirit Rating; SpiritProc → +Main Stat buff."""

    @pytest.fixture
    def setup(
        self, state_always_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> tuple[State, Elarion, WillfulMomentum, Enemy]:
        elarion = unit_elarion__zero_stats
        wm = WillfulMomentum(trait_level=4, owner=elarion)
        elarion.effects.add(wm)
        return state_always_procs__st, elarion, wm, state_always_procs__st.enemies[0]

    def test_passive_adds_spirit_rating(self, setup: tuple[State, Elarion, WillfulMomentum, Enemy]) -> None:
        """WillfulMomentum level 4 adds +148 Spirit Rating, raising spirit_percent above zero."""
        state, elarion, wm, enemy = setup
        assert elarion.stats.spirit_percent > 0.0

    def test_spirit_proc_applies_main_stat_buff(self, setup: tuple[State, Elarion, WillfulMomentum, Enemy]) -> None:
        """SpiritProc triggers WillfulMomentumMainStatBuff (+4.8% main stat at level 4)."""
        state, elarion, wm, enemy = setup
        before = elarion.stats.main_stat
        state.bus.emit(SpiritProc(ability=elarion.focused_shot, owner=elarion, resource_amount=1.0))
        assert elarion.effects.has(WillfulMomentumMainStatBuff)
        assert elarion.stats.main_stat == pytest.approx(before * 1.048)


class TestPowerRevealedBuff:
    """PowerRevealedBuff: +X% Main Stat for 15s (triggered by HiddenPower at 5 stacks)."""

    @pytest.mark.parametrize(("trait_level", "expected_bonus"), [(1, 0.075), (2, 0.09), (3, 0.105), (4, 0.12)])
    def test_main_stat_bonus(
        self,
        trait_level: int,
        expected_bonus: float,
        state_always_procs__st: State,
        unit_elarion__zero_stats: Elarion,
    ) -> None:
        """PowerRevealedBuff grants the correct main stat % bonus for each trait level."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(PowerRevealedBuff(trait_level=trait_level, owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * (1 + expected_bonus))


class TestInspiredAllegianceBuff:
    """InspiredAllegianceBuff: +X Haste Rating for 8s (triggered by InspiredAllegiance proc)."""

    @pytest.mark.parametrize("trait_level", [1, 2, 3, 4])
    def test_adds_haste_rating(
        self,
        trait_level: int,
        state_always_procs__st: State,
        unit_elarion__zero_stats: Elarion,
    ) -> None:
        """InspiredAllegianceBuff raises haste_percent above baseline."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.haste_percent
        elarion.effects.add(InspiredAllegianceBuff(trait_level=trait_level, owner=elarion))
        assert elarion.stats.haste_percent > before


class TestVengefulSoulBuff:
    """VengefulSoulBuff: +X% Main Stat for 6s (triggered by VengefulSoul on crit proc)."""

    @pytest.mark.parametrize(("trait_level", "expected_bonus"), [(1, 0.04), (2, 0.048), (3, 0.056), (4, 0.064)])
    def test_main_stat_bonus(
        self,
        trait_level: int,
        expected_bonus: float,
        state_always_procs__st: State,
        unit_elarion__zero_stats: Elarion,
    ) -> None:
        """VengefulSoulBuff grants the correct main stat % bonus for each trait level."""
        elarion = unit_elarion__zero_stats
        before = elarion.stats.main_stat
        elarion.effects.add(VengefulSoulBuff(trait_level=trait_level, owner=elarion))
        assert elarion.stats.main_stat == pytest.approx(before * (1 + expected_bonus))
