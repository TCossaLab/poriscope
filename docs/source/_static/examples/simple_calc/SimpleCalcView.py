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
# Poriscope contributors

import logging
from typing import Any, Dict, List, Tuple, override

from PySide6.QtCore import Signal
from SimpleCalcControls import SimpleCalcControls

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaControls import MetaControls
from poriscope.utils.MetaView import MetaView


@inherit_docstrings
class SimpleCalcView(MetaView):
    """
    A two-number calculator that plots its results.

    This is its View, which lays out the tab's widgets and draws its plots.
    """

    logger = logging.getLogger(__name__)

    #: Intents: what the user asked for, carrying what was on screen when they asked.
    calculate_requested = Signal(float, str, float)  # left, operator, right
    reset_requested = Signal()

    # public API
    @log(logger=logger)
    def show_results(self, results: List[float]) -> None:
        """
        List the results in the panel and plot them, oldest first.

        :param results: Every result since the last reset.
        :type results: List[float]
        """
        self.simplecalccontrols.set_results(results)
        self.figure.clear()
        if results:
            ax = self.figure.add_subplot(111)
            steps = range(1, len(results) + 1)
            ax.plot(steps, results, marker="o")
            ax.set_xticks(steps)
            ax.set_xlabel("Calculation")
            ax.set_ylabel("Result")
        self.canvas.draw()

    @log(logger=logger)
    @override
    def write_back(
        self, action: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> None:
        """
        Show a replayed calculation's numbers and operator in the panel, without emitting.

        :param action: the entry's declared action name
        :type action: str
        :param args: the entry's recorded positional values, empty when every value has a name
        :type args: Tuple[Any, ...]
        :param kwargs: the entry's recorded values, each under its parameter name
        :type kwargs: Dict[str, Any]
        """
        if action == "calculate":
            self.simplecalccontrols.set_values(
                kwargs["left"], kwargs["operator"], kwargs["right"]
            )

    # public API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def handle_parameter_change(
        self, submodel_name: str, action_name: str, args: tuple
    ) -> None:
        """
        React to an action the tab's controls panel has emitted.

        Abstract because ``_set_control_area`` connects the panel's ``actionTriggered``
        signal straight to it while the View is still being constructed, so a tab that
        does not provide it raises ``AttributeError`` out of ``__init__`` before it can
        ever be shown. Declaring it here is what turns that into a refusal to instantiate
        the class at all, which is the only form of the failure that names the cause. The
        three sibling handlers ``_set_control_area`` connects beside it -
        ``handle_edit_triggered``, ``handle_add_triggered`` and ``handle_delete_triggered``
        - are concrete on this class and need no implementation.

        A tab that lays out its own control area by overriding ``_set_control_area``
        never has this connected, and may implement it as a no-op.

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
        if action_name == "calculate":
            self.calculate_requested.emit(
                parameters["left"], parameters["operator"], parameters["right"]
            )
        elif action_name == "reset":
            self.reset_requested.emit()
        else:
            self.logger.warning(
                f"SimpleCalcView has no handler for the action {action_name!r}"
            )

    @log(logger=logger)
    @override
    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """
        Called by MainController whenever any plugin instance's internal state
        changed elsewhere in the app (e.g. new columns committed to a loader's
        table). Must be implemented by subclasses, even if the correct
        implementation is a no-op (pass).

        Where the implementation is not a no-op, it must make a deliberate
        decision about whether the notification applies to this tab, filter
        accordingly, and determine what the specific reaction should be.

        Currently known (metaclass, reason) combinations in use:

        - ("MetaDatabaseLoader", <loader_key>, "columns") — emitted after
          columns are added to a loader's table (see
          ClusteringView._commit_clusters, ProteinView._commit_fits).

        :param metaclass: The metaclass of the plugin instance whose state
                        changed (e.g. "MetaDatabaseLoader").
        :type metaclass: str
        :param plugin_key: The unique key identifying the plugin instance that
                        changed (e.g. "SQLiteDBLoader_0").
        :type plugin_key: str
        :param reason: A short string identifying what kind of change occurred
                    (e.g. "columns"). Free-form; the emitter and every
                    receiver must agree on the exact string used.
        :type reason: str
        :return: None
        :rtype: None
        """
        pass  # this tab uses no data plugins, so no plugin's state concerns it

    @log(logger=logger)
    @override
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up-to-date
        list of possible data sources for use by this plugin.

        :param available_plugins: Dict of lists keyed by MetaClass, listing the identifiers of all
                                  instantiated plugins throughout the app.
        :type available_plugins: Dict[str, List[str]]
        """
        super().update_available_plugins(available_plugins)

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Perform additional initialization specific to the algorithm being implemented.
        Must be implemented by subclasses.

        This function is called at the end of the class constructor to perform additional
        initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        pass  # the controls panel and the plot canvas are all this tab needs

    @log(logger=logger)
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clears the figure and reinitializes axes. Nothing here is recorded: a tab whose resets are part of its action history declares a reset action on its Controller, which asks the View to clear, and a replay or Undo starts from the last recorded reset.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        self.show_results([])

    @log(logger=logger)
    @override
    def _build_controls(self) -> MetaControls:
        """
        Build this tab's controls panel and return it.

        The subclass also stores it under whatever name the rest of that tab uses -
        ``self.metadatacontrols``, ``self.rawdatacontrols`` and so on - because those
        names appear throughout each tab. This hook
        only has to hand the widget back, so the base can wire it and place it.

        Concrete rather than abstract, returning an empty panel, so that a tab which
        lays out its own control area can override ``_set_control_area`` instead and
        never implement this. Making it abstract would leave such a tab uninstantiable.

        Being concrete is also why ``scripts/new_plugin.py`` writes an override rather
        than leaving it to be discovered: the default is legal and constructs fine, so a
        tab that does not override it simply shows an empty strip under its plot with
        nothing to say which method fills it.

        :return: the tab's controls panel
        :rtype: MetaControls
        """
        self.simplecalccontrols = SimpleCalcControls()
        return self.simplecalccontrols
