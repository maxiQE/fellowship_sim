import pytest

from fellowship_sim.base_classes import AbilityDamage, Enemy, State
from fellowship_sim.base_classes.events import (
    SpiritProc,
)
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.weapon_traits import WillfulMomentumMainStatBuff
from tests.integration.fixtures import SequenceRNG


def test_willful_momentum_is_effective_on_its_cast() -> None:
    """Check that the cast that triggers WM is affected by the buffed main stat."""
    target = Enemy()
    rng = SequenceRNG(values=[0.0, 1.0, 1.0])
    state = State(enemies=[target], rng=rng)
    elarion = ElarionSetup(
        raw_stats=RawStatsFromPercents(main_stat=1000.0, spirit_percent=0.2),
        heroic_traits=[
            "Willful Momentum",
        ],
    ).finalize(state)

    spirit_procs: list[SpiritProc] = []
    damage: list[AbilityDamage] = []
    state.bus.subscribe(SpiritProc, spirit_procs.append)
    state.bus.subscribe(AbilityDamage, damage.append)

    # spirit proc, no crit, no proc on the mark
    elarion.celestial_shot.cast(target)
    elarion.wait(0.2)

    assert len(spirit_procs) == 1
    assert elarion.effects.has(WillfulMomentumMainStatBuff)
    assert elarion.stats.main_stat == 1048
    assert len(damage) == 1
    assert not damage[-1].is_crit
    assert damage[-1].damage == pytest.approx(elarion.celestial_shot.average_damage * 1.048)

    elarion.wait(100)
    rng._values = [1.0]
    rng._index = 0

    # spirit proc, no crit
    elarion.celestial_shot.cast(target)

    assert len(spirit_procs) == 1
    assert len(damage) == 2
    assert not damage[-1].is_crit
    assert damage[-1].damage == elarion.celestial_shot.average_damage
