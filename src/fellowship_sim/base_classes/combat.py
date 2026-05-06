import math
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
    is_secondary: bool = False,
) -> "AbilityDamage | AbilityPeriodicDamage":
    """Resolve a single damage hit: fire PreDamageSnapshotUpdate, roll crit, emit the damage event.

    Args:
        snapshot: Pre-built snapshot with average_damage, crit stats.
        damage_origin: The ability or effect dealing the damage (determines the event type label).
        target: The entity taking the hit.
        cast_specific_predamage_snapshot_modifiers: Per-cast closures applied after bus listeners.
        is_dot: True for periodic (DoT) ticks; fires AbilityPeriodicDamage instead of AbilityDamage.

    Returns:
        The emitted damage event.
    """
    state = damage_origin.owner.state

    # Give global listeners and cast-specific closures a chance to update the snapshot.
    pre_event = PreDamageSnapshotUpdate(
        damage_source=damage_origin,
        target=target,
        snapshot=snapshot,
        is_dot=is_dot,
        is_secondary=is_secondary,
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
            is_secondary=is_secondary,
        )
    else:
        event = AbilityDamage(
            damage_source=damage_origin,
            owner=damage_origin.owner,
            target=target,
            is_crit=is_crit,
            is_grievous_crit=is_grievous_crit,
            damage=damage,
            is_secondary=is_secondary,
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
    num_targets_softcap: int = 12,
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

    snapshot = SnapshotStats.from_base_damage_and_character(
        base_damage=base_damage,
        character=owner,
        damage_source=damage_source,
        is_scaled_by_expertise=is_scaled_by_expertise,
        is_scaled_by_main_stat=is_scaled_by_main_stat,
    )

    def callback() -> None:
        apply_standard_damage(
            state=state,
            damage_source=damage_source,
            target=target,
            snapshot=snapshot,
            main_damage_multiplier=main_damage_multiplier,
            num_secondary_targets=num_secondary_targets,
            num_targets_softcap=num_targets_softcap,
            secondary_damage_multiplier=secondary_damage_multiplier,
            cast_specific_predamage_snapshot_modifiers=cast_specific_predamage_snapshot_modifiers,
            priority_func=priority_func,
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
    target: "Entity | None",
    snapshot: SnapshotStats,
    *,
    main_damage_multiplier: float = 1.0,
    num_secondary_targets: int = 0,
    num_targets_softcap: int = 12,
    secondary_damage_multiplier: float = 1.0,
    cast_specific_predamage_snapshot_modifiers: "list[Callable[..., None]] | None" = None,
    priority_func: Callable[["Entity"], float] | None = None,
) -> None:
    """Immediately deal damage to main and secondary targets from a pre-built snapshot.

    Unlike create_standard_damage, this is called at hit time (no scheduling).

    Args:
        state: The current simulation state.
        damage_source: Ability or effect originating the hit.
        target: Main target; if None, skips the primary hit.
        snapshot: Pre-built snapshot (base damage + stat scaling already applied).
        main_damage_multiplier: Damage multiplier for the primary hit.
        num_secondary_targets: How many additional targets to hit.
        secondary_damage_multiplier: Damage multiplier for each secondary hit.
        cast_specific_predamage_snapshot_modifiers: Per-cast closures applied at hit time.
        priority_func: Scoring function for secondary target selection.
    """
    if target is not None:
        num_targets_total = 1 + min(num_secondary_targets, state.num_enemies - 1)
    else:
        num_targets_total = min(num_secondary_targets, state.num_enemies)

    if num_targets_total > num_targets_softcap:
        softcap_damage_multiplier = math.sqrt(num_targets_softcap / num_targets_total)
        snapshot = snapshot.scale_average_damage(softcap_damage_multiplier)

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
                is_secondary=True,
            )
