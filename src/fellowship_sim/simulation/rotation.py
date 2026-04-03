from collections.abc import Callable
from dataclasses import dataclass

from fellowship_sim.base_classes import Ability, Enemy, Player

type RotationCallable = Callable[[Player, Enemy], bool]


@dataclass
class Optional:
    ability: Ability | RotationCallable
    condition: RotationCallable

    def __call__(self, character: Player, main_target: Enemy) -> bool:
        if self.condition(character, main_target):
            if isinstance(self.ability, Ability):
                if self.ability.can_cast():
                    self.ability.cast(main_target)
                    return True
                else:
                    return False
            else:
                return self.ability(character, main_target)
        else:
            return False


@dataclass
class PriorityList:
    ability_list: list[Ability | RotationCallable]

    def __call__(self, character: Player, main_target: Enemy) -> bool:
        for elem in self.ability_list:
            if isinstance(elem, Ability):
                if elem.can_cast():
                    elem.cast(main_target)
                    return True
            else:
                has_cast = elem(character, main_target)
                if has_cast:
                    return True

        return False
