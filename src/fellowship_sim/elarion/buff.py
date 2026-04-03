from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

from fellowship_sim.base_classes.effect import Buff, Effect
from fellowship_sim.base_classes.events import (
    AbilityDamage,
    ComputeCooldownReduction,
    PreDamageSnapshotUpdate,
)
from fellowship_sim.base_classes.stats import (
    HastePercentAdditive,
    StatModifier,
)

if TYPE_CHECKING:
    from .entity import Elarion


@dataclass(kw_only=True, repr=False)
class SkystriderGraceBuff(Buff):
    """+30% haste for 20 s."""

    name: str = field(default="skystrider_grace", init=False)
    duration: float = field(default=20.0, init=False)

    def stat_modifiers(self) -> list[StatModifier]:
        return [HastePercentAdditive(value=0.30)]


@dataclass(kw_only=True, repr=False)
class EventHorizonBuff(Effect):
    """+20% damage, CDA=haste, focus cost x0.5 for 20s.

    While active:
    - Scales all ability damage by x1.20 via PreDamageSnapshotUpdate.
    - Adds character haste to CDA for all abilities (stacks with has_hasted_cdr).
    - Halves the focus cost of all abilities.
    - Each HighwindArrow hit reduces HeartseekerBarrage cooldown by 0.5s.
    - Each HeartseekerBarrage hit reduces Volley cooldown by 1s.
    """

    owner: "Elarion" = field(init=True)

    name: str = field(default="event_horizon", init=False)
    duration: float = field(default=20.0, init=False)

    def on_add(self) -> None:
        from fellowship_sim.base_classes.state import get_state

        bus = get_state().bus
        bus.subscribe(ComputeCooldownReduction, self._on_compute_cdr, owner=self)
        bus.subscribe(AbilityDamage, self._on_any_ability_damage, owner=self)
        bus.subscribe(PreDamageSnapshotUpdate, self._on_pre_damage, owner=self)

        self.owner.event_horizon__reduce_focust_cost = True

        self.owner._recalculate_cdr_multipliers()

    def on_remove(self) -> None:
        self.owner.event_horizon__reduce_focust_cost = False

        self.owner._recalculate_cdr_multipliers()

    def _on_pre_damage(self, event: PreDamageSnapshotUpdate) -> None:
        event.snapshot = event.snapshot.scale_average_damage(1.20)
        logger.trace("Event Horizon: damage x1.20")

    def _on_compute_cdr(self, event: ComputeCooldownReduction) -> None:
        haste = self.owner.stats.haste_percent
        event.cda_modifiers.append(haste)
        logger.trace("Event Horizon: CDA += {:.2f}", haste)

    def _on_any_ability_damage(self, event: AbilityDamage) -> None:
        from .ability import HeartseekerBarrage, HighwindArrow

        if isinstance(event.damage_source, HighwindArrow):
            barrage = self.owner.heartseeker_barrage
            barrage._reduce_cooldown(0.5)
            logger.trace("Event Horizon: Highwind Arrow hit → barrage CD -0.5s (now {:.2f}s)", barrage.cooldown)

        elif isinstance(event.damage_source, HeartseekerBarrage):
            volley = self.owner.volley
            volley._reduce_cooldown(1.0)
            logger.trace("Event Horizon: barrage hit → volley CD -1.0s (now {:.2f}s)", volley.cooldown)


# ---------------------------------------------------------------------------
# Empowered Multishot provider buffs
#
# Each provider registers with Multishot.register_empowered_provider and exposes:
#   consume_priority  — ClassVar[int]; lower = consumed first when multiple are active
#   apply_to_cast(event) — applies cast-time modifiers (arrows, damage %)
#   consume_charge()  — decrements own charge; removes self when empty
# ---------------------------------------------------------------------------


@dataclass(kw_only=True, repr=False)
class EmpoweredMultishotProvider(Effect):
    """Protocol satisfied by all empowered-Multishot provider buffs.

    consume_priority: lower value → consumed first when multiple providers coexist.
    apply_to_cast: applies cast-time modifiers (arrows, damage bonuses) to the event.
    consume_charge: decrements the provider's own charge; removes itself when exhausted.
    """

    owner: "Elarion" = field(init=True)

    damage_multiplier: float = field(default=1, init=False)
    consume_priority: int  # Lowest is consumed first; supremacy buffs have priority over empowered MS from FE

    def on_add(self) -> None:
        ms = self.owner.multishot
        ms.register_empowered_provider(self)

    def on_remove(self) -> None:
        ms = self.owner.multishot
        ms.unregister_empowered_provider(self)

    def consume_charge(self) -> None:
        self.stacks -= 1
        logger.debug(f"{self.name.replace('_', ' ')}: charge consumed ({self.stacks} remaining)")
        if self.stacks <= 0:
            self.remove()


@dataclass(kw_only=True, repr=False)
class SkystriderSupremacyBuff(EmpoweredMultishotProvider):
    """4s timed buff: infinite empowered Multishot casts (3+ arrows, no extra damage).
    Consumed last among active providers; expires naturally by duration.
    """

    name: str = field(default="skystrider_supremacy", init=False)
    duration: float = field(default=4.0, init=False)
    consume_priority: int = field(default=0, init=False)  # highest priority

    def consume_charge(self) -> None:
        pass  # infinite charges; buff expires by duration


@dataclass(kw_only=True, repr=False)
class FerventSupremacyBuff(EmpoweredMultishotProvider):
    """Charge buff: up to 4 empowered Multishot casts (+50% damage). Consumed first."""

    name: str = field(default="fervent_supremacy", init=False)
    duration: float = field(default=15.0, init=False)
    stacks: int = field(default=4, init=False)
    max_stacks: int = field(default=4, init=False)

    damage_multiplier: float = field(default=1.25, init=False)
    consume_priority: int = field(default=0, init=False)  # highest priority


@dataclass(kw_only=True, repr=False)
class EmpoweredMultishotChargeBuff(EmpoweredMultishotProvider):
    """Charge buff: up to 2 empowered Multishot casts (3+ arrows). 15s duration.
    Consumed after both supremacy buffs.
    """

    name: str = field(default="empowered_multishot_charge", init=False)
    duration: float = field(default=15.0, init=False)
    stacks: int = field(default=1, init=False)
    max_stacks: int = field(default=2, init=False)

    consume_priority: int = field(default=1, init=False)  # after the supremacy empowered MS
