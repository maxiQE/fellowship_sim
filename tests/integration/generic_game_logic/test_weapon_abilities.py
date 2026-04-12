"""Integration tests — weapon ability mechanics.

Tests that VoidbringersTouch, Chronoshift, NaturesFury, and IciclesOfAnzhyr
compose correctly with the event bus, damage pipeline, and stat system.
"""

import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.events import AbilityDamage, AbilityPeriodicDamage
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.generic_game_logic.weapon_abilities import (
    Chronoshift,
    ChronoshiftChannelCDR,
    CurseOfAnzhyr,
    IciclesOfAnzhyr,
    NaturesFury,
    VoidbringersTouch,
    VoidbringersTouchEffect,
)
from tests.integration.fixtures import FixedRNG


class TestVoidbringersTouch:
    """VoidbringersTouch: absorbs 10% of owner damage, explodes at max or on expiry."""

    @pytest.fixture
    def state_1e(self) -> tuple[State, Elarion, Enemy, VoidbringersTouch]:
        """One enemy, RNG never crits, Elarion with VBT weapon ability."""
        state = State(rng=FixedRNG(value=0.99))
        target = Enemy(state=state)
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))
        vbt = VoidbringersTouch(owner=elarion)
        elarion.weapon_ability = vbt
        elarion.voidbringers_touch = vbt
        return state, elarion, target, vbt

    def test_effect_applied_on_cast(self, state_1e: tuple[State, Elarion, Enemy, VoidbringersTouch]) -> None:
        """Casting VBT applies VoidbringersTouchEffect to the target."""
        state, elarion, target, vbt = state_1e
        vbt._do_cast(target)
        assert target.effects.has(VoidbringersTouchEffect)

    def test_absorbs_10_percent_of_owner_damage(
        self, state_1e: tuple[State, Elarion, Enemy, VoidbringersTouch]
    ) -> None:
        """Every damage event owned by the caster accumulates 10% in stored_damage."""
        state, elarion, target, vbt = state_1e
        vbt._do_cast(target)
        vbt_effect = target.effects.get(VoidbringersTouchEffect)
        assert isinstance(vbt_effect, VoidbringersTouchEffect)

        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)

        elarion.focused_shot._do_cast(target)
        state.advance_time(0.2)

        focused_hits = [e for e in damage_events if e.damage_source is elarion.focused_shot]
        assert len(focused_hits) == 1
        assert vbt_effect.stored_damage == pytest.approx(focused_hits[0].damage * 0.10)

    def test_explosion_fires_when_storage_fills(
        self, state_1e: tuple[State, Elarion, Enemy, VoidbringersTouch]
    ) -> None:
        """When stored_damage reaches max, removal is scheduled and explosion fires."""
        state, elarion, target, vbt = state_1e
        vbt._do_cast(target)
        vbt_effect = target.effects.get(VoidbringersTouchEffect)
        assert isinstance(vbt_effect, VoidbringersTouchEffect)

        explosion_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: explosion_events.append(e) if e.damage_source is vbt_effect else None,
        )

        vbt_effect.stored_damage = vbt_effect.max_stored_damage
        elarion.focused_shot._do_cast(target)
        state.advance_time(0.2)

        assert len(explosion_events) == 1

    def test_explosion_is_grievous_crit(self, state_1e: tuple[State, Elarion, Enemy, VoidbringersTouch]) -> None:
        """VBT explosion carries is_grievous_crit=True (crit_percent ≥ 1.0)."""
        state, elarion, target, vbt = state_1e
        vbt._do_cast(target)
        vbt_effect = target.effects.get(VoidbringersTouchEffect)
        assert isinstance(vbt_effect, VoidbringersTouchEffect)

        explosion_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: explosion_events.append(e) if e.damage_source is vbt_effect else None,
        )

        vbt_effect.stored_damage = vbt_effect.max_stored_damage
        elarion.focused_shot._do_cast(target)
        state.advance_time(0.2)

        assert len(explosion_events) == 1
        assert explosion_events[0].is_grievous_crit

    def test_renewal_keeps_stored_damage(self, state_1e: tuple[State, Elarion, Enemy, VoidbringersTouch]) -> None:
        """Re-applying VBT fuses the effect: stored_damage is preserved, duration resets."""
        state, elarion, target, vbt = state_1e
        vbt._do_cast(target)
        vbt_effect = target.effects.get(VoidbringersTouchEffect)
        assert isinstance(vbt_effect, VoidbringersTouchEffect)

        elarion.focused_shot._do_cast(target)
        state.advance_time(0.2)
        stored_before = vbt_effect.stored_damage
        assert stored_before > 0.0

        vbt._do_cast(target)

        assert vbt_effect.stored_damage == pytest.approx(stored_before)

    def test_explodes_on_expiry(self, state_1e: tuple[State, Elarion, Enemy, VoidbringersTouch]) -> None:
        """When the 15s duration expires, the explosion fires as a grievous crit."""
        state, elarion, target, vbt = state_1e
        vbt._do_cast(target)
        vbt_effect = target.effects.get(VoidbringersTouchEffect)
        assert isinstance(vbt_effect, VoidbringersTouchEffect)

        elarion.focused_shot._do_cast(target)
        state.advance_time(0.0)

        explosion_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: explosion_events.append(e) if e.damage_source is vbt_effect else None,
        )

        state.advance_time(16.0)

        assert len(explosion_events) == 1
        assert explosion_events[0].is_grievous_crit


