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
from typing import Any, Dict, Generator, Optional

import pandas as pd
from PySide6.QtWidgets import QMessageBox
from typing_extensions import override

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class ProteinController(MetaController):
    """
    Subclass of MetaController for managing protein view-model logic.

    Relays queries, event data, and filter/column metadata between the
    database backend and ProteinView.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the protein view and model.
        """
        self.view = ProteinView()
        self.model = ProteinModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Connect internal view signals to their corresponding controller slots.
        """
        # No view-side connections currently required.
        pass

    @log(logger=logger)
    def check_column_exists(self, table_name: Optional[str]) -> None:
        """
        Notify the view to check if a fit-data column exists in the given table.

        :param table_name: Name of the table containing the queried column, or None if the loader could not resolve one.
        :type table_name: Optional[str]
        """
        self.view.set_column_exists(table_name)

    @log(logger=logger)
    def alter_database_status(self, status: bool) -> None:
        """
        Inform the view whether database alteration was successful.

        :param status: Result of the database alteration operation.
        :type status: bool
        """
        self.view.set_alter_database_status(status)

    @log(logger=logger)
    def relay_table_by_column(self, table: Optional[str]) -> None:
        """
        Relay the name of the table a column lives in to the view.

        :param table: Name of the table containing the queried column, or None if the loader could not resolve one.
        :type table: Optional[str]
        """
        self.view.set_table_by_column(table)

    @log(logger=logger)
    def relay_baseline_duration(self, duration: Optional[float]) -> None:
        """
        Relay the computed baseline duration to the view.

        :param duration: Duration of the baseline in appropriate units, or None if it could not be resolved.
        :type duration: Optional[float]
        """
        self.view.set_baseline_duration(duration)

    @log(logger=logger)
    def set_exported_event_count(self, written: int) -> None:
        """
        Update the view with the number of events exported.

        :param written: Number of events successfully written to file.
        :type written: int
        """
        self.view.set_exported_event_count(written)

    @log(logger=logger)
    def relay_query(self, query: str, debug: str, table_name: str, *args: str) -> None:
        r"""
        Relay a query and optional debug message to the view, handling optional filter intents.

        :param query: SQL query string to display or execute.
        :type query: str
        :param debug: Debug message to display if query is empty.
        :type debug: str
        :param table_name: Name of the table associated with the query.
        :type table_name: str
        :param \*args: Optional intent string (e.g. 'validate_new_filter', 'validate_edited_filter').
        :type \*args: str
        """
        intent = args[0] if args else None

        if debug and not query:
            # Also on the display panel, not only in the modal: the dialog is
            # dismissed before the user gets back to the filter text, and the
            # message is often a set of instructions for correcting it.
            self.view.add_text_to_display.emit(debug, self.__class__.__name__)
            QMessageBox.warning(
                self.view,
                "Invalid Filter",
                f"The filter could not be validated:\n\n{debug}",
            )
            if intent in ("validate_new_filter", "validate_edited_filter"):
                self.view.clear_pending_filter_state()
            return

        self.view.set_query(query, table_name)

        if intent == "validate_new_filter":
            name = self.view._pending_filter_name
            filter_text = self.view._pending_filter_text

            if name is not None:
                suffixed_name = (
                    f"{name}_assisted" if not name.endswith("_assisted") else name
                )
                self.view.subset_filters[suffixed_name] = filter_text or ""

                if not filter_text:
                    self.view.add_text_to_display.emit(
                        f"Filter '{suffixed_name}' uses all rows (no WHERE clause).",
                        self.__class__.__name__,
                    )

                self.view.add_text_to_display.emit(
                    f"Filter '{suffixed_name}' added.", self.__class__.__name__
                )

                self.view.replace_filter_item(suffixed_name)

        elif intent == "validate_edited_filter":
            old_name = self.view._pending_old_filter_name
            new_name = self.view._pending_filter_name
            new_filter = self.view._pending_filter_text

            if new_name is not None:
                suffixed_new_name = (
                    f"{new_name}_assisted"
                    if not new_name.endswith("_assisted")
                    else new_name
                )
                if old_name is not None:
                    self.view.subset_filters.pop(old_name, None)
                self.view.subset_filters[suffixed_new_name] = new_filter or ""

                if not new_filter:
                    self.view.add_text_to_display.emit(
                        f"Filter '{suffixed_new_name}' uses all rows (no WHERE clause) -> FULL DATASET.",
                        self.__class__.__name__,
                    )

                self.view.add_text_to_display.emit(
                    f"Filter '{old_name}' updated to '{suffixed_new_name}'.",
                    self.__class__.__name__,
                )

                # NOTE: old_name is Optional[str] on the attribute, but
                # show_edit_filter_dialog sets it from a `str` parameter before
                # emitting this intent, so it is never None here. The guarantee
                # travels through a signal connection mypy cannot follow.
                self.view.update_filter_name(old_name, suffixed_new_name)  # type: ignore[arg-type]

        self.view.clear_pending_filter_state()

    @log(logger=logger)
    def relay_event_query(self, query: str, debug: str) -> None:
        """
        Relay an event-level query to the view.

        :param query: SQL query string for fetching event data.
        :type query: str
        :param debug: Debug message to display if query is empty.
        :type debug: str
        """
        if debug and not query:
            self.add_text_to_display.emit(debug, self.__class__.__name__)
        self.view.set_event_query(query)

    @log(logger=logger)
    def relay_event_data_generator(self, generator: Generator) -> None:
        """
        Relay a generator for event data overlays to the view.

        :param generator: Generator yielding event data for overlay purposes.
        :type generator: Generator
        """
        # for event overlays
        self.view.set_event_data_generator(generator)

    @log(logger=logger)
    def relay_event_plot_data_generator(self, generator: Generator) -> None:
        """
        Relay a generator for event plotting to the view.

        :param generator: Generator yielding event data for plotting.
        :type generator: Generator
        """
        # for plotting events
        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    def relay_plot_data(self, data: Any) -> None:
        """
        Relay processed data to the view for plotting.

        :param data: Structured plot data.
        :type data: Any
        """
        self.view.set_plot_data(data)

    @log(logger=logger)
    def relay_units(self, units: Optional[str]) -> None:
        """
        Provide a column unit label to the view.

        :param units: Unit string for the queried column, or None if the loader could not resolve one.
        :type units: Optional[str]
        """
        self.view.set_units(units)

    @log(logger=logger)
    def update_column_names(self, column_names: list[str]) -> None:
        """
        Update the view with new column names.

        :param column_names: List of column names retrieved from the database.
        :type column_names: list[str]
        """
        # Handle the column names fetched from the database
        if column_names:
            self.view.update_column_names(column_names)
            self.logger.info("Axis comboboxes updated with new column names.")
        else:
            self.logger.warning("No column names received to update.")

    @log(logger=logger)
    def update_column_units(self, column_units: Optional[str], axis: str) -> None:
        """
        Update the view with the unit label for a specific axis.

        :param column_units: Unit string for the column plotted on this axis, or None if the loader could not resolve one.
        :type column_units: Optional[str]
        :param axis: Axis to apply the units to (e.g., 'x' or 'y').
        :type axis: str
        """
        # Handle the units fetched for the columns
        self.view.update_column_units(column_units, axis)

    @log(logger=logger)
    def get_experiment_names_for_tree(
        self, experiments: list[str], loader_name: str
    ) -> None:
        """
        Provide a list of experiment names to the view for the tree display.

        :param experiments: List of experiment names fetched from the database.
        :type experiments: list[str]
        :param loader_name: Name of the data loader associated with the experiments.
        :type loader_name: str
        """
        # Handle experiments fetched from DB
        self.view.get_experiment_names_for_tree(experiments, loader_name)

    @log(logger=logger)
    def get_experiment_structure_ready(
        self, structure: dict[str, list[int]], loader_name: str
    ) -> None:
        """
        Pass experiment-to-channel mappings to the view in display-ready format.

        :param structure: Dictionary mapping experiment names to a list of channel IDs.
        :type structure: dict[str, list[int]]
        :param loader_name: Name of the data loader providing the structure.
        :type loader_name: str
        """
        self.logger.debug(
            f"Received full experiment-channel structure for {loader_name}: {structure}"
        )

        # Convert all channels to strings (for display)
        str_structure = {
            exp: [str(ch) for ch in ch_list] for exp, ch_list in structure.items()
        }

        self.view.available_experiment_and_channels_by_loader[loader_name] = (
            str_structure
        )

        self.view.selected_experiment_and_channels_by_loader[loader_name] = (
            str_structure.copy()
        )

    @log(logger=logger)
    def set_experiment_id(self, experiment_id: Optional[int]) -> None:
        """
        Relay the experiment ID to the view.

        :param experiment_id: Integer ID of the experiment.
        :type experiment_id: Optional[int]
        """
        self.view.set_experiment_id(experiment_id)

    @log(logger=logger)
    def set_channel_db_id(self, channel_db_id: Optional[int]) -> None:
        """
        Relay the channel database ID to the view.

        :param channel_db_id: Integer database ID of the channel.
        :type channel_db_id: Optional[int]
        """
        self.view.set_channel_db_id(channel_db_id)

    @log(logger=logger)
    def on_raw_filter_validated(self, valid: bool, error_msg: str) -> None:
        """
        Relay the result of raw filter validation to the view.

        :param valid: Whether the query is valid.
        :type valid: bool
        :param error_msg: Error message if invalid.
        :type error_msg: str
        """
        self.view.on_raw_filter_validated(valid, error_msg)

    @log(logger=logger)
    def relay_query_result(self, result: Optional[pd.DataFrame]) -> None:
        """
        Relay a direct database query result to the view.
        Used by ProteinView._rebuild_event_id_cache to receive the list of filtered event_ids.

        :param result: DataFrame returned by query_database_directly, or None if the query failed.
        :type result: Optional[pd.DataFrame]
        """
        self.view.relay_query_result(result)

    @log(logger=logger)
    @override
    def get_session_state(self) -> Dict[str, Any]:
        """
        Include the view's live subset filters in this tab's session history entry.

        :return: Extra state to serialize into this tab's session history entry.
        :rtype: Dict[str, Any]
        """
        return {"subset_filters": dict(self.view.subset_filters)}

    @log(logger=logger)
    @override
    def restore_session_state(self, state: Dict[str, Any]) -> None:
        """
        Restore subset filters captured by :meth:`get_session_state` onto the view.

        :param state: This tab's session history entry, as previously written by
            :meth:`get_session_state`.
        :type state: Dict[str, Any]
        """
        subset_filters = state.get("subset_filters")
        if subset_filters:
            self.view.restore_subset_filters(subset_filters)
