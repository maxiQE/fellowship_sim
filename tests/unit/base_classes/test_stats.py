# Unit tests for base_classes/stats.py

import pytest

from fellowship_sim.base_classes.stats import (
    CritMultiplierMultiplicativeCharacter,
    CritPercentAdditive,
    CritScoreAdditive,
    ExpertisePercentAdditive,
    ExpertiseScoreAdditive,
    FinalStats,
    HastePercentAdditive,
    HasteScoreAdditive,
    MainStatAdditiveCharacter,
    MainStatAdditiveMultiplierCharacter,
    MutableStats,
    RawStatsFromPercents,
    RawStatsFromScores,
    SpiritPercentAdditive,
    SpiritScoreAdditive,
    secondary_stat_percent_from_score,
)


class TestSecondaryStatPercentFromScore:
    def test_score_to_percent_curve(self) -> None:
        test_cases = [
            (250, 4.25),
            (500, 8.50),
            (750, 12.60),
            (1000, 16.48),
            (1250, 20.10),
            (1500, 23.19),
            (1750, 26.02),
            (2000, 28.50),
        ]

        def rating_to_pct__angry_reference(
            rating: float, mul: float = 0.017, tier: int = 0, low: float = 0, up: float = 10
        ) -> float:
            return (
                low + rating * mul
                if low + rating * mul < up
                else rating_to_pct__angry_reference(
                    rating - (up - low) / mul,
                    max(mul * (1 - 0.05 * (tier + 1)), 0.009883800000000002),
                    tier + 1,
                    up,
                    up + 5,
                )
            )

        for score, expected_pct in test_cases:
            actual_pct = secondary_stat_percent_from_score(score) * 100
            angry_expected_pct = rating_to_pct__angry_reference(score)
            assert actual_pct == pytest.approx(expected_pct, abs=0.1), f"score={score}"
            assert actual_pct == pytest.approx(angry_expected_pct, abs=0.001), f"score={score}"

    @pytest.mark.parametrize(
        "base_score,bonus,expected_gain",
        [
            (0, 100, pytest.approx(0.0170, abs=0.001)),
            (2500, 100, pytest.approx(0.0099, abs=0.001)),
        ],
    )
    def test_score_bonus_gain_diminishes_at_high_score(self, base_score: int, bonus: int, expected_gain: float) -> None:
        """The same 100-point score bonus yields less % at high base score (diminishing returns)."""
        gain = secondary_stat_percent_from_score(base_score + bonus) - secondary_stat_percent_from_score(base_score)
        assert gain == expected_gain


class TestFinalStatsSpiritProcChance:
    def test_spirit_proc_chance_formula(self) -> None:
        """spirit_proc_chance = spirit_percent / (1 + spirit_percent)."""
        test_cases: list[tuple[float, float]] = [
            (0.01, 0.0100),
            (0.05, 1 / 21),
            (0.1, 1 / 11),
            (0.5, 1 / 3),
        ]
        for percent, expected in test_cases:
            stats = FinalStats(
                main_stat=1000.0,
                crit_percent=0.0,
                expertise_percent=0.0,
                haste_percent=0.0,
                spirit_percent=percent,
                crit_multiplier=1.0,
            )
            assert stats.spirit_proc_chance == pytest.approx(expected, abs=0.0001), f"spirit_percent={percent}"


class TestRawStatsFromPercents:
    def test_raw_stats_from_percents_is_immutable(self) -> None:
        raw = RawStatsFromPercents(main_stat=1000.0, crit_percent=0.1)
        with pytest.raises((AttributeError, TypeError)):
            raw.main_stat = 999.0  # ty:ignore[invalid-assignment]

    def test_raw_stats_from_percents_round_trip_no_modifiers(self) -> None:
        raw = RawStatsFromPercents(
            main_stat=1000.0,
            crit_percent=0.1,
            haste_percent=0.2,
            crit_multiplier=1.5,
        )
        fs = raw.to_mutable_stats().finalize()
        assert fs.main_stat == pytest.approx(1000.0)
        assert fs.crit_percent == pytest.approx(0.1)
        assert fs.haste_percent == pytest.approx(0.2)
        assert fs.crit_multiplier == pytest.approx(1.5)

    def test_raw_stats_from_percents_score_bonus_adds_on_zero_base(self) -> None:
        """Score modifiers on a percent-based RawStats start from score=0, adding to the percent base."""
        mutable = RawStatsFromPercents(main_stat=1000.0, crit_percent=0.1).to_mutable_stats()
        CritScoreAdditive(value=500).apply(mutable)
        assert mutable.finalize().crit_percent == pytest.approx(0.1 + secondary_stat_percent_from_score(500))


