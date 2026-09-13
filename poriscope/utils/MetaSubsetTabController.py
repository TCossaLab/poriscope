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
from typing import Any, Dict, Generator, List, Optional, override

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


class MetaSubsetTabController(MetaController):
    """
    Shared base for the Controllers of the two database-backed analysis tabs.

    MetadataController and ProteinController both drive a tab whose data
    comes from a MetaDatabaseLoader: the user picks an experiment and channels,
    builds a subset filter, and plots or exports the rows that come back. The two
    were written by copy-paste and carried seventeen methods verbatim between them;
    this base holds that shared half so there is one copy to fix.

    What a subclass inherits:

    - **Relays into the View.** relay_plot_data, relay_units,
      relay_event_query and the two generator relays hand a Model or plugin result
      to the View, which is the Model-to-View half of the mediation pattern
      Decision B keeps.
    - **Experiment and column state.** set_experiment_id, set_channel_db_id,
      update_column_names, update_column_units,
      get_experiment_structure_ready and get_experiment_names_for_tree
      forward the loader's description of the database to the View.
    - **Filter validation.** validate_filter and validate_raw_filter answer the
      View's two validation intents by calling the loader directly, which is what
      Step 4a replaced a signal-bus round trip with; a failure the bus used to
      swallow is reported through _refuse_filter.
      relay_query receives the query the loader built - or
      the debug message explaining why it could not - and commits, renames or refuses
      the pending filter accordingly. Promoted in Step 4a: this base's own docstring
      had recorded it as unshareable because "the two tabs' copies differ", and they
      differed by one blank line.
    - **Session state.** get_session_state and restore_session_state
      override MetaController's hooks so a tab's subset filters survive a
      save and reload.

    What a subclass owes it:

    - **Its own** logger = logging.getLogger(__name__), so that records made by
      the methods it defines itself stay attributed to its own module. Methods
      defined *here* log under this module, which is the same convention
      MetaView and MetaController already follow for their shared code.
    - **self.view and self.model**, built in its _init() as
      MetaController requires.

    :ivar logger: the module logger the shared methods below log under
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    def set_exported_event_count(self, written: int) -> None:
        """
        Update the view with the number of events exported.

        :param written: Number of events successfully written to file.
        :type written: int
        """
        self.view.set_exported_event_count(written)

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
    @override
    def _setup_connections(self) -> None:
        """
        Wire the four lookups both subset tabs share.

        Step 4a. A subclass with intents of its own overrides this and calls
        ``super()._setup_connections()`` first, so the shared pair is wired once here
        rather than repeated in each tab.

        :return: None
        :rtype: None
        """
        self.view.column_names_requested.connect(self.request_column_names)
        self.view.experiment_structure_requested.connect(
            self.request_experiment_structure
        )
        self.view.filter_validation_requested.connect(self.validate_filter)
        self.view.raw_filter_validation_requested.connect(self.validate_raw_filter)
        self.view.event_id_cache_requested.connect(self.load_event_id_cache)

    @log(logger=logger)
    @Slot(str, object, object)
    def load_event_id_cache(
        self,
        loader: str,
        conditions: Optional[str],
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
    ) -> None:
        """
        Fetch the ``event_id`` values a subset holds, for the navigation cache.

        Step 4a's last conversion, shared by both subset tabs because
        ``_rebuild_event_id_cache`` is shared. A failed query leaves the View's answer
        untouched at ``None``, which is what lets the caller tell "that did not run"
        from "the subset is empty" - a distinction the bus destroyed by swallowing the
        failure and leaving the previous call's rows in place.

        :param loader: the database loader plugin's key
        :type loader: str
        :param conditions: the subset filter, or None for every row
        :type conditions: Optional[str]
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: None
        :rtype: None
        """
        try:
            rows = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_metadata",
                ["event_id"],
                conditions,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to load the filtered event ids: {e!r}")
            self.add_text_to_display.emit(
                f"Could not read this subset's events from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_id_rows(rows)

    @log(logger=logger)
    @Slot(str)
    def request_column_names(self, loader: str) -> None:
        """
        Fetch a loader's column names and hand them to the View.

        Step 4a: the same conversion the reader and loader channel lookups got, against
        ``MetaDatabaseLoader``. An empty answer is logged rather than pushed, as before -
        clearing the axis comboboxes would read as "this database has no columns".

        :param loader: the database loader plugin's key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            column_names = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_names_by_table"
            )
        except Exception as e:
            self.logger.error(f"Failed to request column data: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to read the columns of {loader}: {e}", self.__class__.__name__
            )
            return
        if column_names:
            self.view.update_column_names(column_names)
            self.logger.info("Axis comboboxes updated with new column names.")
        else:
            self.logger.warning("No column names received to update.")

    @log(logger=logger)
    @Slot(str)
    def request_experiment_structure(self, loader_name: str) -> None:
        """
        Fetch a loader's experiment-and-channel structure and file it under its key.

        The loader key was the bus's ``ret_args`` here: the answer has to be filed under
        the loader it came from, and passing it forward explicitly is what replaces that.
        Channels are stringified for display, as they were.

        :param loader_name: the database loader plugin's key
        :type loader_name: str
        :return: None
        :rtype: None
        """
        try:
            structure = self.model.call(
                "MetaDatabaseLoader", loader_name, "get_experiments_and_channels"
            )
        except Exception as e:
            self.logger.error(
                f"Unable to read the experiment structure of {loader_name}: {repr(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to read the experiments in {loader_name}: {e}",
                self.__class__.__name__,
            )
            return
        self.logger.debug(
            f"Received full experiment-channel structure for {loader_name}: {structure}"
        )
        str_structure = {
            exp: [str(ch) for ch in ch_list] for exp, ch_list in structure.items()
        }
        self.view.available_experiment_and_channels_by_loader[loader_name] = (
            str_structure
        )
        self.view.selected_experiment_and_channels_by_loader[loader_name] = (
            self._reconcile_scope_selection(loader_name, str_structure)
        )

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
    def _reconcile_scope_selection(
        self, loader_name: str, structure: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Keep the user's experiment and channel scope across a structure refresh.

        The structure is re-read whenever the loader changes or the selection tree is
        opened, and both sites used to overwrite the *selection* with the whole
        structure. Any refresh therefore widened a narrowed scope back to everything,
        silently: the tree was not open to show it, and only the heatmap and the event
        overlays check, so every other plot type simply drew more data than was asked
        for. Reported from a real run as a heatmap refusing a scope that looked right.

        An existing selection is kept and pruned to what the database still holds, so
        a remembered channel that has gone cannot scope a query to nothing. With no
        selection yet, everything is selected, which is the useful default and what
        both sites did unconditionally before.

        The channel lists are rebuilt rather than shared: ``dict.copy()`` is shallow,
        so the selection and the available structure held the *same* list objects, and
        narrowing one in place would have narrowed what the tree offers.

        :param loader_name: the key of the loader whose structure was read
        :type loader_name: str
        :param structure: every experiment and channel the loader now reports
        :type structure: Dict[str, List[str]]
        :return: the scope to store against this loader
        :rtype: Dict[str, List[str]]
        """
        existing = self.view.selected_experiment_and_channels_by_loader.get(loader_name)
        if existing:
            kept = {}
            for experiment, channels in existing.items():
                if experiment not in structure:
                    continue
                survivors = [
                    channel for channel in channels if channel in structure[experiment]
                ]
                if survivors:
                    kept[experiment] = survivors
            if kept:
                return kept
            self.logger.info(
                f"The remembered scope for {loader_name} no longer matches the "
                "database, so every experiment and channel is selected again"
            )
        return {
            experiment: list(channels) for experiment, channels in structure.items()
        }

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
            self._reconcile_scope_selection(loader_name, str_structure)
        )

    @log(logger=logger)
    @Slot(str, str, str, str, object)
    def validate_filter(
        self,
        loader: str,
        filter_text: str,
        intent: str,
        name: str,
        old_name: Optional[str],
    ) -> None:
        """
        Validate an assisted subset filter by asking the loader to build a query.

        A filter counts as valid if ``construct_metadata_query`` can *build* a query
        around it; the query itself is thrown away. Step 4a converted the emit that
        used to do this, and the conversion matters twice over. The bus swallowed
        every exception, and ``construct_metadata_query`` **raises** for a column it
        cannot map to a table - so a filter naming a column the database does not
        have used to vanish with nothing but a log line. It is reported now.

        The columns are resolved here rather than passed in by the View, and only
        ``events`` columns are asked for. The View used to hand over a hardcoded
        ``["sublevel_current", "voltage", "duration"]`` - one column from each of the
        three tables, which forced the built query to join all three every time, even
        for a filter with no conditions at all. One events column yields exactly the
        joins the filter itself needs: none for ``duration < 300``, one for a filter
        that really does reference sublevels or experiments.

        :param loader: the database loader plugin's key
        :type loader: str
        :param filter_text: the filter expression to validate, without WHERE
        :type filter_text: str
        :param intent: ``validate_new_filter`` or ``validate_edited_filter``, passed
            through to ``relay_query`` to say what to do with the answer
        :type intent: str
        :param name: the name to commit the filter under, carried from the request
        :type name: str
        :param old_name: on an edit, the name being replaced; None when adding
        :type old_name: Optional[str]
        :return: None
        :rtype: None
        """
        try:
            columns = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_names_by_table", "events"
            )
        except Exception as e:
            self.logger.error(f"Failed to read the events columns of {loader}: {e!r}")
            self._refuse_filter(f"Unable to read the columns of {loader}: {e}")
            return

        if not columns:
            # Nothing to build a query around, so nothing can be validated. Refusing
            # is the honest answer: the hardcoded triple this replaces would have
            # "validated" against three columns that may not exist either.
            self.logger.error(f"{loader} reported no columns in its events table")
            self._refuse_filter(
                f"{loader} reports no columns in its events table, so the filter "
                "cannot be validated"
            )
            return

        try:
            query, debug, table_name = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                columns[:1],
                filter_text,
                None,
            )
        except Exception as e:
            # Previously swallowed by the dispatcher. ValueError for an unmappable
            # column, KeyError for an unknown experiment name.
            self.logger.error(f"Failed to validate filter {filter_text!r}: {e!r}")
            self._refuse_filter(f"The filter could not be validated: {e}")
            return

        self.relay_query(query, debug, table_name, intent, name, old_name, filter_text)

    @log(logger=logger)
    @Slot(str, str, str, object)
    def validate_raw_filter(
        self, loader: str, query: str, name: str, old_name: Optional[str]
    ) -> None:
        """
        Validate a raw subset filter, which the loader checks without building.

        A raw filter is a complete SELECT the loader runs verbatim, so it is checked
        with ``validate_filter_query`` rather than by constructing a query around it.
        Step 4a converted the emit; as with the assisted path, a failure that the bus
        swallowed now reaches the user.

        ``LIMIT 0`` is appended here rather than by the View. The clause is what makes
        the check cheap - the database parses and plans the filter without returning a
        row - and choosing it is knowing SQL, which Step 4b takes out of the widget.

        :param loader: the database loader plugin's key
        :type loader: str
        :param query: the raw filter as the user wrote it, without a trailing semicolon
        :type query: str
        :param name: the name to commit the filter under, carried from the request
        :type name: str
        :param old_name: on an edit, the name being replaced; None when adding
        :type old_name: Optional[str]
        :return: None
        :rtype: None
        """
        try:
            valid, error_msg = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "validate_filter_query",
                f"{query} LIMIT 0",
            )
        except Exception as e:
            self.logger.error(f"Failed to validate raw filter {query!r}: {e!r}")
            self.view.on_raw_filter_validated(False, str(e), name, old_name, query)
            return

        self.view.on_raw_filter_validated(valid, error_msg, name, old_name, query)

    @log(logger=logger)
    def _refuse_filter(self, message: str) -> None:
        """
        Report why a filter could not be validated.

        It used to clear the View's pending filter state as well, because a refused
        name left parked there would have been committed by the next validation that
        succeeded. Step 4d threads the name through the request instead, so there is
        nothing parked to go stale and nothing to clear.

        :param message: what to tell the user
        :type message: str
        :return: None
        :rtype: None
        """
        self.add_text_to_display.emit(message, self.__class__.__name__)

    @log(logger=logger)
    def relay_query(
        self,
        query: str,
        debug: str,
        table_name: str,
        intent: Optional[str] = None,
        name: Optional[str] = None,
        old_name: Optional[str] = None,
        filter_text: Optional[str] = None,
    ) -> None:
        r"""
        Relay a query and optional debug message to the view, handling optional filter intents.

        Promoted from both subset tabs in Step 4a. ``MetaSubsetTabController``'s
        docstring recorded this method as deliberately not shared, because "the two
        tabs' copies differ" and each reaches into its own View's pending-filter
        state, with the promotion deferred to Step 4d. Neither half held up: the
        copies differed **by one blank line**, and the pending-filter state has been
        declared on ``MetaSubsetTabView`` since earlier in this step, so both copies
        were already reaching into the same shared attributes.

        :param query: SQL query string to display or execute.
        :type query: str
        :param debug: Debug message to display if query is empty.
        :type debug: str
        :param table_name: Name of the table associated with the query.
        :type table_name: str
        :param intent: 'validate_new_filter', 'validate_edited_filter', or None when
            the query is only being displayed
        :type intent: Optional[str]
        :param name: the name to commit the filter under, carried from the request
        :type name: Optional[str]
        :param old_name: on an edit, the name being replaced; None when adding
        :type old_name: Optional[str]
        :param filter_text: the expression to commit under ``name``, as the user
            wrote it; the query built around it is displayed, not stored
        :type filter_text: Optional[str]
        :return: None
        :rtype: None
        """

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
            return

        self.view.set_query(query, table_name)

        if intent == "validate_new_filter":
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
            new_name = name
            new_filter = filter_text

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

                # NOTE: old_name is Optional[str] because an *added* filter has no
                # name to replace, but show_edit_filter_dialog always sends one, so
                # it is never None on this branch. The guarantee travels through a
                # signal connection mypy cannot follow.
                self.view.update_filter_name(old_name, suffixed_new_name)  # type: ignore[arg-type]

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
