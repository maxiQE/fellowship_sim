from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from fellowship_sim.base_classes import Ability
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.effect import (
    CelestialImpetusAura,
    FinalCrescendo,
    Shimmer,
)
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism
from fellowship_sim.generic_game_logic.weapon_abilities import VoidbringersTouch, VoidbringersTouchEffect
from fellowship_sim.generic_game_logic.weapon_traits import VisionsOfGrandeur
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


@dataclass(kw_only=True)
class HWASyncedCDs(Rotation[Elarion]):
    description = """
    A complex rotation for shimmer HWA.

    NB: this makes theoretical sense but is untuned.
    """

    fs_trigger_proba: float = 1.0

    keep_highwind_arrow_off_cooldown: bool = True

    cleanup_window_duration_s: float = 6.0

    num_enemies_aoe: int = 4

    desync_volley_on_aoe: bool = True

    sync_llm_with_barrage: bool = False

    smart_ci_hsb_cd_threshold: float = 12

    def __call__(self, elarion: Elarion) -> Iterator[Ability | None]:  # noqa: C901
        state = elarion.state

        ci_aura = elarion.effects.get(CelestialImpetusAura)

        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101
        assert ci_aura is not None  # noqa: S101

        ##################
        # Variables
        ##################

        # 0: baseline
        # 1: prepare EH burst
        # 2: start EH burst
        # 3: EH burst: maintain
        rotation_state: Literal[0, 1, 2, 3] = 0

        def enemy_actual_ttl() -> float:
            return state.main_target.time_to_live - state.time

        def update_rotation_state(s: Any) -> None:
            nonlocal rotation_state

            match rotation_state:
                case 0:
                    # switch from baseline to prepare when grace almost ready
                    if elarion.skystrider_grace.cooldown <= 20:
                        rotation_state = 1
                    if enemy_actual_ttl() < elarion.skystrider_grace.cooldown and elarion.event_horizon.can_cast():
                        rotation_state = 1

                case 1:
                    # Stop preparing when grace + hsb is ready
                    if elarion.skystrider_grace.can_cast() and elarion.lunarlight_mark.can_cast():
                        rotation_state = 2
                    if enemy_actual_ttl() < elarion.skystrider_grace.cooldown and elarion.lunarlight_mark.can_cast():
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

        def final_crescendo_ready() -> bool:
            fc = elarion.effects.get(FinalCrescendo)
            return elarion.highwind_arrow.can_cast() and fc is not None and fc.stacks == fc.max_stacks

        ##################
        # Custom actions
        ##################

        voidbringers__dont_overlap = Optional(
            elarion.voidbringers_touch, lambda s: not state.main_target.effects.has(VoidbringersTouchEffect)
        )

        hwa_if_at_max_charges = Optional(
            elarion.highwind_arrow,
            lambda s: (
                (not self.keep_highwind_arrow_off_cooldown)
                and elarion.highwind_arrow.charges == elarion.highwind_arrow.max_charges
            ),
        )

        def enemy_shimmer_duration() -> float:
            shimmer = state.main_target.effects.get(Shimmer)
            return shimmer.duration if shimmer is not None else 0

        hwa_keep_shimmer_alive = Optional(
            elarion.highwind_arrow,
            lambda s: enemy_shimmer_duration() <= 3,
        )

        single_target_priority_list = PriorityList([
            elarion.skystrider_supremacy,
            Optional(elarion.lunarlight_mark, lambda s: rotation_state != 1 and final_crescendo_ready()),
            Optional(elarion.highwind_arrow, lambda s: elarion.highwind_arrow.has_resurgent_winds_buff),
            hwa_if_at_max_charges,
            hwa_keep_shimmer_alive,
            Optional(
                elarion.highwind_arrow, lambda s: elarion.lunarlight_mark.can_cast() and not final_crescendo_ready()
            ),
            elarion.volley,
            elarion.heartseeker_barrage,
            elarion.highwind_arrow,
            Optional(
                elarion.focused_shot,
                lambda s: (
                    (
                        elarion.focus <= 38
                        and (
                            elarion.volley.cooldown <= 1.5
                            or elarion.heartseeker_barrage.cooldown <= 1.5
                            or (elarion.highwind_arrow.charges == 2 and elarion.highwind_arrow.cooldown <= 1.5)
                        )
                    )
                    or ((elarion.focus <= 18) and elarion.multishot.is_empowered())
                ),
            ),
            Optional(elarion.focused_shot, lambda s: ci_aura.real_ppm.proc_chance >= 1),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            elarion.skystrider_supremacy,
            Optional(elarion.lunarlight_mark, lambda s: rotation_state != 1 and final_crescendo_ready()),
            Optional(elarion.highwind_arrow, lambda s: elarion.highwind_arrow.has_resurgent_winds_buff),
            hwa_if_at_max_charges,
            hwa_keep_shimmer_alive,
            Optional(
                elarion.highwind_arrow, lambda s: elarion.lunarlight_mark.can_cast() and not final_crescendo_ready()
            ),
            elarion.heartseeker_barrage,
            elarion.volley,
            elarion.highwind_arrow,
            Optional(
                elarion.focused_shot,
                lambda s: (
                    (
                        elarion.focus <= 38
                        and (
                            elarion.volley.cooldown <= 1.5
                            or elarion.heartseeker_barrage.cooldown <= 1.5
                            or (elarion.highwind_arrow.charges == 2 and elarion.highwind_arrow.cooldown <= 1.5)
                        )
                    )
                    or ((elarion.focus <= 18) and elarion.multishot.is_empowered())
                    or (
                        elarion.focus <= 28 and (not elarion.multishot.is_empowered() and elarion.multishot.charges > 0)
                    )
                ),
            ),
            Optional(elarion.focused_shot, lambda s: ci_aura.real_ppm.proc_chance >= 1),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        prepare_ultimate_priority_list = PriorityList([
            elarion.skystrider_supremacy,
            elarion.volley,
            # elarion.highwind_arrow,
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
            Optional(elarion.lunarlight_mark, lambda s: final_crescendo_ready()),
            Optional(elarion.highwind_arrow, lambda s: elarion.highwind_arrow.has_resurgent_winds_buff),
            elarion.volley,
            Optional(elarion.heartseeker_barrage, lambda s: elarion.volley.cooldown >= 3.0),
            Optional(
                elarion.highwind_arrow,
                lambda s: (  # Check that we don't lose a cast by casting HWA at exactly the wrong time
                    elarion.focus >= 30 or elarion.effects.get(EventHorizonBuff).duration >= 1.5  # ty:ignore[unresolved-attribute]
                ),
            ),
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered() or use_aoe_abilities()),
            elarion.heartseeker_barrage,  # Cast HSB even if volley CD is low
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        grouped_prio = PriorityList([
            update_rotation_state,
            Optional(prepare_ultimate_priority_list, lambda s: use_aoe_abilities() and rotation_state == 1),
            Optional(ultimate_start, lambda s: rotation_state == 2),
            Optional(ultimate_ongoing, lambda s: rotation_state == 3),
            Optional(aoe_target_priority_list, lambda s: use_aoe_abilities()),
            single_target_priority_list,
        ])

        while True:
            yield grouped_prio(state)


class HwaSimple(Rotation[Elarion]):
    description = """
    An AOE rotation for neck barrage, using the method.gg priority list.
    """

    def __call__(self, elarion: Elarion) -> Iterator[Ability | None]:
        state = elarion.state

        assert elarion.skystrider_supremacy.is_fervent_supremacy  # noqa: S101
        assert isinstance(elarion.voidbringers_touch, VoidbringersTouch)  # noqa: S101

        ##################
        # Custom actions
        ##################

        voidbringers__dont_overlap = Optional(
            elarion.voidbringers_touch, lambda s: not state.main_target.effects.has(VoidbringersTouchEffect)
        )

        hwa_if_at_max_charges = Optional(
            elarion.highwind_arrow,
            lambda s: elarion.highwind_arrow.charges == elarion.highwind_arrow.max_charges,
        )

        def enemy_shimmer_duration() -> float:
            shimmer = state.main_target.effects.get(Shimmer)
            return shimmer.duration if shimmer is not None else 0

        def use_aoe_abilities() -> bool:
            return state.num_enemies >= 4

        hwa_keep_shimmer_alive = Optional(
            elarion.highwind_arrow,
            lambda s: enemy_shimmer_duration() <= 3,
        )

        def final_crescendo_ready() -> bool:
            fc = elarion.effects.get(FinalCrescendo)
            return elarion.highwind_arrow.can_cast() and fc is not None and fc.stacks == fc.max_stacks

        dont_send_fc_just_before_llm = lambda s: not (elarion.lunarlight_mark.cooldown <= 5 and final_crescendo_ready())

        single_target_priority_list = PriorityList([
            voidbringers__dont_overlap,
            elarion.event_horizon,
            Optional(elarion.skystrider_grace, lambda s: not elarion.effects.has(SpiritOfHeroism)),
            elarion.skystrider_supremacy,
            Optional(elarion.lunarlight_mark, lambda s: final_crescendo_ready()),
            Optional(
                PriorityList([
                    Optional(
                        elarion.highwind_arrow,
                        lambda s: elarion.lunarlight_mark.cooldown <= 5 and not final_crescendo_ready(),
                    ),
                    Optional(elarion.highwind_arrow, lambda s: elarion.highwind_arrow.has_resurgent_winds_buff),
                    hwa_if_at_max_charges,
                    hwa_keep_shimmer_alive,
                ]),
                dont_send_fc_just_before_llm,
            ),
            elarion.volley,
            elarion.heartseeker_barrage,
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered()),
            Optional(elarion.highwind_arrow, dont_send_fc_just_before_llm),
            Optional(
                elarion.focused_shot,
                lambda s: (
                    (
                        elarion.focus <= 38
                        and (
                            elarion.volley.cooldown <= 1.5
                            or elarion.heartseeker_barrage.cooldown <= 1.5
                            or (elarion.highwind_arrow.charges == 2 and elarion.highwind_arrow.cooldown <= 1.5)
                        )
                    )
                    or ((elarion.focus <= 18) and elarion.multishot.is_empowered())
                    or (
                        elarion.focus <= 28 and (not elarion.multishot.is_empowered() and elarion.multishot.charges > 0)
                    )
                ),
            ),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        aoe_target_priority_list = PriorityList([
            voidbringers__dont_overlap,
            elarion.event_horizon,
            Optional(elarion.skystrider_grace, lambda s: not elarion.effects.has(SpiritOfHeroism)),
            elarion.skystrider_supremacy,
            Optional(elarion.lunarlight_mark, lambda s: final_crescendo_ready()),
            Optional(
                PriorityList([
                    Optional(
                        elarion.highwind_arrow,
                        lambda s: elarion.lunarlight_mark.cooldown <= 5 and not final_crescendo_ready(),
                    ),
                    Optional(elarion.highwind_arrow, lambda s: elarion.highwind_arrow.has_resurgent_winds_buff),
                    hwa_if_at_max_charges,
                    hwa_keep_shimmer_alive,
                ]),
                dont_send_fc_just_before_llm,
            ),
            elarion.heartseeker_barrage,
            elarion.volley,
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered()),
            elarion.multishot,
            Optional(elarion.highwind_arrow, dont_send_fc_just_before_llm),
            Optional(
                elarion.focused_shot,
                lambda s: (
                    (
                        elarion.focus <= 38
                        and (
                            elarion.volley.cooldown <= 1.5
                            or elarion.heartseeker_barrage.cooldown <= 1.5
                            or (elarion.highwind_arrow.charges == 2 and elarion.highwind_arrow.cooldown <= 1.5)
                        )
                    )
                    or ((elarion.focus <= 18) and elarion.multishot.is_empowered())
                    or (
                        elarion.focus <= 28 and (not elarion.multishot.is_empowered() and elarion.multishot.charges > 0)
                    )
                ),
            ),
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        ultimate_ongoing = PriorityList([
            voidbringers__dont_overlap,
            elarion.skystrider_supremacy,
            Optional(elarion.lunarlight_mark, lambda s: final_crescendo_ready()),
            Optional(elarion.highwind_arrow, lambda s: elarion.highwind_arrow.has_resurgent_winds_buff),
            elarion.volley,
            Optional(elarion.heartseeker_barrage, lambda s: elarion.volley.cooldown >= 3.0),
            Optional(
                elarion.highwind_arrow,
                lambda s: (  # Check that we don't lose a cast by casting HWA at exactly the wrong time
                    elarion.focus >= 30 or elarion.effects.get(EventHorizonBuff).duration >= 1.5  # ty:ignore[unresolved-attribute]
                ),
            ),
            Optional(elarion.multishot, lambda s: elarion.multishot.is_empowered() or use_aoe_abilities()),
            elarion.heartseeker_barrage,  # Cast HSB even if volley CD is low
            elarion.celestial_shot,
            elarion.focused_shot,
        ])

        grouped_prio = PriorityList([
            Optional(ultimate_ongoing, lambda s: elarion.effects.has(EventHorizonBuff)),
            Optional(aoe_target_priority_list, lambda s: use_aoe_abilities()),
            single_target_priority_list,
        ])

        while True:
            yield grouped_prio(state)
