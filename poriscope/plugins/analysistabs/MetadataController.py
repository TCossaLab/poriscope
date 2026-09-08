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
from typing import Optional, override

import pandas as pd
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class MetadataController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing metadata view-model logic.

    Relays plot data, query results, and column/unit updates to the view.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the metadata view and model.
        """
        self.view = MetadataView()
        self.model = MetadataModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Wire this tab's own intent on top of the two the subset base wires.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.column_units_requested.connect(self.request_column_units)

    @log(logger=logger)
    @Slot(str, str, str)
    def request_column_units(self, loader: str, column: str, axis: str) -> None:
        """
        Fetch one column's units and apply them to one axis label.

        Step 4a. The axis travels with the request and back out again, which is what the
        bus carried in its ``ret_args``. This is Metadata's alone: ``update_units`` moved
        down from ``MetaSubsetTabView`` in the same commit, because the protein tab has no
        units label to write to.

        :param loader: the database loader plugin's key
        :type loader: str
        :param column: the column whose units are wanted
        :type column: str
        :param axis: the axis whose label they belong to
        :type axis: str
        :return: None
        :rtype: None
        """
        try:
            column_units = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_units", column
            )
        except Exception as e:
            self.logger.error(f"Failed to request units for column {column}: {repr(e)}")
            return
        self.view.update_column_units(column_units, axis)

    @log(logger=logger)
    def relay_column_type(self, column_type: Optional[str]) -> None:
        """
        Relay the data type of a specified column to the view

        :param column_type: The data type of the column, or None if the loader could not resolve one.
        :type column_type: Optional[str]
        """
        self.view.set_column_type(column_type)

    @log(logger=logger)
    def update_features(
        self,
        vertical: Optional[list[float]] = None,
        horizontal: Optional[list[float]] = None,
        points: Optional[list[tuple[float, float]]] = None,
        vlabels: Optional[list[str]] = None,
        hlabels: Optional[list[str]] = None,
        plabels: Optional[list[str]] = None,
    ) -> None:
        """
        Update the plot with visual annotations including vertical lines, horizontal lines, and point markers.

        Validates that each visual feature has a corresponding label (or explicit None) if labels are provided.

        :param vertical: Vertical line positions for the event being plotted.
        :type vertical: Optional[list[float]]
        :param horizontal: Horizontal line positions for the event being plotted.
        :type horizontal: Optional[list[float]]
        :param points: (x, y) point coordinates for the event being plotted.
        :type points: Optional[list[tuple[float, float]]]
        :param vlabels: Labels for the vertical lines.
        :type vlabels: Optional[list[str]]
        :param hlabels: Labels for the horizontal lines.
        :type hlabels: Optional[list[str]]
        :param plabels: Labels for the point markers.
        :type plabels: Optional[list[str]]
        :raises ValueError: If a label list is provided and its length does not match the corresponding feature list.
        """
        if (
            vertical is not None
            and vlabels is not None
            and len(vlabels) != len(vertical)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every vertical line feature, or no labels at all"
            )
        if (
            horizontal is not None
            and hlabels is not None
            and len(hlabels) != len(horizontal)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every horizontal line feature, or no labels at all"
            )
        if points is not None and plabels is not None and len(points) != len(plabels):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every point feature, or no labels at all"
            )
        self.view.update_plot_features(
            vertical, horizontal, points, vlabels, hlabels, plabels
        )

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
    def relay_query_result(self, result: Optional[pd.DataFrame]) -> None:
        """
        Relay the result of a direct DB query to the view.

        :param result: DataFrame returned by query_database_directly.
        :type result: Optional[pd.DataFrame]
        """
        self.view.relay_query_result(result)

    @log(logger=logger)
    def relay_experiment_id(self, exp_id: Optional[int]) -> None:
        """
        Relay a resolved experiment id to the view.

        :param exp_id: Integer experiment id.
        :type exp_id: Optional[int]
        """
        self.view.relay_experiment_id(exp_id)
