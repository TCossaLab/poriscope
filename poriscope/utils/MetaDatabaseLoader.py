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
# Alejandra Carolina González González

import logging
import re
from abc import abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.SerializeDecorator import serialize_channels

Numeric = Union[int, float, np.number]


@inherit_docstrings
class MetaDatabaseLoader(BaseDataPlugin):
    """
    What you get by inheriting from MetaDatabaseLoader
    --------------------------------------------------

    :ref:`MetaDatabaseLoader` is the base class for loading the data written by a :ref:`MetaDatabaseWriter` subclass instance or any other method that produces an equivalent format.

    Poriscope ships with :ref:`SQLiteDBLoader`, a subclass of :ref:`MetaDatabaseLoader` that reads data written by the :ref:`SQLiteDBWriter` subclass. While additional subclasses can read almost any format you desire, we strongly encourage standardization around this format. Think twice before creating additional subclasses of this base class. It is not sufficient to write just a :ref:`MetaEventLoader` subclass. In addition to this base class, you will also need a paired :ref:`MetaDatabaseWriter` subclass to write data in your target format.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Initialize and set up the plugin, if settings are available at this stage
        """
        super().__init__(settings)

    # public API, MUST be implemented by subclasses
    @abstractmethod
    def get_llm_prompt(self) -> Optional[str]:
        """
        **Purpose:** Return a prompt that will tell the LLM the structure of the database to be queried to assist users in accessing the data written in your format

        :return: a prompt that gives an LLM context for the database and how to query it, or None on failure
        :rtype: Optional[str]
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else reset all of them. In most cases for MetaDatabaseLoaders there is no need to reset and you can simplt ``pass``.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        **Purpose:** Clean up any open file handles or memory on app exit.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Do this for all channels if no channel is specified, otherwise limit your closure to the specified channel. If no such operation is needed, it suffices to ``pass``.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    @abstractmethod
    def get_experiment_names(
        self, experiment_id: Optional[int] = None
    ) -> Optional[List[str]]:
        """
        **Purpose:** Retrieve a list of all unique experiment names registered in the database, or a singleton list if an id is given.

        :param experiment_id: the id of the experiment for which to fetch the name
        :type experiment_id: Optional[int]
        :return: List of experiment names, or None on failure
        :rtype: Optional[List[str]]
        """
        pass

    @abstractmethod
    def get_channels_by_experiment(self, experiment: str) -> Optional[List[int]]:
        """
        **Purpose:** Retrieve a list of all channel identifiers (the identifier, not the primary key of the channels table) associated with a given experiment name or None on failure

        :param experiment: The name of the experiment.
        :type experiment: str
        :return: List of channel IDs.
        :rtype: Optional[List[int]]
        """
        pass

    @abstractmethod
    def get_event_counts_by_experiment_and_channel(
        self, experiment: Optional[str] = None, channel: Optional[int] = None
    ) -> Optional[int]:
        """
        **Purpose:**  Return the number of events in the database matching the experiment name and channel identifier.

        If no channel name is provided, count across all channels for that experiment.
        If no experiment is provided, ignore channel and return the number of events in the entire database

        :param experiment: The name of the experiment.
        :type experiment: Optional[str]
        :param channel: The index of the channel
        :type channel: Optional[int]
        :return: event count matching the conditions, or None on failure
        :rtype: Optional[int]
        """
        pass

    @abstractmethod
    def get_column_units(self, column_name: str) -> Optional[str]:
        """
        **Purpose:** Retrieve the units associated with a specific column name or None on failure

        :param column_name: The name of the column.
        :type column_name: str
        :return: The units of the column.
        :rtype: Optional[str]
        """
        pass

    @abstractmethod
    def get_column_type(self, column_name: str) -> Optional[str]:
        """
        **Purpose:** Retrieve the datatype associated with a specific column name or None on failure

        :param column_name: The name of the column.
        :type column_name: str
        :return: The datatype of the column.
        :rtype: Optional[str]
        """
        pass

    @abstractmethod
    def get_column_names_by_table(
        self, table: Optional[str] = None
    ) -> Optional[List[str]]:
        """
        **Purpose:** Retrieve the column names available in a specified table, all columns in the database is table is not specified, or None on failure

        :param table: The name of the table.
        :type table: Optional[str]
        :return: List of column names.
        :rtype: Optional[List[str]]
        """
        pass

    @abstractmethod
    def get_table_names(self) -> Optional[List[str]]:
        """
        **Purpose:** Retrieve the names of available tables in the database or None on failure.

        :return: List of table names.
        :rtype: Optional[List[str]]
        """
        pass

    @abstractmethod
    def validate_filter_query(self, query: str) -> Tuple[bool, str]:
        """
        **Purpose:** Validate a SQL query without executing it.

        Return ``True, ""`` if the query is valid, and ``False, "[[helpful explanation]]"`` if it is not

        :param query: The SQL query string.
        :type query: str
        :return: ``True, ""`` if the query is valid, and ``False, "[[helpful explanation]]"`` if it is not
        :rtype: Tuple[bool, str]
        """
        pass

    @abstractmethod
    def get_samplerate_by_experiment_and_channel(
        self, experiment: str, channel: int
    ) -> Optional[float]:
        """
        **Purpose:** Retrieve the sampling rate for a given experiment and channel id, or None on failure

        :param experiment: The name of the experiment in the database.
        :type experiment: str
        :param channel: The channel id to get sampling rate for.
        :type channel: int
        :return: sampling rate for the specific expreiment-channel combination, or None on failure
        :rtype: Optional[float]
        """
        pass

    @abstractmethod
    def get_table_by_column(self, column: str) -> Optional[str]:
        """
        **Purpose:** Retrieve the names of the table in which the given column is found, or None on failure

        :param column: The name of the column.
        :type column: str
        :return: The name of the table, or None on failure.
        :rtype: Optional[str]
        """
        pass

    @abstractmethod
    def add_columns_to_table(
        self, df: pd.DataFrame, units: List[Optional[str]], table_name: str
    ) -> bool:
        """
        :param df: A pandas DataFrame. Must contain an 'id' column corresponding to the primary key of the target table, and one or more additional columns to be added.
        :type df: pd.DataFrame
        :param units: A list of strings specifying units for the new columns to be added. Must have length equal to the number of new cols, but can contain None values
        :type units: List[Optional[str]]
        :param table_name: The name of the SQLite table to modify. This table must already exist in the databse.
        :type table_name: str

        :return: True on success, False otherwise
        :rtype: bool

        :raises ValueError: If the DataFrame does not contain an 'id' column or if the specified table does not exist.
        :raises IOError: If any write-related error occurs

        **Purpose:** Adds new columns from a pandas DataFrame to an existing SQLite table

        Create new columns in the specified table and populate them with the procided data, matching on the 'id' column against the primary id in the target table
        """
        pass

    @abstractmethod
    def alter_database(self, queries: List[str]) -> bool:
        """
        **Purpose:** Run a given list of queries on the database. There is no validation here, use it sparingly.

        :param queries: a list of queries to  run on the database
        :type queries: List[str]
        :return: True if the operation succeeded, False otherwise
        :rtype: bool
        """
        pass

    # Public API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    def get_plot_features(self, experiment: int, channel: int, index: int) -> Tuple[
        Optional[List[float]],
        Optional[List[float]],
        Optional[List[Tuple[float, float]]],
        Optional[List[str]],
        Optional[List[str]],
        Optional[List[str]],
    ]:
        """
        Get a list of horizontal and vertical lines and associated labels to overlay on the graph generated by construct_fitted_event()

        :param experiment: get only events from this experiment
        :type experiment: int
        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: a list of x locations to plot vertical lines and a list of y locations to plot horizontal lines, list of tuples to plot little x's, labels for the vertical lines, labels for the horizontal lines, labels for x's. Must be lists of equal length, or None
        :rtype: Tuple[Optional[List[float]], Optional[List[float]], Optional[List[Tuple[float, float]]], Optional[List[str]], Optional[List[str]], Optional[List[str]]]
        """
        return None, None, None, None, None, None

    @log(logger=logger)
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaWriter` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Type is required; Value may be omitted or set to None, both meaning there is no default and the user must supply one. All values provided must be consistent with Type.

        .. code-block:: python

           settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        Several parameter keywords are reserved: these are

        'Input File'
        'Output File'
        'Folder'

        These must have Type str and will cause the GUI to generate widgets to allow selection of these elements when used

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaEventLoader`, which already has an implementation of this function that ensures that settings will have the required ``Input File`` key available to users, in most cases you will need to override it to add any other settings required by your subclass or to specify which files types are allowed. If you need additional settings, which you almost certainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this, to limit it to sqlite files:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Input File"]["Options"] = [
                                    "SQLite3 Files (*.sqlite3)",
                                    "Database Files (*.db)",
                                    "SQLite Files (*.sqlite)",
                                    ]
            return settings

        which will ensure that your have the ``Input File`` key and limit visible options to sqlite3 files. By default, it will accept any file type as output, hence the specification of the ``Options`` key for the relevant plugin in the example above.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings: Dict[str, Dict[str, Any]] = {
            "Input File": {"Type": str, "Options": ["All Files (*.*)"]}
        }
        return settings

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool
        """
        return False

    @log(logger=logger)
    def get_experiments_and_channels(self) -> Dict[str, Optional[List[int]]]:
        """
        Retrieve a mapping of experiment names to their associated channel lists.

        Calls `get_experiment_names()` to fetch all experiment identifiers,
        then maps each experiment to its corresponding list of channels using `get_channels_by_experiment()`.

        :return: Dictionary mapping experiment names to lists of channel indices.
        :rtype: Dict[str, Optional[List[int]]]
        """
        experiments = self.get_experiment_names()
        if not experiments:
            return {}
        return {exp: self.get_channels_by_experiment(exp) for exp in experiments}

    @log(logger=logger)
    def get_experiment_id_by_name(self, experiment_name: str) -> Optional[int]:
        """
        Look up the database primary key of the experiment with the given name.

        :param experiment_name: the name of the experiment for which to fetch the id
        :type experiment_name: str

        :return: The experiment's database id, or None if no name was given or no matching experiment was found
        :rtype: Optional[int]
        :raises Exception: if the underlying database query fails
        """
        if experiment_name:
            try:
                escaped_name = experiment_name.replace("'", "''")
                query = (
                    f"SELECT id FROM experiments WHERE name = '{escaped_name}' LIMIT 1"
                )
                result = self.query_database_directly(query)
                if result is not None and not result.empty:
                    return result.at[0, "id"]
                else:
                    return None
            except Exception as e:
                self.logger.info(f"Database query failed: {e}")
                raise
        return None

    @log(logger=logger)
    def get_channel_db_id(self, experiment_name: str, channel_id: int) -> Optional[int]:
        """
        Get the channel primary key (channel_db_id) for a given experiment name and channel identifier.

        :param experiment_name: The name of the experiment.
        :type experiment_name: str
        :param channel_id: The channel identifier (not the primary key).
        :type channel_id: int
        :return: The primary key of the channel, or None on failure.
        :rtype: Optional[int]
        """
        try:
            exp_id = self.get_experiment_id_by_name(experiment_name)
            if exp_id is None:
                return None
            query = f"SELECT id FROM channels WHERE experiment_id = {exp_id} AND channel_id = {channel_id} LIMIT 1"
            result = self.query_database_directly(query)
            if result is not None and not result.empty:
                return int(result.at[0, "id"])
            return None
        except Exception as e:
            self.logger.error(f"Failed to get channel_db_id: {e}")
            return None

    @serialize_channels
    @log(logger=logger)
    def export_subset_to_csv(
        self,
        output_folder: str,
        subset_name: str = "",
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Generator[float, Optional[bool], None]:
        """
        Return a generator that shows progress toward outputting a csv version of the subset of the database satisfying the conditions, including both data and metadata

        :param output_folder: The folder to which the subset should be printed. This is assumed to exist already and will raise an error if it does not.
        :type output_folder: str
        :param subset_name: Optional string to append to filenames in the subset
        :type subset_name: str
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param experiments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :raises KeyError: if any of the requested experiment names cannot be found in the database
        :raises ValueError: if the SQL string constructed from the given conditions is invalid, or no matching data is found
        :yield: a float between 0 and 1 representing progress toward completion
        :ytype: float
        """

        def tuple_builder(id_list: List[int]) -> str:
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Normalize experiment names to IDs if necessary
        experiment_ids = None
        if experiments_and_channels is not None:
            experiment_ids = [
                self.get_experiment_id_by_name(exp)
                for exp in experiments_and_channels.keys()
            ]
            channel_filters = list(experiments_and_channels.values())
            for exp_name, exp_id in zip(
                experiments_and_channels.keys(), experiment_ids
            ):
                if exp_id is None:
                    raise KeyError(f"Could not find experiment ID(s) for: {exp_name}")

        base_conditions = []

        if conditions:
            base_conditions.append(conditions)

        experiment_conditions = []
        if experiment_ids is not None:
            for exp_id, channel_list in zip(experiment_ids, channel_filters):
                if channel_list:
                    condition = f"(experiment_id = {exp_id} AND channel_id IN {tuple_builder(channel_list)})"
                else:
                    condition = f"(experiment_id = {exp_id})"
                experiment_conditions.append(condition)

        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        condition_clause = (
            f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
        )

        events_query = f"SELECT * FROM events {condition_clause}"
        valid, debug = self.validate_filter_query(events_query)
        if debug:
            raise ValueError(
                f"Malformed events query:\n\n{self._format_debug_msg(debug)}"
            )
        events = self._load_metadata(events_query)
        if events is None:
            # Logged at ERROR here, not left to the worker: EventWorker reports a
            # stopped run at WARNING on the status panel, so a genuine failure has to
            # raise QtHandler's dialog from the place that knows it is one. See
            # DECISIONS.md, 2026-09-04. The same applies to every guard below.
            self.logger.error(f"Events query failed: {events_query}")
            raise ValueError("Failed to load events table.")
        if len(events) == 0:
            raise ValueError("No events found matching subset criteria")

        event_ids = [int(eid) for eid in events["id"].values.astype(int)]
        sublevels_query = f"SELECT sub.* FROM sublevels sub WHERE sub.event_db_id IN {tuple_builder(event_ids)}"
        valid, debug = self.validate_filter_query(sublevels_query)
        if debug:
            raise ValueError(
                f"Malformed sublevels query:\n\n{self._format_debug_msg(debug)}"
            )
        sublevels = self._load_metadata(sublevels_query)
        if sublevels is None:
            self.logger.error(
                f"Query failed, could not load sublevels data: {sublevels_query}"
            )
            raise ValueError("Failed to load sublevels data.")

        unique_exp_ids = [int(exp_id) for exp_id in np.unique(events["experiment_id"])]
        experiment_query = f"SELECT exp.* FROM experiments exp WHERE exp.id IN {tuple_builder(unique_exp_ids)}"
        valid, debug = self.validate_filter_query(experiment_query)
        if debug:
            raise ValueError(
                f"Malformed experiments query:\n\n{self._format_debug_msg(debug)}"
            )
        experiments = self.query_database_directly(experiment_query)
        if experiments is None:
            self.logger.error(
                f"Query failed, could not load experiments table: {experiment_query}"
            )
            raise ValueError("Failed to load experiments table.")

        channel_ids = [int(cid) for cid in events["channel_db_id"].values.astype(int)]
        channel_query = (
            f"SELECT ch.* FROM channels ch WHERE ch.id IN {tuple_builder(channel_ids)}"
        )
        valid, debug = self.validate_filter_query(channel_query)
        if debug:
            raise ValueError(
                f"Malformed channels query:\n\n{self._format_debug_msg(debug)}"
            )
        channels = self.query_database_directly(channel_query)
        if channels is None:
            self.logger.error(
                f"Query failed, could not load channels table: {channel_query}"
            )
            raise ValueError("Failed to load channels table.")

        columns_query = "SELECT cols.* FROM columns cols"
        valid, debug = self.validate_filter_query(columns_query)
        if debug:
            raise ValueError(
                f"Malformed columns query:\n\n{self._format_debug_msg(debug)}"
            )
        columns = self.query_database_directly(columns_query)
        if columns is None:
            self.logger.error(
                f"Query failed, could not load columns table: {columns_query}"
            )
            raise ValueError("Failed to load columns table.")

        data_query = f"SELECT d.experiment_id, d.channel_id, d.channel_db_id, d.event_id, d.event_db_id FROM data d WHERE d.event_db_id IN {tuple_builder(event_ids)}"
        valid, debug = self.validate_filter_query(data_query)
        if debug:
            raise ValueError(
                f"Malformed data query:\n\n{self._format_debug_msg(debug)}"
            )
        data = self.query_database_directly(data_query)
        if data is None:
            self.logger.error(f"Query failed, could not load data table: {data_query}")
            raise ValueError("Failed to load data table.")
        if data.empty:
            self.logger.error(
                f"Inconsistent database: {len(event_ids)} events selected but the data "
                "table holds no rows for any of them"
            )
            raise ValueError("No rows in the data table for the selected events.")

        append = f"{subset_name}_" if subset_name else ""

        columns.to_csv(Path(output_folder, f"{append}columns.csv"), index=False)
        channels.to_csv(Path(output_folder, f"{append}channels.csv"), index=False)
        experiments.to_csv(Path(output_folder, f"{append}experiments.csv"), index=False)
        events.to_csv(Path(output_folder, f"{append}events.csv"), index=False)
        sublevels.to_csv(Path(output_folder, f"{append}sublevels.csv"), index=False)

        filenames = [f"{append}event_{event_id}.csv" for event_id in event_ids]
        data["filename"] = filenames
        data.to_csv(Path(output_folder, f"{append}data.csv"), index=False)

        event_data_generator = self.load_event_data(
            f"event_db_id IN {tuple_builder(event_ids)}", experiments_and_channels
        )

        num_events = len(events)
        for i, (filename, event_data) in enumerate(
            zip(filenames, event_data_generator)
        ):
            df = pd.DataFrame(
                {
                    "raw_data": event_data["raw_data"],
                    "filtered_data": event_data["filtered_data"],
                    "fit_data": event_data["fit_data"],
                }
            )
            df.to_csv(Path(output_folder, filename), index=False)
            abort_opt = yield i / num_events
            if bool(abort_opt):
                self.logger.info(
                    "CSV export aborted after "
                    f"{i + 1} of {num_events} events; "
                    "files already written are left in place"
                )
                break
        yield 1.0

    @log(logger=logger)
    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
        """
        Return a string detailing event counts per experiment and channel.

        :param channel: channel ID. Currently unused at the base class level but
            retained for API compatibility with subclasses that may filter by channel.
        :type channel: Optional[int]
        :param init: True if the function is being called as part of plugin
            initialization. Default False.
        :type init: bool

        :return: a formatted string listing the number of experiments and the
            event count per channel for each experiment, or ``"No experiments found."``
            if the database is empty.
        :rtype: str
        """
        self._ensure_event_counts()
        result = self.query_database_directly(
            """
            SELECT exp.name, cs.channel_id, cs.event_count
            FROM event_counts cs
            JOIN experiments exp ON exp.id = cs.experiment_id
            ORDER BY exp.name, cs.channel_id
        """
        )
        if result is None or result.empty:
            return "No experiments found."

        counts: Dict[str, Dict[int, int]] = defaultdict(dict)
        for _, row in result.iterrows():
            counts[row["name"]][row["channel_id"]] = row["event_count"]

        num_experiments = len(counts)
        report = (
            f" {num_experiments} experiment\n"
            if num_experiments == 1
            else f"{num_experiments} experiments\n"
        )
        for exp_name, channel_counts in counts.items():
            report += f"{exp_name}:\n"
            for ch, num in channel_counts.items():
                report += f"Channel: {ch}: {num} events\n"
        return report.rstrip("\n")

    def _split_on_sql_string_literals(self, fragment: str) -> List[str]:
        """
        Split a SQL fragment into alternating code and string-literal segments.

        Even indices hold code, odd indices hold single-quoted literals with their
        quotes intact, and ``"".join`` of the result reproduces the input exactly.
        Callers rewrite the even segments and leave the odd ones alone, so a column
        name that also appears as a value - ``sequence = 'sublevel_current'`` - is
        not rewritten along with the real column references.

        :param fragment: A fragment of SQL, typically a WHERE clause body.
        :type fragment: str
        :return: The alternating code and string-literal segments of the fragment.
        :rtype: List[str]
        """
        # The literal is a capturing group so that re.split returns the literals
        # interleaved with the code around them. "''" is SQL's escape for a quote
        # inside a literal, so it must not be read as the end of one.
        return re.split(r"('(?:[^']|'')*')", fragment)

    def _references_column(self, fragment: str, column: str) -> bool:
        """
        Report whether a SQL fragment refers to a column outside of any string literal.

        Matches a qualified reference (``s.duration``) as well as a bare one, since
        the column name is sought on a word boundary rather than a token boundary.

        :param fragment: A fragment of SQL, typically a WHERE clause body.
        :type fragment: str
        :param column: The column name to look for.
        :type column: str
        :return: True if the fragment refers to the column outside a string literal.
        :rtype: bool
        """
        pattern = rf"(?<!\w){re.escape(column)}(?!\w)"
        segments = self._split_on_sql_string_literals(fragment)
        return any(re.search(pattern, segment) for segment in segments[::2])

    def _qualify_conditions(self, conditions: str, aliases: Dict[str, str]) -> str:
        """
        Qualify bare column references against the tables a query actually joins.

        Lets a user write ``sublevel_duration < 100 AND experiment_id = 2`` and have
        it work against ``FROM events e JOIN sublevels s``. Only the code parts of
        the condition are rewritten; anything inside a single-quoted string literal
        is left exactly as the user typed it, and a reference the user already
        qualified is left alone.

        :param conditions: A WHERE clause body, without the leading ``WHERE``.
        :type conditions: str
        :param aliases: Table name to alias, for every table in the FROM clause, in
            join order. The first entry is the anchor.
        :type aliases: Dict[str, str]
        :return: The condition with its bare column references qualified.
        :rtype: str
        """
        anchor = next(iter(aliases.values()))
        passes = [
            (self.get_column_names_by_table(table) or [], alias)
            for table, alias in aliases.items()
        ]

        if len(aliases) > 1:
            # These are never registered in the "columns" table but exist in more
            # than one of the joined tables, so a bare reference is ambiguous to
            # SQLite. A sublevel row carries its parent event's values for all four,
            # so attributing them to the anchor cannot change which rows match.
            # "id" is deliberately absent: it is the events row id in one table and
            # the sublevels row id in the other, so only the user can say which.
            passes.append(
                (["experiment_id", "channel_db_id", "channel_id", "event_id"], anchor)
            )

        # A registered column belongs to exactly one table - "columns.name" is
        # UNIQUE - so the order of the passes does not matter, and the (?<!\.)
        # guard keeps each pass off the previous pass's output.
        segments = self._split_on_sql_string_literals(conditions)
        for index in range(0, len(segments), 2):
            for cols, alias in passes:
                for col in sorted(set(cols), key=len, reverse=True):
                    segments[index] = re.sub(
                        rf"(?<!\.)\b{re.escape(col)}\b",
                        f"{alias}.{col}",
                        segments[index],
                    )

        return "".join(segments)

    def _find_ambiguous_id(
        self, conditions: str, aliases: Dict[str, str]
    ) -> Optional[str]:
        """
        Explain how to disambiguate a bare ``id`` in a condition, if there is one.

        ``id`` is the only column a joined query cannot resolve on the user's
        behalf: it means a different row in every table, so guessing one would
        silently filter against the wrong thing. Run this after
        :meth:`_qualify_conditions`, since anything still bare at that point is
        genuinely unqualified.

        :param conditions: A WHERE clause body that has already been qualified.
        :type conditions: str
        :param aliases: Table name to alias, for every table in the FROM clause.
        :type aliases: Dict[str, str]
        :return: Guidance to show the user, or None if there is nothing ambiguous.
        :rtype: Optional[str]
        """
        if len(aliases) < 2:
            return None

        segments = self._split_on_sql_string_literals(conditions)
        if not any(
            re.search(r"(?<![\w.])id(?!\w)", segment) for segment in segments[::2]
        ):
            return None

        tables = list(aliases)
        joined = f"{', '.join(tables[:-1])} and {tables[-1]}"
        options = ", ".join(
            f'"{alias}.id" for a row of {table}' for table, alias in aliases.items()
        )
        return (
            'This filter uses "id" on its own, which is ambiguous: the query joins '
            f"{joined}, and each of those has its own id column. "
            f"Say which one you mean - write {options}."
        )

    @log(logger=logger)
    def construct_metadata_query(
        self,
        columns: List[str],
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Tuple[str, str, str]:
        """
        Build a SELECT over the metadata tables, joining whatever the request needs.

        The shape is derived rather than enumerated. Every query is anchored on
        ``events`` (or on ``sublevels``, when no events column is involved) and
        aliased ``e``/``s``/``exp``; the other tables are joined only when the
        selected columns or the conditions refer to them:

        .. code-block:: sql

            SELECT [[DISTINCT]] a.id, a.experiment_id, a.channel_id, a.event_id, [[columns]]
            FROM events e
            [[JOIN sublevels s ON e.id = s.event_db_id]]
            [[JOIN experiments exp ON exp.id = e.experiment_id]]
            WHERE [[conditions]]

        ``DISTINCT`` appears when ``sublevels`` is joined purely to filter an events
        plot, since that repeats each event once per sublevel. The returned id
        column belongs to the returned table name, which callers rely on to write
        derived columns back.

        Conditions are qualified against the tables the query actually joins, so a
        caller passes a plain WHERE clause body - ``sublevel_duration < 100 AND
        voltage > 50`` - without knowing the shape. Text inside single-quoted
        literals is never rewritten. A bare ``id`` is refused, with guidance
        returned as the debug message, because it means a different row in each
        table.

        :param columns: List of column names to retrieve.
        :type columns: List[str]
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param experiments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :raises KeyError: if any of the requested experiment names cannot be found in the database
        :raises ValueError: if columns is empty, or a column cannot be mapped to a table
        :return: a valid SQL query and an empty string, or an empty string and a debug message, and the table name of the affected id column
        :rtype: Tuple[str, str, str]
        """

        def tuple_builder(id_list: List[int]) -> str:
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Validate input
        if not columns:
            raise ValueError("list of columns cannot be empty")

        # Remove redundant columns (before mapping to tables)
        # (include unaliased names so "event_id" doesn't duplicate)
        redundant_cols = {
            "id",
            "experiment_id",
            "channel_id",
            "event_id",
            "s.id",
            "e.experiment_id",
            "e.channel_id",
            "e.event_id",
        }
        filtered = [col for col in columns if col not in redundant_cols]

        # Only apply the filtering if it leaves something usable.
        # Otherwise keep the original columns (so ["event_id"] won't become []).
        if filtered:
            columns = filtered

        if not columns:
            raise ValueError("list of columns cannot be empty")

        # Identify table sources for each column
        tables = [self.get_table_by_column(col) for col in columns]
        if any(table is None for table in tables):
            invalid_columns = [
                col for col, table in zip(columns, tables) if table is None
            ]
            raise ValueError(
                f"The following columns could not be mapped to tables: {', '.join(invalid_columns)}"
            )

        events_columns = [col for col, tbl in zip(columns, tables) if tbl == "events"]
        sublevels_columns = [
            col for col, tbl in zip(columns, tables) if tbl == "sublevels"
        ]
        experiments_columns = [
            col for col, tbl in zip(columns, tables) if tbl == "experiments"
        ]

        # An experiments-only selection is anchored to events, so that the
        # experiments table can be joined through events.experiment_id.
        if experiments_columns and not events_columns and not sublevels_columns:
            events_columns = ["event_id"]

        if not events_columns and not sublevels_columns and not experiments_columns:
            raise ValueError(
                "No valid table columns specified: You must select at least one column from either the events or sublevels tables"
            )

        # Detect the joins the conditions need on top of those the selected columns
        # already imply. _references_column ignores string literals, so this agrees
        # with _qualify_conditions about what counts as a column reference.
        force_events_sublevels_join = False
        force_experiments_join = False
        if conditions:
            sub_cols = self.get_column_names_by_table("sublevels") or []
            evt_cols = self.get_column_names_by_table("events") or []
            exp_cols = self.get_column_names_by_table("experiments") or []

            if events_columns and not sublevels_columns:
                force_events_sublevels_join = any(
                    self._references_column(conditions, col) for col in sub_cols
                )
            elif sublevels_columns and not events_columns:
                force_events_sublevels_join = any(
                    self._references_column(conditions, col) for col in evt_cols
                )

            if not experiments_columns:
                force_experiments_join = any(
                    self._references_column(conditions, col) for col in exp_cols
                )

        # The tables the query joins, in join order. The first is the anchor: it
        # supplies the experiment_id, channel_id and event_id outputs, and the
        # conditions' bare references to those are attributed to it. A sublevel row
        # carries its parent event's values for all three, so which of the two is
        # the anchor does not change the rows that match.
        aliases: Dict[str, str] = {}
        if events_columns:
            aliases["events"] = "e"
            if sublevels_columns or force_events_sublevels_join:
                aliases["sublevels"] = "s"
        else:
            aliases["sublevels"] = "s"
            if force_events_sublevels_join:
                aliases["events"] = "e"
        if experiments_columns or force_experiments_join:
            aliases["experiments"] = "exp"

        anchor_table = next(iter(aliases))
        anchor = aliases[anchor_table]

        # The id column and the table name travel together: callers write derived
        # columns back with UPDATE <table_name> ... WHERE id = ?, so the id returned
        # must belong to that table (see ClusteringView.commit_cluster_data).
        table_name = "sublevels" if sublevels_columns else "events"
        id_alias = aliases[table_name]

        # Normalize experiment names to IDs if necessary
        experiments = None
        if experiments_and_channels is not None:
            experiments = [
                self.get_experiment_id_by_name(exp)
                for exp in experiments_and_channels.keys()
            ]
            channels = [channels for channels in experiments_and_channels.values()]

            for exp_id, exp_name in zip(experiments, experiments_and_channels.keys()):
                if exp_id is None:
                    raise KeyError(f"Could not find experiment ID(s) for: {exp_name}")

        base_conditions = []

        # General conditions (AND logic)
        if conditions:
            base_conditions.append(conditions)

        # Experiment/channel conditions (OR logic between each). Left unqualified
        # here; _qualify_conditions anchors them along with the user's own.
        experiment_conditions = []
        if experiments is not None:
            for exp, channel_list in zip(experiments, channels):
                if channel_list:
                    condition = f"(experiment_id = {exp} AND channel_id IN {tuple_builder(channel_list)})"
                else:
                    condition = f"(experiment_id = {exp})"
                experiment_conditions.append(condition)

        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        condition_clause = ""
        if base_conditions:
            qualified = self._qualify_conditions(" AND ".join(base_conditions), aliases)
            ambiguous_id = self._find_ambiguous_id(qualified, aliases)
            if ambiguous_id is not None:
                return "", ambiguous_id, table_name
            condition_clause = f"WHERE {qualified}"

        # A join to sublevels with no sublevel column selected repeats each event
        # once per sublevel, so those rows have to be collapsed.
        distinct = "DISTINCT " if force_events_sublevels_join else ""

        select_columns = [
            f"{id_alias}.id",
            f"{anchor}.experiment_id",
            f"{anchor}.channel_id",
            f"{anchor}.event_id",
        ]
        for table, table_columns in (
            ("events", events_columns),
            ("sublevels", sublevels_columns),
            ("experiments", experiments_columns),
        ):
            select_columns += [f"{aliases[table]}.{col}" for col in table_columns]

        from_clause = f"FROM {anchor_table} {anchor}"
        if "events" in aliases and "sublevels" in aliases:
            joined = "sublevels" if anchor_table == "events" else "events"
            from_clause += (
                f"\n                        JOIN {joined} {aliases[joined]}"
                "\n                        ON e.id = s.event_db_id"
            )
        if "experiments" in aliases:
            from_clause += (
                "\n                        JOIN experiments exp"
                f"\n                        ON exp.id = {anchor}.experiment_id"
            )

        query = f"""SELECT {distinct}{', '.join(select_columns)}
                        {from_clause}
                        {condition_clause}"""

        # Validate query
        valid, debug = self.validate_filter_query(query)
        if valid:
            return query, "", table_name
        else:
            return "", self._format_debug_msg(debug), table_name

    @log(logger=logger)
    def construct_event_data_query(
        self,
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Tuple[str, str]:
        """
        Construct a query that will get all event data matching a set of conditions

        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param experiments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a valid SQL query and an empty string, or an empty string and a debug message
        :rtype: Tuple[str, str]
        """

        def tuple_builder(id_list: List[int]) -> str:
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Normalize experiment names to IDs if necessary
        experiments = None
        if experiments_and_channels is not None:
            experiments = [
                self.get_experiment_id_by_name(exp)
                for exp in experiments_and_channels.keys()
            ]
            channels = [channels for channels in experiments_and_channels.values()]

            for exp_id, exp_name in zip(experiments, experiments_and_channels.keys()):
                if exp_id is None:
                    raise KeyError(f"Could not find experiment ID(s) for: {exp_name}")

        ####
        base_conditions = []

        # General conditions (AND logic)
        if conditions:
            base_conditions.append(conditions)

        # Experiment/channel conditions (OR logic between each)
        experiment_conditions = []
        if experiments is not None:
            for exp, channel_list in zip(experiments, channels):
                if channel_list:
                    condition = f"(e.experiment_id = {exp} AND e.channel_id IN {tuple_builder(channel_list)})"
                else:
                    condition = f"(e.experiment_id = {exp})"
                experiment_conditions.append(condition)

        # Combine all into final WHERE clause
        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        # The subquery below always joins all three tables, so the same filter text
        # has to be qualified against the same aliases it would get in
        # construct_metadata_query.
        aliases = {"events": "e", "sublevels": "s", "experiments": "exp"}
        subquery_clause = ""
        if base_conditions:
            qualified = self._qualify_conditions(" AND ".join(base_conditions), aliases)
            ambiguous_id = self._find_ambiguous_id(qualified, aliases)
            if ambiguous_id is not None:
                return "", ambiguous_id
            subquery_clause = f"WHERE {qualified}"

        # Main query prefix
        start_clause = """
            SELECT
                d.id,
                d.event_id,
                d.channel_id,
                d.experiment_id,
                d.data_format,
                c.samplerate,
                pb.sublevel_duration AS padding_before,
                pa.sublevel_duration AS padding_after,
                d.raw_data,
                d.filtered_data,
                d.fit_data
            FROM data d
            JOIN channels c ON c.id = d.channel_db_id
            LEFT JOIN (
                SELECT event_db_id, sublevel_duration
                FROM sublevels
                WHERE level_id = 0
            ) pb ON pb.event_db_id = d.event_db_id
            LEFT JOIN (
                SELECT event_db_id, sublevel_duration
                FROM sublevels
                WHERE levels_left = 0
            ) pa ON pa.event_db_id = d.event_db_id
            WHERE d.event_db_id IN (
                SELECT DISTINCT event_db_id
                FROM events e
                JOIN sublevels s
                ON e.id = s.event_db_id
                JOIN experiments exp
                ON exp.id = e.experiment_id
                {subquery_clause}
            )
        """.format(
            subquery_clause=subquery_clause
        )

        # Validate and return
        valid, debug = self.validate_filter_query(start_clause)
        if valid:
            return start_clause.strip(), ""
        else:
            return "", self._format_debug_msg(debug)

    @log(logger=logger)
    def load_metadata_raw(
        self,
        conditions: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Execute a raw SQL query directly, bypassing all query construction.

        :param conditions: A complete SQL query string.
        :type conditions: Optional[str]
        :return: pandas dataframe containing retrieved data, empty if the query matched no rows, or None if the query failed or did not validate
        :rtype: Optional[pd.DataFrame]
        """
        if not conditions:
            return self.query_database_directly("SELECT * FROM events")
        return self.query_database_directly(conditions)

    @log(logger=logger)
    def load_metadata(
        self,
        columns: List[str],
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch specified columns from the metadata database given a query

        Will always include experiment_id, channel_id, and event_id in the dataframe in addition to requested columns.

        :param columns: List of column names to retrieve.
        :type columns: List[str]
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param experiments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: pandas dataframe containing retrieved data, empty if the query matched no rows, or None if the query could not be built or run
        :rtype: Optional[pd.DataFrame]
        """
        query, debug, table = self.construct_metadata_query(
            columns, conditions, experiments_and_channels
        )
        if query:
            df = self._load_metadata(query)
            if df is not None:
                df = df.loc[:, ~df.columns.duplicated()]
            return df
        else:
            self.logger.warning(
                f"Unable to output subset due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )
            return None

    @log(logger=logger)
    def load_event_data(
        self,
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Generator[Dict[str, Any], bool, None]:
        """
        Load data and return a generator that gives a one-row dataframe corresponding one row returned by query
        Make sure you exhaust or explicitly abort the generator, or else connections will remain open
        You can assume that the query was generated by self.construct_event_data_query() and will have 10 colums:
        event_id, channel_id, experiment_id, data_format, baseline, stdev, padding_before, padding_after, samplerate, data
        where data is a bytes object to be interpreted using data_format

        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param experiments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]

        :return: a generator that returns primary database id, experiment_id, channel_id, event_id, samplerate, padding_before, padding_after, samplerate, and a numpy array with event data
        :rtype: Generator[Dict[str, Any], bool, None]
        """
        query, debug = self.construct_event_data_query(
            conditions, experiments_and_channels
        )
        if query:
            event_generator = self._load_event_data(query)
            abort = False
            try:
                for event in event_generator:
                    (
                        db_id,
                        experiment_id,
                        channel_id,
                        event_id,
                        samplerate,
                        padding_before,
                        padding_after,
                        raw_data,
                        filtered_data,
                        fit_data,
                    ) = event
                    abort = yield {
                        "id": db_id,
                        "event_id": event_id,
                        "channel_id": channel_id,
                        "experiment_id": experiment_id,
                        "samplerate": samplerate,
                        "padding_before": padding_before,
                        "padding_after": padding_after,
                        "raw_data": raw_data,
                        "filtered_data": filtered_data,
                        "fit_data": fit_data,
                    }
                    abort = bool(abort)
                    if abort is True:
                        break
            finally:
                event_generator.close()
            if abort is True:
                self.logger.info("Generator aborted")
                return
        else:
            self.logger.warning(
                f"Unable to output subset due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )

    @log(logger=logger)
    def query_database_directly(self, query: str) -> Optional[pd.DataFrame]:
        """
        Run a given query on the DB after basic validation.

        :param query: query to  run on the database
        :type query: str

        :return: List of numpy arrays containing retrieved data.
        :rtype: Optional[pd.DataFrame]
        """
        valid, debug = self.validate_filter_query(query)
        if valid and not debug:
            return self._load_metadata(query)
        else:
            self.logger.warning(
                f"Unable to output subset due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )
            return None

    @log(logger=logger)
    def query_database_directly_and_get_generator(
        self, query: str
    ) -> Generator[pd.DataFrame, bool, None]:
        """
        Run a given querry on the DB after basic validation and return a generator that feeds out one row at a time

        :param query: query to  run on the database
        :type query: str

        :return: A generator that feeds out onne row at a time in the form of a single-line dataframe
        :rtype: Generator[pd.DataFrame, bool, None]
        """
        valid, debug = self.validate_filter_query(query)
        if valid and not debug:
            metadata_generator = self._load_metadata_generator(query)
            abort = False
            try:
                for event in metadata_generator:
                    event = event.loc[:, ~event.columns.duplicated()]
                    abort = yield event
                    abort = bool(abort)
                    if abort is True:
                        break
            finally:
                metadata_generator.close()
            if abort is True:
                self.logger.info("Generator aborted")
                return
        else:
            self.logger.warning(
                f"Unable to get subset generator due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _load_metadata(self, query: str) -> Optional[pd.DataFrame]:
        """
        **Purpose:** Load and return the data specified by a valid SQL query, or None if the query could not be run

        The data should be formatted as a pandas Dataframe object. A query that
        matched no rows must return an empty dataframe rather than None, so that
        callers can tell an empty result from a failed query.

        :param query: a valid SQL query, checked in the calling function for validity
        :type query: str
        :return: A dataframe containing the requested event data as columns, empty if the query matched no rows, or None if the query could not be run
        :rtype: Optional[pd.DataFrame]
        """
        pass

    @abstractmethod
    def _load_metadata_generator(
        self, query: str
    ) -> Generator[pd.DataFrame, None, None]:
        """
        **Purpose:** Load and yield the data specified by a valid SQL query one row at a time. Useful in cases where :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata` returns too much data for memory.

        Data should be formatted as a pandas dataframe in line with :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata`. Make sure you exhaust the generator when done with it, or else database connections will remain open.

        :param query: query to  run on the database
        :type query: str
        :return: A generator that feeds out onne row at a time in the form of a single-line dataframe
        :rtype: Generator[pd.DataFrame, None, None]
        """
        pass

    @abstractmethod
    def _load_event_data(self, query: str) -> Any:
        """
        Load data and return a generator that gives a one-row dataframe corresponding one row returned by query
        Make sure you exhaust the generator, or else connections will remain open
        You can assume that the query was generated by self.construct_event_data_query() and will have 5 colums:
        event_id, channel_id, experiment_id, data_format, data, baseline, stdev, padding_before, padding_after, data
        where data is a bytes object to be interpreted using data_format

        :param query: a valid SQL query, checked in the calling function for validity
        :type query: str

        :return: a generator that yields one item per row matching the query, with id, event_id, channel_id, experiment_id, samplerate, padding_before, padding_after, and numpy array with event data for raw, filtered, and fitted data. The exact shape of each yielded item (e.g. dict vs. tuple) is defined by the concrete subclass; see its own docstring for the precise structure.
        :rtype: Any
        """
        pass

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed

    @abstractmethod
    def _ensure_event_counts(self) -> None:
        """
        Ensure the event_counts summary table exists and is populated.
        If the table does not exist, create it, populate it from existing events,
        and add the appropriate triggers to keep it in sync going forward.

        :return: None
        :rtype: None

        :raises sqlite3.Error: If a database error occurs during table creation or population.
        """
        pass

    @log(logger=logger)
    def _finalize_initialization(self) -> None:
        """
        **Purpose:** Apply application-specific settings to the plugin, if needed.

        If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaDatabaseLoader` that must occur after settings have been applied to the reader instance, you can override this function to add those operations.
        """
        pass

    @log(logger=logger)
    def _format_debug_msg(self, debug: str) -> str:
        """
        Strip out newlines and unnecessary whitespace from SQL queries for printing

        :param debug: a string containing an error message and an SQL string for correction
        :type debug: str

        :return: the input string with whitepsace removed and newlines in it to format for export
        :rtype: str
        """
        debug = re.sub(r"[ \t]+", " ", debug)
        return re.sub(r"\n[ \t]+", "\n", debug)

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters required to configure this database loader.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    # Utility functions, specific to subclasses as needed
