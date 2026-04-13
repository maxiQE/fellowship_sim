from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from fellowship_sim.base_classes import Ability
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.effect import CelestialImpetusAura, CelestialImpetusProc
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect
from fellowship_sim.generic_game_logic.weapon_traits import VisionsOfGrandeur
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


@dataclass(kw_only=True)
class VoidBarrage(Rotation):
    description = """
    A complex rotation for IBH barrage with voidbringers.
    """

    fs_trigger_proba: float = 1.0

    keep_highwind_arrow_off_cooldown: bool = True

    cleanup_window_duration_s: float = 6.0

    num_enemies_aoe: int = 4

    desync_volley_on_aoe: bool = True

    sync_llm_with_barrage: bool = False

    smart_ci_hsb_cd_threshold: float = 12

    sync_grace_in_ult: bool = True
    send_grace_whenever: bool = False
    can_send_early_ult: bool = False

    def __call__(self, elarion: Elarion) -> Iterator[Ability | None]:  # noqa: C901
        state = elarion.state

        ci_aura = elarion.effects.get(CelestialImpetusAura)

        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101
        assert ci_aura is not None  # noqa: S101

        ##################
        # Variables
        ##################

        spirit_regen_rate = elarion.spirit_regen_rate
        has_ihb = ci_aura.triggers_impending_barrage

        # 0: baseline
        # 1: prepare EH burst
        # 2: start EH burst
        # 3: EH burst: maintain
        rotation_state: Literal[0, 1, 2, 3] = 0

        # def enemy_actual_ttl() -> float:
        #     return state.main_target.time_to_live - state.time

        def time_to_eh() -> float:
            grace_cd = elarion.skystrider_grace.cooldown if self.sync_grace_in_ult else 0
            void_cd = elarion.voidbringers_touch.cooldown
            eh_cd = (elarion.spirit_ability_cost - elarion.spirit_points) / spirit_regen_rate
            if self.can_send_early_ult and eh_cd < grace_cd - 55 and eh_cd < void_cd - 40:
                return eh_cd
            else:
                return max([grace_cd, void_cd, eh_cd, 0])

        def update_rotation_state(s: Any) -> None:
            nonlocal rotation_state

            match rotation_state:
                case 0:
                    # switch from baseline to prepare when grace almost ready
                    if time_to_eh() <= 6:
                        rotation_state = 1

                case 1:
                    # Stop preparing when grace + hsb is ready
                    if time_to_eh() <= 0 and elarion.heartseeker_barrage.cooldown == 0:
                        rotation_state = 2

                case 2:
                    # handled somewhere else
                    pass

                case 3:
                    if not elarion.effects.has(EventHorizonBuff):
                        rotation_state = 0

                case _:
                    raise Exception(f"Unexpected state: {rotation_state = }")  # noqa: TRY002, TRY003

            return None

        def use_aoe_abilities() -> bool:
            return state.num_enemies >= self.num_enemies_aoe

        ##################
        # Custom actions
        ##################

        voidbringers__dont_overlap = Optional(
            elarion.voidbringers_touch, lambda s: not state.main_target.effects.has(VoidbringersTouchEffect)
        )

        def celestial_shot__dont_reset_if_hsb_imminent(_t: Any) -> bool:
            return has_ihb and bool(
                elarion.celestial_impetus_stacks >= 1
                and (
                    elarion.heartseeker_barrage.cooldown >= self.smart_ci_hsb_cd_threshold
                    or elarion.effects.get(CelestialImpetusProc).duration <= 4  # ty:ignore[unresolved-attribute]
                )
            )

        celestial_shot_with_proc = Optional(elarion.celestial_shot, celestial_shot__dont_reset_if_hsb_imminent)

        hwa_if_at_max_charges = Optional(
            elarion.highwind_arrow,
            lambda s: (
                (not self.keep_highwind_arrow_off_cooldown)
                and elarion.highwind_arrow.charges == elarion.highwind_arrow.max_charges
            ),
        )

        single_target_priority_list = PriorityList([
            Optional(elarion.skystrider_supremacy, lambda s: rotation_state != 1),
            elarion.lunarlight_mark,
            Optional(elarion.heartseeker_barrage, lambda s: rotation_state != 1),
            Optional(elarion.volley, lambda s: rotation_state != 1),
            Optional(elarion.focused_shot, lambda s: has_ihb and ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
            Optional(celestial_shot_with_proc, lambda s: rotation_state != 1),
            hwa_if_at_max_charges,
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered()),
            elarion.highwind_arrow,
            Optional(
                elarion.focused_shot,
                lambda s: (
                    elarion.focus <= 38
                    and (
                        elarion.volley.cooldown <= 1.5 or elarion.heartseeker_barrage.cooldown <= 1.5
                        # or (elarion.highwind_arrow.charges == 2 and elarion.highwind_arrow.cooldown <= 1.5)
                    )
                ),
            ),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            Optional(elarion.skystrider_supremacy, lambda s: rotation_state != 1),
            Optional(
                elarion.lunarlight_mark,
                lambda s: not self.sync_llm_with_barrage or elarion.heartseeker_barrage.can_cast(),
            ),
            Optional(elarion.heartseeker_barrage, lambda s: rotation_state != 1),
            Optional(celestial_shot_with_proc, lambda s: rotation_state != 1),
            Optional(elarion.focused_shot, lambda s: has_ihb and ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
            Optional(
                elarion.volley,
                lambda s: (not self.desync_volley_on_aoe) or 20 >= elarion.lunarlight_mark.cooldown >= 8,
            ),
            hwa_if_at_max_charges,
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered()),
            elarion.multishot,
            elarion.highwind_arrow,
            Optional(
                elarion.focused_shot,
                lambda s: (
                    elarion.focus <= 38
                    and (
                        elarion.volley.cooldown <= 1.5
                        or elarion.heartseeker_barrage.cooldown <= 1.5
                        or (elarion.highwind_arrow.charges == 2 and elarion.highwind_arrow.cooldown <= 1.5)
                    )
                    # or ((elarion.focus <= 18) and elarion.multishot.is_empowered())
                    # or (
                    #     elarion.focus <= 28 and (not elarion.multishot.is_empowered() and elarion.multishot.charges > 0)
                    # )
                ),
            ),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        def move_rotation_state_to_3(s: Any) -> None:
            nonlocal rotation_state
            rotation_state = 3
            return None

        ultimate_start = PriorityList([
            Optional(voidbringers__dont_overlap, lambda s: elarion.effects.has(VisionsOfGrandeur)),
            elarion.event_horizon,
            elarion.skystrider_grace,
            move_rotation_state_to_3,
        ])

        ultimate_ongoing = PriorityList([
            voidbringers__dont_overlap,
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            Optional(elarion.heartseeker_barrage, lambda s: elarion.volley.cooldown >= 3.0),
            Optional(
                elarion.celestial_shot,
                lambda s: (
                    has_ihb and elarion.celestial_impetus_stacks >= 1 and elarion.heartseeker_barrage.cooldown > 0
                ),
            ),
            Optional(elarion.focused_shot, lambda s: has_ihb and ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered() or state.num_enemies >= 3),
            Optional(
                elarion.highwind_arrow,
                lambda s: (  # Check that we don't lose a cast by casting HWA at exactly the wrong time
                    elarion.focus >= 30 or elarion.effects.get(EventHorizonBuff).duration >= 1.5  # ty:ignore[unresolved-attribute]
                ),
            ),
            elarion.heartseeker_barrage,  # Cast HSB even if volley CD is low
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        grouped_prio = PriorityList([
            update_rotation_state,
            Optional(ultimate_start, lambda s: rotation_state == 2),
            Optional(ultimate_ongoing, lambda s: rotation_state == 3),
            Optional(elarion.skystrider_grace, lambda s: self.send_grace_whenever),
            Optional(aoe_target_priority_list, lambda s: use_aoe_abilities()),
            single_target_priority_list,
        ])

        while True:
            yield grouped_prio(state)
