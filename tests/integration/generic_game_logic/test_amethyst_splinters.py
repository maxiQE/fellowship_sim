# Test that splinters damage does not scale with expertise or crit, only with haste_percent
"""Integration tests — AmethystSplinters damage scaling.

AmethystSplinters stores crit_damage × ratio × (1 + haste_percent) when a crit lands.
Ticks deal that stored amount directly, bypassing the stat pipeline.
This means expertise and crit multiplier do not re-scale the ticks;
only haste_percent (captured at proc time) affects the total DoT output.
"""

import pytest

from fellowship_sim.base_classes import Entity, State
from fellowship_sim.base_classes.events import AbilityDamage, AbilityPeriodicDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_traits import AmethystSplinters
from tests.integration.fixtures import FixedRNG

_CRIT_DAMAGE = 10_000.0
_TRAIT_LEVEL = 4
_TRAIT_RATIO = 0.10  # ratio at trait_level=4
_DOT_ADVANCE = 8.5  # past the 8s duration to capture all ticks + final partial


class TestAmethystSplintersScaling:
    """AmethystSplinters DoT: total = crit_damage × ratio × (1 + haste_percent).

    The proc stores a fixed amount at application time and drains it through ticks.
    No stat pipeline scaling is applied at tick time.
    """

    @pytest.mark.parametrize("haste_percent", [0.0, 0.1, 0.2, 0.3, 0.5])
    def test_total_damage_scales_with_haste(self, haste_percent: float) -> None:
        """Total DoT damage equals crit_damage × ratio × (1 + haste) for any haste value."""
        target = Entity()
        state = State(enemies=[target], rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=haste_percent))
        aura = AmethystSplinters(owner=elarion, trait_level=_TRAIT_LEVEL)
        elarion.effects.add(aura)

        ticks: list[float] = []
        state.bus.subscribe(AbilityPeriodicDamage, lambda e: ticks.append(e.damage))
        state.bus.emit(
            AbilityDamage(
                damage_source=aura,
                owner=elarion,
                target=target,
                is_crit=True,
                is_grievous_crit=False,
                damage=_CRIT_DAMAGE,
            )
        )
        state.advance_time(_DOT_ADVANCE)

        assert sum(ticks) == pytest.approx(_CRIT_DAMAGE * _TRAIT_RATIO * (1 + haste_percent), rel=1e-6)

    @pytest.mark.parametrize("expertise_percent", [0.0, 0.1, 0.2, 0.3])
    def test_ticks_do_not_scale_with_expertise(self, expertise_percent: float) -> None:
        """Total DoT damage is independent of the owner's expertise — ticks bypass the stat pipeline."""
        target = Entity()
        state = State(enemies=[target], rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                haste_percent=0.2,
                expertise_percent=expertise_percent,
            )
        )
        aura = AmethystSplinters(owner=elarion, trait_level=_TRAIT_LEVEL)
        elarion.effects.add(aura)

        ticks: list[float] = []
        state.bus.subscribe(AbilityPeriodicDamage, lambda e: ticks.append(e.damage))
        state.bus.emit(
            AbilityDamage(
                damage_source=aura,
                owner=elarion,
                target=target,
                is_crit=True,
                is_grievous_crit=False,
                damage=_CRIT_DAMAGE,
            )
        )
        state.advance_time(_DOT_ADVANCE)

        assert sum(ticks) == pytest.approx(_CRIT_DAMAGE * _TRAIT_RATIO * 1.2, rel=1e-6)

    @pytest.mark.parametrize("crit_percent", [0.0, 0.1, 0.2, 0.4])
    def test_ticks_do_not_scale_with_crit_percent(self, crit_percent: float) -> None:
        """Total DoT damage is independent of the owner's crit percent — ticks bypass the stat pipeline."""
        target = Entity()
        state = State(enemies=[target], rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                haste_percent=0.2,
                crit_percent=crit_percent,
            )
        )
        aura = AmethystSplinters(owner=elarion, trait_level=_TRAIT_LEVEL)
        elarion.effects.add(aura)

        ticks: list[float] = []
        state.bus.subscribe(AbilityPeriodicDamage, lambda e: ticks.append(e.damage))
        state.bus.emit(
            AbilityDamage(
                damage_source=aura,
                owner=elarion,
                target=target,
                is_crit=True,
                is_grievous_crit=False,
                damage=_CRIT_DAMAGE,
            )
        )
        state.advance_time(_DOT_ADVANCE)

        assert sum(ticks) == pytest.approx(_CRIT_DAMAGE * _TRAIT_RATIO * 1.2, rel=1e-6)

    @pytest.mark.parametrize("crit_multiplier", [1.0, 1.03, 1.09, 1.5])
    def test_ticks_do_not_scale_with_crit_multiplier(self, crit_multiplier: float) -> None:
        """Total DoT damage is independent of the owner's crit multiplier — ticks bypass the stat pipeline."""
        target = Entity()
        state = State(enemies=[target], rng=FixedRNG(value=0.0)).activate()
        elarion = Elarion(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                haste_percent=0.2,
                crit_multiplier=crit_multiplier,
            )
        )
        aura = AmethystSplinters(owner=elarion, trait_level=_TRAIT_LEVEL)
        elarion.effects.add(aura)

        ticks: list[float] = []
        state.bus.subscribe(AbilityPeriodicDamage, lambda e: ticks.append(e.damage))
        state.bus.emit(
            AbilityDamage(
                damage_source=aura,
                owner=elarion,
                target=target,
                is_crit=True,
                is_grievous_crit=False,
                damage=_CRIT_DAMAGE,
            )
        )
        state.advance_time(_DOT_ADVANCE)

        assert sum(ticks) == pytest.approx(_CRIT_DAMAGE * _TRAIT_RATIO * 1.2, rel=1e-6)
