from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger

from fellowship_sim.base_classes.timed_events import DelayedDamage

from .events import AbilityDamage, AbilityPeriodicDamage, PreDamageSnapshotUpdate
from .state import State
from .stats import SnapshotStats

if TYPE_CHECKING:
    from .ability import Ability
    from .effect import Effect
    from .entity import Entity, Player


def compute_damage(snapshot: SnapshotStats, rng_roll: float) -> tuple[float, bool, bool]:
    """Compute (damage, is_crit, is_grievous_crit) from a snapshot and a pre-rolled value.

    When crit_percent >= 1.0 the hit is grievous: guaranteed crit with damage scaled by
    (1 + crit_percent) * crit_multiplier instead of the usual 2 * crit_multiplier.
    rng_roll is only used for the normal (non-grievous) crit check.
    """
    is_grievous_crit = snapshot.crit_percent >= 1.0
    if is_grievous_crit:
        return snapshot.average_damage * (1 + snapshot.crit_percent) * snapshot.crit_multiplier, True, True

    is_crit = rng_roll < snapshot.crit_percent
    crit_multiplier = 2 * snapshot.crit_multiplier if is_crit else 1
    damage = snapshot.average_damage * crit_multiplier
    return damage, is_crit, False


def deal_damage(
    snapshot: SnapshotStats,
    damage_origin: "Ability | Effect",
    target: "Entity",
    cast_specific_predamage_snapshot_modifiers: "list[Callable[..., None]] | None" = None,
    is_dot: bool = False,
) -> "AbilityDamage | AbilityPeriodicDamage":
    state = damage_origin.owner.state

    # Give global listeners and cast-specific closures a chance to update the snapshot.
    pre_event = PreDamageSnapshotUpdate(
        damage_source=damage_origin,
        target=target,
        snapshot=snapshot,
        is_dot=is_dot,
        predamage_snapshot_modifiers=list(cast_specific_predamage_snapshot_modifiers)
        if cast_specific_predamage_snapshot_modifiers
        else [],
    )
    state.bus.emit(pre_event)
    snapshot = pre_event.finalize()

    _roll = state.rng.random()
    damage, is_crit, is_grievous_crit = compute_damage(snapshot=snapshot, rng_roll=_roll)
    if is_grievous_crit:
        logger.trace(
            f"crit roll for {damage_origin}: grievous (crit_pct={snapshot.crit_percent:.3f}) → guaranteed crit"
        )
    else:
        logger.trace(
            f"crit roll for {damage_origin}: {_roll:.3f} < {snapshot.crit_percent:.3f} → {'crit' if is_crit else 'no crit'}"
        )

    logger.debug(
        "  damage detail: avg_base={:.0f}, crit={}, grievous={}, is_dot={}",
        snapshot.average_damage,
        is_crit,
        is_grievous_crit,
        is_dot,
    )

    # HP deduction and info-level logging happen inside AbilityDamage.__post_init__.
    if is_dot:
        event = AbilityPeriodicDamage(
            damage_source=damage_origin,
            owner=damage_origin.owner,
            target=target,
            is_crit=is_crit,
            is_grievous_crit=is_grievous_crit,
            damage=damage,
        )
    else:
        event = AbilityDamage(
            damage_source=damage_origin,
            owner=damage_origin.owner,
            target=target,
            is_crit=is_crit,
            is_grievous_crit=is_grievous_crit,
            damage=damage,
        )
    state.bus.emit(event)
    return event


def create_standard_damage(
    state: State,
    damage_source: "Ability | Effect",
    owner: "Player",
    target: "Entity | None",
    base_damage: float,
    *,
    delay_until_hit: float = 0.1,
    main_damage_multiplier: float = 1.0,
    num_secondary_targets: int = 0,
    secondary_damage_multiplier: float = 1.0,
    cast_specific_predamage_snapshot_modifiers: "list[Callable[..., None]] | None" = None,
    priority_func: Callable[["Entity"], float] | None = None,
    is_scaled_by_expertise: bool = True,
    is_scaled_by_main_stat: bool = True,
) -> None:
    """Schedule main and secondary damage hits given a character and a base damage.

    Main hit is scaled by main_damage_multiplier; each secondary hit by secondary_damage_multiplier.
    Up to num_secondary_targets additional enemies are selected randomly (excluding main target).
    Works for both ability casts and proc effects — callers are responsible for snapshot construction.
    """

    def callback() -> None:
        apply_standard_damage(
            state=state,
            damage_source=damage_source,
            owner=owner,
            target=target,
            base_damage=base_damage,
            main_damage_multiplier=main_damage_multiplier,
            num_secondary_targets=num_secondary_targets,
            secondary_damage_multiplier=secondary_damage_multiplier,
            cast_specific_predamage_snapshot_modifiers=cast_specific_predamage_snapshot_modifiers,
            priority_func=priority_func,
            is_scaled_by_expertise=is_scaled_by_expertise,
            is_scaled_by_main_stat=is_scaled_by_main_stat,
        )

    state.schedule(
        time_delay=delay_until_hit,
        callback=DelayedDamage(
            damage_source=damage_source,
            callback=callback,
        ),
    )


def apply_standard_damage(
    state: State,
    damage_source: "Ability | Effect",
    owner: "Player",
    target: "Entity | None",
    base_damage: float,
    *,
    main_damage_multiplier: float = 1.0,
    num_secondary_targets: int = 0,
    secondary_damage_multiplier: float = 1.0,
    cast_specific_predamage_snapshot_modifiers: "list[Callable[..., None]] | None" = None,
    priority_func: Callable[["Entity"], float] | None = None,
    is_scaled_by_expertise: bool = True,
    is_scaled_by_main_stat: bool = True,
) -> None:
    """Apply standard damage formula to main and secondary targets."""
    snapshot = SnapshotStats.from_base_damage_and_character(
        base_damage=base_damage,
        character=owner,
        is_scaled_by_expertise=is_scaled_by_expertise,
        is_scaled_by_main_stat=is_scaled_by_main_stat,
    )

    if target is not None:
        main_snapshot = (
            snapshot.scale_average_damage(main_damage_multiplier) if main_damage_multiplier != 1.0 else snapshot
        )
        deal_damage(
            main_snapshot,
            damage_source,
            target,
            cast_specific_predamage_snapshot_modifiers=cast_specific_predamage_snapshot_modifiers,
        )

    if num_secondary_targets > 0:
        secondary_snapshot = (
            snapshot.scale_average_damage(secondary_damage_multiplier)
            if secondary_damage_multiplier != 1.0
            else snapshot
        )
        for secondary in state.select_targets(
            main_target=target, num=num_secondary_targets, priority_func=priority_func
        ):
            deal_damage(
                secondary_snapshot,
                damage_source,
                secondary,
                cast_specific_predamage_snapshot_modifiers=cast_specific_predamage_snapshot_modifiers,
            )
