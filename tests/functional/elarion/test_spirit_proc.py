import pytest

from fellowship_sim.base_classes import AbilityDamage, Enemy, State
from fellowship_sim.base_classes.events import (
    SpiritProc,
)
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.setup_effect import AncestralSurgeSetup
from fellowship_sim.generic_game_logic.weapon_traits import WillfulMomentumMainStatBuff
from tests.integration.fixtures import SequenceRNG


@pytest.mark.parametrize("spirit_percent", [0.0, 0.1, 0.25, 0.35])
@pytest.mark.parametrize("ancestral_surge_level", [0, 1, 2])
def test_time_based_spirit_regen(spirit_percent: float, ancestral_surge_level: int) -> None:
    """Check the contribution of spirit percent and ancestral surge level to spirit regen."""
    starting_spirit = 50

    state = State()
    setup = ElarionSetup(
        raw_stats=RawStatsFromPercents(main_stat=1000.0, spirit_percent=spirit_percent),
    )

    if ancestral_surge_level > 0:
        setup.setup_effect_list.append(AncestralSurgeSetup(is_level_2=ancestral_surge_level == 2))

    elarion = setup.finalize(state)

    elarion.spirit_points = starting_spirit

    ancestral_surge_multiplier = 1
    if ancestral_surge_level > 0:
        ancestral_surge_multiplier = 1.1 if ancestral_surge_level == 1 else 1.3

    nominal_rate = (1 + spirit_percent) / 3 * ancestral_surge_multiplier

    assert elarion.spirit_regen_rate == pytest.approx(nominal_rate)

    elarion.wait(5)

    assert elarion.spirit_points == pytest.approx(starting_spirit + state.time * nominal_rate)

    elarion.wait(7)

    assert elarion.spirit_points == pytest.approx(starting_spirit + state.time * nominal_rate)


@pytest.mark.parametrize("spirit_percent", [0.0, 0.35])
@pytest.mark.parametrize("ancestral_surge_level", [0, 2])
@pytest.mark.parametrize("enemy_spirit_score", [1.5, 4])
@pytest.mark.parametrize("ttl", [120, 460])
def test_enemy_based_spirit_regen(
    spirit_percent: float, ancestral_surge_level: int, enemy_spirit_score: float, ttl: float
) -> None:
    """Check the contribution of enemies to spirit regeneration."""
    num_enemies = 12

    starting_spirit = 50

    state = State()
    setup = ElarionSetup(
        raw_stats=RawStatsFromPercents(main_stat=1000.0, spirit_percent=spirit_percent),
    )

    if ancestral_surge_level > 0:
        setup.setup_effect_list.append(AncestralSurgeSetup(is_level_2=ancestral_surge_level == 2))

    elarion = setup.finalize(state)

    elarion.spirit_points = starting_spirit

    base_regen = elarion.spirit_regen_rate

    for _ in range(num_enemies):
        Enemy(state=state, time_to_live=ttl, spirit_score=enemy_spirit_score)

        assert elarion.spirit_regen_rate == pytest.approx(base_regen + state.num_enemies * enemy_spirit_score / 4 / ttl)

    for _ in range(num_enemies // 2):
        state.enemies[-1].kill()

        assert elarion.spirit_regen_rate == pytest.approx(base_regen + state.num_enemies * enemy_spirit_score / 4 / ttl)


def test_willful_momentum_is_effective_on_its_cast() -> None:
    """Check that the cast that triggers WM is affected by the buffed main stat."""
    rng = SequenceRNG(values=[0.0, 1.0, 1.0])
    state = State(rng=rng)
    target = Enemy(state=state)
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

    # no spirit proc, no crit
    elarion.celestial_shot.cast(target)

    assert len(spirit_procs) == 1
    assert len(damage) == 2
    assert not damage[-1].is_crit
    assert damage[-1].damage == elarion.celestial_shot.average_damage


def test_spirit_proc__triggers_spirit_gain() -> None:
    """Triggering a spirit proc gains +1 spirit."""
    spirit_points = 50

    rng = SequenceRNG(values=[0.0, 1.0, 1.0])
    state = State(rng=rng)
    target = Enemy(state=state)
    elarion = ElarionSetup(
        raw_stats=RawStatsFromPercents(main_stat=1000.0, spirit_percent=0.2),
    ).finalize(state)

    spirit_procs: list[SpiritProc] = []
    damage: list[AbilityDamage] = []
    state.bus.subscribe(SpiritProc, spirit_procs.append)
    state.bus.subscribe(AbilityDamage, damage.append)

    elarion.spirit_points = spirit_points
    assert elarion.spirit_points == spirit_points

    # waiting increases spirit from normal time-based spirit regen
    elarion.wait(20)
    assert elarion.spirit_points == pytest.approx(spirit_points + state.time * elarion.spirit_regen_rate)

    # spirit proc, no crit, no proc on the mark
    elarion.celestial_shot.cast(target)

    assert len(spirit_procs) == 1

    assert elarion.spirit_points == pytest.approx(spirit_points + 1 + state.time * elarion.spirit_regen_rate)

    elarion.wait(10)
    assert elarion.spirit_points == pytest.approx(spirit_points + 1 + state.time * elarion.spirit_regen_rate)

    rng._values = [1.0]
    rng._index = 0

    # no spirit proc, no crit
    elarion.celestial_shot.cast(target)

    assert len(spirit_procs) == 1

    assert elarion.spirit_points == pytest.approx(spirit_points + 1 + state.time * elarion.spirit_regen_rate)
