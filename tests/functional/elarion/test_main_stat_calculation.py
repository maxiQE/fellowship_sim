import pytest

from fellowship_sim.base_classes import Enemy, RawStatsFromPercents, State
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism
from fellowship_sim.generic_game_logic.gems import (
    AncientsWisdom,
    ChampionsHeart,
    GemOvercap,
    MightOfTheMinotaur,
    StoicsTeachings,
)
from fellowship_sim.generic_game_logic.set_effects import TormentOfBaelAurum
from fellowship_sim.generic_game_logic.weapon_traits import WillfulMomentumMainStatBuff


# Columns: main_stat, red_2_level, white_2_level, red_1_level, blue_5_level, gem_overcap, willful_momentum, torment, white_4_level
@pytest.mark.parametrize(
    "main_stat,red_2_level,white_2_level,red_1_level,blue_5_level,gem_overcap,willful_momentum,torment,white_4_level",
    [
        (1000, 0, 0, 0, 0, 0, False, False, 0),  # baseline: bare stats, no effects
        (2442, 0, 0, 0, 0, 0, False, False, 0),  # baseline: realistic main stat
        (2442, 1, 0, 0, 0, 0, False, False, 0),  # ChampionsHeart lvl 1 only
        (2442, 2, 0, 0, 0, 0, False, False, 0),  # ChampionsHeart lvl 2 only
        (2442, 0, 1, 0, 0, 0, False, False, 0),  # StoicsTeachings lvl 1 only
        (2442, 0, 0, 2, 0, 0, False, False, 0),  # MightOfTheMinotaur lvl 2 only
        (2442, 0, 0, 0, 2, 0, False, False, 0),  # AncestralSurge lvl 2 only
        (2442, 0, 0, 0, 0, 400, False, False, 0),  # GemOvercap only
        (2442, 0, 0, 0, 0, 0, True, True, 2),  # WillfulMomentum + Torment + AncientsWisdom lvl 2
        (2442, 2, 2, 2, 2, 400, True, True, 2),  # everything at max
    ],
)
def test_main_stat_calculation(
    main_stat: int,
    red_2_level: int,
    white_2_level: int,
    red_1_level: int,
    blue_5_level: int,
    gem_overcap: int,
    willful_momentum: bool,
    torment: bool,
    white_4_level: int,
) -> None:
    state = State()
    Enemy(state=state)
    setup = ElarionSetup(
        raw_stats=RawStatsFromPercents(
            main_stat=main_stat,
        ),
    )
    elarion = setup.finalize(state)

    assert elarion.percent_hp == 1.0

    # ChampionsHeart (red gem 2): +15 at level 1, +45 at level 2
    if red_2_level > 0:
        elarion.effects.add(ChampionsHeart(owner=elarion, is_level_2=(red_2_level == 2)))

    # StoicsTeachings (white gem 2): +25 at level 1, +75 at level 2
    if white_2_level > 0:
        elarion.effects.add(StoicsTeachings(owner=elarion, is_level_2=(white_2_level == 2)))

    # MightOfTheMinotaur (red gem 1): +3% at level 1, +9% at level 2 (requires >80% HP)
    if red_1_level > 0:
        elarion.effects.add(MightOfTheMinotaur(owner=elarion, is_level_2=(red_1_level == 2)))

    # SpiritOfHeroism with AncestralSurge (blue gem 5): +8% at level 1, +24% at level 2
    if blue_5_level > 0:
        elarion.effects.add(
            SpiritOfHeroism(
                owner=elarion,
                duration=float("inf"),
                ancestral_surge_level=blue_5_level,
                blessing_of_the_virtuoso_level=0,
                sapphire_aurastone_level=0,
            )
        )

    # GemOvercap: overcap * 0.005% per point above 2640
    if gem_overcap > 0:
        elarion.effects.add(GemOvercap(owner=elarion, overcap=gem_overcap))

    # WillfulMomentumMainStatBuff (heroic weapon trait, level 4): +4.8%
    if willful_momentum:
        elarion.effects.add(WillfulMomentumMainStatBuff(owner=elarion, trait_level=4))

    # TormentOfBaelAurum (set effect): x1.04
    if torment:
        elarion.effects.add(TormentOfBaelAurum(owner=elarion))

    # AncientsWisdom (white gem 4): x1.03 at level 1, x1.09 at level 2
    if white_4_level > 0:
        elarion.effects.add(AncientsWisdom(owner=elarion, is_level_2=(white_4_level == 2)))

    # (base + additive_bonus) * additive_multiplier * true_multiplier
    additive_bonus = {0: 0, 1: 15, 2: 45}[red_2_level] + {0: 0, 1: 25, 2: 75}[white_2_level]
    additive_multiplier = (
        1.0
        + {0: 0.0, 1: 0.03, 2: 0.09}[red_1_level]  # MightOfTheMinotaur
        + {0: 0.0, 1: 0.08, 2: 0.24}[blue_5_level]  # SpiritOfHeroism AncestralSurge
        + gem_overcap * 0.00005  # GemOvercap
        + (0.048 if willful_momentum else 0.0)  # WillfulMomentumMainStatBuff level 4
    )
    true_multiplier = (
        (1.04 if torment else 1.0)  # TormentOfBaelAurum
        * {0: 1.0, 1: 1.03, 2: 1.09}[white_4_level]  # AncientsWisdom
    )

    predicted_main_stat = (main_stat + additive_bonus) * additive_multiplier * true_multiplier
    assert elarion.stats.main_stat == pytest.approx(predicted_main_stat)


def test_main_stat_from_setup() -> None:
    """Test main stat values from several setups to check that nothing is going wrong during setup."""
    base_main_stat = 1000
    state = State()
    Enemy(state=state)
    elarion = ElarionSetup(
        raw_stats=RawStatsFromPercents(
            main_stat=base_main_stat,
        ),
        gem_power={
            "red__ruby": 2640 + 500,
        },
    ).finalize(state)
    calculated = elarion.stats.main_stat

    assert elarion.percent_hp == 1.0
    assert calculated == (1000 + 45) * (1 + 0.09 + 500 / 200 * 0.01)

    state = State()
    Enemy(state=state)
    elarion = ElarionSetup(
        raw_stats=RawStatsFromPercents(
            main_stat=base_main_stat,
        ),
        gem_power={
            "blue__saphire": 2640 + 500,
        },
    ).finalize(state)
    elarion.event_horizon.cast(state.enemies[0])
    calculated = elarion.stats.main_stat

    assert elarion.percent_hp == 1.0
    assert calculated == pytest.approx(1000 * (1 + 500 / 200 * 0.01 + 0.24))

    state = State()
    Enemy(state=state)
    elarion = ElarionSetup(
        raw_stats=RawStatsFromPercents(
            main_stat=base_main_stat,
        ),
        gem_power={
            "blue__saphire": 2754,
            "red__ruby": 120,
            "white__diamond": 720,
        },
    ).finalize(state)
    elarion.event_horizon.cast(state.enemies[0])
    calculated = elarion.stats.main_stat

    assert elarion.percent_hp == 1.0
    assert calculated == pytest.approx((1000 + 25) * (1 + 0.03 + 114 / 200 * 0.01 + 0.24) * 1.03)