class TestChronoshift:
    """Chronoshift: 3s channel, haste-scaled ticks, 9x CDR on all abilities during channel."""

    @pytest.fixture
    def state_1e(self) -> tuple[State, Elarion, Enemy, Chronoshift]:
        """One enemy, no crits, Elarion with Chronoshift weapon ability."""
        state = State(rng=FixedRNG(value=0.99))
        target = Enemy(state=state)
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))
        cs = Chronoshift(owner=elarion)
        elarion.weapon_ability = cs
        elarion.chronoshift = cs
        elarion.abilities.append(cs)
        return state, elarion, target, cs

    def test_channel_advances_time_by_3s(self, state_1e: tuple[State, Elarion, Enemy, Chronoshift]) -> None:
        """After the 3s channel completes, state.time == 3.0."""
        state, elarion, target, cs = state_1e
        cs.cast(target)
        assert state.time == pytest.approx(3.0)

    def test_fires_2_full_ticks_at_zero_haste(self, state_1e: tuple[State, Elarion, Enemy, Chronoshift]) -> None:
        """At zero haste: tick_interval=1.5s, num_full_ticks=2, no partial tick."""
        state, elarion, target, cs = state_1e
        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)

        cs.cast(target)
        elarion.wait(0.2)

        cs_hits = [e for e in damage_events if e.damage_source is cs]
        assert state.time == pytest.approx(3.2)
        assert len(cs_hits) == 2

    def test_fires_3_full_ticks_with_haste(self) -> None:
        """At haste_percent=0.5: tick_interval=1.0s, num_full_ticks=3, no partial."""
        state = State(rng=FixedRNG(value=0.99))
        target = Enemy(state=state)
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=0.5))
        cs = Chronoshift(owner=elarion)
        elarion.weapon_ability = cs
        elarion.chronoshift = cs
        elarion.abilities.append(cs)

        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)
        cs.cast(target)
        elarion.wait(0.2)

        cs_hits = [e for e in damage_events if e.damage_source is cs]
        assert len(cs_hits) == 3

    def test_fires_partial_tick_at_fractional_haste(self) -> None:
        """At haste_percent=0.25: tick_interval=1.2s, 2 full ticks + 1 partial (0.5x damage)."""
        state = State(rng=FixedRNG(value=0.99))
        target = Enemy(state=state)
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0, haste_percent=0.25))
        cs = Chronoshift(owner=elarion)
        elarion.weapon_ability = cs
        elarion.chronoshift = cs
        elarion.abilities.append(cs)

        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)
        cs.cast(target)
        elarion.wait(0.2)

        cs_hits = [e for e in damage_events if e.damage_source is cs]
        assert len(cs_hits) == 3
        # partial tick = (3.0 % 1.2) / 1.2 = 0.5 of full tick
        assert cs_hits[-1].damage == pytest.approx(cs_hits[0].damage * 0.5)

    def test_cdr_effect_applied_after_do_cast(self, state_1e: tuple[State, Elarion, Enemy, Chronoshift]) -> None:
        """ChronoshiftChannelCDR is present on the owner immediately after _do_cast."""
        state, elarion, target, cs = state_1e
        cs._do_cast(target)
        assert elarion.effects.has(ChronoshiftChannelCDR)

    def test_cdr_multiplier_applied_to_abilities(self, state_1e: tuple[State, Elarion, Enemy, Chronoshift]) -> None:
        """With ChronoshiftChannelCDR active, ability CDR multiplier is greater than 1."""
        state, elarion, target, cs = state_1e
        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(1.0)

        elarion.effects.add(ChronoshiftChannelCDR(duration=3.0, owner=elarion))

        assert elarion.heartseeker_barrage._cdr_multiplier > 1.0

    def test_ability_drains_faster_during_channel(self, state_1e: tuple[State, Elarion, Enemy, Chronoshift]) -> None:
        """With CDR active, an ability at 24s cooldown fully drains in 3s channel."""
        state, elarion, target, cs = state_1e
        elarion.heartseeker_barrage.cooldown = 24.0
        cs.cast(target)
        assert elarion.heartseeker_barrage.cooldown <= 0.0

    def test_cdr_effect_removed_after_channel(self, state_1e: tuple[State, Elarion, Enemy, Chronoshift]) -> None:
        """ChronoshiftChannelCDR expires at channel end; CDR multiplier returns to 1."""
        state, elarion, target, cs = state_1e
        cs.cast(target)
        assert not elarion.effects.has(ChronoshiftChannelCDR)
        assert elarion.heartseeker_barrage._cdr_multiplier == pytest.approx(1.0)

    def test_hits_multiple_enemies(self) -> None:
        """Each tick hits all enemies up to the 12-enemy cap."""
        state = State(rng=FixedRNG(value=0.99))
        enemies = [Enemy(state=state) for _ in range(3)]
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))
        cs = Chronoshift(owner=elarion)
        elarion.weapon_ability = cs
        elarion.chronoshift = cs
        elarion.abilities.append(cs)

        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)
        cs.cast(enemies[0])
        elarion.wait(0.2)

        cs_hits = [e for e in damage_events if e.damage_source is cs]
        # 2 ticks × 3 enemies = 6 hits
        assert len(cs_hits) == 6
        target_ids_hit = {id(e.target) for e in cs_hits}
        assert target_ids_hit == {id(e) for e in enemies}


