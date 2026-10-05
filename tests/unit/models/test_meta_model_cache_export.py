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
