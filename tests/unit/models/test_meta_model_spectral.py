"""
The spectral methods every analysis tab's Model shares: a Welch PSD and a power-law fit.

``MetaModel.power_spectral_density`` is Welch's estimate with a Hann window, density
scaling, an explicit segment length and an overlap given as a fraction of a segment; ``MetaModel.fit_power_law`` fits a
straight line to log10 PSD against log10 frequency over a range. Raw Data's Update PSD and
the Conditioning tab both draw on them, so one segment length gives the same spectrum in
either tab.

``RawDataModel.calculate_psd`` is pinned here as well: its segments of a tenth of the trace
with half-segment overlap are what Update PSD has always drawn, and must not move when it
starts calling the shared method.
"""

import warnings
from typing import override

import numpy as np
import pytest
from scipy.signal import welch

from poriscope.plugins.analysistabs.RawDataModel import RawDataModel
from poriscope.utils.MetaModel import MetaModel


class _ConcreteModel(MetaModel):
    """A minimal concrete MetaModel, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model() -> _ConcreteModel:
    return _ConcreteModel()


@pytest.fixture
def trace() -> np.ndarray:
    rng = np.random.default_rng(3)
    return rng.standard_normal(20_000) + np.cumsum(rng.standard_normal(20_000)) * 0.01


class TestPowerSpectralDensity:
    def test_it_is_welch_with_a_hann_window_and_the_given_segments(
        self, model: _ConcreteModel, trace: np.ndarray
    ) -> None:
        frequency, psd = model.power_spectral_density(trace, 1_000.0, 4_000, 0.0)
        expected_f, expected_psd = welch(
            trace,
            fs=1_000.0,
            window="hann",
            nperseg=4_000,
            noverlap=0,
            scaling="density",
        )
        np.testing.assert_array_equal(frequency, expected_f)
        np.testing.assert_array_equal(psd, expected_psd)

    def test_overlap_is_honoured(
        self, model: _ConcreteModel, trace: np.ndarray
    ) -> None:
        _, overlapped = model.power_spectral_density(trace, 1_000.0, 4_000, 0.5)
        _, expected = welch(trace, fs=1_000.0, nperseg=4_000, noverlap=2_000)
        np.testing.assert_array_equal(overlapped, expected)

    def test_a_segment_longer_than_the_trace_is_shortened_without_a_warning(
        self, model: _ConcreteModel, trace: np.ndarray
    ) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            frequency, psd = model.power_spectral_density(
                trace[:1_500], 1_000.0, 2_000, 0.0
            )
        expected_f, expected_psd = welch(
            trace[:1_500], fs=1_000.0, window="hann", nperseg=1_500, noverlap=0
        )
        np.testing.assert_array_equal(frequency, expected_f)
        np.testing.assert_array_equal(psd, expected_psd)


class TestFitPowerLaw:
    def test_it_recovers_an_exact_power_law(self, model: _ConcreteModel) -> None:
        frequency = np.linspace(0.0, 100.0, 1_001)
        psd = np.zeros_like(frequency)
        psd[1:] = 7.5 * frequency[1:] ** -1.3
        slope, intercept = model.fit_power_law(frequency, psd, 1.0, 30.0)
        assert slope == pytest.approx(-1.3, rel=1e-12)
        assert 10**intercept == pytest.approx(7.5, rel=1e-12)

    def test_only_bins_inside_the_range_count(self, model: _ConcreteModel) -> None:
        frequency = np.arange(0.0, 50.0, 1.0)
        psd = np.where(frequency <= 30.0, 2.0 / np.maximum(frequency, 1.0), 1e6)
        slope, intercept = model.fit_power_law(frequency, psd, 1.0, 30.0)
        assert slope == pytest.approx(-1.0, rel=1e-12)
        assert 10**intercept == pytest.approx(2.0, rel=1e-12)

    def test_fewer_than_two_bins_in_range_is_refused_with_the_count(
        self, model: _ConcreteModel
    ) -> None:
        frequency = np.arange(0.0, 500.0, 50.0)
        psd = np.ones_like(frequency)
        with pytest.raises(ValueError, match="0 frequency bins"):
            model.fit_power_law(frequency, psd, 1.0, 30.0)


class TestRawDataPsdIsUnchanged:
    def test_update_psd_uses_tenth_length_segments_with_half_overlap(
        self, trace: np.ndarray
    ) -> None:
        raw = RawDataModel()
        psds, rms, frequency, kept = raw.calculate_psd([trace, trace[:5_000]], 2_000.0)
        assert kept == [0, 1]
        for data, psd in zip([trace, trace[:5_000]], psds):
            expected_f, expected_psd = welch(data, 2_000.0, nperseg=len(data) // 10)
            np.testing.assert_array_equal(psd, expected_psd)
        np.testing.assert_array_equal(
            frequency, welch(trace[:5_000], 2_000.0, nperseg=500)[0]
        )
