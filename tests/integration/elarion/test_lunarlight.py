"""Integration tests — LunarlightMark proc system.

Proc chance:
  non-crit hit: 0.25  (roll < 0.25 fires)
  crit hit:     0.50  (roll < 0.50 fires)

With crit_percent >= 1.0 (grievous crit), is_crit=True always — no RNG roll for the crit itself.
So with grievous crit, the first RNG call in the mark handler IS the proc roll.

Explosion branch (only on HeartseekerBarrage hits): 20% chance to fire Explosion instead of Salvo.
"""

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.ability import (
    LunarlightExplosion,
    LunarlightSalvo,
)
from fellowship_sim.elarion.effect import (
    LunarFury,
    LunarlightAffinity,
    LunarlightMarkEffect,
)
from fellowship_sim.elarion.entity import Elarion
from tests.integration.fixtures import FixedRNG, SequenceRNG


class TestMarkProcChanceNonCrit:
    """Non-crit proc fires when roll < 0.25 (threshold exclusive)."""

    def test_fires_below_threshold(self) -> None:
        """Roll < 0.25 → salvo procs on non-crit hit."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 1

    def test_does_not_fire_at_threshold(self) -> None:
        """Roll == 0.25 → no proc (roll >= proc_chance)."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.25)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 0

    def test_fires_just_below_threshold(self) -> None:
        """Roll = 0.249 < 0.25 → procs."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.249)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 1


class TestMarkProcChanceCrit:
    """Crit proc fires when roll < 0.50.

    With grievous crit (crit_percent >= 1.0), is_crit=True with no RNG roll for crit.
    The mark proc roll is the first RNG call in the mark handler.
    """

    def test_fires_below_threshold(self) -> None:
        """Grievous crit → is_crit=True → proc_chance=0.50; roll=0.0 procs."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=1.5))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 1

    def test_does_not_fire_at_threshold(self) -> None:
        """Grievous crit, roll=0.5 >= 0.50 → no proc."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.5)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=1.5))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 0

    def test_fires_just_below_threshold(self) -> None:
        """Grievous crit, roll=0.499 < 0.50 → procs."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.499)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=1.5))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_hits) == 1


