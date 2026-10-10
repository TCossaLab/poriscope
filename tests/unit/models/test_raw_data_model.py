"""
Characterization tests for RawDataModel's baseline computation.

``get_baseline_stats`` moved off ``RawDataView`` onto this model, and now delegates to
``MetaEventFinder._fit_baseline_histogram`` rather than keeping a second fit. The
Gaussian-fit tests (``TestGaussianFit*``) that used to live here moved with the code to
``tests/unit/utils/test_meta_event_finder.py``, since ``_gaussian_fit`` now lives on
``MetaEventFinder`` and this model no longer has one.

A fifth class, ``TestGaussian``, never came across. ``RawDataView._gaussian`` was a
Gaussian model function with **zero callers anywhere in poriscope/**, so it was deleted
instead of moving it, and its four tests went with it.

No Qt: these used to need a ``RawDataView`` built by ``__new__`` with its signals
shadowed, which is what moving the computation to a plain ``QObject`` model removes.
"""

from typing import Dict

import numpy as np
import pytest

from poriscope.plugins.analysistabs.RawDataModel import RawDataModel
from poriscope.utils.MetaEventFinder import MetaEventFinder

pytestmark = pytest.mark.characterization


@pytest.fixture
def model() -> RawDataModel:
    """
    A RawDataModel.

    :return: the model under test
    :rtype: RawDataModel
    """
    return RawDataModel()


# ===========================================================================
# get_baseline_stats - delegates to the finders' shared baseline fit
# ===========================================================================


class TestGetBaselineStats:
    """The chunk statistics that drive the raw-data trace display."""

    def test_flat_data_raises(self, model: RawDataModel) -> None:
        """
        No variation means no histogram width, which is a documented raise.

        The message matters: it is what the user sees when a chunk is constant.
        """
        with pytest.raises(ValueError, match="no variation in the data"):
            model.get_baseline_stats(np.full(1000, 5.0))

    def test_it_recovers_the_mean_and_width_of_noisy_data(
        self, model: RawDataModel
    ) -> None:
        """
        A normal sample's baseline is recovered to within a few percent.

        Deliberately a loose tolerance: the point is that the windowing plus fit
        lands on the right answer, not that it is exact. The exact numbers are
        pinned by the golden below.
        """
        rng = np.random.default_rng(20260905)
        data = rng.normal(2000.0, 15.0, 200_000)

        mean, stdev = model.get_baseline_stats(data)

        assert mean == pytest.approx(2000.0, abs=1.0)
        assert stdev == pytest.approx(15.0, rel=0.15)

    def test_it_returns_two_values_in_mean_stdev_order(
        self, model: RawDataModel
    ) -> None:
        """The docstring fixes the order, and callers index it positionally."""
        rng = np.random.default_rng(7)
        out = model.get_baseline_stats(rng.normal(100.0, 2.0, 50_000))

        assert isinstance(out, np.ndarray)
        assert out.shape == (2,)

    def test_a_negative_baseline_is_handled(self, model: RawDataModel) -> None:
        """Nanopore baselines are commonly negative."""
        rng = np.random.default_rng(11)
        mean, stdev = model.get_baseline_stats(rng.normal(-1500.0, 20.0, 100_000))

        assert mean == pytest.approx(-1500.0, abs=2.0)
        assert stdev > 0

    def test_baseline_sweep_is_unchanged(
        self, model: RawDataModel, num_regression
    ) -> None:
        """
        Seeded noise through the shared histogram-window-fit chain, pinned.

        The numbers are those of ``MetaEventFinder._fit_baseline_histogram`` over the
        chunk's own range; the finders' own tests pin that algorithm's behaviour, so this
        golden guards the delegation rather than the windowing.
        """
        recorded: Dict[str, list] = {"mean": [], "stdev": []}
        for seed, (centre, width, size) in enumerate(
            [
                (2000.0, 15.0, 200_000),
                (2000.0, 5.0, 200_000),
                (-1500.0, 20.0, 100_000),
                (0.0, 1.0, 50_000),
                (100.0, 2.0, 50_000),
            ]
        ):
            rng = np.random.default_rng(1000 + seed)
            data = rng.normal(centre, width, size)
            mean, stdev = model.get_baseline_stats(data)
            recorded["mean"].append(mean)
            recorded["stdev"].append(stdev)

        num_regression.check({k: np.asarray(v) for k, v in recorded.items()})

    def test_it_agrees_exactly_with_the_finders_baseline_fit(
        self, model: RawDataModel
    ) -> None:
        """
        The Raw Data tab's baseline is the finders' baseline fit, bit for bit.

        This is what stops a second, independently biased copy growing back: any local
        histogram or fit in ``get_baseline_stats`` would disagree with the shared one
        on at least the last digits.
        """
        rng = np.random.default_rng(31)
        data = np.concatenate(
            [rng.normal(-4000.0, 600.0, 60_000), rng.normal(-100.0, 700.0, 80_000)]
        )

        shared = MetaEventFinder._fit_baseline_histogram(
            data, float(np.min(data)), float(np.max(data))
        )

        assert tuple(model.get_baseline_stats(data)) == shared
