import pytest

from fellowship_sim.base_classes import AbilityDamage, Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.buff import EventHorizonBuff
from fellowship_sim.elarion.setup import ElarionSetup
from fellowship_sim.generic_game_logic.buff import SpiritOfHeroism
from fellowship_sim.generic_game_logic.gems import FirstStrike, FirstStrikeBuff, HarmoniousSoulBuff
from fellowship_sim.generic_game_logic.setup_effect import (
    AncestralSurgeSetup,
    BlessingOfTheProphetSetup,
    BlessingOfTheVirtuosoSetup,
)
from fellowship_sim.generic_game_logic.weapon_traits import (
    DiamondStrike,
    DiamondStrikeEcho,
    RubyStorm,
    SapphireAurastonePulse,
)
from tests.conftest import FixedRNG


class TestSpiritOfHeroismModifiers:
    """Setup effects (gems) that modify Spirit of Heroism stats or behavior."""

    def test_blessing_of_virtuoso(self) -> None:
        """Test blessing of the virtuoso: more haste out of ult; normal 30% haste during ult."""
        for is_level_2 in [False, True]:
            state = State(rng=FixedRNG(value=0.0))
            Enemy(state=state)
            target = state.enemies[0]
            setup = ElarionSetup(
                raw_stats=RawStatsFromPercents(
                    main_stat=1000.0,
                    crit_percent=0.0,
                    expertise_percent=0.0,
                    haste_percent=0.0,
                    spirit_percent=0.0,
                ),
            )

            virtuoso_setup = BlessingOfTheVirtuosoSetup(is_level_2=is_level_2)
            setup.setup_effect_list.append(virtuoso_setup)

            elarion = setup.finalize(state)
            assert elarion.stats.haste_percent == 0.09 if is_level_2 else 0.03

            elarion.spirit_points = 100
            elarion.event_horizon.cast(target)

            assert elarion.effects.has(SpiritOfHeroism)
            assert elarion.effects.has(EventHorizonBuff)
            assert elarion.stats.haste_percent == pytest.approx(0.3)

    def test_ancestral_surge(self) -> None:
        """Test ancestral surge: raised max spirit points; more main stat during ult."""
        for is_level_2 in [False, True]:
            state = State(rng=FixedRNG(value=0.0))
            Enemy(state=state)
            target = state.enemies[0]
            setup = ElarionSetup(
                raw_stats=RawStatsFromPercents(
                    main_stat=1000.0,
                    crit_percent=0.0,
                    expertise_percent=0.0,
                    haste_percent=0.0,
                    spirit_percent=0.0,
                ),
            )

            ancestral_surge_setup = AncestralSurgeSetup(is_level_2=is_level_2)
            setup.setup_effect_list.append(ancestral_surge_setup)

            elarion = setup.finalize(state)
            assert elarion.max_spirit_points == 100 + (30 if is_level_2 else 10)

            elarion.spirit_points = 100
            elarion.event_horizon.cast(target)

            assert elarion.effects.has(SpiritOfHeroism)
            assert elarion.effects.has(EventHorizonBuff)
            assert elarion.stats.main_stat == pytest.approx(1000 * (1.24 if is_level_2 else 1.08))

    def test_blessing_of_the_prophet(self) -> None:
        """Test blessing of the prophet: reduced spirit point cost and increased SOH duration."""
        for is_level_2 in [False, True]:
            state = State(rng=FixedRNG(value=0.0))
            Enemy(state=state)
            target = state.enemies[0]
            setup = ElarionSetup(
                raw_stats=RawStatsFromPercents(
                    main_stat=1000.0,
                    crit_percent=0.0,
                    expertise_percent=0.0,
                    haste_percent=0.0,
                    spirit_percent=0.0,
                ),
            )

            prophet_setup = BlessingOfTheProphetSetup(is_level_2=is_level_2)
            setup.setup_effect_list.append(prophet_setup)

            elarion = setup.finalize(state)
            elarion.spirit_point_per_s = 0

            assert elarion.spirit_point_per_s == 0
            assert elarion.spirit_ability_cost == 100 - (15 if is_level_2 else 5)

            elarion.spirit_points = 100
            elarion.event_horizon.cast(target)

            assert elarion.spirit_points == (15 if is_level_2 else 5)

            soh = elarion.effects.get(SpiritOfHeroism)
            assert elarion.effects.has(EventHorizonBuff)
            assert soh.duration == pytest.approx(20 + (18 if is_level_2 else 6))

            elarion.wait(20 + (18 if is_level_2 else 6) - 0.1)
            assert elarion.effects.has(SpiritOfHeroism)

            elarion.wait(0.2)
            assert not elarion.effects.has(SpiritOfHeroism)


