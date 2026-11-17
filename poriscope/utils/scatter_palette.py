# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Alejandra Carolina González González

from typing import Any, Tuple

from matplotlib import colormaps
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.lines import Line2D

#: Area, in points squared, of a plotted scatter point.
SCATTER_POINT_SIZE = 3

#: Diameter, in points, of a legend dot.
LEGEND_MARKER_SIZE = 8


def scatter_color(index: int) -> Tuple[float, float, float, float]:
    """
    Return the ``index``-th scatterplot colour: ``tab20``'s ten dark shades, then its ten light ones.

    ``tab20`` alternates each hue's dark and light shade, so its even entries are the
    dark ones.

    :param index: position of the dataset among those drawn on the axes
    :type index: int
    :return: an RGBA colour
    :rtype: Tuple[float, float, float, float]
    """
    position = index % 20
    tab20_index = 2 * position if position < 10 else 2 * (position - 10) + 1
    return colormaps["tab20"](tab20_index)


def next_scatter_color(ax: Axes) -> Tuple[float, float, float, float]:
    """
    Return the colour for the next scatter added to ``ax``.

    Only scatters are counted: error bars are collections too, and would skip colours.

    :param ax: the axis the scatter is about to be added to
    :type ax: Axes
    :return: an RGBA colour
    :rtype: Tuple[float, float, float, float]
    """
    scatters = [c for c in ax.collections if isinstance(c, PathCollection)]
    return scatter_color(len(scatters))


def legend_dot(color: Any, label: str) -> Line2D:
    """
    Return a flat legend dot of the standard size.

    :param color: the dot's colour
    :type color: Any
    :param label: the legend entry's text
    :type label: str
    :return: the legend handle
    :rtype: Line2D
    """
    return Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor=color,
        markersize=LEGEND_MARKER_SIZE,
        markeredgewidth=0,
        label=label,
    )


def draw_scatter_legend(ax: Axes) -> None:
    """
    Draw ``ax``'s legend with each scatter shown as a flat dot of the standard size.

    :param ax: the axis whose legend to draw
    :type ax: Axes
    :return: None
    :rtype: None
    """
    handles, labels = ax.get_legend_handles_labels()
    flat = [
        legend_dot(h.get_facecolor()[0], lab) if isinstance(h, PathCollection) else h
        for h, lab in zip(handles, labels)
    ]
    ax.legend(flat, labels, loc="best")
