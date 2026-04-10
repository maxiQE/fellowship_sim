from fellowship_sim.base_classes import AbilityDamage, AbilityPeriodicDamage, Enemy, State, StateInformation
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.effect import LunarlightMarkEffect
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.weapon_traits import AmethystSplintersDoT, Kindling, KindlingDoT
from tests.conftest import SequenceRNG


class TestDoTsCanClearMarks:
    """DoT effects trigger and consume Lunarlight Marks on each tick."""

    def test_amethyst_splinters_procs_marks(self) -> None:
        """Amethyst splinters DOT triggers marks."""
        state = State(
            enemies=[Enemy()],
            rng=SequenceRNG(values=[0.0, 1.0]),  # proc mark -> not a crit -> proc mark -> not a crit
        )
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=0.0,
            ),
            master_trait="Amethyst Splinters",
        )
        elarion = setup.finalize(state)

        start_stack_count = 10
        mark = LunarlightMarkEffect(owner=elarion, stacks=start_stack_count)
        target.effects.add(mark)

        periodic_damage: list[AbilityDamage] = []
        state.bus.subscribe(AbilityPeriodicDamage, periodic_damage.append)

        standard_damage: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, standard_damage.append)

        damage = 10_000
        state.bus.emit(
            AbilityDamage(
                damage_source=elarion._lunarlight_salvo,  # Important! Salvo doesn't clear a mark
                owner=elarion,
                target=target,
                damage=damage,
                is_crit=True,
                is_grievous_crit=False,
            )
        )
        elarion.wait(0.1)

        assert target.effects.has(AmethystSplintersDoT)

        elarion.wait(8)

        assert not target.effects.has(AmethystSplintersDoT)

        # all ticks cleared a mark
        assert len(periodic_damage) == 4
        assert mark.stacks == start_stack_count - 4

    def test_kindle_procs_marks(self) -> None:
        """Kindle DOT triggers marks."""
        state = State(
            enemies=[Enemy()],
            rng=SequenceRNG(
                values=[0.0] + [1.0, 0.0, 1.0, 1.0] * 3
            ),  # proc kindle from artificial event -> (don't crit on kindle dot -> proc mark -> don't crit on salvo -> don't proc kindling aura from salvo) x 3
        )
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=0.0,
            ),
            heroic_traits=["Kindling"],
        )
        elarion = setup.finalize(state)

        start_stack_count = 10

        kindle = elarion.effects.get(Kindling)
        assert kindle is not None
        assert kindle._rppm is not None
        kindle._rppm.last_attempt_time = -10_000

        mark = LunarlightMarkEffect(owner=elarion, stacks=start_stack_count)
        target.effects.add(mark)

        # Kindle triggers on damage
        damage = 10_000
        state.bus.emit(
            AbilityDamage(
                damage_source=elarion._lunarlight_salvo,  # Important! Salvo doesn't clear a mark
                owner=elarion,
                target=target,
                damage=damage,
                is_crit=True,
                is_grievous_crit=False,
            )
        )
        elarion.wait(0.1)

        periodic_damage: list[AbilityDamage] = []
        state.bus.subscribe(AbilityPeriodicDamage, periodic_damage.append)

        standard_damage: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, standard_damage.append)

        assert target.effects.has(KindlingDoT)

        elarion.wait(20)

        assert not target.effects.has(KindlingDoT)

        # all ticks cleared a mark
        assert len(periodic_damage) == 3
        assert mark.stacks == start_stack_count - 3


class TestImmediateMarkClearingFromProcs:
    """Marks granted by procs can be immediately consumed in the same event chain."""

    def test_celestial_shot_can_proc_marks_from_ci_proc(self) -> None:
        """Celestial Shot consumes marks placed by a Celestial Impetus proc in the same cast."""
        rng = SequenceRNG(values=[1.0, 0.99, 1.0, 1.0, 0.0])  # FS crit, CI gain stack, FS crit, CS crit, mark proc
        state = State(
            enemies=[Enemy()],
            rng=rng,
            information=StateInformation(delay_since_last_fight=None),
        )
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=0.0,
            ),
        )
        elarion = setup.finalize(state)

        # initiate rPPM; delay_since_last_fight=None → last_attempt_time=None → no CI roll on first cast
        rng._values = [1.0]  # No crit
        rng._index = 0
        elarion.focused_shot.cast(target)
        assert elarion.celestial_impetus_stacks == 0

        # shortening the wait duration here makes the test fail because the CI proc roll is at 0.99
        elarion.wait(28.5)

        # Guaranteed proc
        rng._values: list[int | float] = [0.99, 1.0]  #  barely proccing the rPPM check on CI aura, no crit
        rng._index = 0
        elarion.focused_shot.cast(target)

        assert elarion.celestial_impetus_stacks == 1

        rng._values: list[int | float] = [1.0, 0.0, 1.0]  # No crit, proc mark salvo, no crit on salvo attack
        # NB: no roll on spirit proc because of proc_chance == 0
        rng._index = 0
        elarion.celestial_shot.cast(target)

        mark = target.effects.get(LunarlightMarkEffect)
        assert mark is not None
        assert mark.stacks == 2
