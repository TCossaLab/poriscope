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
import math
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Slot

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaEventTabView import MetaEventTabView

#: How far a filter's declared sample rate may sit from the data's before the filter is
#: refused. A hand-typed 3333333 Hz against a header's 3333333.2008785727 Hz is a cutoff
#: error of a hundredth of a percent and passes; a 100 kHz filter on 4 MHz data does not.
FILTER_SAMPLERATE_TOLERANCE = 1e-3


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
    - ``_resolve_callable_filter``, which fetches a filter plugin's callable for the
      paths that need one, or None where none was asked for or it could not be
      fetched.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, so records made by the
      methods it defines itself stay attributed to its own module.
    - **``self.view`` and ``self.model``**, built in its ``_init()`` as
      ``MetaController`` requires.

    :ivar logger: the module logger the shared methods below log under
    """

    logger = logging.getLogger(__name__)

    #: Redeclared with this tab's own types, so the type checker sees the methods
    #: the base View and Model do not have (see MetaController.view).
    view: MetaEventTabView

    @log(logger=logger)
    @Slot(dict)
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Relay an updated dict of available plugin keys, keyed by metaclass, to both the model and the view.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: Dict[str, List[str]]
        """
        self.logger.debug(
            f"Controller received available plugins update: {available_plugins}"
        )
        self.model.update_available_plugins(available_plugins)
        self.view.update_available_plugins(available_plugins)

    @log(logger=logger)
    def _resolve_callable_filter(
        self,
        data_filter: str,
        samplerate_of: Optional[Callable[[], float]] = None,
    ) -> Optional[Callable]:
        """
        Fetch a filter's callable, or proceed without one.

        A filter that cannot be fetched is a warning rather than a failure, because the
        work is still worth doing unfiltered - which is what both Views did.

        Shared rather than copied: RawData's event-plot and event-finding paths and
        EventAnalysis's fitting path all need it, and two identical bodies in the
        ``*Controller.py`` family would *add* removable lines to the
        duplication ratchet. It is stateless and adds no contract, which is what makes it
        safe on the common base: it carries no instance state and adds no abstract
        hook, so a subclass that never calls it pays nothing.

        With ``samplerate_of`` the filter is also checked against the data by
        :meth:`_verify_filter_samplerate`, whose ``ValueError`` on a mismatch propagates
        out of here so the caller abandons the action rather than filtering at the
        wrong rate.

        :param data_filter: the filter plugin's key, or "" for no filtering
        :type data_filter: str
        :param samplerate_of: returns the rate, in Hz, of the data about to be filtered;
            None skips the check
        :type samplerate_of: Optional[Callable[[], float]]
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
        if samplerate_of is not None:
            self._verify_filter_samplerate(data_filter, samplerate_of)
        return resolved

    @log(logger=logger)
    def _verify_filter_samplerate(
        self, data_filter: str, samplerate_of: Callable[[], float]
    ) -> None:
        """
        Refuse a filter built for a sample rate other than the data's.

        Asked of the filter, not assumed: a filter declares through
        ``get_data_requirements`` which of its settings the data must match, and only a
        filter that declares ``Samplerate`` is checked. The data's rate is fetched lazily,
        so a filter with nothing to declare costs no extra call. A rate of 1 is the tabs'
        could-not-read fallback and skips the check, as does a declaration that cannot
        be read; neither is the mismatch this guards against.

        :param data_filter: the filter plugin's key
        :type data_filter: str
        :param samplerate_of: returns the rate, in Hz, of the data about to be filtered
        :type samplerate_of: Callable[[], float]
        :raises ValueError: if the declared and actual rates differ by more than
            ``FILTER_SAMPLERATE_TOLERANCE``, relatively
        """
        try:
            requirements: Dict[str, float] = self.model.call(
                "MetaFilter", data_filter, "get_data_requirements"
            )
        except Exception:
            self.logger.warning(
                f"Unable to read what {data_filter} requires of its data; applying it unchecked"
            )
            return
        declared = requirements.get("Samplerate")
        if declared is None:
            return
        samplerate = samplerate_of()
        if samplerate <= 1:
            return
        if math.isclose(declared, samplerate, rel_tol=FILTER_SAMPLERATE_TOLERANCE):
            return
        message = (
            f"Filter {data_filter} was built for {declared:.10g} Hz but this data is at "
            f"{samplerate:.10g} Hz; edit the filter's Samplerate or choose another filter"
        )
        self.logger.error(message)
        self.add_text_to_display.emit(message, self.__class__.__name__)
        raise ValueError(message)
