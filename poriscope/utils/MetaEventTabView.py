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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, override

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
    - **Commit-time helpers.** ``_extract_commit_event_parameters`` and
      ``validate_single_channel`` read the controls panel's channel selection and
      reject anything that is not exactly one channel.
    - **The data filter.** ``set_data_filter_function`` records the callable the tab
      applies to raw samples before finding or fitting.

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
        channels = [int(ch) for ch in parameters["channel"]]
        return writer, channels

    @log(logger=logger)
    def set_data_filter_function(self, data_filter: Callable) -> None:
        """
        Set the callcable function to filter data

        :param data_filter: a callable function
        :type data_filter: Callable
        """
        self.data_filter = data_filter
