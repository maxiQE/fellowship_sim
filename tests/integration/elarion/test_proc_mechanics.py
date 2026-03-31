"""Integration tests — CelestialImpetus (RealPPM) and Spirit procs.

Tests interact with mechanics at the event level:
- CI tests emit AbilityCastSuccess directly to trigger _on_ability_cast.
- Spirit proc tests emit ResourceSpent directly and listen for SpiritProc.
- StartstrikersAscent tests emit SpiritProc directly and check ImpendingHeartseeker.

This avoids coupling to the full cast pipeline and is insensitive to FocusAura timing.

CelestialImpetus: RealPPM with base_ppm=2.0, haste-scaled.
  proc_chance = elapsed_since_last / (60 / effective_ppm)
  At t=0 (first cast): elapsed=0 → proc_chance=0 → never procs.
  After 30s (haste=0): elapsed=30, proc_interval=30 → proc_chance=1.0 → guaranteed proc.

Spirit proc: proc_chance = spirit / (1 + spirit).
  RNG roll < proc_chance to fire. Fires SpiritProc event on proc.
"""

from collections.abc import Callable

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.events import (
    AbilityCastSuccess,
    ResourceSpent,
    SpiritProc,
)
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.effect import (
    CelestialImpetusProc,
    ImpendingHeartseeker,
    LunarlightMarkEffect,
    SpiritEffectProc,
    StarstrikersAscentLegendary,
)
from fellowship_sim.elarion.setup import Elarion
from tests.integration.fixtures import SequenceRNG


