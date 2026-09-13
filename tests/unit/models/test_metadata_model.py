"""
Unit-test suite for MetadataModel.

MetadataModel was a minimal MetaModel subclass with a no-op ``_init()``. **Step 4c
is giving it the metadata tab's binning and fitting**, moved off MetadataView so
that ``scipy``, ``scipy.optimize`` and ``scipy.stats`` leave the View layer.

The two bin-count rules are pinned here before any caller moves onto them, because
``MetadataView`` held **four** near-copies of the Freedman-Diaconis calculation in
one file - a shape the duplication ratchet cannot see, since it only compares
bodies *across* files in a family. Three of the four agreed; the heatmap's differed
in two places. Both rules are preserved exactly rather than unified, so the move
changes no output, and the tests below are what say so.
"""

import numpy as np
import pytest

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.utils.MetaModel import MetaModel


@pytest.fixture
def model():
    """
    A MetadataModel to compute with.

    :return: a constructed MetadataModel
    :rtype: MetadataModel
    """
    return MetadataModel()


# ===========================================================================
# Construction / inheritance
# ===========================================================================


class TestConstruction:
    def test_instantiates_without_error(self, model):
        assert model is not None

    def test_is_instance_of_meta_model(self, model):
        assert isinstance(model, MetaModel)

    def test_init_returns_none(self, model):
        assert model._init() is None


# ===========================================================================
# _auto_bins_1d - the rule the density, histogram and capture-rate paths share
# ===========================================================================


class TestAutoBins1d:
    """The Freedman-Diaconis bin count, cube-root form."""

    def test_matches_the_freedman_diaconis_expression(self, model):
        """
        Asserted against the formula rather than a recorded number.

        A golden here would pass just as happily against the fourth-root form, which
        is the one thing these two rules must not be allowed to drift into.
        """
        from scipy.stats import iqr

        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 13.0, 21.0])
        expected = int(
            (np.max(data) - np.min(data)) * len(data) ** (1.0 / 3.0) / iqr(data)
        )

        assert model._auto_bins_1d(data) == expected

    def test_a_zero_interquartile_range_falls_back_to_sturges(self, model):
        """
        Every value identical means no spread to divide by, so the count comes from
        the sample size alone.
        """
        data = np.array([5.0] * 40)

        assert model._auto_bins_1d(data) == int(3.332 * np.log10(len(data)))

    def test_the_fallback_is_not_the_two_dimensional_one(self, model):
        """
        The 1-D and 2-D degenerate fallbacks differ, and this is the assertion that
        fails if someone unifies them without deciding to.
        """
        data = np.array([5.0] * 40)

        assert model._auto_bins_1d(data) != int(np.sqrt(len(data)))


# ===========================================================================
# _auto_bins_2d - the heatmap's rule, which differs in two places
# ===========================================================================


class TestAutoBins2d:
    """The heatmap's bin count: fourth root, square-root fallback."""

    def test_uses_a_fourth_root_not_a_cube_root(self, model):
        """The exponent is the first of the two divergences from the 1-D rule."""
        from scipy.stats import iqr

        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 13.0, 21.0])
        expected = int(
            (np.max(data) - np.min(data)) * len(data) ** (1.0 / 4.0) / iqr(data)
        )

        assert model._auto_bins_2d(data, len(data)) == expected

    def test_a_zero_interquartile_range_falls_back_to_the_square_root(self, model):
        """The degenerate fallback is the second divergence."""
        data = np.array([5.0] * 40)

        assert model._auto_bins_2d(data, len(data)) == int(np.sqrt(len(data)))

    def test_the_count_is_taken_from_the_argument_not_from_the_data(self, model):
        """
        The heatmap's y-axis calculation raises the **x** array's length to the
        fourth power, not the y array's.

        Inert in the application, because the filter that runs first masks both
        arrays jointly and they are always the same length. Pinned rather than
        quietly corrected, so that the move changes nothing and the oddity stays
        visible to whoever decides about it.
        """
        data = np.array([1.0, 2.0, 3.0, 4.0])

        assert model._auto_bins_2d(data, 4) != model._auto_bins_2d(data, 100000)
