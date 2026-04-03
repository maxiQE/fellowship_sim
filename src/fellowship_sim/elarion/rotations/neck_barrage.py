from fellowship_sim.base_classes import Enemy, Player
from fellowship_sim.base_classes.state import get_state
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.effect import CelestialImpetusAura
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


class NeckBarragePriorityList(Rotation):
    description = """
    A refined rotation for neck barrage.
    """

    def run(self, elarion: Elarion) -> None:
        state = get_state()
        target = state.enemies[0]

        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101

        def eh_duration__get_fs_proc(c: Player, t: Enemy) -> bool:
            eh_buff = c.effects.get(EventHorizonBuff)
            return eh_buff is not None and 4.5 <= eh_buff.duration <= 7

        def eh_duration__long_enough_for_hwa_reset(c: Player, t: Enemy) -> bool:
            eh_buff = c.effects.get(EventHorizonBuff)
            return eh_buff is not None and eh_buff.duration >= 8

        def focused_shot__high_proc_proba(c: Player, t: Enemy) -> bool:
            ci_aura = c.effects.get(CelestialImpetusAura)
            return ci_aura is not None and ci_aura.real_ppm.proc_chance >= 1.0

        ultimate_active_priority_list = PriorityList([
            Optional(elarion.voidbringers_touch, lambda c, t: not t.effects.has(VoidbringersTouchEffect)),
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, lambda c, t: c.celestial_impetus_stacks >= 1),
            Optional(elarion.multishot, lambda c, t: c.celestial_impetus_stacks >= 1),  # MS if CI; keep HWA for reset
            Optional(elarion.focused_shot, eh_duration__get_fs_proc),
            Optional(elarion.highwind_arrow, eh_duration__long_enough_for_hwa_reset),
            elarion.multishot,
            elarion.highwind_arrow,
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        single_target_priority_list = PriorityList([
            elarion.event_horizon,
            elarion.skystrider_grace,
            Optional(elarion.voidbringers_touch, lambda c, t: not t.effects.has(VoidbringersTouchEffect)),
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            elarion.heartseeker_barrage,
            Optional(elarion.focused_shot, focused_shot__high_proc_proba),
            Optional(elarion.celestial_shot, lambda c, t: c.celestial_impetus_stacks >= 1),
            Optional(elarion.multishot, lambda c, t: elarion.multishot.is_empowered()),
            elarion.highwind_arrow,
            elarion.multishot,
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            Optional(elarion.voidbringers_touch, lambda c, t: not t.effects.has(VoidbringersTouchEffect)),
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.heartseeker_barrage,
            Optional(elarion.focused_shot, focused_shot__high_proc_proba),
            Optional(elarion.celestial_shot, lambda c, t: c.celestial_impetus_stacks >= 1),
            Optional(elarion.volley, lambda c, t: 20 >= elarion.lunarlight_mark.cooldown >= 8),
            Optional(elarion.multishot, lambda c, t: elarion.multishot.is_empowered()),
            elarion.multishot,
            elarion.highwind_arrow,
            elarion.multishot,
            elarion.focused_shot,
        ])

        grouped_priority = PriorityList([
            elarion.event_horizon,
            elarion.skystrider_grace,
            Optional(ultimate_active_priority_list, lambda c, t: elarion.effects.has(EventHorizonBuff)),
            Optional(aoe_target_priority_list, lambda c, t: state.num_enemies >= 3),
            single_target_priority_list,
        ])

        while grouped_priority(elarion, target):
            pass

        raise Exception()  # noqa: TRY002
