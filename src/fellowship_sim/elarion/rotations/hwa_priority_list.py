from fellowship_sim.base_classes.state import get_state
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.simulation.base import Rotation


class HighwindArrowPriorityList(Rotation):
    description = """
    A simple priority list highwind-arrow rotation.
    """

    def run(self, elarion: Elarion) -> None:  # noqa: C901
        state = get_state()

        main_target = state.enemies[0]

        while True:
            if elarion.lunarlight_mark.can_cast():
                elarion.lunarlight_mark.cast(main_target)
                continue
            if elarion.skystrider_supremacy.can_cast():
                elarion.skystrider_supremacy.cast(main_target)
                continue
            if elarion.heartseeker_barrage.can_cast():
                elarion.heartseeker_barrage.cast(main_target)
                continue
            if elarion.volley.can_cast():
                elarion.volley.cast(main_target)
                continue
            if elarion.highwind_arrow.can_cast():
                elarion.highwind_arrow.cast(main_target)
                continue

            if elarion.multishot.is_empowered():  # noqa: SIM102
                if elarion.multishot.can_cast():
                    elarion.multishot.cast(main_target)
                    continue

            if state.num_enemies >= 4:
                if elarion.multishot.can_cast():
                    elarion.multishot.cast(main_target)
                    continue
                if elarion.celestial_shot.can_cast():
                    elarion.celestial_shot.cast(main_target)
                    continue
            else:
                if elarion.celestial_shot.can_cast():
                    elarion.celestial_shot.cast(main_target)
                    continue
                if elarion.multishot.can_cast():
                    elarion.multishot.cast(main_target)
                    continue

            if elarion.focused_shot.can_cast():
                elarion.focused_shot.cast(main_target)
                continue

            break
