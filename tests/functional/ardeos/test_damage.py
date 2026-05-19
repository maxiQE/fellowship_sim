import pytest

from fellowship_sim.ardeos import ardeos_config
from fellowship_sim.ardeos.ability import Detonate
from fellowship_sim.ardeos.effect import (
    DevouringFlameAura,
    EngulfingFlamesDoT,
    FireBallDoT,
    FireFrogsDoT,
    SearingBlazeDoT,
)
from fellowship_sim.ardeos.entity import Ardeos
from fellowship_sim.base_classes import AbilityDamage, AbilityPeriodicDamage, State
from tests.conftest import SequenceRNG
from tests.functional.ardeos.conftest import build_ardeos


class TestDetonateDamage:
    def test_detonate_damage_increase_with_wildfire(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Wildfire increases dot_tick_acceleration by 20%, increasing Detonate DPS by 20%.

        Detonate fires exactly 3 hits each cast; damage per hit equals
        DoT_avg / tick_interval × window_size / 3. Wildfire lowers tick_interval
        by 20% without affecting the snapshot average_damage.
        """
        # Reference value checked by MaxiQE on 18/05/26
        DETONATE_BLAZE_REFERENCE_VALUE = 284

        target = state.main_target
        haste = ardeos.stats.haste_percent

        hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, Detonate) else None,
        )

        ardeos.embers = 1
        ardeos.searing_blaze.cast(target)
        ardeos.detonate.cast(target)

        ardeos.embers = 1
        ardeos.wildfire.cast(target)
        ardeos.detonate.cast(target)

        hits_no_wildfire = hits[:3]
        hits_with_wildfire = hits[3:]

        base = DETONATE_BLAZE_REFERENCE_VALUE * (1 + haste)
        wildfire_multiplier = 1 + ardeos_config.WILDFIRE_DOT_TICK_ACCELERATION

        assert len(hits_no_wildfire) == 3
        assert all(h.damage == pytest.approx(base, rel=0.01) for h in hits_no_wildfire)

        assert len(hits_with_wildfire) == 3
        assert all(h.damage == pytest.approx(base * wildfire_multiplier, rel=0.01) for h in hits_with_wildfire)

    @pytest.mark.parametrize(
        "haste,expertise,main_stat,crit",
        [
            (0.0, 0.0, 1000.0, 0.0),
            (0.1, 0.2, 1000.0, 0.2),
            (0.2, 0.0, 1000.0, 0.0),
            (0.0, 0.1, 1000.0, 0.2),
            (0.2, 0.0, 2000.0, 0.0),
            (0.0, 0.1, 1000.0, 0.2),
        ],
    )
    def test_detonate_damage_scaling(
        self,
        state: State,
        rng: SequenceRNG,
        haste: float,
        expertise: float,
        main_stat: float,
        crit: float,
    ) -> None:
        """Detonate scales linearly with haste (via tick_interval), expertise, and main_stat.

        Crit is ignored: Detonate emits AbilityDamage with is_crit=False unconditionally.
        Formula: base × (1 + expertise) × (1 + haste) × main_stat / 1000.
        """
        # Reference value checked by MaxiQE on 18/05/26
        DETONATE_BLAZE_REFERENCE_VALUE = 284

        ardeos = build_ardeos(
            state,
            haste_percent=haste,
            expertise_percent=expertise,
            main_stat=main_stat,
            crit_percent=crit,
        )

        hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, Detonate) else None,
        )

        ardeos.embers = 1
        ardeos.searing_blaze.cast(state.main_target)
        ardeos.detonate.cast(state.main_target)

        expected = DETONATE_BLAZE_REFERENCE_VALUE * (1 + expertise) * (1 + haste) * main_stat / 1000
        assert len(hits) == 3
        assert all(h.damage == pytest.approx(expected, rel=0.01) for h in hits)

    @pytest.mark.parametrize("has_boots", [False, True])
    def test_detonate_damage_increase_with_boots_legendary(
        self, state: State, ardeos: Ardeos, rng: SequenceRNG, has_boots: bool
    ) -> None:
        """Detonate damage is increased by legendary effects: enemies take 8% more damage for each engulfing flame on them."""
        # TODO: compute reference in game
        DETONATE_BLAZE_REFERENCE_VALUE = 1244

        if has_boots:
            ardeos.effects.add(DevouringFlameAura(owner=ardeos))

        target = state.main_target
        haste = ardeos.stats.haste_percent

        hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, Detonate) else None,
        )

        ardeos.embers = 1
        ardeos.searing_blaze.cast(target)
        ardeos.engulfing_flames.cast(target)
        ardeos.detonate.cast(target)

        base = DETONATE_BLAZE_REFERENCE_VALUE * (1 + haste)
        expected = base * (1.08 if has_boots else 1)

        assert len(hits) == 3
        assert all(h.damage == pytest.approx(expected, rel=0.01) for h in hits)

    def test_detonate_damage_only_affects_dotted_enemies(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Detonate only damages enemies that have an active Ardeos DoT.

        With 5 enemies and SearingBlazeDoT on enemies[1] and enemies[2] only,
        Detonate fires exactly 3 hits per dotted enemy (6 total) and deals
        zero damage to the remaining three enemies.
        """
        from fellowship_sim.base_classes import Enemy

        for _ in range(4):
            Enemy(state=state)

        assert len(state.enemies) == 5

        hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, Detonate) else None,
        )

        ardeos.searing_blaze.cast(state.enemies[1])
        ardeos.searing_blaze.cast(state.enemies[2])

        ardeos.embers = 1
        ardeos.detonate.cast(state.enemies[0])

        assert len(hits) == 6
        assert len([1 for h in hits if h.target is state.enemies[1]]) == 3
        assert len([1 for h in hits if h.target is state.enemies[2]]) == 3


