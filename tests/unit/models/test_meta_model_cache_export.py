"""
``MetaModel.format_cache_data`` - the plot cache on its way to a CSV.

Every tab caches the series it drew through ``MetaView._update_cache``, and "Export
plot data" writes them out through this method. It had **three references in the
suite and all three replaced it with a ``Mock``**, so the body had never run under
test - which is how it went years without anyone noticing that the categorical
histogram's export could not work at all.

The old implementation coerced every cached series with ``arr.astype(float)``. Two
things broke on that assumption: a series cached as a plain list has no ``astype``,
and a series of text categories cannot become float even as an array. Reported from a
real run, from the export of a plot type whose cache holds category names.

These tests cover both halves: that the numeric columns come out exactly as they did,
and that a non-numeric column now survives.
"""

from typing import override

import numpy as np
import pytest

from poriscope.utils.MetaModel import MetaModel


class _ConcreteModel(MetaModel):
    """A minimal concrete MetaModel, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model():
    """
    A concrete MetaModel with an empty cache.

    :return: the model under test
    :rtype: _ConcreteModel
    """
    return _ConcreteModel()


class TestNothingCached:
    def test_an_empty_cache_gives_none(self, model):
        """The Controller warns the user rather than opening a save dialog."""
        model.cache_data = []
        model.cache_labels = []

        assert model.format_cache_data() is None

    def test_data_without_labels_gives_none(self, model):
        model.cache_data = [np.array([1.0])]
        model.cache_labels = []

        assert model.format_cache_data() is None


class TestNumericSeries:
    """The behaviour that already worked, pinned so the fix cannot have moved it."""

    def test_one_column_per_label_in_order(self, model):
        model.cache_data = [np.array([1.0, 2.0]), np.array([3.0, 4.0])]
        model.cache_labels = ["x", "y"]

        df = model.format_cache_data()

        assert list(df.columns) == ["x", "y"]
        assert df["x"].tolist() == [1.0, 2.0]

    def test_a_shorter_series_is_padded_to_the_longest(self, model):
        """
        A plot may cache an x array and a shorter y, and a CSV needs square columns.
        The padding reads as an empty field, which is what NaN writes as.
        """
        model.cache_data = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0])]
        model.cache_labels = ["x", "y"]

        df = model.format_cache_data()

        assert len(df) == 3
        assert np.isnan(df["y"].iloc[2])

    def test_a_padded_numeric_column_stays_numeric(self, model):
        """
        Padding with ``None`` must not turn a float column into an object column -
        that would change what the CSV contains for every ragged export.
        """
        model.cache_data = [np.array([1.0, 2.0, 3.0]), np.array([4.0])]
        model.cache_labels = ["x", "y"]

        df = model.format_cache_data()

        assert df["y"].dtype.kind == "f"

    def test_the_padding_writes_as_an_empty_field(self, model):
        model.cache_data = [np.array([1.0, 2.0]), np.array([3.0])]
        model.cache_labels = ["x", "y"]

        csv = model.format_cache_data().to_csv(index=False)

        assert csv.strip().split("\n")[-1] == "2.0,"


class TestNonNumericSeries:
    """
    The half that never worked.

    The categorical histogram caches its category names beside their counts, so its
    export raised for as long as it existed - as an ``AttributeError`` when the names
    were cached as a list, and as a ``ValueError`` had they been an array of text.
    """

    def test_a_list_of_text_categories_exports(self, model):
        model.cache_data = [["a", "b", "null"], np.array([2.0, 1.0, 1.0])]
        model.cache_labels = ["kind", "Count"]

        df = model.format_cache_data()

        assert df["kind"].tolist() == ["a", "b", "null"]
        assert df["Count"].tolist() == [2.0, 1.0, 1.0]

    def test_an_array_of_text_categories_exports_too(self, model):
        """The other shape the old coercion could not take, for the other reason."""
        model.cache_data = [np.array(["a", "b"], dtype=object), np.array([1.0, 2.0])]
        model.cache_labels = ["kind", "Count"]

        df = model.format_cache_data()

        assert df["kind"].tolist() == ["a", "b"]

    def test_numeric_looking_categories_stay_as_written(self, model):
        """
        The categories are already strings by the time they are cached, and the
        histogram's own tests pin that they keep numeric order rather than being
        re-sorted as text. Coercing them back to float here would undo that and
        silently renumber the axis in the file.
        """
        model.cache_data = [["1", "2", "10"], np.array([1.0, 1.0, 1.0])]
        model.cache_labels = ["kind", "Count"]

        df = model.format_cache_data()

        assert df["kind"].tolist() == ["1", "2", "10"]

    def test_a_short_text_column_is_padded_too(self, model):
        model.cache_data = [["a"], np.array([1.0, 2.0])]
        model.cache_labels = ["kind", "Count"]

        df = model.format_cache_data()

        assert len(df) == 2
        assert df["kind"].iloc[1] is None

    def test_a_list_of_numbers_exports(self, model):
        """
        Cached as a plain list rather than an array - the shape that produced the
        reported ``'list' object has no attribute 'astype'``.
        """
        model.cache_data = [[1.0, 2.0], [3.0, 4.0]]
        model.cache_labels = ["x", "y"]

        df = model.format_cache_data()

        assert df["x"].tolist() == [1.0, 2.0]


def _series(*arrays):
    """
    Cached series for a test, as the views cache them.

    :param arrays: one array or list per cached series
    :type arrays: Any
    :return: the same series as a list
    :rtype: list
    """
    return list(arrays)


# The cache each plot type builds when it draws more than one dataset, or more than
# one curve, under the same axis labels. The label lists are the ones the tabs
# produce; the values are small stand-ins of the right shape.
_REPEATED_LABELS = {
    "metadata scatter, two datasets": (
        ["duration (us)", "num_sublevels", "duration (us)", "num_sublevels"],
        _series(
            np.array([1.0, 2.0, 3.0]),
            np.array([4.0, 5.0, 6.0]),
            np.array([7.0, 8.0, 9.0, 10.0]),
            np.array([1.0, 2.0, 3.0, 4.0]),
        ),
    ),
    "metadata 3D scatter, two datasets": (
        ["x", "y", "z", "x", "y", "z"],
        _series(*(np.arange(n, dtype=float) + k for k in range(2) for n in (3,) * 3)),
    ),
    "metadata histogram, two datasets": (
        ["duration (us)", "Count", "duration (us)", "Count"],
        _series(
            np.array([0.5, 1.5]),
            np.array([4.0, 2.0]),
            np.array([0.5, 1.5]),
            np.array([1.0, 7.0]),
        ),
    ),
    "metadata kernel density, two datasets": (
        ["duration (us)", "Density", "duration (us)", "Density"],
        _series(
            np.array([1.0, 2.0, 3.0]),
            np.array([0.1, 0.4, 0.2]),
            np.array([1.0, 2.0, 3.0]),
            np.array([0.3, 0.3, 0.1]),
        ),
    ),
    "metadata all points histogram, two datasets": (
        ["Normalized Current (pA)", "Amplitude"] * 2,
        _series(
            np.array([0.1, 0.2]),
            np.array([5.0, 6.0]),
            np.array([0.1, 0.2]),
            np.array([7.0, 8.0]),
        ),
    ),
    "metadata categorical histogram, two datasets": (
        ["kind", "Count", "kind", "Count"],
        _series(
            ["a", "b", "c"], np.array([2.0, 1.0, 1.0]), ["a", "b"], np.array([3.0, 5.0])
        ),
    ),
    "protein individual, two solutions": (
        ["V (nm$^{3}$)", "m", "V (nm$^{3}$)", "m"],
        _series(
            np.array([1.0, 2.0, 3.0]),
            np.array([4.0, 5.0, 6.0]),
            np.array([7.0, 8.0]),
            np.array([9.0, 1.0]),
        ),
    ),
    "protein ensemble, histogram and fit curve": (
        ["Normalized Current (pA)", "Amplitude"] * 4,
        _series(*(np.arange(4, dtype=float) * (k + 1) for k in range(8))),
    ),
    "event plot, one time base for two currents": (
        ["Event 0 Time (us)", "Event 0 Filtered Current (nA)"]
        + ["Event 0 Time (us)", "Event 0 FittedCurrent (nA)"],
        _series(
            np.array([0.0, 1.0, 2.0]),
            np.array([5.0, 6.0, 7.0]),
            np.array([0.0, 1.0, 2.0]),
            np.array([5.5, 6.5, 7.5]),
        ),
    ),
    "raw data PSD": (
        ["Channel 3 Frequency (Hz)", "Channel 3 Spectral Power (pA^2/Hz)"]
        + ["Channel 3 Frequency (Hz)", "Channel 3 RMS Noise (pA)"],
        _series(
            np.array([1.0, 2.0]),
            np.array([9.0, 8.0]),
            np.array([1.0, 2.0]),
            np.array([0.5, 0.4]),
        ),
    ),
}


class TestRepeatedLabels:
    """
    A plot that draws several datasets, or several curves, caches each under the same
    axis labels. Every one of them has to reach the file.

    The first version of the padding keyed a dict by label, so a repeated label
    overwrote the earlier series: an overlay of two datasets exported only the last.
    The tests above all gave every series its own label, which is why the suite
    passed. The cases below are the caches the tabs really build, one per plot type.
    """

    @pytest.mark.parametrize("case", list(_REPEATED_LABELS), ids=list(_REPEATED_LABELS))
    def test_every_cached_series_gets_its_own_column(self, model, case):
        labels, data = _REPEATED_LABELS[case]
        model.cache_data = data
        model.cache_labels = labels

        df = model.format_cache_data()

        assert list(df.columns) == labels

    @pytest.mark.parametrize("case", list(_REPEATED_LABELS), ids=list(_REPEATED_LABELS))
    def test_no_dataset_is_lost_or_moved(self, model, case):
        labels, data = _REPEATED_LABELS[case]
        model.cache_data = data
        model.cache_labels = labels

        df = model.format_cache_data()

        for position, series in enumerate(data):
            written = df.iloc[:, position].tolist()
            assert written[: len(series)] == list(series)
            assert all(v is None or v != v for v in written[len(series) :])

    def test_the_last_dataset_does_not_overwrite_the_first(self, model):
        """The reported symptom: two scatter datasets, only the second in the file."""
        model.cache_data = [
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([5.0, 6.0]),
            np.array([7.0, 8.0]),
        ]
        model.cache_labels = ["x", "y", "x", "y"]

        csv = model.format_cache_data().to_csv(index=False)

        assert csv.splitlines() == ["x,y,x,y", "1.0,3.0,5.0,7.0", "2.0,4.0,6.0,8.0"]

    @pytest.mark.parametrize("seed", range(20))
    def test_one_column_per_series_whatever_the_labels(self, model, seed):
        """
        The invariant under every plot type: the file has exactly as many columns as
        series were cached, in order, whatever repeats and whatever the lengths.
        """
        rng = np.random.default_rng(seed)
        count = int(rng.integers(1, 9))
        labels = [str(rng.choice(["x", "y", "Count"])) for _ in range(count)]
        data = [rng.random(int(rng.integers(1, 12))) for _ in range(count)]
        model.cache_data = data
        model.cache_labels = labels

        df = model.format_cache_data()

        assert list(df.columns) == labels
        for position, series in enumerate(data):
            assert df.iloc[: len(series), position].tolist() == series.tolist()