class TestCelestialImpetus:
    """CelestialImpetus RealPPM: proc gating, haste scaling, stack consumption, and talent interaction."""

    def test_no_proc_at_first_cast(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """At t=0, CI proc_chance=0 → AbilityCastSuccess on FocusedShot does not gain a stack."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.effects.add(CelestialImpetusProc(owner=elarion))
        ci = elarion.effects.get("celestial_impetus")
        assert isinstance(ci, CelestialImpetusProc)

        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=state.enemies[0]))
        state.advance_time(0.0)

        assert ci.stacks == 0

    def test_procs_after_full_interval(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """At t=30 (haste=0, PPM=2): proc_chance=1.0 → stack gained on FocusedShot cast."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.effects.add(CelestialImpetusProc(owner=elarion))
        ci = elarion.effects.get("celestial_impetus")
        assert isinstance(ci, CelestialImpetusProc)

        # First cast at t=0: sets last_attempt_time, no proc (elapsed=0)
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=state.enemies[0]))
        state.advance_time(0.0)
        assert ci.stacks == 0

        state.advance_time(30.0)

        # Second cast at t=30: proc_chance = 30/30 = 1.0 → procs
        state.bus.emit(AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=state.enemies[0]))
        state.advance_time(0.0)
        assert ci.stacks == 1

    def test_haste_scales_proc_interval(
        self, state_no_procs__st: State, setup_hasted_elarion: Callable[..., Elarion]
    ) -> None:
        """With haste=0.5: effective_ppm=3.0 → proc_interval=20s → proc at t=20."""
        elarion = setup_hasted_elarion(haste=0.5)
        elarion.effects.add(CelestialImpetusProc(owner=elarion))
        ci = elarion.effects.get("celestial_impetus")
        assert isinstance(ci, CelestialImpetusProc)

        state_no_procs__st.bus.emit(
            AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=state_no_procs__st.enemies[0])
        )
        state_no_procs__st.advance_time(0.0)
        assert ci.stacks == 0

        state_no_procs__st.advance_time(20.0)

        state_no_procs__st.bus.emit(
            AbilityCastSuccess(ability=elarion.focused_shot, owner=elarion, target=state_no_procs__st.enemies[0])
        )
        state_no_procs__st.advance_time(0.0)
        assert ci.stacks == 1

    def test_stack_consumed_on_celestial_shot(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """CelestialShot with 1 CI stack → stack consumed → main_target_mark_count marks on target."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.effects.add(CelestialImpetusProc(owner=elarion))
        ci = elarion.effects.get("celestial_impetus")
        assert isinstance(ci, CelestialImpetusProc)
        ci.stacks = 1

        state.bus.emit(AbilityCastSuccess(ability=elarion.celestial_shot, owner=elarion, target=state.enemies[0]))
        state.advance_time(0.0)

        assert ci.stacks == 0
        mark = state.enemies[0].effects.get("lunarlight_mark")
        assert mark is not None
        assert isinstance(mark, LunarlightMarkEffect)
        assert mark.stacks == ci.main_target_mark_count

    def test_no_stack_consumed_when_no_stacks(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """CelestialShot with 0 CI stacks → no marks applied."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.effects.add(CelestialImpetusProc(owner=elarion))

        state.bus.emit(AbilityCastSuccess(ability=elarion.celestial_shot, owner=elarion, target=state.enemies[0]))
        state.advance_time(0.0)

        assert state.enemies[0].effects.get("lunarlight_mark") is None

    def test_applies_impending_heartseeker_when_talented(
        self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion
    ) -> None:
        """CI with triggers_impending_barrage=True → ImpendingHeartseeker applied on stack consumption."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.effects.add(CelestialImpetusProc(owner=elarion))
        ci = elarion.effects.get("celestial_impetus")
        assert isinstance(ci, CelestialImpetusProc)
        ci.triggers_impending_barrage = True
        ci.stacks = 1

        elarion.heartseeker_barrage.cooldown = 20.0
        elarion.heartseeker_barrage.charges = 0

        state.bus.emit(AbilityCastSuccess(ability=elarion.celestial_shot, owner=elarion, target=state.enemies[0]))
        state.advance_time(0.0)  # avoid ImpendingHeartseeker expiry at t=15

        assert ci.stacks == 0
        assert elarion.heartseeker_barrage.cooldown == 0.0
        ih = elarion.effects.get("impending_heartseeker")
        assert ih is not None
        assert isinstance(ih, ImpendingHeartseeker)


class TestSpiritProc:
    """Spirit proc fires on ResourceSpent with probability spirit / (1 + spirit)."""

    def test_never_fires_with_zero_spirit(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """spirit=0 → proc_chance=0 → ResourceSpent never produces a SpiritProc."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.effects.add(SpiritEffectProc(owner=elarion))

        spirit_procs: list[SpiritProc] = []
        state.bus.subscribe(SpiritProc, spirit_procs.append)

        state.bus.emit(
            ResourceSpent(owner=elarion, ability=elarion.celestial_shot, target=state.enemies[0], resource_amount=15)
        )
        state.advance_time(0.0)

        assert len(spirit_procs) == 0

    def test_fires_below_threshold(self, state_no_procs__st: State, unit_elarion__zero_stats: Elarion) -> None:
        """spirit=0.5 → proc_chance=0.333; roll=0.0 < 0.333 → SpiritProc emitted."""
        state = state_no_procs__st
        elarion = unit_elarion__zero_stats
        elarion.raw_stats = RawStatsFromPercents(main_stat=1000.0, spirit_percent=0.5)
        elarion._recalculate_stats()
        elarion.effects.add(SpiritEffectProc(owner=elarion))

        spirit_procs: list[SpiritProc] = []
        state.bus.subscribe(SpiritProc, spirit_procs.append)

        state.bus.emit(
            ResourceSpent(owner=elarion, ability=elarion.celestial_shot, target=state.enemies[0], resource_amount=15)
        )
        state.advance_time(0.0)

        assert len(spirit_procs) == 1
        assert spirit_procs[0].resource_amount == 15

    def test_does_not_fire_at_threshold(self) -> None:
        """spirit=1.0 → proc_chance=0.5; roll=0.5 >= 0.5 → no SpiritProc."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=SequenceRNG(values=[0.5])).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, spirit_percent=1.0))
        state.character = elarion
        elarion.effects.add(SpiritEffectProc(owner=elarion))

        spirit_procs: list[SpiritProc] = []
        state.bus.subscribe(SpiritProc, spirit_procs.append)

        state.bus.emit(
            ResourceSpent(owner=elarion, ability=elarion.celestial_shot, target=enemies[0], resource_amount=15)
        )
        state.advance_time(0.0)

        assert len(spirit_procs) == 0

    def test_fires_just_below_threshold(self) -> None:
        """spirit=1.0 → proc_chance=0.5; roll=0.499 < 0.5 → SpiritProc emitted."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=SequenceRNG(values=[0.499])).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, spirit_percent=1.0))
        state.character = elarion
        elarion.effects.add(SpiritEffectProc(owner=elarion))

        spirit_procs: list[SpiritProc] = []
        state.bus.subscribe(SpiritProc, spirit_procs.append)

        state.bus.emit(
            ResourceSpent(owner=elarion, ability=elarion.celestial_shot, target=enemies[0], resource_amount=15)
        )
        state.advance_time(0.0)

        assert len(spirit_procs) == 1


class TestStartstrikersAscent:
    """StartstrikersAscentLegendary applies ImpendingHeartseeker on SpiritProc with 50% chance."""

    def test_applies_impending_on_spirit_proc(self) -> None:
        """SpiritProc emitted + startstrikers roll < 0.50 → ImpendingHeartseeker applied."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=SequenceRNG(values=[0.0])).activate()  # roll: 0.0 < 0.5 → procs
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        elarion.effects.add(StarstrikersAscentLegendary(owner=elarion))
        elarion.heartseeker_barrage.cooldown = 20.0
        elarion.heartseeker_barrage.charges = 0

        state.bus.emit(SpiritProc(ability=elarion.celestial_shot, owner=elarion, resource_amount=15))
        state.advance_time(0.0)

        assert elarion.heartseeker_barrage.cooldown == 0.0
        ih = elarion.effects.get("impending_heartseeker")
        assert ih is not None
        assert isinstance(ih, ImpendingHeartseeker)

    def test_does_not_apply_impending_when_roll_misses(self) -> None:
        """SpiritProc emitted + startstrikers roll >= 0.50 → no ImpendingHeartseeker."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=SequenceRNG(values=[0.5])).activate()  # at threshold → no proc
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0))
        state.character = elarion
        elarion.effects.add(StarstrikersAscentLegendary(owner=elarion))

        state.bus.emit(SpiritProc(ability=elarion.celestial_shot, owner=elarion, resource_amount=15))
        state.advance_time(0.0)

        assert elarion.effects.get("impending_heartseeker") is None
