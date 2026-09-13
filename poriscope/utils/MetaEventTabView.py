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
# Kyle Briggs

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, override

from PySide6.QtWidgets import QMessageBox

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaView import MetaView


class MetaEventTabView(MetaView):
    """
    Shared base for the Views of the two event-oriented analysis tabs.

    ``RawDataView`` and ``EventAnalysisView`` both drive a tab that works from a
    reader and a time-series channel rather than from a database of results: the user
    picks a reader, a filter and a channel, and the tab finds or fits events in the
    raw signal. The two carried five methods verbatim between them; this base holds
    that shared half so there is one copy to fix.

    What a subclass inherits:

    - **Two of ``MetaView``'s abstract hooks, made concrete.**
      ``notify_plugin_state_changed`` is a deliberate no-op for both tabs - neither
      shows a database column list, so a plugin-state change elsewhere in the app is
      not their business - and ``_reset_actions`` clears the figure identically in
      each. ``MetaView`` still declares both abstract; satisfying them here is what
      keeps both subclasses instantiable without a per-tab copy.
    - ``_channels_from``, which reads the channel selection out of a parameter dict
      and reports a missing one as ``ValueError``, which every caller already guards.
    - **Commit-time helpers.** ``_extract_commit_event_parameters`` and
      ``validate_single_channel`` read the controls panel's channel selection and
      reject anything that is not exactly one channel.
    - **The data filter.** ``set_data_filter_function`` records the callable the tab
      applies to raw samples before finding or fitting.
    - **The event-index range helpers.** ``_parse_event_indices``, ``_expand_event_indices``,
      ``_shift_ranges``, ``_merge_ranges`` and ``_format_ranges`` turn the event-index
      field's text into ranges and back. They lived on ``MetaView`` until Step 3e, where
      only these two tabs ever called them; they are pure apart from one logger call.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, so records made by the
      methods it defines itself stay attributed to its own module.
    - **``MetaView``'s remaining abstract methods** - ``_init``, ``_set_control_area``
      and ``update_available_plugins`` - which this base does not implement.

    :ivar logger: the module logger the shared methods below log under
    :ivar data_filter: the callable applied to raw samples, or None for no filtering
    """

    logger = logging.getLogger(__name__)

    #: Assigned by ``set_data_filter_function`` and by each tab's own plot paths.
    data_filter: Optional[Callable]

    @log(logger=logger)
    def _parse_event_indices(
        self, indices: str, allow_floats: bool
    ) -> list[tuple[float, float]]:
        """
        Parse '7-10,12' → [(7,10), (12,12)]
        If allow_floats=True, accepts '1.5-4.5,6' → [(1.5, 4.5), (6.0, 6.0)];
        otherwise every bound is parsed with int().
        """
        result: list[tuple[float, float]] = []
        caster = float if allow_floats else int

        for segment in indices.split(","):
            segment = segment.strip()
            if "-" in segment:
                try:
                    start, end = map(caster, segment.split("-"))
                    result.append((start, end))
                except ValueError:
                    self.logger.warning(f"Invalid range segment: {segment}")
            elif segment:
                try:
                    val = caster(segment)
                    result.append((val, val))
                except ValueError:
                    self.logger.warning(f"Invalid index segment: {segment}")

        return result

    @log(logger=logger)
    def _shift_ranges(
        self, ranges: Sequence[tuple[float, float]], direction: str, offset: float
    ) -> list[tuple[float, float]]:
        """Shift each tuple range left or right."""
        shifted: list[tuple[float, float]] = []
        for start, end in ranges:
            if start == end:  # Sigle index
                val = start + offset if direction == "right" else start - offset
                shifted.append((val, val))
            else:  # Range
                new_start = (
                    end + offset
                    if direction == "right"
                    else ((2 * start) - end) - offset
                )
                new_end = (
                    ((2 * end) - start) + offset
                    if direction == "right"
                    else start - offset
                )
                shifted.append((new_start, new_end))
        return shifted

    @log(logger=logger)
    def _merge_ranges(
        self, ranges: Sequence[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Merge overlapping or contiguous ranges."""
        merged: list[tuple[float, float]] = []
        for start, end in sorted(ranges):
            if not merged or merged[-1][1] < start - 1:
                merged.append((start, end))
            else:
                last_start, last_end = merged[-1]
                merged[-1] = (last_start, max(last_end, end))
        return merged

    @log(logger=logger)
    def _format_ranges(self, ranges: Sequence[tuple[float, float]]) -> str:
        """Format list of tuples into '8-11,13'"""
        return ",".join(
            f"{start}-{end}" if start != end else str(start) for start, end in ranges
        )

    @log(logger=logger)
    def _expand_event_indices(self, indices_str: str) -> list[int]:
        """
        Expand '1,3-5' → [1,3,4,5], exclude segments with negatives.
        """
        result: Set[int] = set()
        for segment in indices_str.split(","):
            segment = segment.strip()
            try:
                if "-" in segment:
                    parts = segment.split("-")
                    if len(parts) != 2:
                        raise ValueError
                    start, end = map(int, parts)
                    if start < 0 or end < 0:
                        continue
                    result.update(range(start, end + 1))
                else:
                    val = int(segment)
                    if val < 0:
                        continue
                    result.add(val)
            except ValueError:
                continue
        return sorted(result)

    @log(logger=logger)
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history if @register_action is being used to keep track of actions. Only actions applied after the most recent call to this function will be recreated if the related file is loaded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        pass

    @log(logger=logger)
    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """
        This tab does not currently react to any plugin_state_changed
        notifications.

        :param metaclass: The metaclass of the plugin instance whose state
                        changed.
        :type metaclass: str
        :param plugin_key: The unique key identifying the plugin instance that
                        changed.
        :type plugin_key: str
        :param reason: A short string identifying what kind of change occurred.
        :type reason: str
        :return: None
        :rtype: None
        """
        pass

    @log(logger=logger)
    def _channels_from(self, parameters: Dict[str, Any]) -> List[int]:
        """
        The selected channels, as ints, from a controls-panel parameter dict.

        Raises ``ValueError`` rather than letting ``KeyError`` out when the key is
        absent. Every caller of the six extractors that need this already guards
        ``ValueError`` and none guarded ``KeyError``, so a parameter dict without a
        ``channel`` key escaped a handler advertising "Parameter extraction failed" -
        in one case out of the tab entirely, since ``handle_parameter_change`` has no
        handler of its own. Latent rather than live, because the controls panel always
        supplies the key.

        Those six extractors across the two event tabs each repeated this comprehension,
        which is why the guard goes here rather than being written out six times.

        :param parameters: the parameter dict the controls panel emitted
        :type parameters: Dict[str, Any]
        :raises ValueError: if the parameters carry no channel selection
        :return: the selected channel numbers
        :rtype: List[int]
        """
        if "channel" not in parameters:
            raise ValueError("No channel supplied in the parameters")
        return [int(ch) for ch in parameters["channel"]]

    @log(logger=logger)
    def validate_single_channel(self, channels: Sequence[int]) -> None:
        """
        Ensure only one channel is selected.

        :param channels: List of selected channel indices.
        :type channels: Sequence[int]
        :raises ValueError: If more than one channel is selected.
        """
        if len(channels) > 1:
            raise ValueError(
                "Unable to plot events from multiple channels, select only one"
            )

    @log(logger=logger)
    def _extract_commit_event_parameters(
        self, parameters: Dict[str, Any]
    ) -> Tuple[Optional[str], List[int]]:
        """
        Extract writer and channels from parameters.

        :param parameters: Input dictionary.
        :type parameters: Dict[str, Any]
        :return: (writer, channels)
        :rtype: Tuple[Optional[str], List[int]]
        """
        writer = parameters.get("writer")
        channels = self._channels_from(parameters)
        return writer, channels

    @log(logger=logger)
    def confirm_unfiltered_run(self, operation: str) -> bool:
        """
        Ask the user to confirm launching an analysis with no filter selected.

        Running an event finder or fitter on unfiltered data is a legitimate choice, but
        on a noisy trace it can be a **degenerate** one: the threshold is crossed
        constantly and effectively every sample registers as an event, which grinds for a
        very long time and is easy to mistake for a hang. Cancelling does work -
        ``find_events`` reads the abort flag at every chunk boundary and breaks out of the
        range immediately - but with that many events a single chunk takes long enough
        that the cancel can look as though it has not registered.

        Shared by the two tabs that launch this kind of work rather than copied into both.
        It is stateless and adds no contract, which is what makes it safe on the common
        base rather than needing an intermediate (method rule 34).

        :param operation: what is about to run, named for the prompt, e.g. "Event finding"
        :type operation: str
        :return: True to proceed, False if the user declined
        :rtype: bool
        """
        reply = QMessageBox.question(
            self,
            "No filter selected",
            f"{operation} is about to run on unfiltered data."
            "\n\nOn a noisy trace this can register almost every sample as an event, "
            "which may take a very long time. Cancelling will work, but it only takes "
            "effect at the end of the current chunk, so it may be slow to respond."
            "\n\nContinue without a filter?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            self.logger.info(f"{operation} cancelled: no filter selected")
            return False
        return True

    @log(logger=logger)
    def set_data_filter_function(self, data_filter: Callable) -> None:
        """
        Set the callcable function to filter data

        :param data_filter: a callable function
        :type data_filter: Callable
        """
        self.data_filter = data_filter
