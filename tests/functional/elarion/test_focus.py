import pytest

from fellowship_sim.base_classes import Enemy, State
from fellowship_sim.base_classes.stats import RawStatsFromPercents
from fellowship_sim.elarion.buff import EmpoweredMultishotChargeBuff
from fellowship_sim.elarion.effect import ResurgentWinds
from fellowship_sim.elarion.entity import Elarion
from fellowship_sim.elarion.setup import ElarionSetup
from tests.conftest import FixedRNG


class TestFocusCosts:
    """Net focus change after casting equals regen_during_cast - cost.

    For non-channel abilities: regen_during_cast = 5 × base_player_downtime
    (haste cancels out: faster cast × faster regen = constant). Parametrized to confirm independence.

    Exception: HeartseekerBarrage is a channel — its window is fixed at 2.0s regardless of haste,
    so regen = 5 × (1 + haste) × 2.0 and is haste-dependent.
    """

    @pytest.fixture(params=[0.0, 0.2, 0.5])
    def haste_percent(self, request: pytest.FixtureRequest) -> float:
        return request.param  # type: ignore[no-any-return]

    @pytest.fixture
    def state(self) -> State:
        state = State(rng=FixedRNG(value=0.0))
        Enemy(state=state)
        return state

    @pytest.fixture
    def elarion(self, state: State, haste_percent: float) -> Elarion:
        return ElarionSetup(
            raw_stats=RawStatsFromPercents(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=haste_percent,
                spirit_percent=0.0,
            ),
        ).finalize(state)

    def test_focused_shot_net_gain(self, state: State, elarion: Elarion) -> None:
        """FocusedShot: no cost, +20 focus gain, +7.5 regen during 1.5s cast. Net: +27.5."""
        elarion.focus = 0.0  # prevent cap from masking the gain
        elarion.focused_shot.cast(state.enemies[0])

        assert elarion.focus == pytest.approx(27.5, rel=1e-6)

    def test_celestial_shot_net_cost(self, state: State, elarion: Elarion) -> None:
        """CelestialShot: 15 focus cost; with regen, effective -7.5, regardless of haste."""
        focus_before = elarion.focus

        elarion.celestial_shot.cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 7.5, rel=1e-6)

    def test_multishot_net_cost(self, state: State, elarion: Elarion) -> None:
        """Multishot has 12.5 net cost."""
        focus_before = elarion.focus

        elarion.multishot._add_charge()
        elarion.multishot.cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 12.5, rel=1e-6)

    def test_empowered_multishot_net_cost__skystrider_supremacy(self, state: State, elarion: Elarion) -> None:
        """Empowered Multishot has net cost 2.5 instead.
        Once buff decays, back to normal 12.5 net cost.
        """
        focus_before = elarion.focus

        elarion.skystrider_supremacy.cast(state.enemies[0])

        for idx in range(3):
            elarion.multishot.cast(state.enemies[0])

            assert elarion.focus == pytest.approx(focus_before - 2.5 * (idx + 1), rel=1e-6)

        # wait for buff to clear and full energy regen
        elarion.wait(20)

        focus_before = elarion.focus

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.enemies[0])

        # net focus cost is back to normal
        assert elarion.focus == pytest.approx(focus_before - 12.5, rel=1e-6)

    def test_empowered_multishot_net_cost__fervent_supremacy(self, state: State, elarion: Elarion) -> None:
        """Empowered Multishot has net cost 2.5 instead.
        Once buff decays, back to normal 12.5 net cost.
        """
        focus_before = elarion.focus

        elarion.skystrider_supremacy.is_fervent_supremacy = True

        elarion.skystrider_supremacy.cast(state.enemies[0])

        for idx in range(4):
            elarion.multishot.cast(state.enemies[0])

            assert elarion.focus == pytest.approx(focus_before - 2.5 * (idx + 1), rel=1e-6)

        # wait for buff to clear and full energy regen
        elarion.wait(20)

        focus_before = elarion.focus

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.enemies[0])

        # net focus cost is back to normal
        assert elarion.focus == pytest.approx(focus_before - 12.5, rel=1e-6)

    def test_empowered_multishot_net_cost__empowered_multishot(self, state: State, elarion: Elarion) -> None:
        """Empowered Multishot has net cost 2.5 instead.
        Once buff decays, back to normal 12.5 net cost.
        """
        focus_before = elarion.focus

        elarion.effects.add(EmpoweredMultishotChargeBuff(owner=elarion))
        elarion.effects.add(EmpoweredMultishotChargeBuff(owner=elarion))

        for idx in range(2):
            elarion.multishot.cast(state.enemies[0])

            assert elarion.focus == pytest.approx(focus_before - 2.5 * (idx + 1), rel=1e-6)

        # wait for buff to clear and full energy regen
        elarion.wait(20)

        focus_before = elarion.focus

        elarion.multishot.charges = 5
        elarion.multishot.cast(state.enemies[0])

        # net focus cost is back to normal
        assert elarion.focus == pytest.approx(focus_before - 12.5, rel=1e-6)

    def test_highwind_arrow_net_cost(self, state: State, elarion: Elarion) -> None:
        """HighwindArrow: 30 focus cost; regen during 2.0s cast = 5 × 2.0 = 10.

        NB: when starting from full focus, since cost occurs at the end, the effective cost is 30!"""
        elarion.focus = 100
        focus_before = elarion.focus

        elarion.highwind_arrow.cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 30, rel=1e-6)

        elarion.focus = 80
        focus_before = elarion.focus

        elarion.highwind_arrow.cast(state.enemies[0])
        assert elarion.focus == pytest.approx(focus_before - 30 + 5 * 2.0, rel=1e-6)

    def test_highwind_arrow_net_cost__resurgent_winds(self, state: State, elarion: Elarion) -> None:
        """HighwindArrow with resurgent winds: 0 focus cost, instant cast (with GCD); regen during 1.5 GCD = 7.5."""
        elarion.effects.add(ResurgentWinds(owner=elarion))

        elarion.focus = 0
        focus_before = elarion.focus

        elarion.highwind_arrow.cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before + 7.5, rel=1e-6)

    def test_volley_net_cost(self, state: State, elarion: Elarion) -> None:
        """Volley: 30 focus cost; regen during 1.5s GCD = 5 × 1.5 = 7.5. Net: -22.5."""
        focus_before = elarion.focus

        elarion.volley.cast(state.enemies[0])

        assert elarion.focus == pytest.approx(focus_before - 22.5, rel=1e-6)

    def test_heartseeker_barrage_net_cost(self, state: State, elarion: Elarion) -> None:
        """HeartseekerBarrage: 30 focus cost; channel window is 2.0s regardless of haste.

        Regen = 5 × (1 + haste) × 2.0 — unlike other abilities, this IS haste-dependent.
        """
        focus_before = elarion.focus

        elarion.heartseeker_barrage.cast(state.enemies[0])

        regen = 5 * (1 + elarion.stats.haste_percent) * elarion.heartseeker_barrage.base_player_downtime
        assert elarion.focus == pytest.approx(focus_before - 30 + regen, rel=1e-6)

    def test_focus_cost__five_cs_two_fs_loop(self, state: State, elarion: Elarion) -> None:
        """Rotation of 5× CelestialShot + 2× FocusedShot: net CS=-7.5, net FS=+27.5."""
        elarion.focus = 70
        target = state.enemies[0]

        for _ in range(5):
            elarion.celestial_shot.cast(target)
            assert elarion.focus < 70

        assert elarion.focus == pytest.approx(32.5)

        elarion.focused_shot.cast(target)
        assert elarion.focus < 70

        elarion.focused_shot.cast(target)
        assert elarion.focus == pytest.approx(87.5)
