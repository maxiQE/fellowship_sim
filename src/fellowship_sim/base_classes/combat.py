from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger

from .events import AbilityDamage, AbilityPeriodicDamage, PreDamageSnapshotUpdate
from .state import State, get_state
from .stats import SnapshotStats
from .timed_events import DelayedDamage

if TYPE_CHECKING:
    from .ability import Ability
    from .effect import Effect
    from .entity import Entity, Player


def schedule_damage(
    state: State,
    snapshot: SnapshotStats,
    damage_origin: "Ability | Effect",
    target: "Entity",
    delay: float = 0.0,
    *,
    cast_specific_predamage_snapshot_modifiers: "list[Callable[..., None]] | None" = None,
    owner: "Entity | None" = None,
) -> None:
    """Schedule a deal_damage call at state.time + delay."""

    def _fire() -> None:
        logger.trace(f"damage tick firing: {damage_origin} at t={get_state().time:.3f}")
        deal_damage(snapshot, damage_origin, target, cast_specific_predamage_snapshot_modifiers)

    state.schedule(time_delay=delay, callback=DelayedDamage(damage_source=damage_origin, callback=_fire))


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
    state = get_state()

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
    target: "Entity",
    base_damage: float,
    *,
    main_damage_multiplier: float = 1.0,
    num_secondary_targets: int = 0,
    secondary_damage_multiplier: float = 1.0,
    cast_specific_predamage_snapshot_modifiers: "list[Callable[..., None]] | None" = None,
    priority_func: Callable[["Entity"], float] | None = None,
) -> None:
    """Schedule main and secondary damage hits given a character and a base damage.

    Main hit is scaled by main_damage_multiplier; each secondary hit by secondary_damage_multiplier.
    Up to num_secondary_targets additional enemies are selected randomly (excluding main target).
    Works for both ability casts and proc effects — callers are responsible for snapshot construction.
    """

    snapshot = SnapshotStats.from_base_damage_and_character(base_damage=base_damage, character=owner)

    main_snapshot = snapshot.scale_average_damage(main_damage_multiplier) if main_damage_multiplier != 1.0 else snapshot
    schedule_damage(
        state,
        main_snapshot,
        damage_source,
        target,
        owner=owner,
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
            schedule_damage(state, secondary_snapshot, damage_source, secondary, owner=owner)