class TestNaturesFury:
    """NaturesFury: 2x main damage, up to 3 secondaries, +30% crit on all hits."""

    @pytest.fixture
    def state_5e(self) -> tuple[State, Elarion, list[Enemy], NaturesFury]:
        """Five enemies, no crits, Elarion with NaturesFury weapon ability."""
        state = State(rng=FixedRNG(value=0.99))
        enemies = [Enemy(state=state) for _ in range(5)]
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))
        nf = NaturesFury(owner=elarion)
        elarion.weapon_ability = nf
        elarion.natures_fury = nf
        return state, elarion, enemies, nf

    def test_main_target_takes_double_damage(self, state_5e: tuple[State, Elarion, list[Enemy], NaturesFury]) -> None:
        """Main target damage is 2x the secondary target damage (main_damage_multiplier=2.0)."""
        state, elarion, enemies, nf = state_5e
        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)

        nf._do_cast(enemies[0])
        state.advance_time(0.2)

        nf_hits = [e for e in damage_events if e.damage_source is nf]
        main_hit = next(e for e in nf_hits if e.target is enemies[0])
        secondary_hits = [e for e in nf_hits if e.target is not enemies[0]]
        assert len(secondary_hits) > 0
        assert main_hit.damage == pytest.approx(secondary_hits[0].damage * 2.0)

    def test_all_hits_gain_30_percent_crit(self) -> None:
        """NaturesFuryAura adds +30% crit: at RNG=0.29, NaturesFury crits but FocusedShot does not."""
        state = State(rng=FixedRNG(value=0.29))
        target = Enemy(state=state)
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0, crit_percent=0.0))
        nf = NaturesFury(owner=elarion)

        # FocusedShot: crit_percent=0.0, 0.29 ≥ 0.0 → no crit
        focused_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, focused_events.append)
        elarion.focused_shot._do_cast(target)
        state.advance_time(0.2)
        focused_hit = next(e for e in focused_events if e.damage_source is elarion.focused_shot)
        assert not focused_hit.is_crit

        # NaturesFury: effective crit_percent=0.0+0.30=0.30, 0.29 < 0.30 → crit
        nf_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, nf_events.append)
        nf._do_cast(target)
        state.advance_time(0.2)
        nf_hits = [e for e in nf_events if e.damage_source is nf]
        assert len(nf_hits) > 0
        assert all(e.is_crit for e in nf_hits)

    def test_hits_up_to_3_secondary_targets(self, state_5e: tuple[State, Elarion, list[Enemy], NaturesFury]) -> None:
        """With 5 enemies, NaturesFury hits main + exactly 3 secondary targets (4 total hits)."""
        state, elarion, enemies, nf = state_5e
        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(AbilityDamage, damage_events.append)

        nf._do_cast(enemies[0])
        state.advance_time(0.2)

        nf_hits = [e for e in damage_events if e.damage_source is nf]
        assert len(nf_hits) == 4
        target_ids_hit = {id(e.target) for e in nf_hits}
        assert len(target_ids_hit) == 4

    def test_cast_time_is_1_5s(self, state_5e: tuple[State, Elarion, list[Enemy], NaturesFury]) -> None:
        """NaturesFury.cast() advances time by 1.5s (base_cast_time, not haste-scaled for test)."""
        state, elarion, enemies, nf = state_5e
        elarion.weapon_ability = nf
        elarion.abilities.append(nf)
        nf.cast(enemies[0])
        assert state.time == pytest.approx(1.5)


