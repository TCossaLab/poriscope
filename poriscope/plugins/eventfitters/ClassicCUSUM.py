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

import logging
from typing import Any, Dict, List, Optional, override

from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class ClassicCUSUM(CUSUM):
    """
    Abstract base class to analyze and flag the start and end times of regions
    of interest in a timeseries for further analysis.
    """

    logger = logging.getLogger(__name__)

    # public API, must be overridden by subclasses:
    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Declare the settings this event fitter exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to build
        the settings dialog and to sanity-check whatever the user enters; the accepted
        values are then readable through ``self.settings``. See
        :py:meth:`~poriscope.utils.MetaEventFitter.MetaEventFitter.get_empty_settings`
        for the structure of the dict and what ``Type``, ``Value``, ``Min``, ``Max``, ``Options`` and
        ``Units`` mean in it, and for the reserved keys the GUI builds file pickers
        from.

        The ``super()`` call supplies the mandatory ``"MetaEventLoader"`` key, which is how
        this plugin is wired to its data source.

        The keys this plugin adds:

        - ``Step Size`` (σ) - the smallest change the detector should call a sublevel
          transition, **in baseline standard deviations** rather than the pA ``CUSUM``
          takes. That is the only difference between the two fitters.
        - ``Sensitivity`` - divides the detection threshold that CUSUM chooses from the
          event's length and the step size. 1, the default and the minimum, is the most
          conservative; higher values call smaller or shorter steps, at the cost of more
          false transitions.
        - ``Rise Time`` (us) - how much of the signal either side of a transition to
          exclude from the level averages.
        - ``Max Sublevels`` - the largest number of sublevels an event may be fitted
          with before it is rejected; 0 removes the limit.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaEventLoader" as a key, with explicitly set Type MetaEventLoader.
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Step Size"] = {"Type": float, "Min": 0.0, "Units": "σ"}
        settings["Sensitivity"] = {"Type": float, "Value": 1.0, "Min": 1.0, "Max": 5.0}
        return settings

    @log(logger=logger)
    @override
    def _step_size_in_sigma(self, baseline_std: float) -> float:
        """
        Return the ``Step Size`` setting, which this fitter already takes in units of the local baseline standard deviation.

        ``CUSUM`` divides a pA step by the local sigma here; ``ClassicCUSUM`` has the user
        state the step in sigma, so the value is used as given. Everything else about the
        detector is inherited.

        :param baseline_std: the local baseline standard deviation, in pA (unused here)
        :type baseline_std: float
        :return: the step size in units of ``baseline_std``
        :rtype: float
        """
        return float(self.settings["Step Size"]["Value"])
