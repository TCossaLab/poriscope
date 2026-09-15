"""
``MetaModel.logscale_and_filter_columns`` - the NaN and log filter every plot runs.

Each plot path hands its raw columns down and draws what comes back. The filter
masks every column it is given together, so a row dropped for one axis is dropped
for all of them and the arrays stay the same length - which is what lets a caller
pass a value column and its error column and still have them line up.

It is not a pure transform: it reports on the status panel how many points the NaN
mask and the log filter removed, which is why it cannot be a module-level function.

An identical copy sat on ``MetaView`` while the plot paths were converted one at a
time, with a test comparing the two bodies so neither could be edited alone. The
last caller converted and that copy is gone, so the test is too.
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
    A concrete MetaModel to filter with.

    :return: the model under test
    :rtype: _ConcreteModel
    """
    return _ConcreteModel()


class TestLogscaleAndFilterColumns:
    """
    The behaviour, asserted against the Model copy directly.

    These overlap ``test_meta_view_characterization.py`` on purpose: that file pins the
    copy the unconverted callers still use, and this one pins the copy that survives.
    """

    def test_no_arrays_returns_an_empty_tuple(self, model):
        assert model.logscale_and_filter_columns() == ()

    def test_without_log_flags_only_nans_are_removed(self, model):
        a = np.array([1.0, 2.0, np.nan, 4.0])
        b = np.array([10.0, 20.0, 30.0, 40.0])

        out_a, out_b = model.logscale_and_filter_columns(a, b)

        np.testing.assert_array_equal(out_a, [1.0, 2.0, 4.0])
        np.testing.assert_array_equal(out_b, [10.0, 20.0, 40.0])

    def test_a_nan_in_one_column_drops_that_row_from_all_of_them(self, model):
        """
        The filtering is joint, which is what keeps the columns aligned. It is also
        what lets a clustering frame be rebuilt from the results.
        """
        a = np.array([1.0, np.nan, 3.0])
        b = np.array([10.0, 20.0, 30.0])

        out_a, out_b = model.logscale_and_filter_columns(a, b)

        np.testing.assert_array_equal(out_a, [1.0, 3.0])
        np.testing.assert_array_equal(out_b, [10.0, 30.0])

    def test_an_object_column_of_nulls_is_filtered_rather_than_raising(self, model):
        """
        A column that is NULL for every row in the requested scope comes back from
        pandas as an object array of ``None``, which ``np.isnan`` cannot take.
        """
        nulls = np.array([None, None, None], dtype=object)

        (out,) = model.logscale_and_filter_columns(nulls)

        assert len(out) == 0

    def test_an_object_column_mixing_nulls_and_numbers_keeps_the_numbers(self, model):
        mixed = np.array([1.0, None, 3.0], dtype=object)

        (out,) = model.logscale_and_filter_columns(mixed)

        np.testing.assert_array_equal(out, [1.0, 3.0])

    def test_a_flagged_column_is_log_scaled(self, model):
        a = np.array([1.0, 10.0, 100.0])

        (out,) = model.logscale_and_filter_columns(a, log_flags=[True])

        np.testing.assert_allclose(out, [0.0, 1.0, 2.0])

    def test_a_negative_column_is_rectified_before_scaling(self, model):
        """
        Rectification flips on the average sign, so an all-negative column scales
        rather than vanishing.
        """
        a = np.array([-1.0, -10.0, -100.0])

        (out,) = model.logscale_and_filter_columns(a, log_flags=[True])

        np.testing.assert_allclose(out, [0.0, 1.0, 2.0])

    def test_non_positive_values_are_dropped_from_every_column(self, model):
        """Log filtering is joint too, for the same alignment reason."""
        a = np.array([1.0, 0.0, 100.0])
        b = np.array([10.0, 20.0, 30.0])

        out_a, out_b = model.logscale_and_filter_columns(a, b, log_flags=[True, False])

        np.testing.assert_allclose(out_a, [0.0, 2.0])
        np.testing.assert_array_equal(out_b, [10.0, 30.0])

    def test_mismatched_log_flags_are_refused(self, model):
        a = np.array([1.0, 2.0])

        with pytest.raises(ValueError, match="log_flags"):
            model.logscale_and_filter_columns(a, log_flags=[True, False])

    def test_dropped_rows_are_reported_to_the_status_panel(self, model):
        """
        The helper is not a pure transform - it says how many points it removed,
        which is why it cannot be a module-level function.
        """
        received = []
        model.add_text_to_display.connect(lambda text, source: received.append(text))

        model.logscale_and_filter_columns(np.array([1.0, np.nan, 3.0]))

        assert any("NaN" in message for message in received)

    def test_a_non_numeric_column_is_reported_rather_than_raising(self, model):
        """
        Genuinely non-numeric is a different thing from empty, and the user can act
        on it, so it is named. The arity of the return is part of the contract -
        every caller unpacks it positionally - so the column is masked out rather
        than the tuple being shortened.
        """
        received = []
        model.add_text_to_display.connect(lambda text, source: received.append(text))
        text = np.array([1.0, "oops", 3.0], dtype=object)

        (out,) = model.logscale_and_filter_columns(text)

        assert len(out) == 0
        assert any("not numeric" in message for message in received)

    def test_a_zero_average_defaults_to_a_positive_sign(self, model):
        """``np.sign(0)`` is 0, which would zero the data, so the code forces +1."""
        a = np.array([-1.0, 1.0])

        (out,) = model.logscale_and_filter_columns(a, log_flags=[True])

        np.testing.assert_allclose(out, [0.0])
