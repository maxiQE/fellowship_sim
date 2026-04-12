import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.effect import VolleyEffect
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.weapon_abilities import ChronoshiftChannelCDR
from tests.integration.fixtures import FixedRNG


class TestComplexCDRStacking:
    """Test interactions between:

    - Highwind Arrow built-in CDA;
    - EH providing CDA;
    - skylit grace talent providing cooldown recovery;
    - chronoshift providing CDR.
    """

    @pytest.mark.parametrize("haste", [0.0, 0.2])
    def test_highwind_arrow_cda_and_eh_cda_stack_additively(self, haste: float) -> None:
        """Tested by MaxiQE on 08/04/26."""
        state = State(rng=FixedRNG(value=0.0))
        target = Enemy(state=state)

        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
        )
        elarion = setup.finalize(state)

        t_before_cast = state.time
        elarion.highwind_arrow.cast(target)

        # NB: haste affects both CDA and cast time, cancelling the effect on cooldown
        assert elarion.highwind_arrow._cdr_multiplier == pytest.approx(1 + haste)
        assert elarion.highwind_arrow.cooldown == pytest.approx(15)  # Cooldown starts ticking at end of cast

        elarion.wait(20)

        elarion.event_horizon.cast(target)
        elarion.skystrider_grace.cast(target)

        haste = elarion.stats.haste_percent

        t_before_cast = state.time
        elarion.highwind_arrow.cast(target)

        assert state.time == pytest.approx(t_before_cast + 2.0 / (1 + haste))

        assert elarion.highwind_arrow._cdr_multiplier == pytest.approx(1 + 2 * haste)

        recovery_time = elarion.highwind_arrow.base_cooldown / (1 + 2 * haste)
        # wait to just before recovery
        elarion.wait(recovery_time - 0.1)

        assert elarion.highwind_arrow.cooldown == pytest.approx(0.1 * (1 + 2 * haste))

    @pytest.mark.parametrize("haste", [0.0, 0.2])
    def test_chronoshift_and_eh_stack_multiplicatively__integration(self, haste: float) -> None:
        """Tested by MaxiQE on 08/04/26.

        NB: split into an integration test and functional test."""
        state = State(rng=FixedRNG(value=0.0))
        target = Enemy(state=state)

        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
        )
        elarion = setup.finalize(state)

        chrono_effect = ChronoshiftChannelCDR(owner=elarion)
        elarion.effects.add(chrono_effect)

        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(8.0)

        chrono_effect.remove()

        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(1.0)

        chrono_effect = ChronoshiftChannelCDR(owner=elarion)
        elarion.effects.add(chrono_effect)
        eh_effect = EventHorizonBuff(owner=elarion)
        elarion.effects.add(eh_effect)

        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(8.0 * (1 + elarion.stats.haste_percent))

        chrono_effect.remove()

        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(1 + elarion.stats.haste_percent)

        eh_effect.remove()

        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(1.0)

    @pytest.mark.parametrize("haste", [0.0, 0.2])
    def test_chronoshift_and_eh_stack_multiplicatively__functional(self, haste: float) -> None:
        """Tested by MaxiQE on 08/04/26.

        NB: split into an integration test and functional test."""
        state = State(rng=FixedRNG(value=0.0))
        target = Enemy(state=state)

        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
            weapon_ability="Chronoshift",
        )
        elarion = setup.finalize(state)

        elarion.event_horizon.cast(target)
        elarion.skystrider_grace.cast(target)

        elarion.wait(60)

        # Having cast EH (with total haste percent: `haste + 0.6`) does an effective CDR of `20 * (haste + 0.6)`
        assert elarion.skystrider_grace.cooldown == pytest.approx(120 - 60 - 20 * (haste + 0.6))

        # recover cooldowns
        elarion.wait(200)

        t_before = state.time

        elarion.skystrider_grace.cast(target)
        elarion.chronoshift.cast(target)

        # 60 seconds after the grace cast
        elarion.wait(57)
        assert state.time == pytest.approx(t_before + 60)

        # Casting chronoshift produces a 21s reduction in cooldown
        assert elarion.skystrider_grace.cooldown == pytest.approx(120 - 60 - 21)

        # recover cooldowns
        elarion.wait(200)

        elarion.spirit_points = 100
        elarion.event_horizon.cast(target)
        t_before = state.time
        elarion.skystrider_grace.cast(target)
        elarion.chronoshift.cast(target)

        # 60 seconds after the grace cast
        elarion.wait(57)
        assert state.time == pytest.approx(t_before + 60)

        # With both EH and chronoshift, the effective CDR is:
        # - the 20 * (haste + 0.6) from EH
        # - the 21 * (1 + haste + 0.6) from chronoshift, amplified by EH
        assert elarion.skystrider_grace.cooldown == pytest.approx(
            120 - 60 - 20 * (haste + 0.6) - 21 * (1 + haste + 0.6)
        )

    @pytest.mark.parametrize("haste", [0.0, 0.2])
    def test_skylit_grace_stacks_additively_with_eh_and_chronoshift__integration(self, haste: float) -> None:
        """Tested by MaxiQE on 08/04/26."""
        state = State(rng=FixedRNG(value=0.0))
        target = Enemy(state=state)

        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
        )
        elarion = setup.finalize(state)

        chrono_effect = ChronoshiftChannelCDR(owner=elarion)
        elarion.effects.add(chrono_effect)
        volley_effect = VolleyEffect(
            owner=elarion,
            duration=8,
            tick_interval=1,
            ability=elarion.volley,
            multishot_extends_duration_by=0.0,
            has_skylit_grace=True,
        )
        target.effects.add(volley_effect)

        assert elarion.skystrider_grace._cdr_multiplier == pytest.approx(8.0 + 1.0)

        chrono_effect.remove()
        volley_effect.remove()

        chrono_effect = ChronoshiftChannelCDR(owner=elarion)
        elarion.effects.add(chrono_effect)
        eh_effect = EventHorizonBuff(owner=elarion)
        elarion.effects.add(eh_effect)
        volley_effect = VolleyEffect(
            owner=elarion,
            duration=8,
            tick_interval=1,
            ability=elarion.volley,
            multishot_extends_duration_by=0.0,
            has_skylit_grace=True,
        )
        target.effects.add(volley_effect)

        assert elarion.skystrider_grace._cdr_multiplier == pytest.approx(8.0 * (1 + elarion.stats.haste_percent) + 1.0)

        chrono_effect.remove()
        eh_effect.remove()
        volley_effect.remove()

        assert elarion.skystrider_grace._cdr_multiplier == pytest.approx(1.0)

    @pytest.mark.parametrize("haste", [0.0, 0.2])
    @pytest.mark.parametrize("n_volley", [1, 2, 3])
    def test_skylit_grace_stacks_additively_with_eh_and_chronoshift__functional(
        self, haste: float, n_volley: int
    ) -> None:
        """Tested by MaxiQE on 08/04/26.

        NB: builds upon the EH + chronoshift interaction test"""
        state = State(rng=FixedRNG(value=0.0))
        target = Enemy(state=state)

        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste,
                spirit_percent=0.0,
            ),
            weapon_ability="Chronoshift",
            talents=["Skylit Grace"],
        )
        elarion = setup.finalize(state)

        elarion.event_horizon.cast(target)
        t_before = state.time
        elarion.skystrider_grace.cast(target)
        for _ in range(n_volley):
            elarion.volley._add_charge()
            elarion.volley.cast(target)

        # 60 seconds after the grace cast
        elarion.wait(t_before - state.time + 60)
        assert state.time == pytest.approx(t_before + 60)

        # EH contribution `20 * (haste + 0.6)`
        # Each volley reduces CD by 8s
        assert elarion.skystrider_grace.cooldown == pytest.approx(120 - 60 - 20 * (haste + 0.6) - 8 * n_volley)

        # recover cooldowns
        elarion.wait(200)

        t_before = state.time

        elarion.skystrider_grace.cast(target)
        elarion.chronoshift.cast(target)
        for _ in range(n_volley):
            elarion.volley._add_charge()
            elarion.volley.cast(target)

        # 60 seconds after the grace cast
        elarion.wait(t_before - state.time + 60)
        assert state.time == pytest.approx(t_before + 60)

        # Chronoshift contribution: 21s
        # Volley contribution unchanged: 8s per volley
        assert elarion.skystrider_grace.cooldown == pytest.approx(120 - 60 - 21 - 8 * n_volley)

        # recover cooldowns
        elarion.wait(200)

        elarion.spirit_points = 100
        elarion.event_horizon.cast(target)
        t_before = state.time
        elarion.skystrider_grace.cast(target)
        elarion.chronoshift.cast(target)
        for _ in range(n_volley):
            elarion.volley._add_charge()
            elarion.volley.cast(target)

        # 30 seconds after the grace cast
        # NB: note the change of time!
        elarion.wait(t_before - state.time + 30)
        assert state.time == pytest.approx(t_before + 30)

        # With both EH and chronoshift, the effective CDR is:
        # - the 20 * (haste + 0.6) from EH
        # - the 21 * (1 + haste + 0.6) from chronoshift, amplified by EH
        # Volley contribution unchanged: 8s per volley
        assert elarion.skystrider_grace.cooldown == pytest.approx(
            120 - 30 - 20 * (haste + 0.6) - 21 * (1 + haste + 0.6) - 8 * n_volley
        )
