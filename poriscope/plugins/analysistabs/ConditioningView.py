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
# Kyle Briggs
# Michel Stephan

import logging
import math
from typing import Any, Dict, List, Sequence, Tuple, override

from matplotlib.axes import Axes
from PySide6.QtCore import Signal

from poriscope.plugins.analysistabs.utils.conditioningcontrols import (
    ConditioningControls,
)
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaControls import MetaControls
from poriscope.utils.MetaView import MetaView


@inherit_docstrings
class ConditioningView(MetaView):
    """
    The Conditioning tab's View: one panel per channel, pore size against cycle, with the 1 Hz
    noise of the positive-bias PSDs in the top half and the negative-bias PSDs, inverted, in the
    bottom half.

    The layout follows the conditioning app it was ported from: the pore size and its target
    band on the left axis over the whole panel, the two noise axes logarithmic on the right,
    sharing one range across every channel so channels compare at a glance, and each PSD's
    cycle shaded green, orange or red by its noise against the Good and Decent thresholds.
    A channel with no pore size measured in any cycle is greyed out as disabled.
    """

    logger = logging.getLogger(__name__)

    #: loader, channels, fit start, fit end, good noise, decent noise, noise axis min, bands
    plot_requested = Signal(str, list, float, float, float, float, float, bool)
    #: loader: the View needs that experiment's channels for the panel
    channels_requested = Signal(str)

    #: Where each polarity is drawn: its half of the panel, axis colour, and whether the
    #: axis is inverted so that more noise points away from the dividing line.
    POLARITY_LAYOUT: Dict[str, Dict[str, Any]] = {
        "+": {
            "bounds": (0.52, 0.47),
            "band": (0.5, 1.0),
            "colour": "red",
            "invert": False,
        },
        "-": {
            "bounds": (0.0, 0.47),
            "band": (0.0, 0.5),
            "colour": "blue",
            "invert": True,
        },
    }

    # public API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def handle_parameter_change(
        self, submodel_name: str, action_name: str, args: tuple
    ) -> None:
        """
        React to an action the tab's controls panel has emitted.

        :param submodel_name: Name of the controls submodel the action came from.
        :type submodel_name: str
        :param action_name: Identifier of the action to perform.
        :type action_name: str
        :param args: The action's arguments, as the controls panel packed them.
        :type args: tuple
        :return: None
        :rtype: None
        """
        parameters = args[0]
        if action_name == "plot":
            self.plot_requested.emit(
                parameters["loader"],
                parameters["channels"],
                parameters["fit_start"],
                parameters["fit_end"],
                parameters["good_noise"],
                parameters["decent_noise"],
                parameters["psd_axis_min"],
                parameters["show_bands"],
            )
        elif action_name == "loader_changed":
            self.channels_requested.emit(parameters["loader"])
        elif action_name == "export_plot_data":
            self.export_plot_data.emit()
        else:
            self.logger.warning(
                f"ConditioningView has no handler for the action {action_name!r}"
            )

    @log(logger=logger)
    @override
    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """
        Do nothing: an experiment's state is all in its settings, and a settings change
        reaches this tab through :py:meth:`update_available_plugins`.

        :param metaclass: The metaclass of the plugin instance whose state changed.
        :type metaclass: str
        :param plugin_key: The unique key identifying the plugin instance that changed.
        :type plugin_key: str
        :param reason: A short string identifying what kind of change occurred.
        :type reason: str
        :return: None
        :rtype: None
        """

    @log(logger=logger)
    @override
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Offer every conditioning experiment in the app.

        :param available_plugins: Dict of lists keyed by MetaClass, listing the identifiers of all
                                  instantiated plugins throughout the app.
        :type available_plugins: Dict[str, List[str]]
        """
        super().update_available_plugins(available_plugins)
        self.conditioningcontrols.update_loaders(
            available_plugins.get("MetaConditioningLoader", [])
        )

    @log(logger=logger)
    @override
    def write_back(
        self, action: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> None:
        """
        Show a recorded plot's experiment, channels and numbers in the panel, without emitting.

        :param action: the entry's declared action name
        :type action: str
        :param args: the entry's recorded positional values, empty when every value has a name
        :type args: Tuple[Any, ...]
        :param kwargs: the entry's recorded values, each under its parameter name
        :type kwargs: Dict[str, Any]
        """
        if action != "plot_conditioning":
            return
        if self.conditioningcontrols.set_loader(kwargs["loader"]):
            self.channels_requested.emit(kwargs["loader"])
        else:
            self._say_not_shown("experiment", kwargs["loader"])
        for missing in self.conditioningcontrols.set_values(kwargs):
            self._say_not_shown("channel", missing)

    @log(logger=logger)
    def set_channels(self, channels: Sequence[int]) -> None:
        """
        Offer the chosen experiment's channels in the panel.

        :param channels: the channels, numbered from 0
        :type channels: Sequence[int]
        """
        self.conditioningcontrols.update_channels(channels)

    @log(logger=logger)
    def draw_conditioning(
        self,
        data: Sequence[Dict[str, Any]],
        good_noise: float,
        decent_noise: float,
        psd_axis_min: float,
        show_bands: bool,
    ) -> None:
        """
        Draw one panel per channel: pore size and target band, and the 1 Hz noise of each polarity.

        :param data: one entry per channel, as ``ConditioningModel.plot_data`` builds it
        :type data: Sequence[Dict[str, Any]]
        :param good_noise: noise below this is shaded green, pA^2/Hz
        :type good_noise: float
        :param decent_noise: noise below this is shaded orange, above it red, pA^2/Hz
        :type decent_noise: float
        :param psd_axis_min: the lower end of both noise axes, pA^2/Hz
        :type psd_axis_min: float
        :param show_bands: shade each PSD's cycle by its noise
        :type show_bands: bool
        """
        self.figure.clear()
        self._clear_cache()
        columns = self._columns(len(data))
        rows = math.ceil(len(data) / columns)
        grid = self.figure.add_gridspec(rows, columns)
        noise_max = self._noise_axis_max(data)
        for i, entry in enumerate(data):
            ax = self.figure.add_subplot(grid[i // columns, i % columns])
            self._draw_channel(
                ax,
                entry,
                (good_noise, decent_noise),
                (psd_axis_min, noise_max),
                show_bands,
            )
        self.figure.suptitle(
            f"Pore size and 1 Hz noise against cycle ({len(data)} channels)"
        )
        self.figure.set_layout_engine("constrained")
        self.canvas.draw()
        self._commit_cache()

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Nothing to set up beyond what the base builds.
        """

    @log(logger=logger)
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clears the figure. Nothing here is recorded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        self.figure.clear()
        self.canvas.draw()

    @log(logger=logger)
    @override
    def _build_controls(self) -> MetaControls:
        """
        Build this tab's controls panel and return it.

        :return: the tab's controls panel
        :rtype: MetaControls
        """
        self.conditioningcontrols = ConditioningControls()
        return self.conditioningcontrols

    # private API
    @log(logger=logger)
    def _columns(self, channels: int) -> int:
        """
        How many panels wide the grid is, as the conditioning app chose it.

        :param channels: the number of panels
        :type channels: int
        :return: the number of columns
        :rtype: int
        """
        if channels <= 1:
            return 1
        if channels <= 4:
            return 2
        if channels <= 9:
            return 3
        return 4

    @log(logger=logger)
    def _noise_axis_max(self, data: Sequence[Dict[str, Any]]) -> float:
        """
        The top of every noise axis: just above the noisiest value drawn, on a log scale.

        :param data: the entries being drawn
        :type data: Sequence[Dict[str, Any]]
        :return: the upper limit, pA^2/Hz; 1000 when nothing positive is drawn
        :rtype: float
        """
        values = [
            value
            for entry in data
            if not entry["disabled"]
            for result in entry["psd"].values()
            for value in result["one_hz"]
            if value > 0
        ]
        if not values:
            return 1000.0
        return 10 ** (math.ceil(math.log10(max(values))) + 0.3)

    @log(logger=logger)
    def _draw_channel(
        self,
        ax: Axes,
        entry: Dict[str, Any],
        thresholds: Tuple[float, float],
        noise_range: Tuple[float, float],
        show_bands: bool,
    ) -> None:
        """
        Draw one channel's panel.

        :param ax: the panel's pore-size axes
        :type ax: Axes
        :param entry: the channel's entry from ``ConditioningModel.plot_data``
        :type entry: Dict[str, Any]
        :param thresholds: Good, then Decent, pA^2/Hz
        :type thresholds: Tuple[float, float]
        :param noise_range: the noise axes' lower and upper limits, pA^2/Hz
        :type noise_range: Tuple[float, float]
        :param show_bands: shade each PSD's cycle by its noise
        :type show_bands: bool
        """
        channel = entry["channel"]
        cycles = entry["cycles"]
        label = f"Channel {channel}"
        x_limits = (float(cycles[0]) - 0.5, float(cycles[-1]) + 0.5)
        ax.plot(cycles, entry["max_target"], "--", color="black", lw=0.8, alpha=0.7)
        ax.plot(cycles, entry["min_target"], "--", color="black", lw=0.8, alpha=0.7)
        ax.set_xlim(*x_limits)
        ax.set_xlabel("Cycle #")
        ax.set_ylabel("Pore Size (nm)")
        ax.grid(True, alpha=0.2)
        if entry["disabled"]:
            ax.set_title(f"{label} (disabled)", color="gray")
            ax.set_facecolor((0.5, 0.5, 0.5, 0.8))
            return
        ax.set_title(label)
        ax.scatter(cycles, entry["measured"], s=10, color="black", zorder=3)
        self._update_cache(
            (cycles, f"{label} Cycle"),
            (entry["measured"], f"{label} Pore Size (nm)"),
        )
        ax.plot([0, 1], [0.5, 0.5], transform=ax.transAxes, color="dimgray", lw=0.6)
        for polarity, layout in self.POLARITY_LAYOUT.items():
            ax.text(
                1.09,
                layout["band"][0] + 0.25,
                f"PSD{polarity}",
                transform=ax.transAxes,
                color=layout["colour"],
                va="center",
                rotation=90,
            )
            result = entry["psd"].get(polarity)
            if result is None:
                continue
            if show_bands:
                for cycle, value in zip(result["cycles"], result["one_hz"]):
                    ax.axvspan(
                        cycle - 0.5,
                        cycle + 0.5,
                        ymin=layout["band"][0],
                        ymax=layout["band"][1],
                        color=self.noise_shade(value, *thresholds),
                        zorder=0,
                    )
            bottom, height = layout["bounds"]
            inset = ax.inset_axes([0.0, bottom, 1.0, height])
            inset.set_yscale("log")
            low, high = noise_range
            inset.set_ylim((high, low) if layout["invert"] else (low, high))
            inset.set_xlim(*x_limits)
            inset.yaxis.tick_right()
            inset.tick_params(axis="y", colors=layout["colour"], labelsize=8)
            inset.xaxis.set_visible(False)
            inset.patch.set_alpha(0.0)
            for side in ("top", "left", "bottom"):
                inset.spines[side].set_visible(False)
            inset.spines["right"].set_color(layout["colour"])
            inset.scatter(
                result["cycles"],
                result["one_hz"],
                s=10,
                color=layout["colour"],
                marker="D",
                zorder=4,
            )
            self._update_cache(
                (result["cycles"], f"{label} PSD{polarity} Cycle"),
                (result["one_hz"], f"{label} PSD{polarity} 1 Hz Noise (pA^2/Hz)"),
            )
