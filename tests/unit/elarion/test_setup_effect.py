# Unit tests for elarion/setup_effect.py

import pytest

from fellowship_sim.base_classes.setup import SetupContext
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup_effect import ElarionTalentSelection


class TestElarionTalentSelection:
    def test_talent_selection_within_budget_does_not_raise(self, unit_elarion__zero_stats: Elarion) -> None:
        """A selection whose cost equals the budget is accepted."""
        # PathOfTwilight costs 1, budget is 1 — exactly on budget
        sel = ElarionTalentSelection(talents=["PathOfTwilight"], total_talent_points=1)
        sel.apply(character=unit_elarion__zero_stats, context=SetupContext())  # must not raise

    def test_talent_selection_over_budget_raises(self, unit_elarion__zero_stats: Elarion) -> None:
        """A selection whose total cost exceeds the budget raises ValueError."""
        # PathOfTwilight (1) + MagicWard (1) = 2, budget is 1
        with pytest.raises(ValueError):
            sel = ElarionTalentSelection(talents=["PathOfTwilight", "MagicWard"], total_talent_points=1)
