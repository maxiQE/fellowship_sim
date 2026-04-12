from collections.abc import Iterator

from fellowship_sim.base_classes import Ability
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


class NeckBarragePriorityListMethod(Rotation):
    description = """
    An AOE rotation for neck barrage, using the method.gg priority list.
    """

    def __call__(self, elarion: Elarion) -> Iterator[Ability | None]:
        state = elarion.state

        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101

        single_target_priority_list = PriorityList([
            Optional(elarion.voidbringers_touch, lambda s: not state.main_target.effects.has(VoidbringersTouchEffect)),
            elarion.event_horizon,
            elarion.skystrider_grace,
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, lambda s: elarion.celestial_impetus_stacks >= 1),
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered()),
            elarion.highwind_arrow,
            elarion.multishot,
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            Optional(elarion.voidbringers_touch, lambda s: not state.main_target.effects.has(VoidbringersTouchEffect)),
            elarion.event_horizon,
            elarion.skystrider_grace,
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, lambda s: elarion.celestial_impetus_stacks >= 1),
            Optional(elarion.volley, lambda s: 20 >= elarion.lunarlight_mark.cooldown >= 8),
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered()),
            elarion.multishot,
            elarion.highwind_arrow,
            elarion.celestial_shot,  # better ignored actually, but on the method list
            elarion.focused_shot,
        ])

        while True:
            if state.num_enemies >= 3:
                yield aoe_target_priority_list(state)
            else:
                yield single_target_priority_list(state)
