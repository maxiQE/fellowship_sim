from fellowship_sim.base_classes.state import get_state
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


class NeckBarragePriorityListMethod(Rotation):
    description = """
    An AOE rotation for neck barrage, using the method.gg priority list.
    """

    def run(self, elarion: Elarion) -> None:
        state = get_state()
        main_target = state.enemies[0]

        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101

        single_target_priority_list = PriorityList([
            Optional(elarion.voidbringers_touch, lambda t: not t.effects.has(VoidbringersTouchEffect)),
            elarion.event_horizon,
            elarion.skystrider_grace,
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, lambda t: elarion.celestial_impetus_stacks >= 1),
            Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered()),
            elarion.highwind_arrow,
            elarion.multishot,
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            Optional(elarion.voidbringers_touch, lambda t: not t.effects.has(VoidbringersTouchEffect)),
            elarion.event_horizon,
            elarion.skystrider_grace,
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, lambda t: elarion.celestial_impetus_stacks >= 1),
            Optional(elarion.volley, lambda t: 20 >= elarion.lunarlight_mark.cooldown >= 8),
            Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered()),
            elarion.multishot,
            elarion.highwind_arrow,
            elarion.celestial_shot,  # better ignored actually, but on the method list
            elarion.focused_shot,
        ])

        if state.num_enemies >= 3:
            while aoe_target_priority_list(main_target):
                pass
        else:
            while single_target_priority_list(main_target):
                pass