class TestIciclesOfAnzhyr:
    """IciclesOfAnzhyr: 3 waves, final wave applies CurseOfAnzhyr, cursed targets take +200% damage."""

    @pytest.fixture
    def state_2e(self) -> tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]:
        """Two enemies, no crits, Elarion with IciclesOfAnzhyr weapon ability."""
        state = State(rng=FixedRNG(value=0.99))
        enemies = [Enemy(state=state), Enemy(state=state)]
        elarion = Elarion(state=state, raw_stats=RawStatsFromPercents(main_stat=1000.0))
        icicles = IciclesOfAnzhyr(owner=elarion)
        elarion.weapon_ability = icicles
        elarion.icicles_of_anzhyr = icicles
        return state, elarion, enemies, icicles

    def test_fires_3_waves(self, state_2e: tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]) -> None:
        """Three waves of damage fire, one per second after cast."""
        state, elarion, enemies, icicles = state_2e
        wave_times: list[float] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: wave_times.append(state.time) if e.damage_source is icicles else None,
        )

        icicles._do_cast(enemies[0])
        state.advance_time(4.0)

        # Wave times (per enemy): at 1.0, 2.0, 3.0 (two enemies → 6 events, repeated times)
        unique_times = sorted(set(wave_times))
        assert unique_times == pytest.approx([1.0, 2.0, 3.0])

    def test_third_wave_applies_curse(self, state_2e: tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]) -> None:
        """After the 3rd wave fires, every target has CurseOfAnzhyr."""
        state, elarion, enemies, icicles = state_2e
        icicles._do_cast(enemies[0])
        state.advance_time(4.0)

        for enemy in enemies:
            assert enemy.effects.has(CurseOfAnzhyr)

    def test_first_two_waves_do_not_apply_curse(
        self, state_2e: tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]
    ) -> None:
        """Curse is not present before the 3rd wave fires (at t=2.5, after waves 1 and 2)."""
        state, elarion, enemies, icicles = state_2e
        icicles._do_cast(enemies[0])
        state.advance_time(2.5)

        for enemy in enemies:
            assert not enemy.effects.has(CurseOfAnzhyr)

    def test_cursed_target_takes_3x_direct_damage(
        self, state_2e: tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]
    ) -> None:
        """Targets with CurseOfAnzhyr take +200% damage (3x) from IciclesOfAnzhyr hits."""
        state, elarion, enemies, icicles = state_2e

        wave_hits: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: wave_hits.append(e) if e.damage_source is icicles else None,
        )

        # First cast: wave 1 hits before curse (uncursed baseline), wave 3 applies curse
        icicles._do_cast(enemies[0])
        state.advance_time(4.0)
        uncursed_damage = wave_hits[0].damage  # wave 1, first enemy, no curse yet
        wave_hits.clear()

        # Second cast: wave 1 now hits cursed enemies → 3x damage
        icicles._do_cast(enemies[0])
        state.advance_time(4.0)
        cursed_damage = wave_hits[0].damage

        assert cursed_damage == pytest.approx(uncursed_damage * 3.0)

    def test_curse_reapplication_is_noop(self, state_2e: tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]) -> None:
        """Re-applying CurseOfAnzhyr via the 3rd wave of a second cast is a no-op (fuse ignored)."""
        state, elarion, enemies, icicles = state_2e
        icicles._do_cast(enemies[0])
        state.advance_time(4.0)

        curse_before = enemies[0].effects.get(CurseOfAnzhyr)
        assert isinstance(curse_before, CurseOfAnzhyr)

        # Second cast re-applies curse (no-op fuse)
        icicles._do_cast(enemies[0])
        state.advance_time(4.0)

        curse_after = enemies[0].effects.get(CurseOfAnzhyr)
        assert curse_after is curse_before  # same object, not replaced

    def test_curse_ticks_as_periodic_damage(
        self, state_2e: tuple[State, Elarion, list[Enemy], IciclesOfAnzhyr]
    ) -> None:
        """CurseOfAnzhyr fires AbilityPeriodicDamage events as a DoT after being applied."""
        state, elarion, enemies, icicles = state_2e
        icicles._do_cast(enemies[0])
        state.advance_time(4.0)

        periodic_events: list[AbilityPeriodicDamage] = []
        state.bus.subscribe(
            AbilityPeriodicDamage,
            lambda e: periodic_events.append(e) if isinstance(e.damage_source, CurseOfAnzhyr) else None,
        )

        state.advance_time(7.0)

        assert len(periodic_events) >= 1
        assert all(e.damage > 0 for e in periodic_events)
