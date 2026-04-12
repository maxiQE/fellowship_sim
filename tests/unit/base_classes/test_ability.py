# Unit tests for base_classes/ability.py

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from fellowship_sim.base_classes import Entity
from fellowship_sim.base_classes.ability import (
    WEAPON_ABILITY_NOT_INITIALIZED,
    Ability,
    WeaponAbility,
)
from fellowship_sim.elarion.entity import Elarion


@dataclass(kw_only=True)
class _TestAbility(Ability[Elarion]):
    base_cast_time: float = 2.0


@dataclass(kw_only=True)
class _TestWeaponAbility(WeaponAbility):
    base_cast_time: float = 2.0


class TestWeaponAbilityNotInitialized:
    def test_weapon_ability_not_initialized_setattr_raises(self) -> None:
        with pytest.raises(AttributeError):
            WEAPON_ABILITY_NOT_INITIALIZED.cooldown = 10

    def test_weapon_ability_not_initialized_getattr_returns_noop(self) -> None:
        fn = WEAPON_ABILITY_NOT_INITIALIZED.cast
        assert callable(fn)
        result = fn(object())
        assert result is None


class TestChargeAndCooldownMechanics:
    def test_pay_cost_first_charge_starts_cooldown(self, unit_elarion__zero_stats: Elarion) -> None:
        """For a 2-charge ability, consuming the FIRST charge starts the cooldown."""
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        ability.max_charges = 2
        ability.charges = 2
        ability.cooldown = 0.0
        ability.base_cooldown = 10.0

        ability._pay_cost_for_cast(Entity(state=unit_elarion__zero_stats.state))

        assert ability.charges == 1
        assert ability.cooldown == pytest.approx(10.0)

    def test_pay_cost_second_charge_does_not_restart_cooldown(self, unit_elarion__zero_stats: Elarion) -> None:
        """Second charge consumed while CD is already running does not restart the CD."""
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        ability.max_charges = 2
        ability.charges = 1
        ability.cooldown = 5.0  # CD already running
        ability.base_cooldown = 10.0

        ability._pay_cost_for_cast(Entity(state=unit_elarion__zero_stats.state))

        assert ability.charges == 0
        assert ability.cooldown == pytest.approx(5.0)  # unchanged

    def test_finalize_charges_grants_charge_at_cooldown_zero(self, unit_elarion__zero_stats: Elarion) -> None:
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        ability.max_charges = 2
        ability.charges = 0
        ability.cooldown = 0.0
        ability.base_cooldown = 10.0

        ability._finalize_cooldown_and_grant_charges()

        assert ability.charges == 1
        assert ability.cooldown == pytest.approx(10.0)  # restarts immediately for the next charge

    def test_finalize_charges_grants_multiple_on_overshoot(self, unit_elarion__zero_stats: Elarion) -> None:
        """When the cooldown overshoots, multiple charges can be granted in one call."""
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        ability.max_charges = 3
        ability.charges = 0
        ability.cooldown = -15.0  # 15s overshoot with base_cooldown=10
        ability.base_cooldown = 10.0

        ability._finalize_cooldown_and_grant_charges()

        # -15s overshoot: grants charge at -15 (+10=−5), grants charge at -5 (+10=+5), stops
        assert ability.charges == 2
        assert ability.cooldown == pytest.approx(5.0)

    def test_reduce_cooldown_grants_charge_on_overshoot(self, unit_elarion__zero_stats: Elarion) -> None:
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        ability.max_charges = 2
        ability.charges = 0
        ability.cooldown = 3.0
        ability.base_cooldown = 10.0

        ability._reduce_cooldown(flat_cdr=5.0)

        # cooldown 3.0 - 5.0 = -2.0 → finalize: grant charge, cooldown = -2 + 10 = 8.0
        assert ability.charges == 1
        assert ability.cooldown == pytest.approx(8.0)


class TestCastTimeAndHaste:
    def test_cast_time_reduced_by_haste(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.2)
        ability = _TestAbility(owner=player)
        assert ability.cast_time == pytest.approx(2.0 / 1.2)

    def test_cast_time_channel_ignores_haste(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        player = setup_hasted_elarion(haste=0.2)
        ability = _TestAbility(owner=player)
        ability.is_channel = True
        assert ability.cast_time == pytest.approx(2.0)

    def test_weapon_ability_cdr_always_one(self, setup_hasted_elarion: Callable[..., Elarion]) -> None:
        """WeaponAbility ignores haste and returns CDR multiplier of 1.0."""
        player = setup_hasted_elarion(haste=0.5)
        ability = _TestWeaponAbility(owner=player)
        assert ability._compute_cooldown_reduction_and_acceleration() == pytest.approx(1.0)


class TestSpiritCost:
    def test_spirit_cost_is_zero_for_non_ultimate(self, unit_elarion__zero_stats: Elarion) -> None:
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        assert ability.spirit_cost == 0

    def test_spirit_cost_equals_spirit_ability_cost_for_ultimate(self, unit_elarion__zero_stats: Elarion) -> None:
        ability = _TestAbility(owner=unit_elarion__zero_stats)
        ability.is_ultimate_ability = True
        assert ability.spirit_cost == pytest.approx(unit_elarion__zero_stats.spirit_ability_cost)
