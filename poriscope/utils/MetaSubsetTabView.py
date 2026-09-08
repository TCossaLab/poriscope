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
from PySide6.QtWidgets import QFileDialog

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabControls import MetaSubsetTabControls
from poriscope.utils.MetaView import MetaView
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
    - **Subset filters.** ``_save_filter``, ``_delete_filter_by_name``,
      ``_show_filter_info_dialog`` and ``clear_pending_filter_state`` manage the named
      filters in ``subset_filters`` and the three pending fields the Controller reads
      back after a validation round-trip.
    - **Experiment selection.** ``show_selection_tree`` and
      ``request_experiment_structure`` drive the ``SelectionTree`` dialog and remember
      what was chosen per loader.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, so that records made by
      the methods it defines itself stay attributed to its own module. Methods defined
      *here* log under this module, which is the convention ``MetaView`` already
      follows for its shared code.
    - **``_delete_filter`` and ``show_edit_filter_dialog``**, declared abstract below.
      Both tabs implement them differently, because each rebuilds its own filter
      widgets afterwards.
    - **The five abstract methods ``MetaView`` declares**, unchanged - this base
      implements none of them.

    Deliberately *not* shared: ``relay_query`` and the pending-filter state it reads
    stay per-tab until Step 4d moves that state to the Model, and ``update_filters``
    stays per-tab because the two tabs hold their filter combobox under different
    names.

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

    logger = logging.getLogger(__name__)

    #: Assigned in each subclass's ``_init``, identically in both tabs today. The
    #: annotation moves here with the methods that read it; the assignment stays with
    #: the subclass, since ``MetaView`` gives this base no ``_init`` of its own.
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

    @abstractmethod
    def _delete_filter(self, name: str) -> None:
        """
        Remove a named subset filter and rebuild whatever widgets displayed it.

        Abstract because the two tabs hold their filter widgets under different names,
        so each rebuilds its own.

        :param name: the filter to remove
        :type name: str
        """

    @abstractmethod
    def show_edit_filter_dialog(self, name: str, loader: str) -> None:
        """
        Open the dialog that edits an existing subset filter, and validate the result.

        Abstract for the same reason as ``_delete_filter``.

        :param name: the filter to edit
        :type name: str
        :param loader: the database loader the filter applies to
        :type loader: str
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
