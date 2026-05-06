from collections.abc import Iterator
from dataclasses import dataclass

from fellowship_sim.base_classes import Ability, WeaponAbilityNotInitialized
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism
from fellowship_sim.rime.effect import WrathOfWinterEffect
from fellowship_sim.rime.entity import Rime
from fellowship_sim.simulation.base import Rotation
from fellowship_sim.simulation.rotation import Optional, PriorityList


@dataclass(kw_only=True)
class RimeSpender(Rotation[Rime]):
    description = """
    A basic rotation for Rime:
    - keep Cold Snap off cooldown
    - pool resources for WE window
    """

    num_enemies_aoe: int = 4

    def __call__(self, rime: Rime) -> Iterator[Ability | None]:
        state = rime.state

        assert not isinstance(rime.weapon_ability, WeaponAbilityNotInitialized)  # noqa: S101

        ##################
        # Variables
        ##################

        def use_aoe_abilities() -> bool:
            return state.num_enemies >= self.num_enemies_aoe

        def at_max_winter_orbs(*args: object) -> bool:
            return rime.winter_orbs >= rime.max_winter_orbs

        ##################
        # Custom actions
        ##################

        cold_snap_at_max_charges = Optional(
            rime.cold_snap, lambda s: rime.cold_snap.charges == rime.cold_snap.max_charges
        )

        ##################
        # Priority lists
        ##################

        single_target_we = PriorityList([
            Optional(rime.glacial_blast, lambda s: rime.winters_embrace_duration >= rime.glacial_blast.cast_time),
            rime.cold_snap,
            rime.freezing_torrent,
            rime.frost_bolt,
        ])

        single_target_priority_list = PriorityList([
            Optional(rime.wrath_of_winter, lambda s: not rime.effects.has(SpiritOfHeroism)),
            Optional(rime.ice_blitz, lambda s: rime.effects.has(WrathOfWinterEffect)),
            Optional(rime.winters_blessing, lambda s: rime.effects.has(WrathOfWinterEffect)),
            Optional(rime.flight_of_the_navir, lambda s: rime.effects.has(WrathOfWinterEffect)),
            Optional(single_target_we, lambda s: rime.winters_embrace_duration > 0),
            Optional(rime.glacial_blast, at_max_winter_orbs),
            cold_snap_at_max_charges,
            rime.bursting_ice,
            rime.freezing_torrent,
            rime.weapon_ability,
            rime.frost_bolt,
        ])

        aoe_we = PriorityList([
            rime.ice_comet,
            rime.cold_snap,
            rime.freezing_torrent,
            rime.frost_bolt,
        ])

        aoe_target_priority_list = PriorityList([
            Optional(rime.wrath_of_winter, lambda s: not rime.effects.has(SpiritOfHeroism)),
            Optional(rime.ice_blitz, lambda s: rime.effects.has(WrathOfWinterEffect)),
            Optional(rime.winters_blessing, lambda s: rime.effects.has(WrathOfWinterEffect)),
            Optional(rime.flight_of_the_navir, lambda s: rime.effects.has(WrathOfWinterEffect)),
            Optional(aoe_we, lambda s: rime.winters_embrace_duration > 0),
            Optional(rime.ice_comet, at_max_winter_orbs),
            cold_snap_at_max_charges,
            rime.bursting_ice,
            rime.freezing_torrent,
            rime.weapon_ability,
            rime.frost_bolt,
        ])

        grouped_prio = PriorityList([
            Optional(aoe_target_priority_list, lambda s: use_aoe_abilities()),
            single_target_priority_list,
        ])

        while True:
            yield grouped_prio(state)