class TestGemProcs:
    @pytest.mark.parametrize("first_strike_level", [0, 1, 2])
    def test_emerald_judgement(self, first_strike_level: int) -> None:
        """Test that emerald judgement proc provides the First Strike buff at appropriate level."""
        rng = FixedRNG(value=1.0)
        state = State(rng=rng)
        Enemy(state=state)
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=0.0,
            ),
            master_trait="Emerald Judgement",
        )

        elarion = setup.finalize(state)

        if first_strike_level > 0:
            elarion.effects.add(FirstStrike(owner=elarion, is_level_2=first_strike_level == 2))

        elarion.celestial_shot.cast(target)

        assert (first_strike_level > 0) == elarion.effects.has(FirstStrikeBuff)

        elarion.wait(20)

        elarion.celestial_shot.cast(target)
        assert not elarion.effects.has(FirstStrikeBuff)

        # guarantee procs
        rng.value = 0.0

        elarion.celestial_shot.cast(target)

        assert (first_strike_level > 0) == elarion.effects.has(FirstStrikeBuff)

    @pytest.mark.parametrize("h_soul_stacks", [0, 2, 4])
    def test_diamond_strike(self, h_soul_stacks: int) -> None:
        """Diamond Strike proc applies DiamondStrikeEcho to the target; echo stacks amplify subsequent procs by 40% per stack."""
        # FixedRNG(0.5): too high for post-proc rPPM check (~0.01), so no cascade after each proc fires.
        rng = FixedRNG(value=0.5)
        state = State(rng=rng)
        Enemy(state=state)
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
            ),
            master_trait="Diamond Strike",
        )
        elarion = setup.finalize(state)

        if h_soul_stacks > 0:
            harmonious_soul = HarmoniousSoulBuff(owner=elarion, is_level_2=False)
            harmonious_soul.stacks = h_soul_stacks
            elarion.effects.add(harmonious_soul)

        ds = elarion.effects.get(DiamondStrike)
        assert ds is not None

        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: damage_events.append(e) if isinstance(e.damage_source, DiamondStrike) else None,
        )

        # First proc — no echo stacks on target yet
        ds._rppm.last_attempt_time = -10_000
        state.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=target,
                damage=1_000.0,
                is_crit=False,
                is_grievous_crit=False,
            )
        )
        elarion.wait(1.0)

        ds_echo: DiamondStrikeEcho | None = target.effects.get(DiamondStrikeEcho)
        assert ds_echo is not None
        assert ds_echo.stacks == 1
        assert len(damage_events) == 1
        assert damage_events[-1].damage == pytest.approx(
            2370 * (1 + h_soul_stacks * 0.35) * (1 + h_soul_stacks * 0.003)
        )

        # Second proc — 1 echo stack on target → damage × 1.40
        ds._rppm.last_attempt_time = -10_000
        state.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=target,
                damage=1_000.0,
                is_crit=False,
                is_grievous_crit=False,
            )
        )
        elarion.wait(1.0)

        ds_echo: DiamondStrikeEcho | None = target.effects.get(DiamondStrikeEcho)
        assert ds_echo is not None
        assert ds_echo.stacks == 2
        assert len(damage_events) == 2
        assert damage_events[-1].damage == pytest.approx(
            2370 * 1.40 * (1 + h_soul_stacks * 0.35) * (1 + h_soul_stacks * 0.003)
        )

        # 3rd proc — 2 echo stack on target → damage × 1.80
        ds._rppm.last_attempt_time = -10_000
        state.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=target,
                damage=1_000.0,
                is_crit=False,
                is_grievous_crit=False,
            )
        )
        elarion.wait(1.0)

        ds_echo: DiamondStrikeEcho | None = target.effects.get(DiamondStrikeEcho)
        assert ds_echo is not None
        assert ds_echo.stacks == 3
        assert len(damage_events) == 3
        assert damage_events[-1].damage == pytest.approx(
            2370 * 1.80 * (1 + h_soul_stacks * 0.35) * (1 + h_soul_stacks * 0.003)
        )

    def test_sapphire_aurastone(self) -> None:
        """SapphireAurastonePulse is active during Spirit of Heroism and pulses accumulated damage every 3s."""
        rng = FixedRNG(value=1.0)
        state = State(rng=rng)
        Enemy(state=state)
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=0.0,
            ),
            master_trait="Sapphire Aurastone",
        )
        elarion = setup.finalize(state)

        assert not elarion.effects.has(SapphireAurastonePulse)

        elarion.spirit_points = 100
        elarion.event_horizon.cast(target)

        assert elarion.effects.has(SpiritOfHeroism)
        sap = elarion.effects.get(SapphireAurastonePulse)
        assert sap is not None

        # Feed a known damage amount into the accumulator
        count = 4
        known_damage = 50_000.0
        for _ in range(count):
            state.bus.emit(
                AbilityDamage(
                    damage_source=elarion.focused_shot,
                    owner=elarion,
                    target=target,
                    damage=known_damage,
                    is_crit=False,
                    is_grievous_crit=False,
                )
            )
        expected_pulse = count * known_damage * sap.ratio

        pulse_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: pulse_events.append(e) if isinstance(e.damage_source, SapphireAurastonePulse) else None,
        )

        elarion.wait(5.0)  # first pulse fires 3s after SapphireAurastonePulse was added

        assert len(pulse_events) == 1
        assert pulse_events[-1].damage == pytest.approx(expected_pulse)

        elarion.wait(5.0)

        # no further pulse emmitted
        assert len(pulse_events) == 1

        count = 2
        known_damage = 20_000.0
        for _ in range(count):
            state.bus.emit(
                AbilityDamage(
                    damage_source=elarion.focused_shot,
                    owner=elarion,
                    target=target,
                    damage=known_damage,
                    is_crit=False,
                    is_grievous_crit=False,
                )
            )
        expected_pulse = count * known_damage * sap.ratio

        elarion.wait(5.0)  # first pulse fires 3s after SapphireAurastonePulse was added

        assert len(pulse_events) == 2
        assert pulse_events[-1].damage == pytest.approx(expected_pulse)

        elarion.wait(5.0)

        # no further pulse emmitted
        assert len(pulse_events) == 2

    @pytest.mark.parametrize("healthpoints", [100_000.0, 200_000.0, 300_000.0])
    @pytest.mark.parametrize("main_stat", [1000.0, 2444.0])
    @pytest.mark.parametrize("expertise_percent", [0.1, 0.2])
    def test_ruby_storm_scales_with_healthpoints(
        self, healthpoints: float, main_stat: float, expertise_percent: float
    ) -> None:
        """RubyStorm proc damage scales proportionally with caster healthpoints (main_stat=1000 neutralises stat factor)."""
        # FixedRNG(0.5): passes the guaranteed first proc check (interval >> proc_interval),
        # but too high for the re-check after the proc fires (~0.002), so no cascade.
        rng = FixedRNG(value=0.5)
        state = State(rng=rng)
        Enemy(state=state)
        target = state.enemies[0]
        setup = ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=main_stat,
                expertise_percent=expertise_percent,
            ),
            master_trait="Ruby Storm",
        )
        elarion = setup.finalize(state)
        elarion.healthpoints = healthpoints

        rs = elarion.effects.get(RubyStorm)
        assert rs is not None
        rs._rppm.last_attempt_time = -10_000

        damage_events: list[AbilityDamage] = []
        state.bus.subscribe(
            AbilityDamage,
            lambda e: damage_events.append(e) if isinstance(e.damage_source, RubyStorm) else None,
        )

        state.bus.emit(
            AbilityDamage(
                damage_source=elarion.focused_shot,
                owner=elarion,
                target=target,
                damage=1_000.0,
                is_crit=False,
                is_grievous_crit=False,
            )
        )
        elarion.wait(1.0)

        assert len(damage_events) == 1
        # base = ratio * healthpoints; with main_stat=1000, stat multiplier = 1000/1000 = 1
        assert damage_events[0].damage == pytest.approx(rs.ratio * healthpoints * (1 + expertise_percent))