_DOT_DAMAGE_PARAMS = pytest.mark.parametrize(
    "expertise,main_stat,crit",
    [
        (0.0, 1000.0, 0.0),
        (0.1, 1000.0, 0.0),
        (0.2, 1000.0, 0.0),
        (0.0, 2000.0, 0.0),
        (0.0, 3000.0, 0.0),
        (0.0, 1000.0, 0.2),  # crit must not affect DoT damage
    ],
)


class TestDoTDamage:
    @_DOT_DAMAGE_PARAMS
    def test_searing_blaze_damage_scaling(
        self, state: State, rng: SequenceRNG, expertise: float, main_stat: float, crit: float
    ) -> None:
        """SearingBlazeDoT total damage scales linearly with expertise and main_stat; crit is irrelevant.

        Base: 12 ticks × 680.5 avg = 8166 at haste=0, expertise=0, main_stat=1000.
        Formula: base × (1 + expertise) × main_stat / 1000.
        """
        BASE = 8166.0

        ardeos = build_ardeos(state, expertise_percent=expertise, main_stat=main_stat, crit_percent=crit)
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, SearingBlazeDoT) else None,
        )

        ardeos.searing_blaze.cast(state.main_target)
        ardeos.wait(60)

        total = sum(h.damage for h in hits)
        assert total == pytest.approx(BASE * (1 + expertise) * main_stat / 1000, rel=0.01)

    @_DOT_DAMAGE_PARAMS
    def test_engulfing_flames_damage_scaling(
        self, state: State, rng: SequenceRNG, expertise: float, main_stat: float, crit: float
    ) -> None:
        """EngulfingFlamesDoT total damage scales linearly with expertise and main_stat; crit is irrelevant.

        Base: 6 ticks × 1728.5 avg = 10371 at haste=0, expertise=0, main_stat=1000.
        Formula: base × (1 + expertise) × main_stat / 1000.
        """
        BASE = 10371.0

        ardeos = build_ardeos(state, expertise_percent=expertise, main_stat=main_stat, crit_percent=crit)
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, EngulfingFlamesDoT) else None,
        )

        ardeos.engulfing_flames.cast(state.main_target)
        ardeos.wait(60)

        total = sum(h.damage for h in hits)
        assert total == pytest.approx(BASE * (1 + expertise) * main_stat / 1000, rel=0.01)

    @_DOT_DAMAGE_PARAMS
    def test_fireball_dot_damage_scaling(
        self, state: State, rng: SequenceRNG, expertise: float, main_stat: float, crit: float
    ) -> None:
        """FireBallDoT total damage scales linearly with expertise and main_stat; crit is irrelevant.

        The DoT accumulates 20% of each FireBall hit. Base: 6 ticks × (6155.5 × 0.20) = 7386.6
        at haste=0, expertise=0, main_stat=1000. Formula: base × (1 + expertise) × main_stat / 1000.
        """
        BASE = 7386.6

        ardeos = build_ardeos(state, expertise_percent=expertise, main_stat=main_stat, crit_percent=crit)
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, FireBallDoT) else None,
        )

        ardeos.fire_ball.cast(state.main_target)
        ardeos.wait(60)

        total = sum(h.damage for h in hits)
        assert total == pytest.approx(BASE * (1 + expertise) * main_stat / 1000, rel=0.01)

    @_DOT_DAMAGE_PARAMS
    def test_frogs_dot_damage_scaling(
        self, state: State, rng: SequenceRNG, expertise: float, main_stat: float, crit: float
    ) -> None:
        """FireFrogsDoT total damage scales linearly with expertise and main_stat; crit is irrelevant.

        The DoT accumulates 100% of the toad hit. Base: 4 ticks × (731 × 8) = 23392
        at haste=0, expertise=0, main_stat=1000. Formula: base × (1 + expertise) × main_stat / 1000.

        NB: _toad_attack() has a 0.35s hit delay so advance_time(1) is used before the wait.
        """
        BASE = 23392.0

        ardeos = build_ardeos(state, expertise_percent=expertise, main_stat=main_stat, crit_percent=crit)
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, FireFrogsDoT) else None,
        )

        ardeos.fire_frogs._toad_attack(state.main_target)
        state.advance_time(1)
        ardeos.wait(59)

        total = sum(h.damage for h in hits)
        assert total == pytest.approx(BASE * (1 + expertise) * main_stat / 1000, rel=0.01)