class TestRawStatsFromScores:
    def test_raw_stats_from_scores_is_immutable(self) -> None:
        raw = RawStatsFromScores(main_stat=1000.0, crit_score=500)
        with pytest.raises((AttributeError, TypeError)):
            raw.main_stat = 999.0  # ty:ignore[invalid-assignment]

    def test_raw_stats_from_scores_converts_to_percents(self) -> None:
        raw = RawStatsFromScores(main_stat=1000.0, crit_score=500)
        fs = raw.to_mutable_stats().finalize()
        assert fs.crit_percent == pytest.approx(secondary_stat_percent_from_score(500))

    def test_raw_stats_from_scores_applies_score_modifier(self) -> None:
        mutable = RawStatsFromScores(main_stat=1000.0, crit_score=500).to_mutable_stats()
        CritScoreAdditive(value=200).apply(mutable)
        assert mutable.finalize().crit_percent == pytest.approx(secondary_stat_percent_from_score(700))

    def test_raw_stats_from_scores_applies_percent_modifier(self) -> None:
        base_pct = secondary_stat_percent_from_score(500)
        mutable = RawStatsFromScores(main_stat=1000.0, crit_score=500).to_mutable_stats()
        CritPercentAdditive(value=0.05).apply(mutable)
        assert mutable.finalize().crit_percent == pytest.approx(base_pct + 0.05)

    def test_raw_stats_from_scores_score_and_percent_compose(self) -> None:
        mutable = RawStatsFromScores(main_stat=1000.0, haste_score=300).to_mutable_stats()
        HasteScoreAdditive(value=100).apply(mutable)
        HastePercentAdditive(value=0.02).apply(mutable)
        assert mutable.finalize().haste_percent == pytest.approx(secondary_stat_percent_from_score(400) + 0.02)


class TestFinalStats:
    def test_final_stats_is_immutable(self) -> None:
        fs = FinalStats(
            main_stat=1000.0,
            crit_percent=0.1,
            expertise_percent=0.05,
            haste_percent=0.2,
            spirit_percent=0.03,
            crit_multiplier=1.5,
        )
        with pytest.raises((AttributeError, TypeError)):
            fs.main_stat = 1100.0  # ty:ignore[invalid-assignment]


class TestStatModifierOrdering:
    @staticmethod
    def _base_mutable() -> MutableStats:
        return MutableStats(
            base_main_stat=1000.0,
            crit_score=0,
            expertise_score=0,
            haste_score=0,
            spirit_score=0,
            crit_percent=0.1,
            expertise_percent=0.05,
            haste_percent=0.2,
            spirit_percent=0.03,
            crit_multiplier=1.5,
        )

    def test_modifiers_compose_in_sequence(self) -> None:
        """Additive then multiplicative: (base + additive) * multiplicative."""
        ms = self._base_mutable()
        MainStatAdditiveCharacter(value=100).apply(ms)
        MainStatAdditiveMultiplierCharacter(value=0.1).apply(ms)
        assert ms.finalize().main_stat == pytest.approx(1210.0)  # (1000 + 100) * 1.1

    def test_crit_multiplier_multiplicative(self) -> None:
        ms = self._base_mutable()
        CritMultiplierMultiplicativeCharacter(multiplier=1.2).apply(ms)
        assert ms.crit_multiplier == pytest.approx(1.8)  # 1.5 * 1.2


class TestMutableStatsFinalize:
    def test_mutable_stats_finalize_converts_scores(self) -> None:
        ms = MutableStats(
            base_main_stat=1000.0,
            crit_score=500,
            expertise_score=0,
            haste_score=300,
            spirit_score=0,
            crit_percent=0.0,
            expertise_percent=0.0,
            haste_percent=0.0,
            spirit_percent=0.0,
            crit_multiplier=1.0,
        )
        fs = ms.finalize()
        assert fs.crit_percent == pytest.approx(secondary_stat_percent_from_score(500))
        assert fs.haste_percent == pytest.approx(secondary_stat_percent_from_score(300))

    def test_mutable_stats_finalize_sums_score_and_percent(self) -> None:
        ms = MutableStats(
            base_main_stat=1000.0,
            crit_score=500,
            expertise_score=0,
            haste_score=0,
            spirit_score=0,
            crit_percent=0.05,
            expertise_percent=0.0,
            haste_percent=0.0,
            spirit_percent=0.0,
            crit_multiplier=1.0,
        )
        assert ms.finalize().crit_percent == pytest.approx(0.05 + secondary_stat_percent_from_score(500))


class TestInputValidation:
    @pytest.mark.parametrize("field", ["crit_percent", "expertise_percent", "haste_percent", "spirit_percent"])
    def test_raw_stats_from_percents_rejects_negative(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            RawStatsFromPercents(main_stat=1000.0, **{field: -0.01})

    @pytest.mark.parametrize("field", ["crit_score", "expertise_score", "haste_score", "spirit_score"])
    def test_raw_stats_from_scores_rejects_negative(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            RawStatsFromScores(main_stat=1000.0, **{field: -1})

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (CritPercentAdditive, {"value": -0.01}),
            (ExpertisePercentAdditive, {"value": -0.01}),
            (HastePercentAdditive, {"value": -0.01}),
            (SpiritPercentAdditive, {"value": -0.01}),
            (CritScoreAdditive, {"value": -1}),
            (ExpertiseScoreAdditive, {"value": -1}),
            (HasteScoreAdditive, {"value": -1}),
            (SpiritScoreAdditive, {"value": -1}),
        ],
    )
    def test_additive_modifier_rejects_negative_value(self, cls: type[object], kwargs: dict[str, float | int]) -> None:
        with pytest.raises(ValueError, match="value"):
            cls(**kwargs)
