from dataclasses import dataclass
from typing import Any, Literal

from loguru import logger

from fellowship_sim.base_classes.state import get_state
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.effect import CelestialImpetusAura
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect
from fellowship_sim.generic_game_logic.weapon_traits import VisionsOfGrandeur
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


@dataclass(kw_only=True)
class NeckBarragePriorityList(Rotation):
    description = """
    A refined rotation for neck barrage.

    Overview: the rotation switches between three states:

    - Ultimate window:
        - Prepare ultimate: send weapon before ultimate, check focus, check for CI proc chance
        - Ultimate: maximize volley resets
    - Normal rotation:
        - optimized for AOE or ST
    - Pre-ultimate preparation:
        - hold cooldowns for ultimate
        - hold voidbringer and grace
        - wait for barrage before ulting

    State is assessed at each player action.
    """

    # Only send CI if barrage CD is above this level; 0 = always send CI
    smart_ci_hsb_cd_threshold: float = 0

    fs_trigger_proba: float = 1.0

    desync_volley_on_aoe: bool = True

    sync_llm_with_barrage: bool = False

    keep_highwind_arrow_off_cooldown: bool = False

    def run(self, elarion: Elarion) -> None:  # noqa: C901
        state = get_state()
        target = state.enemies[0]

        ci_aura = elarion.effects.get(CelestialImpetusAura)

        assert ci_aura is not None  # noqa: S101
        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101

        def ultimate__if_volley_imminent(_t: Any) -> bool:
            num_cd_for_volley_reset = elarion.volley.cooldown / 1.5

            # only optimize on very short volley times
            if num_cd_for_volley_reset > 2:
                return False

            # Volley is imminent and we don't have focus: cast FS
            if elarion.focus < 30:
                elarion.focused_shot.cast(target)
                return True

            # HSB already available and CI proc ready: do not cast CS
            if elarion.heartseeker_barrage.can_cast() and elarion.celestial_impetus_stacks >= 1:
                return PriorityList([
                    Optional(elarion.focused_shot, lambda t: ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
                    Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered() or state.num_enemies >= 3),
                    elarion.highwind_arrow,
                    elarion.focused_shot,  # Probably better than waiting; TODO: check
                    lambda _t: elarion.wait(0.1),
                ])(_t)

            # HSB not already available: return to normal prior
            return False

        def celestial_shot__dont_reset_if_hsb_imminent(_t: Any) -> bool:
            if (  # noqa: SIM103
                elarion.celestial_impetus_stacks >= 1
                and elarion.heartseeker_barrage.cooldown >= self.smart_ci_hsb_cd_threshold
            ):
                return True

            return False

        prepare_ultimate_priority_list = PriorityList([
            Optional(
                elarion.focused_shot,
                lambda t: elarion.focus <= 40 or ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba,
            ),
            Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered() or state.num_enemies >= 3),
            elarion.highwind_arrow,
            Optional(elarion.celestial_shot, lambda t: elarion.celestial_impetus_stacks == 0),
            elarion.focused_shot,
        ])

        ultimate_active_priority_list = PriorityList([
            Optional(
                Optional(elarion.voidbringers_touch, lambda t: not t.effects.has(VoidbringersTouchEffect)),
                lambda t: elarion.effects.has(VisionsOfGrandeur),
            ),
            elarion.event_horizon,
            Optional(elarion.voidbringers_touch, lambda t: not t.effects.has(VoidbringersTouchEffect)),
            elarion.skystrider_grace,
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            ultimate__if_volley_imminent,  # Special priority if volley imminent and HSB already reset
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, lambda t: elarion.celestial_impetus_stacks >= 1),
            Optional(elarion.focused_shot, lambda t: ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
            Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered() or state.num_enemies >= 3),
            Optional(
                elarion.highwind_arrow,
                lambda t: (  # Check that we don't lose a cast by casting HWA at exactly the wrong time
                    elarion.focus >= 30 or elarion.effects.get(EventHorizonBuff).duration >= 1.5  # ty:ignore[unresolved-attribute]
                ),
            ),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        single_target_priority_list = PriorityList([
            Optional(
                elarion.voidbringers_touch, lambda t: can_cast_weapon and not t.effects.has(VoidbringersTouchEffect)
            ),
            Optional(elarion.skystrider_grace, lambda t: can_cast_grace),
            elarion.skystrider_supremacy,
            elarion.lunarlight_mark,
            elarion.volley,
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, celestial_shot__dont_reset_if_hsb_imminent),
            Optional(elarion.focused_shot, lambda t: ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
            Optional(
                elarion.highwind_arrow,
                lambda t: (
                    (not self.keep_highwind_arrow_off_cooldown)
                    and elarion.highwind_arrow.charges == elarion.highwind_arrow.max_charges
                ),
            ),
            Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered()),
            elarion.highwind_arrow,
            Optional(elarion.celestial_shot, lambda t: elarion.focus >= 20),
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            Optional(
                elarion.voidbringers_touch, lambda t: can_cast_weapon and not t.effects.has(VoidbringersTouchEffect)
            ),
            Optional(elarion.skystrider_grace, lambda t: can_cast_grace),
            elarion.skystrider_supremacy,
            Optional(
                elarion.lunarlight_mark,
                lambda t: not (self.sync_llm_with_barrage) or elarion.heartseeker_barrage.can_cast(),
            ),
            elarion.heartseeker_barrage,
            Optional(elarion.celestial_shot, celestial_shot__dont_reset_if_hsb_imminent),
            Optional(elarion.focused_shot, lambda t: ci_aura.real_ppm.proc_chance >= self.fs_trigger_proba),
            Optional(
                elarion.volley,
                lambda t: (not self.desync_volley_on_aoe) or 20 >= elarion.lunarlight_mark.cooldown >= 8,
            ),
            Optional(
                elarion.highwind_arrow,
                lambda t: (
                    (not self.keep_highwind_arrow_off_cooldown)
                    and elarion.highwind_arrow.charges == elarion.highwind_arrow.max_charges
                ),
            ),
            Optional(elarion.multishot, lambda t: elarion.multishot.is_empowered()),
            elarion.multishot,
            elarion.highwind_arrow,
            Optional(elarion.celestial_shot, lambda t: elarion.focus >= 30),
            elarion.focused_shot,
        ])

        rotation_state: Literal["ultimate", "prepare", "normal"] = "normal"
        can_cast_grace: bool = False
        can_cast_weapon: bool = False

        def assess_current_state(_t: Any) -> bool:
            nonlocal rotation_state, can_cast_grace, can_cast_weapon

            # default value
            can_cast_grace = True
            can_cast_weapon = True

            # If we have buff, the status is clear
            if elarion.effects.has(EventHorizonBuff):
                rotation_state = "ultimate"
                return False

            time_until__just_send_it = state.information.duration - 40 - state.time

            # if remaining time is too low, just send ultimate asap
            if time_until__just_send_it <= 0:
                rotation_state = "ultimate" if elarion.event_horizon.can_cast() else "normal"
                return False

            spirit_regen = (
                elarion.spirit_point_per_s + elarion.stats.spirit_proc_chance * (1 + elarion.stats.haste_percent) / 1.8
            )
            time_until_enough_spirit_points = (elarion.spirit_ability_cost - elarion.spirit_points) / spirit_regen
            time_until_spirit_point_saturation = (elarion.max_spirit_points - elarion.spirit_points) / spirit_regen
            time_until_weapon_ready: float = elarion.voidbringers_touch.cooldown
            time_until_grace_ready: float = elarion.skystrider_grace.cooldown

            # Current code: wait for all
            can_cast_grace = False
            can_cast_weapon = False

            time_until_ultimate_cast = max([
                time_until_enough_spirit_points,
                time_until_weapon_ready
                if time_until_weapon_ready <= 0
                else 0,  # the "if-else" is necessary because weapon should be recast just before ultimate
                time_until_grace_ready,
            ])

            if time_until_spirit_point_saturation <= 0 and time_until_ultimate_cast > 0:
                logger.error("Spirit is saturated")

            small_cooldowns_ready = (
                elarion.focus >= 40 and elarion.heartseeker_barrage.cooldown <= 0
                # and elarion.volley.can_cast()  # TODO test if waiting for volley helps on aoe or ST
            )

            if time_until_ultimate_cast <= 0 and small_cooldowns_ready:
                assert elarion.event_horizon.can_cast()  # noqa: S101
                rotation_state = "ultimate"
            elif time_until_ultimate_cast <= 10:
                rotation_state = "prepare"
            else:
                rotation_state = "normal"

            # logger.warning(
            #     f"{rotation_state}\t{elarion.focus:<3.0f}\t{elarion.heartseeker_barrage.cooldown:<3.0f}{time_until_ultimate_ready = :<3.0f}\t{time_until_enough_spirit_points = :<3.0f}\t{time_until_grace_ready = :<3.0f}\t{time_until_weapon_ready = :<3.0f}"
            # )

            # Always continue to next possible action
            return False

        grouped_priority = PriorityList([
            assess_current_state,
            Optional(ultimate_active_priority_list, lambda t: rotation_state == "ultimate"),
            Optional(prepare_ultimate_priority_list, lambda t: rotation_state == "prepare"),
            Optional(aoe_target_priority_list, lambda t: state.num_enemies >= 3),
            single_target_priority_list,
        ])

        while grouped_priority(target):
            pass

        raise Exception()  # noqa: TRY002
