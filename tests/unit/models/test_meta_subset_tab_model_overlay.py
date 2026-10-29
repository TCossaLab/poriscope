"""
``MetaSubsetTabModel``'s overlay state: what the overlaid figure holds, changed only
through the Model's own methods.

The Controller decides when the figure starts again and when a dataset was drawn; these
methods are where that is written down, so the state cannot be left half updated.
"""

from typing import override

import numpy as np
import pytest

from poriscope.utils.MetaSubsetTabModel import (
    FigureKind,
    MetaSubsetTabModel,
    OverlayState,
)

KEY = ("loader", "exp", 0, "duration > 0", "F0")


class _ConcreteModel(MetaSubsetTabModel):
    """A minimal concrete subset-tab Model, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model() -> _ConcreteModel:
    """
    A fresh subset-tab Model.

    :return: the model under test
    :rtype: _ConcreteModel
    """
    return _ConcreteModel()


def test_a_new_model_holds_an_empty_two_dimensional_figure(model) -> None:
    assert model.overlay == OverlayState()
    assert model.overlay.figure is FigureKind.EMPTY_2D


def test_a_drawn_dataset_is_noted_with_the_figure_s_options(model) -> None:
    model.add_overlay_dataset(
        KEY, FigureKind.OVERLAY_2D, "Histogram", [20], False, ["duration"], [True]
    )

    kept = model.overlay
    assert kept.figure is FigureKind.OVERLAY_2D
    assert (kept.plot_type, kept.bins, kept.sizes) == ("Histogram", [20], False)
    assert (kept.columns, kept.logs) == (["duration"], [True])
    assert kept.datasets == {KEY}


def test_accumulated_values_keep_their_order_and_the_latest_limits(model) -> None:
    first, second = np.array([1.0]), np.array([2.0])

    model.accumulate_overlay_values(first, "a", 0.0, 1.0)
    labels = model.accumulate_overlay_values(second, "b", -1.0, 3.0)

    assert labels == ["a", "b"]
    assert model.overlay.values == [first, second]
    assert (model.overlay.hist_min, model.overlay.hist_max) == (-1.0, 3.0)


def test_the_labels_returned_are_a_copy(model) -> None:
    labels = model.accumulate_overlay_values(np.array([1.0]), "a", None, None)

    labels.append("not kept")

    assert model.overlay.labels == ["a"]


@pytest.mark.parametrize(
    "axis_type, kind", [("2d", FigureKind.EMPTY_2D), ("3d", FigureKind.EMPTY_3D)]
)
def test_clearing_forgets_everything_and_keeps_the_projection(
    model, axis_type: str, kind: FigureKind
) -> None:
    model.add_overlay_dataset(
        KEY, FigureKind.OVERLAY_2D, "Histogram", [20], False, [], []
    )
    model.accumulate_overlay_values(np.array([1.0]), "a", 0.0, 1.0)

    model.clear_overlay(axis_type)

    assert model.overlay == OverlayState(figure=kind)
