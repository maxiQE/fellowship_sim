"""Functional tests — entity kill interactions with real game mechanics."""

from fellowship_sim.base_classes import AbilityDamage, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.effect import LunarlightMarkEffect
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect


class TestVoidbringersTouchOnKill:
    """VoidbringersTouchEffect explodes when an enemy is killed, but damage is not recorded."""

    def test_vbt_explodes_on_kill_but_damage_not_recorded(self, state_no_procs__st: State) -> None:
        """VBT explosion fires an AbilityDamage event when the enemy dies, but since
        the enemy is already dead when effect removal runs, no damage is registered."""
        state = state_no_procs__st
        elarion = ElarionSetup(
            raw_stats=RawStatsFromPercents(main_stat=1000.0),
            weapon_ability="Voidbringer's Touch",
        ).finalize(state)
        target = state.enemies[0]

        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)
        target.effects.add(
            VoidbringersTouchEffect(
                ability=elarion.voidbringers_touch,
                max_stored_damage=42.5 * elarion.stats.main_stat,
                owner=elarion,
            )
        )

        for _ in range(5):
            elarion.celestial_shot.cast(target=target)

        target.effects.add(LunarlightMarkEffect(owner=elarion))

        damage_before_kill = target.damage_tracker.total

        vbt_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: vbt_events.append(e) if isinstance(e.damage_source, VoidbringersTouchEffect) else None,
        )

        # shift to all procs
        assert state_no_procs__st.rng.value == 1.0  # ty:ignore[unresolved-attribute]
        state_no_procs__st.rng.value = 0.0  # ty:ignore[unresolved-attribute]

        target.kill()

        assert len(vbt_events) == 1
        assert target.damage_tracker.total == damage_before_kill
        assert len(target.effects) == 0
