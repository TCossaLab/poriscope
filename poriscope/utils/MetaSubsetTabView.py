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

import json
import logging
import os
from abc import abstractmethod
from typing import Any, Dict, Iterator, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDialog, QFileDialog, QMessageBox

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabControls import MetaSubsetTabControls
from poriscope.utils.MetaView import MetaView
from poriscope.views.widgets.add_subset_filter_dialog import AddSubsetFilterDialog
from poriscope.views.widgets.edit_subset_filter_dialog import EditSubsetFilterDialog
from poriscope.views.widgets.multiselect import MultiSelectComboBox
from poriscope.views.widgets.SelectionTree import SelectionTree


class MetaSubsetTabView(MetaView):
    """
    Shared base for the Views of the two subset-filtering analysis tabs.

    ``MetadataView`` and ``ProteinView`` both drive a tab whose data comes from a
    ``MetaDatabaseLoader``: the user picks an experiment and channels from a
    selection tree, builds a named subset filter over the queried columns, and plots
    or exports the rows that come back. The two were written by copy-paste and
    carried fifteen methods verbatim between them; this base holds that shared half
    so there is one copy to fix.

    What a subclass inherits:

    - **Query state.** ``set_query``, ``set_event_query`` and ``set_experiment_id``
      receive the SQL and the scope the Controller
      resolved, and optionally echo it to the status panel.
    - **Column and experiment state.** ``update_available_columns`` and
      ``set_units`` keep the tab's column comboboxes and axis labels in step with the
      loader's description of the database.
    - **Subset filters.** ``_delete_filter``, ``replace_filter_item``,
      ``update_filter_name`` and ``on_raw_filter_validated`` keep the filter combobox
      in step with ``subset_filters``, reaching the combobox through
      ``_subset_controls``. ``_save_filter``, ``_delete_filter_by_name``,
      ``_show_filter_info_dialog`` and ``clear_pending_filter_state`` manage the named
      filters in ``subset_filters`` and the three pending fields the Controller reads
      back after a validation round-trip. ``_show_add_filter_dialog`` and
      ``show_edit_filter_dialog`` open the two filter dialogs and validate what they
      return, through ``_reject_non_select_raw_filter`` and the Controller;
      ``_save_filter`` and ``_load_filter`` write them to and read them back from a
      JSON file.
    - **Experiment selection.** ``show_selection_tree`` and
      ``request_experiment_structure`` drive the ``SelectionTree`` dialog and remember
      what was chosen per loader.
    - **The selected filters.** ``get_selected_filters`` reads the filter combobox
      through ``_subset_controls``, the property each tab implements below.
    - **The filtered event_id cache.** ``_rebuild_event_id_cache`` queries every
      event_id matching the current filter and scope, sorted, and keeps the four
      ``current_*``/``filtered_event_ids`` values the staleness checks compare.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, so that records made by
      the methods it defines itself stay attributed to its own module. Methods defined
      *here* log under this module, which is the convention ``MetaView`` already
      follows for its shared code.
    - **``_subset_controls``**, a one-line property returning whatever name the tab
      holds its controls panel under, so the shared methods here can reach it.
    - **The five abstract methods ``MetaView`` declares**, unchanged - this base
      implements none of them.

    Deliberately *not* shared: ``relay_query`` and the pending-filter state it reads
    stay per-tab until Step 4d moves that state to the Model.

    :ivar logger: the module logger the shared methods below log under
    :ivar subset_filters: named subset filters, filter name to SQL WHERE clause
    :ivar selected_experiment_and_channels_by_loader: per-loader selection tree state
    """

    #: Asks the Controller for a loader's column names. Step 4a replaced a
    #: ``global_signal`` emit whose answer came back through ``update_column_names``
    #: several hops later; the answer arrives one hop later now and a loader that
    #: cannot be read is reported instead of failing silently in the dispatcher.
    column_names_requested = Signal(str)

    #: Asks the Controller for a loader's experiment-and-channel structure. The loader
    #: key is carried so the answer can be filed under it, which is what the bus used
    #: its ``ret_args`` for.
    experiment_structure_requested = Signal(str)

    #: Asks the Controller to validate an assisted subset filter: the loader's key,
    #: the filter expression, and which intent the answer serves
    #: (``validate_new_filter`` or ``validate_edited_filter``). Step 4a replaced a
    #: ``global_signal`` emit whose answer came back through ``relay_query``; the
    #: Controller now calls the loader directly and invokes ``relay_query`` itself, so
    #: a filter naming a column the database does not have is *reported* rather than
    #: swallowed by the dispatcher.
    #:
    #: The columns the throwaway validation query selects are resolved by the
    #: Controller, not carried here - see ``MetaSubsetTabController.validate_filter``.
    filter_validation_requested = Signal(str, str, str)

    #: The same for a raw filter, which is a complete SELECT the loader checks with
    #: ``validate_filter_query`` rather than building a query around. The answer
    #: arrives through ``on_raw_filter_validated``.
    raw_filter_validation_requested = Signal(str, str)

    logger = logging.getLogger(__name__)

    #: Where ``relay_query_result`` parks a query's answer for the emitter to read on
    #: the next statement. Assigned in each subclass's ``_init`` as well, so that a
    #: read before any query has run sees None rather than raising. Goes away with the
    #: last of the emit-then-read pairs.
    #:
    #: A DataFrame in practice, typed ``Any`` because a View may not import pandas -
    #: ``check_mvc_boundary``'s rule 2, whose target is zero, so earning a new
    #: allowlist entry for a member already scheduled for deletion would be a poor
    #: trade. The two tabs keep the precise type where they use it, and so does
    #: ``MetaSubsetTabController.relay_query_result``, which is allowed pandas.
    relayed_query_result: Optional[Any]

    #: Assigned in each subclass's ``_init``, identically in both tabs today. The
    #: annotation moves here with the methods that read it; the assignment stays with
    #: the subclass, since ``MetaView`` gives this base no ``_init`` of its own.
    #: The four ``current_*``/``filtered_event_ids`` values are the filter-aware event
    #: navigation cache, rebuilt when the filter or the scope changes.
    current_channel: Optional[int]
    current_experiment: Optional[str]
    current_sql_filter: Optional[str]
    filtered_event_ids: List[int]
    _pending_filter_name: Optional[str]
    _pending_filter_text: Optional[str]
    _pending_old_filter_name: Optional[str]
    _show_event_sql_in_display: bool
    _show_sql_in_display: bool
    selected_experiment_and_channels_by_loader: Dict[str, Dict[str, List[str]]]
    subset_filters: Dict[str, str]

    #: Set by their own setters rather than in ``_init``, in both tabs today.
    #: Declared here without a value so the contract is visible and mypy can see it,
    #: while reading one before its setter has run stays the AttributeError it is now.
    experiment_id: Optional[int]
    event_data_generator: Iterator[Any]
    event_query: str
    query: str
    selection_tree: SelectionTree
    table_name: str
    units: Dict[str, str]

    def _connect_control_signals(self, controls: MetaSubsetTabControls) -> None:
        """
        Connect the two filter signals only a subset tab's controls panel carries.

        ``MetaView._set_control_area`` wires the four every panel has; these two are
        declared on ``MetaSubsetTabControls`` and were the sole difference between the
        Metadata and Protein copies of that method before Step 3a-bis.

        :param controls: the panel just built by ``_build_controls``
        :type controls: MetaSubsetTabControls
        """
        controls.edit_filter_requested.connect(self.show_edit_filter_dialog)
        controls.delete_filter_requested.connect(self._delete_filter_by_name)

    @log(logger=logger)
    def relay_query_result(self, result: Optional[Any]) -> None:
        """
        A callback from a global_signal call that stores the result of a DB query.

        Shared by the ``query_database_directly`` and ``load_metadata`` dispatches,
        which return the same thing: the rows, an empty frame if none matched, or
        None if the query could not be built or run. Read back by
        ``_rebuild_event_id_cache`` and by the tabs' own plot paths.

        Typed ``Any`` rather than ``Optional[pd.DataFrame]`` because a View may not
        import pandas; see ``relayed_query_result`` above.

        :param result: DataFrame returned by the query, or None if it failed.
        :type result: Optional[Any]
        """
        self.relayed_query_result = result

    @log(logger=logger)
    def _delete_filter(self, name: str) -> None:
        """
        Remove a named subset filter and take its row out of the combobox.

        Promoted from both subset tabs, and **no longer abstract**. The reason
        recorded for its abstractness - that each tab rebuilds its own filter
        widgets - was true only because each reached its panel under its own name;
        the two bodies were otherwise identical, and ``_subset_controls`` is what
        that reason reduced to.

        :param name: the filter to remove
        :type name: str
        :return: None
        :rtype: None
        """
        self.subset_filters.pop(name, None)

        list_widget = self._subset_controls.filter_comboBox.listWidget
        for i in reversed(range(list_widget.count())):
            widget = list_widget.itemWidget(list_widget.item(i))
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.text() == name:
                    list_widget.takeItem(i)
                    break

        self._subset_controls.filter_comboBox.refreshDisplayText()

    @log(logger=logger)
    def replace_filter_item(self, name: str) -> None:
        """
        Remove any existing filter item with the same name and add the new one.

        Promoted from both subset tabs, whose copies differed only in the name each
        held its controls panel under.

        :param name: The name of the filter to (re)add.
        :type name: str
        :return: None
        :rtype: None
        """
        list_widget = self._subset_controls.filter_comboBox.listWidget
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox and checkbox.text() == name:
                list_widget.takeItem(i)
                break

        self._subset_controls.filter_comboBox.addItem(name)
        self._subset_controls.filter_comboBox.selectItem(name, select=True)

    @log(logger=logger)
    def update_filter_name(self, old_name: str, new_name: str) -> None:
        """
        Replace old filter name with new one in the ComboBox, removing any duplicates.

        Promoted from both subset tabs, whose copies differed only in the name each
        held its controls panel under.

        :param old_name: The filter name being replaced.
        :type old_name: str
        :param new_name: The filter name to display instead.
        :type new_name: str
        :return: None
        :rtype: None
        """
        list_widget = self._subset_controls.filter_comboBox.listWidget

        # Remove old name
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox and checkbox.text() == old_name:
                list_widget.takeItem(i)
                break

        # Remove new name if it already exists and is different
        if new_name != old_name:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                widget = list_widget.itemWidget(item)
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.text() == new_name:
                    list_widget.takeItem(i)
                    break

        # Add updated name
        self._subset_controls.filter_comboBox.addItem(new_name)
        self._subset_controls.filter_comboBox.selectItem(new_name, select=True)
        self._subset_controls.filter_comboBox.refreshDisplayText()

    @log(logger=logger)
    def on_raw_filter_validated(self, valid: bool, error_msg: str) -> None:
        """
        Commit a raw SQL filter once the loader has said the query is valid.

        Promoted from both subset tabs. Beyond the controls-panel name they
        diverged in one place, the same one the two filter dialogs diverged in and
        settled the same way: an invalid filter is reported in a **modal**, which
        was Metadata's behaviour, rather than on the status panel.

        :param valid: Whether the query is valid.
        :type valid: bool
        :param error_msg: Error message if invalid.
        :type error_msg: str
        :return: None
        :rtype: None
        """
        if not valid:
            QMessageBox.warning(
                self,
                "Invalid Raw SQL Filter",
                f"The filter could not be validated:\n\n{error_msg}",
            )
            self.clear_pending_filter_state()
            return

        name = self._pending_filter_name
        filter_text = self._pending_filter_text
        old_name = self._pending_old_filter_name

        if name is None:
            # Mirrors the guard the assisted-filter path already applies in
            # relay_query: with no pending name there is nothing to commit.
            self.logger.warning(
                "Raw filter validated with no pending filter name, ignoring."
            )
            self.clear_pending_filter_state()
            return

        if old_name is not None:  # edit path
            self.subset_filters.pop(old_name, None)
            self.subset_filters[name] = filter_text or ""
            self.update_filter_name(old_name, name)
            self.add_text_to_display.emit(
                f"Filter '{old_name}' updated to '{name}'.",
                self.__class__.__name__,
            )
        else:  # add path
            self.subset_filters[name] = filter_text or ""
            self._subset_controls.filter_comboBox.addItem(name)
            self._subset_controls.filter_comboBox.selectItem(name, select=True)
            self._subset_controls.filter_comboBox.refreshDisplayText()
            self.add_text_to_display.emit(
                f"Filter '{name}' added.",
                self.__class__.__name__,
            )

        self.clear_pending_filter_state()

    @log(logger=logger)
    def _load_filter(self, parameters: Dict[str, Any]) -> None:
        """
        Append filters from a JSON file, rejecting the whole file on a name clash.

        Promoted from both subset tabs in Step 4a. The copies diverged once, and
        ``ProteinView``'s is taken: a filter whose name ends in ``_raw`` is stored
        as it is instead of being sent through ``construct_metadata_query``, which
        builds a WHERE clause and so cannot validate a complete SELECT. Measured
        consequence of not bypassing it: the query is built anyway, with the raw
        SELECT spliced in after ``WHERE`` and an empty debug message, so the
        validation *succeeds* and the filter is committed as
        ``<name>_raw_assisted`` - renamed, and reclassified as an assisted filter.

        :param parameters: Dictionary with 'db_loader'.
        :type parameters: Dict[str, Any]
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Filters", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "r") as f:
                new_filters = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            message = f"Failed to load filters from {path}: {e}"
            self.logger.error(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        if not isinstance(new_filters, dict):
            message = (
                f"Invalid filter file format in {path}: expected a dictionary, "
                f"got {type(new_filters).__name__}."
            )
            self.logger.error(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        # All or nothing: a partial load would leave the user guessing which half
        # of the file arrived.
        existing_names = set(self.subset_filters.keys())
        duplicate_names = existing_names & set(new_filters.keys())
        if duplicate_names:
            message = (
                f"Duplicate filter names found when loading from {path}: "
                f"{', '.join(duplicate_names)}. No filters were loaded."
            )
            self.logger.warning(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        combo = self._subset_controls.filter_comboBox
        loader = parameters.get("db_loader")

        if not loader:
            self.logger.warning("No loader found - filters loaded but not validated.")

        for name, filter_text in new_filters.items():
            # A raw filter is a complete SELECT the loader runs verbatim, and it
            # was already validated when it was created, so it goes straight in.
            if loader and not name.endswith("_raw"):
                # Read back by relay_query once the round-trip returns.
                self._pending_filter_name = name
                self._pending_filter_text = filter_text
                self.filter_validation_requested.emit(
                    loader, filter_text, "validate_new_filter"
                )
            else:
                self.subset_filters[name] = filter_text
                combo.addItem(name)
                combo.selectItem(name, select=True)

        combo.refreshDisplayText()
        self.logger.info(f"Filters loaded from {path}")

    @log(logger=logger)
    def _reject_non_select_raw_filter(self, filter_text: str) -> bool:
        """
        Report a raw filter that is not a complete SELECT, and say whether it was.

        A raw filter is handed to the loader verbatim, so anything that is not a
        SELECT cannot be validated and must not be saved. Reported in a modal
        rather than on the status panel, which is ``MetadataView``'s behaviour of
        the two and the one chosen: the dialog has just closed, and a line on the
        status panel is easy to miss at that moment.

        :param filter_text: the raw filter text the dialog returned
        :type filter_text: str
        :return: True if the filter was rejected and the caller should stop
        :rtype: bool
        """
        if filter_text.strip().upper().startswith("SELECT"):
            return False
        QMessageBox.warning(
            self,
            "Invalid Raw SQL Filter",
            "Raw SQL filters must be complete SELECT statements, e.g. SELECT "
            "duration FROM events WHERE duration > 1000",
        )
        return True

    @log(logger=logger)
    def _show_add_filter_dialog(self, parameters: dict) -> None:
        """
        Open the dialog that adds a subset filter, and validate what it returns.

        Promoted from both subset tabs in Step 4a. The copies diverged twice, in
        the same two places as ``show_edit_filter_dialog``: the columns the
        validation query is built from, which the same step moved to the Controller
        along with the call itself, and how an invalid raw filter is reported, now
        ``_reject_non_select_raw_filter``.

        :param parameters: Dictionary with 'db_loader'.
        :type parameters: dict
        """
        self._show_sql_in_display = True

        dialog = AddSubsetFilterDialog(
            self, existing_names=list(self.subset_filters.keys())
        )

        if self._walkthrough_active:
            self.logger.info("Launching walkthrough from _show_add_filter_dialog()")
            dialog._init_walkthrough()
            dialog.launch_walkthrough()
            if dialog.walkthrough_dialog:
                dialog.finished.connect(
                    lambda _: dialog.walkthrough_dialog.force_close()
                )

        if dialog.exec() == QDialog.Accepted:
            # These are Optional[str] until the dialog's try_accept/accept
            # fills them, and exec() cannot return Accepted without that
            # having run - but the guarantee travels through a signal
            # connection mypy cannot follow, so it is asserted here once
            # rather than guarded at each of the six downstream uses.
            name: str = dialog.name  # type: ignore[assignment]
            filter_text: str = dialog.filter_text  # type: ignore[assignment]
            loader = parameters["db_loader"]

            if not loader:
                self.add_text_to_display.emit(
                    "No event database selected", self.__class__.__name__
                )
                return

            # Read back by relay_query once the validation round-trip returns.
            self._pending_filter_name = name
            self._pending_filter_text = filter_text
            self._pending_old_filter_name = None

            if dialog.is_raw:
                # Raw SQL is validated by validate_filter_query, not by
                # construct_metadata_query, which builds its own SQL.
                if self._reject_non_select_raw_filter(filter_text):
                    return
                name = f"{name}_raw" if not name.endswith("_raw") else name
                self._pending_filter_name = name
                self.raw_filter_validation_requested.emit(
                    loader, filter_text.strip().rstrip(";") + " LIMIT 0"
                )
                return

            self._show_sql_in_display = True

            self.filter_validation_requested.emit(
                loader, filter_text, "validate_new_filter"
            )

    @log(logger=logger)
    def show_edit_filter_dialog(self, name: str, loader: str) -> None:
        """
        Open the dialog that edits a subset filter, and validate what it returns.

        Promoted from both subset tabs in Step 4a, and no longer abstract. The
        reason recorded for its being abstract - that each tab rebuilds its own
        filter widgets afterwards - was ``_delete_filter``'s, not this method's:
        neither copy touched a filter widget. They diverged in the same two places
        as ``_show_add_filter_dialog``, resolved the same way.

        :param name: the filter to edit
        :type name: str
        :param loader: the database loader the filter applies to
        :type loader: str
        """
        self._show_sql_in_display = True

        self.logger.debug(f"Editing filter: {name}")
        self.logger.debug(f"Filters available: {self.subset_filters}")

        dialog = EditSubsetFilterDialog(self, name, self.subset_filters)

        if dialog.exec():
            # Optional[str] until the dialog fills them; see _show_add_filter_dialog.
            new_name: str = dialog.new_name  # type: ignore[assignment]
            new_filter: str = dialog.new_filter  # type: ignore[assignment]

            self.logger.debug(f"Updated filter: {name} -> {new_name}: {new_filter}")

            if not loader:
                self.add_text_to_display.emit(
                    "No event database selected", self.__class__.__name__
                )
                return

            self._pending_filter_name = new_name
            self._pending_filter_text = new_filter
            # The old name is what relay_query replaces, so it has to travel too.
            self._pending_old_filter_name = name

            if dialog.is_raw:
                if self._reject_non_select_raw_filter(new_filter):
                    return
                new_name = (
                    f"{new_name}_raw" if not new_name.endswith("_raw") else new_name
                )
                self._pending_filter_name = new_name
                self.raw_filter_validation_requested.emit(
                    loader, new_filter.strip().rstrip(";") + " LIMIT 0"
                )
                return

            self._show_sql_in_display = True
            self.filter_validation_requested.emit(
                loader, new_filter, "validate_edited_filter"
            )

    @log(logger=logger)
    def _rebuild_event_id_cache(
        self,
        loader: str,
        sql_filter: str,
        exp: Optional[str],
        channel: Optional[int],
    ) -> bool:
        """
        Fetch every event_id matching the current filter, sorted, in one query.

        Also updates ``current_sql_filter``, ``current_experiment`` and
        ``current_channel``, which is what the staleness checks in
        ``_shift_range_and_update_plot`` and the plot handlers compare against to
        decide whether the scope has moved, and reports the resulting total and
        bounds on the status panel.

        Goes through ``load_metadata`` rather than querying the events table
        directly, so that the filter is evaluated against the same joins the
        subset and scatter paths give it. A filter on a sublevels column -
        ``filtered = 5``, meaning every event with at least one sublevel that
        matches - is only meaningful against ``events JOIN sublevels``, and the
        hand-built ``SELECT event_id FROM events`` this replaces made every such
        filter fail as an unknown column and then report itself as an empty
        subset.

        Promoted from both subset tabs in Step 4a. The copies diverged three ways
        and each was resolved to ``ProteinView``'s: it also rejects a result with
        no ``event_id`` column, where Metadata indexed straight into it and would
        have raised; its empty-subset message names the scope; and when a filter
        is active but no filter name is selected it labels the subset with the
        filter expression rather than the bare word "Filter". The order of the
        first two checks is reversed from either copy, so that a result with no
        rows is an empty subset whether or not the loader returned columns with
        it, and only a *populated* result missing ``event_id`` is an error.

        :param loader: Name of the active database loader.
        :type loader: str
        :param sql_filter: Raw filter expression without WHERE, used for the label and for staleness tracking.
        :type sql_filter: str
        :param exp: Current experiment name.
        :type exp: Optional[str]
        :param channel: Current channel identifier.
        :type channel: Optional[int]
        :return: True if the cache was populated, False if it could not be or no events matched.
        :rtype: bool
        """
        # event_id is only unique within an experiment/channel, so without this
        # scoping the cache mixes duplicate ids from every channel, navigation
        # jumps to ids the active channel does not have, and the reported total
        # is inflated.
        exp_and_ch: Optional[Dict[str, Optional[List[int]]]] = None
        if exp is not None:
            exp_and_ch = {exp: [channel] if channel is not None else None}

        # Cleared first: a dispatch that fails never calls the return function,
        # so without this the read below sees the previous call's value and
        # treats it as this call's answer.
        self.relayed_query_result = None
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "load_metadata",
            (["event_id"], sql_filter or None, exp_and_ch),
            "relay_query_result",
            (),
        )
        result = getattr(self, "relayed_query_result", None)
        if result is not None and result.empty:
            self.add_text_to_display.emit(
                "No filtered events found for the current scope.",
                self.__class__.__name__,
            )
            return False
        if result is None or "event_id" not in result.columns:
            # None means the query could not be built or run at all, and a
            # populated result with no event_id means the loader did not honour
            # its own contract - both are real problems rather than an empty
            # subset. Logged at ERROR so QtHandler raises its dialog from the
            # place that can tell the two apart.
            self.logger.error(
                f"Could not query event ids for filter {sql_filter!r} - check that "
                "the columns it names exist in the database"
            )
            return False

        # load_metadata applies no ORDER BY of its own, and the navigation that
        # reads this list bisects it.
        self.filtered_event_ids = sorted(result["event_id"].tolist())
        self.current_sql_filter = sql_filter
        self.current_experiment = exp
        self.current_channel = channel

        total = len(self.filtered_event_ids)
        first_id = self.filtered_event_ids[0]
        last_id = self.filtered_event_ids[-1]
        if sql_filter:
            # Falls back to the expression itself rather than a placeholder, so
            # the panel still says which subset it is reporting on.
            selected_filters = self.get_selected_filters()
            filter_name = next(iter(selected_filters.keys()), sql_filter)
            label = f'"{filter_name}" subset'
        else:
            label = "All events"
        self.add_text_to_display.emit(
            f"{label}: {total} total | first event_id: {first_id} | last event_id: {last_id}",
            self.__class__.__name__,
        )
        return True

    @log(logger=logger)
    def get_selected_filters(self) -> dict:
        """
        The filters the user has selected for the current plotting or export task.

        Promoted from both subset tabs, whose copies differed only in the name each
        held its controls panel under, and otherwise verbatim - including reaching
        past the panel to its combobox, which ``MetaSubsetTabControls`` already
        wraps as ``get_selected_filter_names``. Delegating to that wrapper instead
        would be an improvement but not this commit's; it would also change what
        the existing tab tests have to mock, which is exactly the noise a promotion
        should not carry.

        :return: selected filter names mapped to their SQL WHERE clauses
        :rtype: dict
        """
        return {
            name: self.subset_filters.get(name, "")
            for name in self._subset_controls.filter_comboBox.getSelectedItems()
        }

    @property
    @abstractmethod
    def _subset_controls(self) -> MetaSubsetTabControls:
        """
        This tab's controls panel, under a name the shared methods here can use.

        Each tab stores the panel under a name of its own inside ``_build_controls``
        and uses that name throughout, which is fine for tab-specific code; a method
        promoted up to this base cannot know it. A property rather than a second
        attribute assigned alongside, so there is still exactly one place the panel
        is held and no chance of the two names drifting apart.

        :return: the panel built by ``_build_controls``
        :rtype: MetaSubsetTabControls
        """

    @log(logger=logger)
    def get_save_filename(self) -> str:
        """
        Open a file dialog for the user to choose a save location.

        :return: Selected filename.
        :rtype: str
        """
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV File",
            os.path.expanduser("~"),
            "CSV Files (*.csv);;All Files (*)",
        )
        return file_name

    @log(logger=logger)
    def set_experiment_id(self, experiment_id: Optional[int]) -> None:
        """
        A global signal callback that provides an experiment id for a given filter.

        :param experiment_id: the integer id of the experiment in a MetaEventLoader object
        :type experiment_id: Optional[int]
        """
        self.experiment_id = experiment_id

    @log(logger=logger)
    def set_event_data_generator(self, generator: Iterator[Dict[str, Any]]) -> None:
        """
        Set the event data generator for event-based plots.

        :param generator: A generator that yields event data.
        :type generator: Iterator[Dict[str, Any]]
        """
        self.event_data_generator = generator

    @log(logger=logger)
    def _save_filter(self) -> None:
        """
        Save the current filters to a JSON file.

        """
        if not self.subset_filters:
            self.logger.info("There are no filters to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Filters", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "w") as f:
                json.dump(self.subset_filters, f, indent=4)
            self.logger.info(f"Filters saved to {path}")
        except Exception as e:
            self.logger.error(f"Failed to save filters: {e}")

    @log(logger=logger)
    def set_query(self, query: str, table_name: str) -> None:
        """
        Set the SQL query and table name used in plotting.

        :param query: SQL query string.
        :type query: str
        :param table_name: Name of the database table.
        :type table_name: str
        """
        self.query = query
        self.table_name = table_name
        if not query:
            return

        # Only display SQL for filter creation/edit validation
        if self._show_sql_in_display:
            self.add_text_to_display.emit(
                f"SQL ({table_name}):\n{query.strip()}",
                self.__class__.__name__,
            )
            # one-shot so normal plot queries never show
            self._show_sql_in_display = False

    @log(logger=logger)
    def set_event_query(self, query: str) -> None:
        """
        A global signal callback that provides a valid SQL query for fetching event data.

        :param query: SQL query string for fetching event data.
        :type query: str
        """
        self.event_query = query
        if not query:
            return

        if self._show_event_sql_in_display:
            self.add_text_to_display.emit(
                f"Event SQL:\n{query.strip()}",
                self.__class__.__name__,
            )
            self._show_event_sql_in_display = False

    @log(logger=logger)
    def set_units(self, units: Any) -> None:
        """
        Set the units returned from the database for use in axis labels.

        :param units: List or string representing units.
        :type units: Any
        """
        self.units = units

    @log(logger=logger)
    def update_available_columns(self, loader: str) -> None:
        """
        Request available columns from the database loader.

        :param loader: Name of the active database loader.
        :type loader: str
        """
        if not loader or loader == "No Event Database":
            return
        self.column_names_requested.emit(loader)

    @log(logger=logger)
    def request_experiment_structure(self, loader_name: str) -> None:
        """
        Get a dict of all experiments and channels available in a specified MetaDatabaseLoader object.

        :param loader_name: the key of the loader
        :type loader_name: str
        """
        if not loader_name or loader_name == "No Event Database":
            return

        self.logger.debug(
            f"Requesting experiment-channel structure from loader: {loader_name}"
        )

        self.experiment_structure_requested.emit(loader_name)

    @log(logger=logger)
    def show_selection_tree(
        self,
        structure: dict[str, list[str]],
        loader_name: str,
        selection: Optional[dict[str, list[str]]] = None,
    ) -> None:
        """
        Displays the selection tree for a given loader using the full structure and current selection.
        """
        self.logger.debug(
            f"Displaying selection tree with structure: {structure} for loader: {loader_name}"
        )

        if not hasattr(self, "selection_tree"):
            self.selection_tree = SelectionTree()

        selected = self.selection_tree.show_dialog(
            structure,
            loader_name,
            title="Select Experiment and Channels",
            selected=selection,
        )

        self.selected_experiment_and_channels_by_loader[loader_name] = selected
        self.logger.debug(f"Updated selection for {loader_name}: {selected}")

    @log(logger=logger)
    def clear_pending_filter_state(self) -> None:
        """
        reset all filters to factory settings
        """
        self._pending_filter_name = None
        self._pending_filter_text = None
        self._pending_old_filter_name = None

    @log(logger=logger)
    def _show_filter_info_dialog(
        self, comboBox: MultiSelectComboBox, parameters: Dict[str, Any]
    ) -> None:
        """
        Called when clicking the edit button for filters with multiple selection.

        Validates that exactly one filter is selected and delegates to the edit dialog.

        :param comboBox: The combo box containing the list of selectable filters.
        :type comboBox: MultiSelectComboBox
        :param parameters: Dictionary with 'db_loader'.
        :type parameters: Dict[str, Any]
        """
        loader = parameters["db_loader"]
        selected = comboBox.getSelectedItems()
        if len(selected) != 1:
            self.logger.warning("Please select exactly one filter to edit.")
            return

        self.show_edit_filter_dialog(selected[0], loader)

    @log(logger=logger)
    def _delete_filter_by_name(self, name: str) -> None:
        """
        Deletes a single filter by name.

        :param name: The name of the filter to delete.
        :type name: str
        """
        self._delete_filter(name)
