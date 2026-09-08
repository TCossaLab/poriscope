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
from typing import Any, Dict, Generator, Optional, override

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
      relay_event_query, relay_baseline_duration
      and the two generator relays hand a Model or plugin result to the View, which
      is the Model-to-View half of the mediation pattern Decision B keeps.
    - **Experiment and column state.** set_experiment_id, set_channel_db_id,
      update_column_names, update_column_units,
      get_experiment_structure_ready and get_experiment_names_for_tree
      forward the loader's description of the database to the View.
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
    - **relay_query**, which is deliberately *not* shared: the two tabs' copies
      differ, and each reaches into its own View's pending-filter state. Step 4d
      moves that state to the Model, after which the method can be promoted here.

    :ivar logger: the module logger the shared methods below log under
    """

    logger = logging.getLogger(__name__)

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