class TestMarkStackConsumption:
    """Each proc consumes exactly one mark stack; mark is removed when stacks reach zero."""

    def test_stack_decremented_on_proc(self) -> None:
        """One proc consumes exactly one mark stack.
        Uses advance_time(0.0) to process only t=0 damage events, not the mark expiry at t=15.
        """
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=3))

        elarion.focused_shot._do_cast(enemies[0])
        state.advance_time(0.0)  # process damage + proc at t=0, not mark expiry at t=15

        mark = enemies[0].effects.get("lunarlight_mark")
        assert mark is not None
        assert mark.stacks == 2

    def test_removed_when_stacks_reach_zero(self) -> None:
        """Final stack consumed → mark removed from target."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        assert enemies[0].effects.get("lunarlight_mark") is None


class TestSalvoNonRetrigger:
    """Salvo and Explosion hits do not re-trigger the mark (no recursion)."""

    def test_salvo_does_not_retrigger_mark(self) -> None:
        """Salvo hit on a marked target does not fire another salvo (no recursion)."""
        enemies = [Entity()]
        state = State(enemies=enemies, rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        # 3 stacks: if salvo retriggered, we'd get many more than 1 salvo
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=3))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.focused_shot._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        # Only 1 salvo: the initial FocusedShot procs it, but Salvo itself does not retrigger
        assert len(salvo_hits) == 1


class TestExplosionBranch:
    """On HeartseekerBarrage hits, a 20% roll fires Explosion instead of Salvo.

    RNG sequence (crit=0): [crit_roll, proc_roll, explosion_roll]
    With crit=0: crit roll is consumed (0.0 < 0.0 = False → no crit), then proc/explosion rolls.
    """

    def test_barrage_triggers_explosion_on_low_roll(self) -> None:
        """FixedRNG(0.0): crit=no, proc=yes (0.0<0.25), explosion=yes (0.0<0.20)."""
        enemies = [Entity() for _ in range(12)]  # 1 main + 11 secondary for explosion
        state = State(enemies=enemies, rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.heartseeker_barrage._do_cast(enemies[0])
        state.step()  # first tick fires and triggers mark

        explosion_hits = [e for e in damages if isinstance(e.damage_source, LunarlightExplosion)]
        assert len(explosion_hits) == 12  # 1 main + 11 secondary

    def test_barrage_triggers_salvo_when_explosion_roll_misses(self) -> None:
        """SequenceRNG: crit=no, proc=yes, explosion=no → salvo fires (1 hit)."""
        # [crit_roll=0.0, proc_roll=0.10, explosion_roll=0.25]
        enemies = [Entity() for _ in range(12)]
        state = State(enemies=enemies, rng=SequenceRNG(values=[0.0, 0.10, 0.25])).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state.character = elarion
        enemies[0].effects.add(LunarlightMarkEffect(owner=elarion, stacks=1))

        damages: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damages.append)

        elarion.heartseeker_barrage._do_cast(enemies[0])
        state.step()

        salvo_hits = [e for e in damages if isinstance(e.damage_source, LunarlightSalvo)]
        explosion_hits = [e for e in damages if isinstance(e.damage_source, LunarlightExplosion)]
        assert len(salvo_hits) == 1
        assert len(explosion_hits) == 0


class TestDoubledProcChance:
    """Talent effects double the proc chance for specific ability types."""

    def test_lunarfury_doubles_proc_chance_on_barrage(self) -> None:
        """LunarFury: barrage hits proc at 0.50 (not 0.25); roll=0.30 → procs with talent, not without."""
        # Without LunarFury: roll=0.30 >= 0.25 → no proc
        # SequenceRNG: [crit_roll=0.0, proc_roll=0.30, ...]
        enemies_no = [Entity()]
        state_no = State(enemies=enemies_no, rng=SequenceRNG(values=[0.0, 0.30])).activate()
        elarion_no = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state_no.character = elarion_no
        enemies_no[0].effects.add(LunarlightMarkEffect(owner=elarion_no, stacks=1))
        damages_no: list[AbilityDamage] = []
        state_no.bus.subscribe(AbilityDamage, damages_no.append)
        elarion_no.heartseeker_barrage._do_cast(enemies_no[0])
        state_no.step()
        salvo_no = [e for e in damages_no if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_no) == 0

        # With LunarFury: elarion.has_increased_proc_chance_barrage=True → proc_chance=0.50
        # roll=0.30 < 0.50 → procs; explosion_roll=0.30 >= 0.20 → salvo
        enemies_t = [Entity()]
        state_t = State(enemies=enemies_t, rng=SequenceRNG(values=[0.0, 0.30, 0.30])).activate()
        elarion_t = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state_t.character = elarion_t
        elarion_t.has_increased_proc_chance_barrage = True
        elarion_t.effects.add(LunarFury(owner=elarion_t))
        enemies_t[0].effects.add(LunarlightMarkEffect(owner=elarion_t, stacks=1))
        damages_t: list[AbilityDamage] = []
        state_t.bus.subscribe(AbilityDamage, damages_t.append)
        elarion_t.heartseeker_barrage._do_cast(enemies_t[0])
        state_t.step()
        salvo_t = [e for e in damages_t if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_t) == 1

    def test_lunarlight_affinity_doubles_proc_chance_on_volley(self) -> None:
        """LunarlightAffinity: volley ticks proc at 0.50 (not 0.25); roll=0.30 → procs with talent."""
        # Without talent: roll=0.30 >= 0.25 → no proc
        enemies_no = [Entity()]
        state_no = State(enemies=enemies_no, rng=FixedRNG(value=0.30)).activate()
        elarion_no = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state_no.character = elarion_no
        enemies_no[0].effects.add(LunarlightMarkEffect(owner=elarion_no, stacks=1))
        damages_no: list[AbilityDamage] = []
        state_no.bus.subscribe(AbilityDamage, damages_no.append)
        elarion_no.volley._do_cast(enemies_no[0])
        state_no.step()  # first tick
        salvo_no = [e for e in damages_no if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_no) == 0

        # With LunarlightAffinity: volley proc_chance doubled to 0.50; roll=0.30 < 0.50 → procs
        enemies_t = [Entity()]
        state_t = State(enemies=enemies_t, rng=FixedRNG(value=0.30)).activate()
        elarion_t = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        state_t.character = elarion_t
        elarion_t.has_increased_proc_chance_volley = True
        elarion_t.effects.add(LunarlightAffinity(owner=elarion_t))
        enemies_t[0].effects.add(LunarlightMarkEffect(owner=elarion_t, stacks=1))
        damages_t: list[AbilityDamage] = []
        state_t.bus.subscribe(AbilityDamage, damages_t.append)
        elarion_t.volley._do_cast(enemies_t[0])
        state_t.step()
        salvo_t = [e for e in damages_t if isinstance(e.damage_source, LunarlightSalvo)]
        assert len(salvo_t) == 1
