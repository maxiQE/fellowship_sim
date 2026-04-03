from fellowship_sim.base_classes import Enemy, Player
from fellowship_sim.base_classes.state import get_state
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import PriorityList


class HighwindArrowPriorityList(Rotation):
    description = """
    A simple priority list highwind-arrow rotation.
    """

    def run(self, elarion: Elarion) -> None:
        state = get_state()

        main_target = state.enemies[0]

        def multishot_if_empowered(character: Player, target: Enemy) -> bool:
            if elarion.multishot.is_empowered() and elarion.multishot.can_cast():
                elarion.multishot.cast(target)
                return True
            return False

        def multishot_or_cs_by_target_count(character: Player, target: Enemy) -> bool:
            if state.num_enemies >= 4:
                if elarion.multishot.can_cast():
                    elarion.multishot.cast(target)
                    return True
                if elarion.celestial_shot.can_cast():
                    elarion.celestial_shot.cast(target)
                    return True
            else:
                if elarion.celestial_shot.can_cast():
                    elarion.celestial_shot.cast(target)
                    return True
                if elarion.multishot.can_cast():
                    elarion.multishot.cast(target)
                    return True
            return False

        priority = PriorityList(
            ability_list=[
                elarion.lunarlight_mark,
                elarion.skystrider_supremacy,
                elarion.heartseeker_barrage,
                elarion.volley,
                elarion.highwind_arrow,
                multishot_if_empowered,
                multishot_or_cs_by_target_count,
                elarion.focused_shot,
            ]
        )

        while priority(character=elarion, main_target=main_target):
            pass
