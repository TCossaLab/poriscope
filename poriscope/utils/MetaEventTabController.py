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
from typing import Callable, Optional

from PySide6.QtCore import Slot

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


class MetaEventTabController(MetaController):
    """
    Shared base for the Controllers of the two event-oriented analysis tabs.

    ``RawDataController`` and ``EventAnalysisController`` both drive a tab that works
    from a reader and a time-series channel rather than from a database of results:
    the user picks a reader, a filter and a channel, and the tab finds or fits events
    in the raw signal. The two carried two methods verbatim between them; this base
    holds that shared half so there is one copy to fix.

    What a subclass inherits:

    - ``update_available_plugins``, which passes the app-wide plugin registry down to
      both the View and the Model when a plugin is instantiated anywhere.
    - ``update_plot_samplerate``, which relays the sampling rate of the trace being
      plotted to the View.
    - ``_resolve_callable_filter``, which fetches a filter plugin's callable for the
      paths Step 4a converted, or None where none was asked for or it could not be
      fetched.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, so records made by the
      methods it defines itself stay attributed to its own module.
    - **``self.view`` and ``self.model``**, built in its ``_init()`` as
      ``MetaController`` requires.

    :ivar logger: the module logger the shared methods below log under
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @Slot(dict)
    def update_available_plugins(self, available_plugins: dict) -> None:
        """
        Relay an updated dict of available plugin keys, keyed by metaclass, to both the model and the view.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: dict
        """
        self.logger.debug(
            f"Controller received available plugins update: {available_plugins}"
        )
        self.model.update_available_plugins(available_plugins)
        self.view.update_available_plugins(available_plugins)

    @log(logger=logger)
    def _resolve_callable_filter(self, data_filter: str) -> Optional[Callable]:
        """
        Fetch a filter's callable, or proceed without one.

        A filter that cannot be fetched is a warning rather than a failure, because the
        work is still worth doing unfiltered - which is what both Views did.

        Shared rather than copied: Step 4a needs it on RawData's event-plot and
        event-finding paths and on EventAnalysis's fitting path, and two identical bodies
        in the ``*Controller.py`` family would have *added* removable lines to the
        duplication ratchet. It is stateless and adds no contract, which is what makes it
        safe on the common base rather than needing an intermediate (method rule 34).

        :param data_filter: the filter plugin's key, or "" for no filtering
        :type data_filter: str
        :return: the callable, or None if none was asked for or it could not be fetched
        :rtype: Optional[Callable]
        """
        if not data_filter:
            return None
        try:
            resolved: Callable = self.model.call(
                "MetaFilter", data_filter, "get_callable_filter"
            )
        except Exception:
            self.logger.warning(
                f"Unable to load filter {data_filter}, proceeding without a filter"
            )
            return None
        return resolved

    @log(logger=logger)
    def update_plot_samplerate(self, samplerate: float) -> None:
        """
        Set the sampling rate to be used for time axis conversion in the plot.

        :param samplerate: Sampling rate in Hz.
        :type samplerate: float
        """
        self.view.update_plot_samplerate(samplerate)
