from collections.abc import Callable
from dataclasses import dataclass, field

from fellowship_sim.base_classes import Ability, State

type RotationElement = Callable[[State], Ability | None]
type RotationCondition = Callable[[State], bool]
type RotationScore = Callable[[State], float]


@dataclass
class Optional:
    element: Ability | RotationElement
    condition: RotationCondition

    def __call__(self, state: State) -> Ability | None:
        if self.condition(state):
            if isinstance(self.element, Ability):
                if self.element.can_cast():
                    return self.element
                else:
                    return None
            else:
                return self.element(state)
        else:
            return None


@dataclass
class PriorityList:
    element_list: list[Ability | RotationElement]

    def __call__(self, state: State) -> Ability | None:
        for elem in self.element_list:
            if isinstance(elem, Ability):
                if elem.can_cast():
                    return elem
            else:
                potential_ability = elem(state)
                if potential_ability is not None:
                    return potential_ability

        return None


@dataclass(kw_only=True)
class Sequence:
    element_list: list[Ability | RotationElement]
    _index: int = field(default=0, init=False)

    def __call__(self, state: State) -> Ability | None:
        elem = self.element_list[self._index]
        self._index = (self._index + 1) % len(self.element_list)
        if isinstance(elem, Ability):
            if elem.can_cast():
                return elem
            return None
        else:
            return elem(state)


type WeightedChoice = tuple[Ability | RotationElement, Callable[[State], float | None]]


@dataclass
class WeightedChoiceList:
    weighted_choice_list: list[WeightedChoice]

    def __call__(self, state: State) -> Ability | None:
        choices_with_weights: list[tuple[Ability | RotationElement, float]] = [
            (elem, weight_function(state))
            for elem, weight_function in self.weighted_choice_list
            if weight_function(state) is not None
        ]  # ty:ignore[invalid-assignment]

        if len(choices_with_weights) == 0:
            return None

        else:
            choices_with_weights = sorted(
                choices_with_weights, reverse=True, key=lambda weighted_choice: weighted_choice[1]
            )
            choice = choices_with_weights[0][0]

            if isinstance(choice, Ability):
                return choice
            else:
                return choice(state)
