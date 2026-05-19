import pytest

from fellowship_sim.ardeos.effect import (
    CracklingInfernoBurnDoT,
    EngulfingFlamesDoT,
    FireBallDoT,
    FireFrogsDoT,
    IncinerateDoT,
    SearingBlazeDoT,
)
from fellowship_sim.ardeos.entity import Ardeos
from fellowship_sim.base_classes import AbilityPeriodicDamage, State
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism
from tests.conftest import SequenceRNG


class TestDetonateCastTime:
    def test_detonate_cast_time_is_always_1_second(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Detonate's player downtime is always 1 second, regardless of haste.

        has_unhasted_cast_time=True means player_downtime is not divided by
        (1 + haste_percent), so state.time advances by exactly 1.0s at any haste level.
        """
        ardeos.embers = 1
        ardeos.detonate.cast(state.enemies[0])
        assert state.time == pytest.approx(1.0, abs=1e-9)


class TestIncinerateTimings:
    def test_incinerate_total_downtime(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Incinerate's total downtime is cast_time + channel_time.

        The cast phase is hasted (1.5s base), the 2.5s channel is not.
        AbilityCastSuccess fires at the end of the cast phase.
        """
        from fellowship_sim.base_classes.events import AbilityCastSuccess

        cast_success_times: list[float] = []
        state.bus.subscribe(AbilityCastSuccess, lambda e: cast_success_times.append(state.time))

        haste = ardeos.stats.haste_percent
        ardeos.incinerate.cast(state.main_target)

        assert cast_success_times == [pytest.approx(1.5 / (1 + haste), abs=1e-9)]
        assert state.time == pytest.approx(1.5 / (1 + haste) + 2.5, abs=1e-9)

    def test_incinerate_number_of_hits(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """Incinerate tick count scales with haste: more ticks fit in the fixed 2.5s channel.

        Expected hits per haste level: 0.0 → 7, 0.1 → 8, 0.2 → 8.
        """
        from fellowship_sim.base_classes import AbilityDamage

        # NB: actual haste is +0.3 after SOH application
        EXPECTED_HITS: dict[float, int] = {
            0.0: 8,
            0.1: 8,
            0.2: 9,
        }

        damage_list: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_list.append)

        haste: int | float = ardeos.stats.haste_percent

        ardeos.incinerate.cast(state.main_target)

        assert ardeos.stats.haste_percent == pytest.approx(haste + 0.3)
        assert ardeos.effects.has(SpiritOfHeroism)
        assert len(damage_list) == EXPECTED_HITS[haste]


class TestDotNumberOfHits:
    """Full-duration tick counts for every Ardeos DoT, measured over a 60-second window."""

    def test_searing_blaze_dot(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """SearingBlazeDoT ticks every (2.0s / (1+haste)) over a 24.0s duration.

        NB: breakpoints are at 8.3%.
        Finals hits are partials on 10% and 20% haste.
        """
        EXPECTED_HITS: dict[float, int] = {
            0.0: 12,
            0.1: 14,
            0.2: 15,
        }

        haste = ardeos.stats.haste_percent
        target = state.main_target
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, SearingBlazeDoT) else None,
        )
        ardeos.searing_blaze.cast(target)
        assert target.effects.has(SearingBlazeDoT)
        ardeos.wait(60)
        assert len(hits) == EXPECTED_HITS[haste]

    def test_engulfing_flames_dot(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """EngulfingFlamesDoT ticks every (1.5s / (1+haste)) over a 9.0s duration.

        NB: breakpoints are at 16.6%.
        Finals hits are partials on 10% and 20% haste."""
        EXPECTED_HITS: dict[float, int] = {
            0.0: 6,
            0.1: 7,
            0.2: 8,
        }

        haste = ardeos.stats.haste_percent
        target = state.main_target
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, EngulfingFlamesDoT) else None,
        )
        ardeos.engulfing_flames.cast(target)
        assert target.effects.has(EngulfingFlamesDoT)
        ardeos.wait(60)
        assert len(hits) == EXPECTED_HITS[haste]

    def test_incinerate_dot(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """IncinerateDoT: applied by IncinerateHitAura on each Incinerate hit; 3.0s ticks over 12.0s duration.

        NB: SpiritOfHeroism (+30% haste) is active after the cast, accelerating tick rate.

        Incinerate DOT is super complex:
        - On full cast, effective duration is 14.5 to to renew.
        - With 14.5 base duration and 3s tick interval, breakpoints are at 3.4% and every 20.7% after that.
        - Base number of hits at 0% base haste would be 5, including a final partial.
        - At 0% base -> 30% haste post spirit of heroism, we get 7 hits (after 24.1% breakpoint).
        - 40% haste, 7 hits again (before 44.8% breakpoint).
        - 50% haste, 8 hits.
        """
        EXPECTED_HITS: dict[float, int] = {
            0.0: 7,
            0.1: 7,
            0.2: 8,
        }

        haste = ardeos.stats.haste_percent
        target = state.main_target
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, IncinerateDoT) else None,
        )
        ardeos.incinerate.cast(target)
        assert target.effects.has(IncinerateDoT)
        ardeos.wait(60)
        assert len(hits) == EXPECTED_HITS[haste]

    def test_fireball_dot(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """FireBallDoT: created by FireBallAccumulatorAura on FireBall hit; 2.0s ticks over 12.0s duration.

        NB: breakpoints are at 16.6%.
        Finals hits are partials on 10% and 20% haste."""
        EXPECTED_HITS: dict[float, int] = {
            0.0: 6,
            0.1: 7,
            0.2: 8,
        }

        haste = ardeos.stats.haste_percent
        target = state.main_target
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, FireBallDoT) else None,
        )
        ardeos.fire_ball.cast(target)
        assert target.effects.has(FireBallDoT)
        ardeos.wait(60)
        assert len(hits) == EXPECTED_HITS[haste]

    def test_fire_frogs_dot(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """FireFrogsDoT: applied by FireFrogsAccumulatorAura via _toad_attack(); 3.0s ticks over 12.0s duration.

        NB: the toad hit has a 0.35s travel delay, so state.advance_time(1) is used to let
        the hit land and the DoT appear before the main 59-second wait.

        NB: breakpoints are at 25%.
        Finals hits are partials on 10% and 20% haste."""
        EXPECTED_HITS: dict[float, int] = {
            0.0: 4,
            0.1: 5,
            0.2: 5,
        }

        haste = ardeos.stats.haste_percent
        target = state.main_target
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, FireFrogsDoT) else None,
        )
        ardeos.fire_frogs._toad_attack(target)
        state.advance_time(1)
        assert target.effects.has(FireFrogsDoT)
        ardeos.wait(59)
        assert len(hits) == EXPECTED_HITS[haste]

    def test_crackling_inferno_burn_dot(self, state: State, ardeos: Ardeos, rng: SequenceRNG) -> None:
        """CracklingInfernoBurnDoT: added directly; 3.0s ticks over 24.0s duration.

        NB: applying via InfernalWave requires a crit; direct addition is used to isolate tick-count behaviour.

        NB: breakpoints are at 12.5%.
        Finals hits are partials on 10% and 20% haste."""
        EXPECTED_HITS: dict[float, int] = {
            0.0: 8,
            0.1: 9,
            0.2: 10,
        }

        haste = ardeos.stats.haste_percent
        target = state.main_target
        hits: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: hits.append(e) if isinstance(e.damage_source, CracklingInfernoBurnDoT) else None,
        )
        target.effects.add(CracklingInfernoBurnDoT(owner=ardeos, average_damage=1000.0))
        assert target.effects.has(CracklingInfernoBurnDoT)
        ardeos.wait(60)
        assert len(hits) == EXPECTED_HITS[haste]
