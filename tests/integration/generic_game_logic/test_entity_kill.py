"""Integration tests — Entity.kill() mechanics."""

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.events import AbilityDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.effect import LunarlightMarkEffect
from fellowship_sim.elarion.entity import Elarion
from tests.integration.fixtures import FixedRNG


class TestEntityKill:
    """Entity.kill(): is_alive flag, state.enemies filtering, effect cleanup, and damage gating."""

    @pytest.fixture
    def state(self) -> State:
        return State(rng=FixedRNG(value=0.0))

    @pytest.fixture
    def elarion(self, state: State) -> Elarion:
        return Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))

    def test_dead_enemy_excluded_from_state_enemies(self, state: State, elarion: Elarion) -> None:
        """Killing e1 removes it from state.enemies; e2 remains."""
        e1 = Enemy(state=state)
        e2 = Enemy(state=state)
        e1.kill()
        assert e1 not in state.enemies
        assert e2 in state.enemies
        assert len(state.enemies) == 1

    def test_main_target_skips_dead_unit(self, state: State, elarion: Elarion) -> None:
        """state.main_target returns the surviving enemy after e1 is killed."""
        e1 = Enemy(state=state)
        e2 = Enemy(state=state)
        e1.kill()
        assert state.main_target is e2

    def test_main_target_raises_when_all_enemies_dead(self, state: State, elarion: Elarion) -> None:
        """state.main_target raises when no alive enemies remain."""
        enemy = Enemy(state=state)
        enemy.kill()
        with pytest.raises(Exception, match="State has no valid main target"):
            _ = state.main_target

    def test_dead_unit_does_not_register_damage(self, state: State, elarion: Elarion) -> None:
        """Dead enemies ignore incoming damage; damage_tracker.total stays zero."""
        enemy = Enemy(state=state)
        enemy.kill()
        AbilityDamage(
            damage_source=elarion.focused_shot,
            owner=elarion,
            target=enemy,
            is_crit=False,
            is_grievous_crit=False,
            damage=100.0,
        )
        assert enemy.damage_tracker.total == 0.0

    def test_all_effects_removed_after_kill(self, state: State, elarion: Elarion) -> None:
        """All effects are stripped from an enemy on kill; attached_to is cleared."""
        enemy = Enemy(state=state)
        mark = LunarlightMarkEffect(owner=elarion)
        enemy.effects.add(mark)
        assert len(enemy.effects) == 1

        enemy.kill()

        assert len(enemy.effects) == 0
        assert mark.attached_to is None
