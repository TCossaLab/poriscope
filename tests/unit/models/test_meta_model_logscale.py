"""
``MetaModel.logscale_and_filter_columns`` - the logscale helper on the Model side.

Step 4's closeout copies the helper here from ``MetaView`` so that concrete Models can
reach it, because no View holds a Model reference and a caller can only convert once the
Model side has it. ``MetaView`` keeps its own copy meanwhile - it still serves the seven
call sites that have not converted - and that copy is deleted in branch 6 once the last
one does. ``DECISIONS.md`` 2026-09-14 carries the ordering argument.

**The risk that arrangement creates is the two copies drifting apart**, and
``TestTheTwoCopiesAgree`` below is aimed squarely at it: it compares the two function
bodies rather than sampling their behaviour, so an edit to either one fails here rather
than showing up as a plot that differs between tabs depending on which copy ran.

That test is written against a structure with a scheduled end, so it says so by name: when
branch 6 deletes ``MetaView``'s copy, it raises with a message saying that is what
happened, rather than passing vacuously over a method that is no longer there.
"""

import ast
from pathlib import Path
from typing import override

import numpy as np
import pytest

from poriscope.utils.MetaModel import MetaModel

REPO_ROOT = Path(__file__).resolve().parents[3]
VIEW_SOURCE = REPO_ROOT / "poriscope" / "utils" / "MetaView.py"
MODEL_SOURCE = REPO_ROOT / "poriscope" / "utils" / "MetaModel.py"

VIEW_NAME = "_logscale_and_filter_multiple_columns"
MODEL_NAME = "logscale_and_filter_columns"


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


def _body_without_docstring(path, name):
    """
    The source of a named method, with its docstring removed.

    The docstrings differ deliberately - the Model copy explains why there are two -
    so comparing them would fail for the one reason that is not drift.

    :param path: the module to read
    :type path: Path
    :param name: the method to extract
    :type name: str
    :return: the method's statements as source text, or None if it is absent
    :rtype: object
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            statements = node.body
            if (
                statements
                and isinstance(statements[0], ast.Expr)
                and isinstance(statements[0].value, ast.Constant)
            ):
                statements = statements[1:]
            return "\n".join(ast.unparse(s) for s in statements)
    return None


class TestTheTwoCopiesAgree:
    """
    While both copies exist, they must be the same computation.

    Compared as source rather than sampled as behaviour: a sampled comparison only
    covers the inputs someone thought of, and the failure being guarded against is an
    edit to one copy, which the text sees whatever it touches.
    """

    def test_the_bodies_are_identical(self):
        view_body = _body_without_docstring(VIEW_SOURCE, VIEW_NAME)
        if view_body is None:
            raise AssertionError(
                f"{VIEW_NAME} is gone from MetaView, so the closeout's branch 6 has "
                "landed and this equivalence test has outlived its purpose - delete "
                "it rather than loosening it."
            )

        model_body = _body_without_docstring(MODEL_SOURCE, MODEL_NAME)
        assert model_body is not None, "MetaModel has lost its logscale helper"
        assert model_body == view_body

    def test_the_signatures_agree_apart_from_the_name(self):
        """The callers being converted pass the same arguments to either copy."""

        def signature(path, name):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            node = next(
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name
            )
            return ast.unparse(node.args), ast.unparse(node.returns)

        assert signature(MODEL_SOURCE, MODEL_NAME) == signature(VIEW_SOURCE, VIEW_NAME)


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
        The helper is not a pure transform - it says how many points it removed, which
        is why it could not become a module-level function. Method rule 59.
        """
        received = []
        model.add_text_to_display.connect(lambda text, source: received.append(text))

        model.logscale_and_filter_columns(np.array([1.0, np.nan, 3.0]))

        assert any("NaN" in message for message in received)
