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

    def __init__(self, settings: Optional[dict] = None):
        """
        Initialize and set up the plugin, if settings are available at this stage
        """
        super().__init__(settings)

    # public API, MUST be implemented by subclasses
    @abstractmethod
    def get_llm_prompt(self) -> str:
        """
        :return: a prompt that gives an LLM context for the database and  how to query it
        :rtype: str

        **Purpose:** Return a prompt that will tell the LLM the structure of the database to be queried to assist users in accessing the data written in your format
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else reset all of them. In most cases for MetaDatabaseLoaders there is no need to reset and you can simplt ``pass``.
        """
        pass

    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory on app exit.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Do this for all channels if no channel is specified, otherwise limit your closure to the specified channel. If no such operation is needed, it suffices to ``pass``.
        """
        pass

    @abstractmethod
    def get_experiment_names(
        self, experiment_id: Optional[int] = None
    ) -> Optional[List[str]]:
        """
        :param experiment_id: the id of the experiment for which to fetch the name
        :type experiment_id: Optional[int]

        :return: List of experiment names, or None on failure
        :rtype: Optional[List[str]]

        **Purpose:** Retrieve a list of all unique experiment names registered in the database, or a singleton list if an id is given.
        """
        pass

    @abstractmethod
    def get_channels_by_experiment(self, experiment: str) -> Optional[List[int]]:
        """
        :param experiment: The name of the experiment.
        :type experiment: str
        :return: List of channel IDs.
        :rtype: Optional[List[int]]

        **Purpose:** Retrieve a list of all channel identifiers (the identifier, not the primary key of the channels table) associated with a given experiment name or None on failure
        """
        pass

    @abstractmethod
    def get_event_counts_by_experiment_and_channel(
        self, experiment: Optional[str] = None, channel: Optional[int] = None
    ) -> int:
        """
        :param experiment: The name of the experiment.
        :type experiment: Optional[str]
        :param channel: The index of the channel
        :type channel: Optional[int]

        :return: event count matching the conditions
        :rtype: int

        **Purpose:**  Return the number of events in the database matching the experiment name and channel identifier.

        If no channel name is provided, count across all channels for that experiment.
        If no experiment is provided, ignore channel and return the number of events in the entire database
        """
        pass

    @abstractmethod
    def get_column_units(self, column_name: str) -> Optional[str]:
        """
        :param column_name: The name of the column.
        :type column_name: str
        :return: The units of the column.
        :rtype: Optional[str]

        **Purpose:** Retrieve the units associated with a specific column name or None on failure
        """
        pass

    @abstractmethod
    def get_column_type(self, column_name: str) -> Optional[str]:
        """
        :param column_name: The name of the column.
        :type column_name: str
        :return: The datatype of the column.
        :rtype: Optional[str]

        **Purpose:** Retrieve the datatype associated with a specific column name or None on failure
        """
        pass

    @abstractmethod
    def get_column_names_by_table(
        self, table: Optional[str] = None
    ) -> Optional[List[str]]:
        """
        :param table: The name of the table.
        :type table: Optional[str]
        :return: List of column names.
        :rtype: Optional[List[str]]

        **Purpose:** Retrieve the column names available in a specified table, all columns in the database is table is not specified, or None on failure
        """
        pass

    @abstractmethod
    def get_table_names(self) -> Optional[List[str]]:
        """
        :return: List of table names.
        :rtype: Optional[List[str]]

        **Purpose:** Retrieve the names of available tables in the database or None on failure.
        """
        pass

    @abstractmethod
    def validate_filter_query(self, query: str) -> Tuple[bool, str]:
        """
        :param query: The SQL query string.
        :type query: str
        :return: ``True, ""`` if the query is valid, and ``False, "[[helpful explanation]]"`` if it is not
        :rtype:  Tuple[bool, str]

        **Purpose:** Validate a SQL query without executing it.

        Return ``True, ""`` if the query is valid, and ``False, "[[helpful explanation]]"`` if it is not
        """
        pass

    @abstractmethod
    def get_samplerate_by_experiment_and_channel(
        self, experiment: str, channel: int
    ) -> Optional[float]:
        """
        :param experiment: The name of the experiment in the database.
        :type experiment: str
        :param channel: The channel id to get sampling rate for.
        :type channel: int
        :return: sampling rate for the specific expreiment-channel combination, or None on failure
        :rtype: Optional[float]

        **Purpose:** Retrieve the sampling rate for a given experiment and channel id, or None on failure
        """
        pass

    @abstractmethod
    def get_table_by_column(self, column: str) -> Optional[str]:
        """
        :param column: The name of the column.
        :type column: str

        :return: List of table names.
        :rtype: List[str]

        **Purpose:** Retrieve the names of the table in which the given column is found, or None on failure
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
        :param queries: a list of queries to  run on the database
        :type queries: List[str]

        :return: True if the operation succeeded, False otherwise
        :rtype: bool

        **Purpose:** Run a given list of queries on the database. There is no validation here, use it sparingly.
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

        :raises RuntimeError: if fitting is not complete yet
        """
        return None, None, None, None, None, None

    @log(logger=logger)
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaWriter` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

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
        """
        settings: Dict[str, Dict[str, Any]] = {
            "Input File": {"Type": str, "Options": ["All Files (*.*)"]}
        }
        return settings

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).
        """
        return False

    @log(logger=logger)
    def get_experiments_and_channels(self) -> Dict[str, Optional[List[int]]]:
        """
        Retrieve a mapping of experiment names to their associated channel lists.

        Calls `get_experiment_names()` to fetch all experiment identifiers,
        then maps each experiment to its corresponding list of channels using `get_channels_by_experiment()`.

        :return: Dictionary mapping experiment names to lists of channel indices.
        :rtype: dict[str, Optional[list[int]]]
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
        """
        if experiment_name:
            try:
                escaped_name = experiment_name.replace("'", "''")
                query = (
                    f"SELECT id FROM experiments WHERE name = '{escaped_name}' LIMIT 1"
                )
                result = self.query_database_directly(query)
                if result is not None:
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

    @log(logger=logger)
    def export_subset_to_csv(
        self,
        output_folder: str,
        subset_name: str = "",
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Generator[float, None, None]:
        """
        Return a generator that shows progress toward outputting a csv version of the subset of the database satisfying the conditions, including both data and metadata

        :param output_folder: The folder to which the subset should be printed. This is assumed to exist already and will raise an error if it does not.
        :type output_folder: str

        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param conditions: Optional string to append to filenames in the subset
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a float between 0 and 1 representing progress toward completion
        :rtype: float

        :raises: IOError if output_folder does not already exist
        :raises: ValueError if the SQL string is invalid
        """

        def tuple_builder(id_list):
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
        if events is None or len(events) == 0:
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
            raise ValueError("Failed to load channels table.")

        columns_query = "SELECT cols.* FROM columns cols"
        valid, debug = self.validate_filter_query(columns_query)
        if debug:
            raise ValueError(
                f"Malformed columns query:\n\n{self._format_debug_msg(debug)}"
            )
        columns = self.query_database_directly(columns_query)
        if columns is None:
            raise ValueError("Failed to load columns table.")

        data_query = f"SELECT d.experiment_id, d.channel_id, d.channel_db_id, d.event_id, d.event_db_id FROM data d WHERE d.event_db_id IN {tuple_builder(event_ids)}"
        valid, debug = self.validate_filter_query(data_query)
        if debug:
            raise ValueError(
                f"Malformed data query:\n\n{self._format_debug_msg(debug)}"
            )
        data = self.query_database_directly(data_query)
        if data is None:
            raise ValueError("Failed to load data table.")

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
            yield i / num_events
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

        :raises sqlite3.Error: If a database error occurs while reading from
            event_counts.
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

    @log(logger=logger)
    def construct_metadata_query(
        self,
        columns: List[str],
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Tuple[str, str, str]:
        """
        The query to be constructed will take one of three forms, depending on the tables in which the metadata reside.

        If all queries are in the events table, then the query executed will be:

        .. code-block:: sql

            SELECT id, experiment_id, channel_id, event_id, [[columns]]
            FROM events
            WHERE [[conditions]]

        If all queries are in the sublevels table, then the query executed will be:

        .. code-block:: sql

            SELECT id, experiment_id, channel_id, event_id, [[columns]]
            FROM sublevels
            WHERE [[conditions]]

        If the columns are mixed between the tables, the query will be:

        .. code-block:: sql

            SELECT e.id, e.experiment_id, e.channel_id, e.event_id, [[events_columns]], [[sublevels_columns]]
            FROM events e
            JOIN sublevels s on e.id = s.event_db_id
            WHERE [[conditions]]

        Note when constructing the conditions clause that it will need to take into account this structure.

        :param columns: List of column names to retrieve.
        :type columns: List[str]
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a valid SQL query and an empty string, or an empty string and a debug message, and the table name of the affected id column
        :rtype: Tuple[str, str, str]
        """

        def tuple_builder(id_list):
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Qualify conditions for joined queries to avoid "no such column" / ambiguity
        def _qualify_conditions_for_events_sublevels_join(cond: str) -> str:
            """
            Qualify bare column references so a user can write:
                sublevel_duration < 100 AND experiment_id = 2
            and it will work in a query that has:
                FROM events e JOIN sublevels s ...
            """
            # Only qualify if not already qualified with a dot (e.g. "e.id", "s.sublevel_duration")
            sub_cols = self.get_column_names_by_table("sublevels") or []
            evt_cols = self.get_column_names_by_table("events") or []
            exp_cols = self.get_column_names_by_table("experiments") or []

            # Qualify sublevels columns first
            for col in sorted(set(sub_cols), key=len, reverse=True):
                cond = re.sub(rf"(?<!\.)\b{re.escape(col)}\b", f"s.{col}", cond)

            # Then events columns
            for col in sorted(set(evt_cols), key=len, reverse=True):
                cond = re.sub(rf"(?<!\.)\b{re.escape(col)}\b", f"e.{col}", cond)

            # Then experiments columns (if present in condition text)
            for col in sorted(set(exp_cols), key=len, reverse=True):
                cond = re.sub(rf"(?<!\.)\b{re.escape(col)}\b", f"exp.{col}", cond)

            return cond

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

        # "events" anchor to JOIN experiments via events.
        if experiments_columns and not events_columns and not sublevels_columns:
            events_columns = ["event_id"]

        # Detect whether we must force a JOIN for cross-table filtering
        force_events_sublevels_join = False
        if conditions:
            sub_cols = self.get_column_names_by_table("sublevels") or []
            evt_cols = self.get_column_names_by_table("events") or []

            if events_columns and not sublevels_columns:
                for col in sub_cols:
                    # match word boundaries; also catches "s.col" because it contains "col"
                    if re.search(rf"(?<!\w){re.escape(col)}(?!\w)", conditions):
                        force_events_sublevels_join = True
                        break

            elif sublevels_columns and not events_columns:
                for col in evt_cols:
                    if re.search(rf"(?<!\w){re.escape(col)}(?!\w)", conditions):
                        force_events_sublevels_join = True
                        break

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

        # Experiment/channel conditions (OR logic between each)
        experiment_conditions = []
        if experiments is not None:
            # when JOINing events+sublevels (including forced join),
            # always qualify experiment_id/channel_id as e.* to avoid ambiguity.
            prefix = (
                "e."
                if (events_columns and sublevels_columns) or force_events_sublevels_join
                else ""
            )

            for exp, channel_list in zip(experiments, channels):
                if channel_list:
                    condition = f"({prefix}experiment_id = {exp} AND {prefix}channel_id IN {tuple_builder(channel_list)})"
                else:
                    condition = f"({prefix}experiment_id = {exp})"
                experiment_conditions.append(condition)

        # Combine all into final WHERE clause
        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        condition_clause = (
            f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
        )

        # Determine query type and build it
        if force_events_sublevels_join and not experiments_columns:
            # Qualify WHERE clause contents for e./s. usage
            if condition_clause:
                raw = condition_clause.replace("WHERE ", "", 1)
                qualified_conditions = _qualify_conditions_for_events_sublevels_join(
                    raw
                )
                qualified_where = f"WHERE {qualified_conditions}"
            else:
                qualified_where = ""

            if events_columns and not sublevels_columns:
                # events plot filtered by sublevels column
                events_str = ", ".join([f"e.{col}" for col in events_columns])
                query = f"""SELECT DISTINCT e.id, e.experiment_id, e.channel_id, e.event_id, {events_str}
                            FROM events e
                            JOIN sublevels s ON e.id = s.event_db_id
                            {qualified_where}"""
                table_name = "events"
            else:
                # sublevels plot filtered by events column
                sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns])
                query = f"""SELECT DISTINCT s.id, e.experiment_id, e.channel_id, e.event_id, {sublevels_str}
                            FROM sublevels s
                            JOIN events e ON e.id = s.event_db_id
                            {qualified_where}"""
                table_name = "sublevels"

        elif events_columns and not sublevels_columns and not experiments_columns:
            events_str = ", ".join(events_columns)
            query = f"""SELECT id, experiment_id, channel_id, event_id, {events_str}
                        FROM events
                        {condition_clause}"""
            table_name = "events"

        elif sublevels_columns and not events_columns and not experiments_columns:
            sublevels_str = ", ".join(sublevels_columns)
            query = f"""SELECT id, experiment_id, channel_id, event_id, {sublevels_str}
                        FROM sublevels
                        {condition_clause}"""
            table_name = "sublevels"

        elif events_columns and sublevels_columns and not experiments_columns:
            events_str = ", ".join([f"e.{col}" for col in events_columns])
            sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns])
            query = f"""SELECT s.id, e.experiment_id, e.channel_id, e.event_id, {events_str}, {sublevels_str}
                        FROM events e
                        JOIN sublevels s
                        ON e.id = s.event_db_id
                        {condition_clause}"""
            table_name = "sublevels"

        elif events_columns and not sublevels_columns and experiments_columns:
            events_str = ", ".join([f"e.{col}" for col in events_columns])
            experiments_str = ", ".join([f"exp.{col}" for col in experiments_columns])
            query = f"""SELECT e.id, e.experiment_id, e.channel_id, e.event_id, {events_str}, {experiments_str}
                        FROM events e
                        JOIN experiments exp
                        ON exp.id = e.experiment_id
                        {condition_clause}"""
            table_name = "events"

        elif sublevels_columns and not events_columns and experiments_columns:
            sublevels_str = ", ".join(sublevels_columns)
            experiments_str = ", ".join([f"exp.{col}" for col in experiments_columns])
            query = f"""SELECT s.id, s.experiment_id, s.channel_id, s.event_id, {sublevels_str}, {experiments_str}
                        FROM sublevels s
                        JOIN experiments exp
                        ON exp.id = s.experiment_id
                        {condition_clause}"""
            table_name = "sublevels"

        elif events_columns and sublevels_columns and experiments_columns:
            events_str = ", ".join([f"e.{col}" for col in events_columns])
            sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns])
            experiments_str = ", ".join([f"exp.{col}" for col in experiments_columns])
            query = f"""SELECT s.id, e.experiment_id, e.channel_id, e.event_id, {events_str}, {sublevels_str}, {experiments_str}
                        FROM events e
                        JOIN sublevels s
                        ON e.id = s.event_db_id
                        JOIN experiments exp
                        ON exp.id = s.experiment_id
                        {condition_clause}"""
            table_name = "sublevels"
        else:
            raise ValueError(
                "No valid table columns specified: You must select at least one column from either the events or sublevels tables"
            )

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
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a valid SQL query and an empty string, or an empty string and a debug message
        :rtype: Tuple[str, str]
        """

        def tuple_builder(id_list):
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

        subquery_clause = (
            f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
        )

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
    ) -> pd.DataFrame:
        """
        Execute a raw SQL query directly, bypassing all query construction.

        :param conditions: A complete SQL query string.
        :type conditions: Optional[str]
        :return: pandas dataframe containing retrieved data
        :rtype: pd.DataFrame
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
    ) -> pd.DataFrame:
        """
        Fetch specified columns from the metadata database given a query

        Will always include experiment_id, channel_id, and event_id in the dataframe in addition to requested columns.

        :param columns: List of column names to retrieve.
        :type columns: List[str]
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: pandas dataframe containing retrieved data
        :rtype: pd.DataFrame
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
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
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
            if metadata_generator is not None:
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
                    "Unable to get events from subset generator that returned None"
                )
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
        :param query: a valid SQL query, checked in the calling function for validity
        :type query: str

        :return: A dataframe containing the requested event data as columns or None on failure
        :rtype: Optional[pd.DataFrame]

        **Purpose:** Load and return the data specified by a valid SQL query, or None on failure

        The data should be formatted as a pandas Dataframe object
        """
        pass

    @abstractmethod
    def _load_metadata_generator(
        self, query: str
    ) -> Generator[pd.DataFrame, None, None]:
        """
        :param query: query to  run on the database
        :type query: str

        :return: A generator that feeds out onne row at a time in the form of a single-line dataframe
        :rtype: Generator[pd.DataFrame, None, None]

        **Purpose:** Load and yield the data specified by a valid SQL query one row at a time. Useful in cases where :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata` returns too much data for memory.

        Data should be formatted as a pandas dataframe in line with :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata`. Make sure you exhaust the generator when done with it, or else database connections will remain open.
        """
        pass

    @abstractmethod
    def _load_event_data(self, query: str) -> Generator[Dict[str, Any], bool, None]:
        """
        Load data and return a generator that gives a one-row dataframe corresponding one row returned by query
        Make sure you exhaust the generator, or else connections will remain open
        You can assume that the query was generated by self.construct_event_data_query() and will have 5 colums:
        event_id, channel_id, experiment_id, data_format, data, baseline, stdev, padding_before, padding_after, data
        where data is a bytes object to be interpreted using data_format

        :param query: a valid SQL query, checked in the calling function for validity
        :type query: str

        :return: a generator that returns a dict with id, event_id, channel_id, experiment_id, samplerate, padding_before, padding_after, and numpy array with event data for raw, filtered, and fitted data
        :rtype: Generator[Dict[str, Any], bool, None]
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
    def _finalize_initialization(self):
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
