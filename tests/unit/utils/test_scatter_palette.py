"""Tests for the shared scatterplot colours and legend."""

import numpy as np
from matplotlib import colormaps
from matplotlib.figure import Figure

from poriscope.utils.scatter_palette import (
    LEGEND_MARKER_SIZE,
    draw_scatter_legend,
    next_scatter_color,
    scatter_color,
)


def test_scatter_color_takes_tab20_s_dark_shades_then_its_light_ones() -> None:
    """tab20 alternates dark and light; all ten darks come first, then the lights."""
    tab20 = colormaps["tab20"]
    darks = [tab20(i) for i in range(0, 20, 2)]
    lights = [tab20(i) for i in range(1, 20, 2)]
    assert [scatter_color(i) for i in range(20)] == darks + lights
    assert scatter_color(20) == scatter_color(0)


def test_next_scatter_color_follows_the_scatters_already_on_the_axes() -> None:
    """Each overlaid scatter takes the following colour."""
    ax = Figure().add_subplot(1, 1, 1)
    assert next_scatter_color(ax) == scatter_color(0)
    ax.scatter([0], [0])
    assert next_scatter_color(ax) == scatter_color(1)


def test_a_3d_scatter_counts_like_a_2d_one() -> None:
    ax = Figure().add_subplot(1, 1, 1, projection="3d")
    ax.scatter([0], [0], [0])
    assert next_scatter_color(ax) == scatter_color(1)


def test_error_bars_do_not_use_up_colours() -> None:
    """Only scatters count: a dataset's error bars leave the next colour unchanged."""
    ax = Figure().add_subplot(1, 1, 1)
    ax.scatter([0], [0])
    ax.errorbar([0], [0], xerr=[0.1], yerr=[0.1], fmt="none")
    assert next_scatter_color(ax) == scatter_color(1)


def test_legend_dot_keeps_the_points_transparency() -> None:
    ax = Figure().add_subplot(1, 1, 1)
    ax.scatter([0, 1], [0, 1], color=scatter_color(0), alpha=0.75, label="data")

    draw_scatter_legend(ax)

    handle = ax.get_legend().legend_handles[0]
    assert np.isclose(handle.get_markerfacecolor()[3], 0.75)


def test_legend_dot_is_flat_and_the_points_colour() -> None:
    """The legend shows a standard-size dot with no edge in the point's colour."""
    ax = Figure().add_subplot(1, 1, 1)
    ax.scatter([0, 1], [0, 1], s=3, color=scatter_color(2), label="data")

    draw_scatter_legend(ax)

    handle = ax.get_legend().legend_handles[0]
    assert handle.get_markeredgewidth() == 0
    assert handle.get_markersize() == LEGEND_MARKER_SIZE
    assert np.allclose(handle.get_markerfacecolor(), scatter_color(2))
