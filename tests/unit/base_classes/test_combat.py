# Unit tests for base_classes/combat.py

import pytest

from fellowship_sim.base_classes.combat import compute_damage
from fellowship_sim.base_classes.stats import SnapshotStats


class TestComputeDamage:
    """Unit tests for compute_damage: the crit/damage formula.

    compute_damage takes a SnapshotStats and a pre-rolled float in [0, 1) and returns
    (damage, is_crit, is_grievous_crit).  All RNG is injected, so no RNG infrastructure
    is needed here.
    """

    def test_no_crit(self) -> None:
        """Roll above crit_percent yields average_damage with no crit flags."""
        snapshot = SnapshotStats(average_damage=1000.0, crit_percent=0.3, crit_multiplier=1.0)
        damage, is_crit, is_grievous_crit = compute_damage(snapshot=snapshot, rng_roll=0.5)
        assert damage == pytest.approx(1000.0)
        assert not is_crit
        assert not is_grievous_crit

    def test_normal_crit(self) -> None:
        """Roll below crit_percent yields 2 * crit_multiplier * average_damage."""
        snapshot = SnapshotStats(average_damage=1000.0, crit_percent=0.3, crit_multiplier=1.0)
        damage, is_crit, is_grievous_crit = compute_damage(snapshot=snapshot, rng_roll=0.1)
        assert damage == pytest.approx(2000.0)
        assert is_crit
        assert not is_grievous_crit

    def test_crit_roll_boundary_is_strict(self) -> None:
        """A roll exactly equal to crit_percent does not crit (strict <)."""
        snapshot = SnapshotStats(average_damage=1000.0, crit_percent=0.3, crit_multiplier=1.0)
        _, is_crit, _ = compute_damage(snapshot=snapshot, rng_roll=0.3)
        assert not is_crit

    @pytest.mark.parametrize("crit_multiplier", [1.0, 1.25, 1.5, 2.0])
    def test_crit_damage_scales_with_multiplier(self, crit_multiplier: float) -> None:
        """Crit damage is exactly 2 * crit_multiplier * average_damage."""
        snapshot = SnapshotStats(average_damage=1000.0, crit_percent=0.5, crit_multiplier=crit_multiplier)
        damage, is_crit, _ = compute_damage(snapshot=snapshot, rng_roll=0.0)
        assert is_crit
        assert damage == pytest.approx(2.0 * crit_multiplier * 1000.0)

    def test_grievous_crit_continuity_at_threshold(self) -> None:
        """Damage is continuous at the grievous threshold.

        Just below 100% crit (with a guaranteed-crit roll) and exactly at 100% both
        yield 2 * crit_multiplier * average_damage.
        """
        avg = 1000.0
        mult = 1.0
        snap_below = SnapshotStats(average_damage=avg, crit_percent=0.99, crit_multiplier=mult)
        damage_below, _, _ = compute_damage(snapshot=snap_below, rng_roll=0.0)
        snap_at = SnapshotStats(average_damage=avg, crit_percent=1.0, crit_multiplier=mult)
        damage_at, _, _ = compute_damage(snapshot=snap_at, rng_roll=0.99)
        assert damage_below == pytest.approx(2.0 * mult * avg)
        assert damage_at == pytest.approx(2.0 * mult * avg)

    def test_grievous_crit_above_100_percent(self) -> None:
        """At 101% crit, damage is (1 + 1.01) * average_damage = 2.01 * average_damage."""
        snapshot = SnapshotStats(average_damage=1000.0, crit_percent=1.01, crit_multiplier=1.0)
        damage, is_crit, is_grievous_crit = compute_damage(snapshot=snapshot, rng_roll=0.99)
        assert is_crit
        assert is_grievous_crit
        assert damage == pytest.approx(2.01 * 1000.0)

    @pytest.mark.parametrize("crit_percent", [1.0, 1.01, 1.1, 1.5])
    def test_grievous_crit_damage_formula(self, crit_percent: float) -> None:
        """Grievous crit damage is (1 + crit_percent) * crit_multiplier * average_damage."""
        avg = 1000.0
        mult = 1.25
        snapshot = SnapshotStats(average_damage=avg, crit_percent=crit_percent, crit_multiplier=mult)
        damage, _, is_grievous_crit = compute_damage(snapshot=snapshot, rng_roll=0.0)
        assert is_grievous_crit
        assert damage == pytest.approx((1 + crit_percent) * mult * avg)
