# Unit tests for simulation/metrics.py

import math

import pytest

from fellowship_sim.simulation.metrics import mean_stderr


class TestMeanStderr:
    """Unit tests for mean_stderr: mean and standard error of the mean."""

    def test_translation_shifts_mean_preserves_stderr(self) -> None:
        """Adding a constant to every value shifts the mean by that constant but leaves stderr unchanged."""
        base = [1.0, 2.0, 3.0, 4.0, 5.0]
        offset = 100.0
        shifted = [v + offset for v in base]

        result_base = mean_stderr(base)
        result_shifted = mean_stderr(shifted)

        assert result_shifted.mean == pytest.approx(result_base.mean + offset)
        assert result_shifted.stderr == pytest.approx(result_base.stderr)

    def test_scaling_scales_both_mean_and_stderr(self) -> None:
        """Multiplying every value by a constant scales both mean and stderr by that constant."""
        base = [1.0, 2.0, 3.0, 4.0, 5.0]
        factor = 3.0
        scaled = [v * factor for v in base]

        result_base = mean_stderr(base)
        result_scaled = mean_stderr(scaled)

        assert result_scaled.mean == pytest.approx(result_base.mean * factor)
        assert result_scaled.stderr == pytest.approx(result_base.stderr * factor)

    def test_doubling_sample_size_halves_stderr_by_sqrt2(self) -> None:
        """Doubling sample size divides stderr by sqrt(2) without changing the mean.

        The exact ratio is sqrt((n-1)/(2n-1)) due to Bessel's correction; for large n
        this converges to 1/sqrt(2).  We use n=1001 so the approximation holds to 0.1%.
        """
        base: list[int | float] = list(range(1001))
        doubled: list[int | float] = base + base

        result_base = mean_stderr(base)
        result_doubled = mean_stderr(doubled)

        assert result_doubled.mean == pytest.approx(result_base.mean)
        assert result_doubled.stderr == pytest.approx(result_base.stderr / math.sqrt(2), rel=0.001)

    def test_single_element_returns_zero_stderr(self) -> None:
        """A single-element list returns that value as the mean and 0 as stderr."""
        result = mean_stderr([42.0])
        assert result.mean == pytest.approx(42.0)
        assert result.stderr == pytest.approx(0.0)
