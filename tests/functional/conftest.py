# Fixtures specific to functional tests

# Shared integration+functional fixtures are imported from tests.fixtures.conftest
# from tests.fixtures.conftest import ...

import pytest

from fellowship_sim.base_classes.ability import Ability, CastReturnCode
from fellowship_sim.base_classes.entity import Entity, Player


@pytest.fixture(autouse=True)
def no_cast_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert that every ability.cast() call succeeds. Fails immediately on ON_COOLDOWN or INSUFFICENT_RESOURCES.

    This fixture is automatically appended to every functional test."""
    original_cast = Ability.cast

    def _cast(self: Ability[Player], target: Entity) -> CastReturnCode:
        result = original_cast(self, target)
        assert result is CastReturnCode.OK, f"cast blocked — {self} ({result.value})"
        return result

    monkeypatch.setattr(Ability, "cast", _cast)
