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
from PySide6.QtWidgets import QMessageBox

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class ProteinController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing protein view-model logic.

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
        Relay a direct database query result to the view.
        Used by ProteinView._rebuild_event_id_cache to receive the list of filtered event_ids.

        :param result: DataFrame returned by query_database_directly, or None if the query failed.
        :type result: Optional[pd.DataFrame]
        """
        self.view.relay_query_result(result)
