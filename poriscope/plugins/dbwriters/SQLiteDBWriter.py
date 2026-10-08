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

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, override

import numpy as np
import numpy.typing as npt

from poriscope.constants import __VERSION__
from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaEventFitter import MetaEventFitter


@inherit_docstrings
class SQLiteDBWriter(MetaDatabaseWriter):
    """
    Abstract base class for database writer that will store metadata and data from fitted events for postprocessing later
    """

    logger = logging.getLogger(__name__)
    #: The schema version stamped, as ``PRAGMA user_version``, on a file this writer
    #: creates. SQLiteDBLoader reads up to its own ``SCHEMA_VERSION`` and refuses
    #: anything newer, so the two move together.
    SCHEMA_VERSION = 1
    conn: Optional[sqlite3.Connection]
    cursor: Optional[sqlite3.Cursor]

    # public API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Permanently delete the given channel's row (and, via cascading foreign keys,
        its events/sublevels/data rows) from the database, so a subsequent write starts
        from a clean slate. This is destructive, not a resource-cleanup step.

        :param channel: channel ID. Note that `channel=None` does not reset all
            channels; SQL `channel_id = NULL` never matches, so no rows are deleted.
        :type channel: Optional[int]
        :raises RuntimeError: if the configured experiment cannot be found in the database
        :raises sqlite3.Error: if the delete fails, so that the caller cannot treat an
            unreset channel as a clean slate
        """
        conn = None
        cursor = None
        experiment_id = None
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("SAVEPOINT reset_channel")
            experiment_name = self.settings["Experiment Name"]["Value"]
            cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )
            experiment_id = cursor.fetchone()
            if not experiment_id:
                raise RuntimeError(
                    f"Experiment '{experiment_name}' not found, unable to reset channel."
                )
            experiment_id = experiment_id[0]

            cursor.execute(
                "DELETE FROM channels WHERE experiment_id = ? AND channel_id = ?",
                (experiment_id, channel),
            )

            self.logger.info(
                f"Deleted (experiment_id={experiment_id}, channel_id={channel}) from channels."
            )

        except sqlite3.Error as e:
            if conn:
                conn.execute("ROLLBACK TO SAVEPOINT reset_channel")
                conn.rollback()
            # Raised rather than swallowed, and at ERROR rather than WARNING. This
            # is a destructive operation the caller relies on having happened -
            # MetaDatabaseWriter.write_events follows an abort with
            # `self.written[channel] = 0`, which claims a clean slate - so
            # returning normally after a failed delete left the writer's
            # bookkeeping disagreeing with the database, and at WARNING the user
            # was never told, since QtHandler floors at ERROR. The abort path that
            # calls this guards against the raise so it cannot mask an in-flight
            # error.
            self.logger.error(
                f"Failed to delete (experiment_id={experiment_id}, channel_id={channel}): {e}, channel not reset"
            )
            raise
        else:
            conn.execute("RELEASE SAVEPOINT reset_channel")
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Commit and close the shared database connection/cursor, if open.

        :param channel: unused; this writer shares a single connection across all
            channels, so there is no per-channel resource to close independently.
        :type channel: Optional[int]
        """
        if self.cursor:
            # Guarded like the commit below, and for the same reason: closing a
            # cursor whose connection has already gone raises, and this method is
            # called inline just before the errors its callers actually want
            # reported. SQLiteEventWriter.close_resources already guarded this.
            try:
                self.cursor.close()
            except Exception:
                self.logger.info(
                    f"Failed to close cursor cleanly for channel {channel}"
                )
            self.cursor = None
        if self.conn:
            self.logger.debug("Closing database connection.")
            try:
                self.conn.commit()  # Ensure all writes are committed
                self.conn.close()  # Close the connection to release the lock
            except Exception:
                # Reported at ERROR rather than raised, matching
                # SQLiteEventWriter.close_resources. For a batch that ends via
                # write_events' `finally` this is the only commit, so a failure
                # here means the batch was not saved and the user has to be told;
                # QtHandler floors at ERROR, so this is what surfaces it.
                #
                # It must not raise: several callers invoke close_resources inline
                # immediately before raising the error they actually want reported
                # (the early-exit arms of MetaDatabaseWriter.write_events), and an
                # unguarded commit here replaced those errors rather than adding to
                # them - measured, a failing commit surfaced as sqlite3's
                # ProgrammingError in place of the ValueError explaining that
                # eventfitting had not completed.
                self.logger.error(
                    f"Failed to commit and close the database for channel {channel}; "
                    "events written in this batch may not have been saved.",
                    exc_info=True,
                )
            self.conn = None
        else:
            self.logger.debug("Database connection not open to close.")

    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Declare the settings this database writer exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to build
        the settings dialog and to sanity-check whatever the user enters; the accepted
        values are then readable through ``self.settings``. See
        :py:meth:`~poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter.get_empty_settings`
        for the structure of the dict and what ``Type``, ``Value``, ``Min``, ``Max``, ``Options`` and
        ``Units`` mean in it, and for the reserved keys the GUI builds file pickers
        from.

        The ``super()`` call supplies the mandatory ``"MetaEventFitter"`` key, which is how
        this plugin is wired to its data source.

        The keys this plugin adds:

        - ``Output File`` - the SQLite database to write fitted events and their
          sublevels into.
        - ``Experiment Name`` - the label these events are filed under, so one database
          can hold several runs.
        - ``Voltage`` (mV) - the applied bias, stored with the experiment.
        - ``Membrane Thickness`` (nm) and ``Conductivity`` (S/m) - stored with the
          experiment so that downstream analysis can convert blockage depths into pore
          and molecule geometry.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaEventFitter" as a key, with explicitly set Type MetaEventFitter.
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Output File"]["Options"] = [
            "SQLite3 Files (*.sqlite3)",
            "Database Files (*.db)",
            "SQLite Files (*.sqlite)",
        ]
        settings["Experiment Name"] = {"Type": str}
        settings["Voltage"] = {"Type": float, "Units": "mV"}
        settings["Membrane Thickness"] = {"Type": float, "Units": "nm", "Min": 0}
        settings["Conductivity"] = {"Type": float, "Units": "S/m", "Min": 0}
        return settings

    # Public API continued, should implemented by subclasses, but has default behavior if it is not needed

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        All data plugins have this function and must provide an implementation. This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        self.conn = None
        self.cursor = None

    @log(logger=logger)
    @override
    def _write_event(
        self,
        channel: int,
        event_metadata: Dict[str, Union[int, float, str, bool]],
        sublevel_metadata: Dict[str, List[Union[int, float, str, bool]]],
        event_data: npt.NDArray[np.float64],
        raw_data: npt.NDArray[np.float64],
        fit_data: npt.NDArray[np.float64],
        abort: Optional[bool] = False,
        last_call: Optional[bool] = False,
    ) -> bool:
        """
        Write a single event worth of data and metadata to the database. Do NOT commit.

        :param channel: identifier for the channel to write events from
        :type channel: int
        :param event_metadata: a dict of metadata associated to the event
        :type event_metadata: Dict[str, Union[int, float, str, bool]]
        :param sublevel_metadata: a dict of lists of metadata associated to sublevels within the event. You can assume they all have the same length.
        :type sublevel_metadata: Dict[str, List[Union[int, float, str, bool]]]
        :param event_data: the filtered data for the event
        :type event_data: npt.NDArray[np.float64]
        :param raw_data: A numpy array of raw event data to be stored as binary in the database.
        :type raw_data: npt.NDArray[np.float64]
        :param fit_data: A numpy array of fitted event data to be stored as binary in the database.
        :type fit_data: npt.NDArray[np.float64]
        :param abort: True if an abort request was issued in the caller, perform cleanup as needed
        :type abort: Optional[bool]
        :param last_call: True if this is the last time the function will be called, commit to file and clean up as needed
        :type last_call: Optional[bool]

        :return: True on successful write, False if the row already existed
            (rejected by ``INSERT OR IGNORE``). Any other failure (a genuine
            database error) is raised rather than returned, so the caller can
            report the real reason instead of assuming a duplicate row.
        :rtype: bool
        :raises ValueError: if a database connection cannot be opened
        :raises RuntimeError: if the experiment or channel cannot be found in the database, or if the event insert reports success without producing a row id
        :raises sqlite3.Error: if a database operation fails
        :raises Exception: if an unexpected error occurs while writing the event
        """
        if abort is True:
            # Discarding the channel's whole uncommitted batch is intended here:
            # MetaDatabaseWriter follows an abort with reset_channel() and sets
            # written = 0, so the caller already treats the run as void. Only the
            # per-event savepoint is not rolled back to, because on this path no
            # event is in progress.
            if self.conn:
                self.conn.rollback()
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.conn:
                self.conn.close()
                self.conn = None
            return False
        # Tracks whether this call has an open savepoint to roll back to, so a
        # failure raised before the SAVEPOINT below (connecting, say) does not try
        # to roll back to a savepoint that was never taken.
        savepoint_active = False
        try:
            success = False
            if self.conn is None:
                self.conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
                self.conn.execute("PRAGMA foreign_keys = ON;")
                self.cursor = self.conn.cursor()
            if self.conn is None or self.cursor is None:
                raise ValueError("Unable to open database connection in _write_event")
            # One savepoint per event, not one per batch. Taken per call so that a
            # failure rolls back only the event that failed; the batch stays in a
            # single transaction and still commits once, at last_call. The previous
            # form took this savepoint only when the connection was first opened,
            # so rolling back to it discarded every event written since - and the
            # conn.rollback() that followed destroyed the savepoint outright, so
            # the next failure raised "no such savepoint" from inside the handler
            # and masked the real error.
            self.conn.execute("SAVEPOINT write_event")
            savepoint_active = True
            # Get the experiment ID based on the experiment name
            experiment_name = self.settings["Experiment Name"]["Value"]
            self.cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )

            experiment_id = self.cursor.fetchone()
            if not experiment_id:
                raise RuntimeError(f"Experiment '{experiment_name}' not found.")
            experiment_id = experiment_id[0]

            self.cursor.execute(
                "SELECT id FROM channels WHERE experiment_id = ? AND channel_id = ?;",
                (experiment_id, channel),
            )
            channel_db_id = self.cursor.fetchone()
            if not channel_db_id:
                raise RuntimeError(
                    f"Channel {channel} for experiment {experiment_name} not found."
                )
            channel_db_id = channel_db_id[0]  # Extract the actual ID

            success = self._insert_event(
                self.cursor, event_metadata, experiment_id, channel_db_id
            )
            event_db_id = self.cursor.lastrowid

            if success:
                if event_db_id is None:
                    raise RuntimeError(
                        f"Event insert for experiment '{experiment_name}' reported "
                        "success but produced no row id."
                    )
                self._insert_sublevels(
                    self.cursor,
                    sublevel_metadata,
                    experiment_id,
                    channel_db_id,
                    event_db_id,
                )
                self._insert_event_data(
                    self.cursor,
                    event_metadata,
                    event_data,
                    raw_data,
                    fit_data,
                    experiment_id,
                    channel_db_id,
                    event_db_id,
                )

        except sqlite3.Error as e:
            # Undo only this event. Deliberately no conn.rollback() here - the
            # caller files this as a per-event rejection and carries on to the next
            # event, so the events already written in this batch must survive.
            if self.conn and savepoint_active:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.execute("RELEASE SAVEPOINT write_event")
            self.logger.error(f"Failed to write event: {e}")
            raise
        except Exception as e:  # Fallback for truly unexpected errors
            if self.conn and savepoint_active:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.execute("RELEASE SAVEPOINT write_event")
            self.logger.critical(f"Unexpected error writing event: {e}", exc_info=True)
            raise
        else:
            if self.conn and savepoint_active:
                if success:
                    self.conn.execute("RELEASE SAVEPOINT write_event")
                else:
                    # The event is already stored, so nothing was inserted; the
                    # savepoint is closed without keeping anything.
                    self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                    self.conn.execute("RELEASE SAVEPOINT write_event")
            if self.conn and last_call is True:
                self.conn.commit()
        finally:
            if self.cursor and last_call is True:
                self.cursor.close()
                self.cursor = None
            if self.conn and last_call is True:
                self.conn.close()
                self.conn = None
        return success

    @log(logger=logger)
    @override
    def _write_experiment_metadata(self, channel: Optional[int] = None) -> None:
        """
        Write any information you need to save about the experiment itself

        :param channel: int indicating which output to flush
        :type channel: Optional[int]
        :raises sqlite3.Error: if a database operation fails
        """
        conn = None
        cursor = None
        experiment_name = self.settings["Experiment Name"]["Value"]
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )
            existing_experiment = cursor.fetchone()

            if not existing_experiment:
                voltage = self.settings["Voltage"]["Value"]
                thickness = self.settings["Membrane Thickness"]["Value"]
                conductivity = self.settings["Conductivity"]["Value"]
                cursor.execute(
                    "INSERT INTO experiments (name, voltage, thickness, conductivity) VALUES (?, ?, ?, ?);",
                    (experiment_name, voltage, thickness, conductivity),
                )
            else:
                self.logger.info(f"Experiment already exists: {experiment_name}")
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.warning(
                f"Failed to write experiment metadata (experiment_name={experiment_name}): {e}"
            )
            raise
        else:
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def _write_channel_metadata(self, channel: int) -> None:
        """
        Write any information you need to save about the channel

        :param channel: int indicating which output to flush
        :type channel: int
        :raises RuntimeError: if the configured experiment cannot be found in the database
        :raises sqlite3.Error: if a database operation fails
        """
        conn = None
        cursor = None
        experiment_id = None
        experiment_name = self.settings["Experiment Name"]["Value"]
        samplerate = self.eventfitter.get_samplerate(channel)
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )
            experiment_id = cursor.fetchone()

            if not experiment_id:
                raise RuntimeError(
                    f"Unable to find an appropriate experiment names {experiment_name} while preparing to write to channel {channel}"
                )
            experiment_id = experiment_id[0]

            # Directly attempt to insert the channel
            cursor.execute(
                """INSERT OR IGNORE INTO channels (experiment_id, channel_id, samplerate, provenance) VALUES (?, ?, ?, ?);""",
                (
                    experiment_id,
                    channel,
                    samplerate,
                    self._provenance_json(),
                ),
            )
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.warning(
                f"Failed to write channel metadata (experiment_id={experiment_id}, channel_id={channel}): {e}"
            )
            raise
        else:
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Refuse an existing output file that is not a fitted-metadata database.

        A new or empty file is created as one, and an existing metadata database is
        appended to. Anything else is refused here, when the plugin is configured,
        rather than failing on every channel once writing starts - an events database
        from the Raw Data tab in particular, which also has an ``events`` table.

        A metadata database holds results from one type of fitter, from any number of runs,
        so one holding another type's is refused here too; see :meth:`_other_fitter_reason`.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the output file exists and is not an SQLite database, is
            one without the fitted-metadata tables, or holds another fitter's results.
        """
        value = settings.get("Output File", {}).get("Value")
        if not value:
            return
        output_file = Path(value)
        if not output_file.is_file() or output_file.stat().st_size == 0:
            return
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(
                f"{output_file.resolve().as_uri()}?mode=ro", uri=True
            )
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            fitter = settings.get("MetaEventFitter", {}).get("Value")
            other_fitter = (
                self._other_fitter_reason(cursor, fitter)
                if isinstance(fitter, MetaEventFitter)
                and {"channels", "columns"} <= tables
                else None
            )
        except sqlite3.DatabaseError as e:
            raise ValueError(
                f"{output_file} is not an SQLite database, so it cannot hold fitted "
                f"metadata ({e}). Choose a metadata database or a new file."
            ) from e
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()
        if tables and not {"experiments", "sublevels"} <= tables:
            kind = (
                "an events database, as the Raw Data tab writes"
                if {"channels", "events"} <= tables
                else "an SQLite database of some other kind"
            )
            raise ValueError(
                f"{output_file} is {kind}, not a fitted-metadata database. Choose a "
                "metadata database or a new file."
            )
        if other_fitter is not None:
            raise ValueError(
                f"{output_file} {other_fitter}. A database holds results from one type of "
                "fitter, from any number of runs; write this one to a new file."
            )

    @log(logger=logger)
    @override
    def _initialize_database(self, channel: Optional[int] = None) -> None:
        """
        Do whatever you need to do to initialize the database file for a given channel before writing the first event

        :param channel: int indicating which output to flush
        :type channel: Optional[int]
        :raises ValueError: if event or sublevel metadata declares an unsupported datatype
        :raises RuntimeError: if database initialization fails at the SQL level
        :raises sqlite3.Error: if a database operation fails
        :raises Exception: if an unexpected error occurs during initialization
        """

        table_creation_queries = [
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                voltage REAL NOT NULL,
                thickness REAL NOT NULL,
                conductivity REAL NOT NULL
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_experiment_name ON experiments(name);
            """,
            # Two channel columns, and they are not the same thing. channel_id is the
            # physical channel the data came from. channel_db_id, in events, sublevels
            # and data, is channels.id - the AUTOINCREMENT row of one (experiment_id,
            # channel_id) pair. Writing a dataset under a new experiment name adds a
            # channels row, so channel_db_id moves while channel_id stays put; that is
            # not a relabelling. UNIQUE (experiment_id, channel_id, event_id) on events
            # is the rule against duplicates, and event_id restarts at 0 per fitting
            # run. Renaming either column would be a schema migration.
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                samplerate REAL NOT NULL,
                UNIQUE (experiment_id, channel_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_channels_experiment_channel ON channels(experiment_id, channel_id);
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                start_time REAL NOT NULL,
                num_sublevels INTEGER NOT NULL,
                UNIQUE (experiment_id, channel_id, event_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sublevels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_db_id INTEGER NOT NULL,
                event_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                level_id INTEGER NOT NULL,
                levels_left INTEGER NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (event_db_id) REFERENCES events(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_db_id INTEGER NOT NULL,
                event_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                data_format TEXT NOT NULL,
                filtered_data BLOB NOT NULL,
                raw_data BLOB NOT NULL,
                fit_data BLOB NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (event_db_id) REFERENCES events(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                table_name TEXT NOT NULL,
                units TEXT
            );
            """,
            # Dropped and recreated rather than CREATE IF NOT EXISTS: earlier
            # versions installed unscoped forms of both triggers, and IF NOT EXISTS
            # is a no-op against a database that already carries one, so every
            # existing file would keep the unscoped version. _initialize_database
            # runs against existing databases too, so this migrates them in place.
            """
            DROP TRIGGER IF EXISTS delete_childless_experiments;
            """,
            # Scoped to OLD.experiment_id. The unscoped form this replaces deleted
            # every childless experiment in the file on any channel deletion, so
            # removing one channel from one experiment could cascade away unrelated
            # experiments that happened to have no channels of their own.
            """
            CREATE TRIGGER delete_childless_experiments
            AFTER DELETE ON channels
            BEGIN
                DELETE FROM experiments
                WHERE id = OLD.experiment_id
                  AND NOT EXISTS (
                      SELECT 1 FROM channels WHERE experiment_id = OLD.experiment_id
                  );
            END;
            """,
            """
            DROP TRIGGER IF EXISTS delete_childless_channels;
            """,
            # Scoped to OLD.channel_db_id, for the same reason: deleting one
            # channel's events used to sweep every childless channel in the file,
            # which then fired the trigger above and took their experiments with
            # them.
            """
            CREATE TRIGGER delete_childless_channels
            AFTER DELETE ON events
            BEGIN
                DELETE FROM channels
                WHERE id = OLD.channel_db_id
                  AND NOT EXISTS (
                      SELECT 1 FROM events WHERE channel_db_id = OLD.channel_db_id
                  );
            END;
            """,
            """
            CREATE TABLE IF NOT EXISTS event_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE (experiment_id, channel_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_event_counts_exp_channel ON event_counts(experiment_id, channel_id);
            """,
            """
            CREATE TRIGGER IF NOT EXISTS increment_event_counts
            AFTER INSERT ON events
            BEGIN
                INSERT INTO event_counts (experiment_id, channel_id, event_count)
                VALUES (NEW.experiment_id, NEW.channel_id, 1)
                ON CONFLICT(experiment_id, channel_id)
                DO UPDATE SET event_count = event_count + 1;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS decrement_event_counts
            AFTER DELETE ON events
            BEGIN
                UPDATE event_counts
                SET event_count = event_count - 1
                WHERE experiment_id = OLD.experiment_id AND channel_id = OLD.channel_id;
            END;
            """,
            # The foreign keys the event-data query, an events-to-sublevels join and the
            # cascade from deleting a channel all search on; without them each is a
            # nested scan. SQLiteDBLoader adds the same three, by the same names, to
            # any file it opens that lacks them.
            """
            CREATE INDEX IF NOT EXISTS idx_data_event_db_id ON data(event_db_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sublevels_event_db_id ON sublevels(event_db_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_events_channel_db_id ON events(channel_db_id);
            """,
        ]

        # Connect to the SQLite database (creates the file if it doesn't exist)
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")  # Start a transaction
            # The schema version is stamped only by the transaction that creates the
            # schema, and rolls back with it, so a file reads it exactly when this
            # version created it; an older file this writer appends to keeps its own.
            creating = (
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'experiments';"
                ).fetchone()
                is None
            )
            # Create tables if they do not exist
            for query in table_creation_queries:
                cursor.execute(query)
            if creating:
                cursor.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")

            event_metadata = self.eventfitter.get_event_metadata_types()
            sublevel_metadata = self.eventfitter.get_sublevel_metadata_types()
            event_metadata_units = self.eventfitter.get_event_metadata_units()
            sublevel_metadata_units = self.eventfitter.get_sublevel_metadata_units()
            pytype_to_sql_type = {
                int: "INTEGER",
                float: "REAL",
                str: "TEXT",
                bool: "INTEGER",
            }

            # Insert new column definitions into the columns table
            for name, units in event_metadata_units.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, "events", units),
                )
            for name, units in sublevel_metadata_units.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, "sublevels", units),
                )
            # Attached to every sublevel by MetaEventFitter rather than declared by the
            # fitter, so registered here, or no query could name them.
            for name in ("level_id", "levels_left"):
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, NULL);",
                    (name, "sublevels"),
                )

            base_settings = self.get_empty_settings()
            experimental_metadata = {
                "voltage": base_settings["Voltage"]["Units"],
                "thickness": base_settings["Membrane Thickness"]["Units"],
                "conductivity": base_settings["Conductivity"]["Units"],
            }

            for name, units in experimental_metadata.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, "experiments", units),
                )

            # Alter events table
            for column_name, column_type in event_metadata.items():
                if column_type not in [int, float, str, bool]:
                    raise ValueError(
                        f"SQLite3 only supports int, float, str, bool datatypes for event metadata, but you sent {column_name} with type {column_type}"
                    )
                if not self._column_exists(cursor, "events", column_name):
                    cursor.execute(
                        f"ALTER TABLE events ADD COLUMN {column_name} {pytype_to_sql_type[column_type]};"
                    )

            # Alter sublevels table
            for column_name, column_type in sublevel_metadata.items():
                if column_type not in [int, float, str, bool]:
                    raise ValueError(
                        f"SQLite3 only supports int, float, str, bool datatypes for sublevel metadata, but you sent {column_name} with type {column_type}"
                    )
                if not self._column_exists(cursor, "sublevels", column_name):
                    cursor.execute(
                        f"ALTER TABLE sublevels ADD COLUMN {column_name} {pytype_to_sql_type[column_type]};"
                    )

            # A file created before 2.1 has no provenance column; it gains one here, and
            # its existing channels read NULL.
            if not self._column_exists(cursor, "channels", "provenance"):
                cursor.execute("ALTER TABLE channels ADD COLUMN provenance TEXT;")

        except (sqlite3.Error, RuntimeError, ValueError) as e:
            if conn is not None:
                conn.rollback()  # Rollback all changes if any operation fails
            self.logger.error(f"Failed to initialize database: {e}")
            raise
        except Exception as e:  # Fallback for truly unexpected errors
            if conn is not None:
                conn.rollback()
            self.logger.critical(f"Unexpected error: {e}", exc_info=True)
            raise
        else:
            if conn is not None:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed

    @log(logger=logger)
    def _insert_event(
        self,
        cursor: sqlite3.Cursor,
        event_metadata: Dict[str, Union[int, float, str, bool]],
        experiment_id: int,
        channel_db_id: int,
    ) -> bool:
        """
        Insert event metadata into the 'events' table.

        A plain INSERT, not INSERT OR IGNORE: OR IGNORE also swallows a NOT NULL
        violation, which then read as a duplicate. Only a UNIQUE violation - the event
        is already stored - returns False; any other refusal raises, naming the column.

        :param cursor: The SQLite cursor to execute the query.
        :type cursor: sqlite3.Cursor
        :param event_metadata: A dictionary of metadata associated with the event.
        :type event_metadata: Dict[str, Union[int, float, str, bool]]
        :param experiment_id: The ID of the experiment for which the event is being logged.
        :type experiment_id: int
        :param channel_db_id: The database ID of the channel to associate with the event.
        :type channel_db_id: int

        :return: True if the event was inserted, False if it is already stored
        :rtype: bool
        :raises sqlite3.IntegrityError: if the schema refuses the row for any other reason
        """
        columns = ", ".join(event_metadata.keys()) + ", experiment_id, channel_db_id"
        values = ", ".join("? " for _ in event_metadata) + ", ?, ?"
        try:
            cursor.execute(
                f"INSERT INTO events ({columns}) VALUES ({values});",
                (*event_metadata.values(), experiment_id, channel_db_id),
            )
        except sqlite3.IntegrityError as e:
            if e.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
                return False
            raise
        return True

    @log(logger=logger)
    def _insert_sublevels(
        self,
        cursor: sqlite3.Cursor,
        sublevel_metadata: Dict[str, List[Union[int, float, str, bool]]],
        experiment_id: int,
        channel_db_id: int,
        event_db_id: int,
    ) -> None:
        """
        Insert sublevel metadata into the 'sublevels' table.

        A plain INSERT: the table has no UNIQUE constraint, so a refused row can only be
        one the schema rejects, and the error that says which column is what the user
        should see.

        :param cursor: The SQLite cursor to execute the query.
        :type cursor: sqlite3.Cursor
        :param sublevel_metadata: A dictionary of sublevel metadata, where each key corresponds to a list of values.
        :type sublevel_metadata: Dict[str, List[Union[int, float, str, bool]]]
        :param experiment_id: The ID of the experiment for which the sublevels are being logged.
        :type experiment_id: int
        :param channel_db_id: The database ID of the channel to associate with the sublevels.
        :type channel_db_id: int
        :param event_db_id: The database ID of the event to associate with the sublevels.
        :type event_db_id: int

        """

        def convert_value(value: Any) -> Any:  # helper function
            if isinstance(value, np.int64):  # Convert numpy int64 to native Python int
                return int(value)
            elif isinstance(
                value, np.float64
            ):  # Convert numpy float64 to native Python float
                return float(value)
            return value  # Leave other types as they are

        columns = (
            ", ".join(sublevel_metadata.keys())
            + ", experiment_id, channel_db_id, event_db_id"
        )
        values = ", ".join("?" for _ in sublevel_metadata) + ", ?, ?, ?"
        # Every list in sublevel_metadata is the same length by the time it reaches
        # here: MetaEventFitter.fit_events rejects any event whose metadata lists
        # disagree with its sublevel count. strict=True asserts that invariant at the
        # point of use, so a hand-built dict from a test or a future fitter fails
        # loudly instead of silently transposing into fewer rows than the event has.
        rows = zip(
            *(map(convert_value, sublevel_metadata[key]) for key in sublevel_metadata),
            strict=True,
        )
        cursor.executemany(
            f"INSERT INTO sublevels ({columns}) VALUES ({values});",
            [(*row, experiment_id, channel_db_id, event_db_id) for row in rows],
        )

    @log(logger=logger)
    def _insert_event_data(
        self,
        cursor: sqlite3.Cursor,
        event_metadata: Dict[str, Union[int, float, str, bool]],
        event_data: npt.NDArray[np.float64],
        raw_data: npt.NDArray[np.float64],
        fit_data: npt.NDArray[np.float64],
        experiment_id: int,
        channel_db_id: int,
        event_db_id: int,
    ) -> None:
        """
        Insert the event data into the 'data' table after converting it to the appropriate binary format.

        A plain INSERT: the table has no UNIQUE constraint, so a refused row is one the
        schema rejects, and its error names the column.

        :param cursor: The SQLite cursor to execute the query.
        :type cursor: sqlite3.Cursor
        :param event_metadata: A dictionary of metadata associated with the event.
        :type event_metadata: Dict[str, Union[int, float, str, bool]]
        :param event_data: A numpy array of filtered event data to be stored as binary in the database.
        :type event_data: npt.NDArray[np.float64]
        :param raw_data: A numpy array of raw event data to be stored as binary in the database.
        :type raw_data: npt.NDArray[np.float64]
        :param fit_data: A numpy array of fitted event data to be stored as binary in the database.
        :type fit_data: npt.NDArray[np.float64]
        :param experiment_id: The ID of the experiment to which the data belongs.
        :type experiment_id: int
        :param channel_db_id: The database ID of the channel to associate with the event data.
        :type channel_db_id: int
        :param event_db_id: The database ID of the event this data belongs to.
        :type event_db_id: int

        :raises ValueError: if event_data is not a numpy array of dtype np.float64
        """
        if not isinstance(event_data, np.ndarray) or event_data.dtype != np.float64:
            raise ValueError("event_data must be a numpy array of dtype np.float64")

        filtered_data_blob = event_data.astype("<f8").tobytes()
        raw_data_blob = raw_data.astype("<f8").tobytes()
        fit_data_blob = fit_data.astype("<f8").tobytes()
        data_format = "<f8"
        cursor.execute(
            """INSERT INTO data (experiment_id, channel_id, channel_db_id, event_id, event_db_id, data_format, filtered_data, raw_data, fit_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                experiment_id,
                event_metadata["channel_id"],
                channel_db_id,
                event_metadata["event_id"],
                event_db_id,
                data_format,
                filtered_data_blob,
                raw_data_blob,
                fit_data_blob,
            ),
        )

    @log(logger=logger)
    def _other_fitter_reason(
        self, cursor: sqlite3.Cursor, fitter: MetaEventFitter
    ) -> Optional[str]:
        """
        Say why a metadata database holds another fitter's results, or None if it does not.

        A file written by 2.1 records each channel's fitter in ``channels.provenance``,
        and any recorded class other than this fitter's is another fitter. A file from
        before 2.1 records none, so it is judged by its columns: every column this fitter
        declares must already be registered, on the table it declares it for. Columns the
        file has beyond those - an analysis tab's cluster labels, say - are not counted
        against it, so a fitter whose columns are a subset of another's is not told apart.

        :param cursor: a read-only cursor on the existing database
        :type cursor: sqlite3.Cursor
        :param fitter: the fitter this writer would write from
        :type fitter: MetaEventFitter
        :return: the reason, worded to follow the file's name, or None
        :rtype: Optional[str]
        """
        fitter_class = type(fitter).__name__
        channel_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(channels);")
        }
        if "provenance" in channel_columns:
            recorded = set()
            for (text,) in cursor.execute(
                "SELECT provenance FROM channels WHERE provenance IS NOT NULL;"
            ):
                try:
                    recorded.add(json.loads(text)["fitter"]["class"])
                except (ValueError, KeyError, TypeError):
                    continue
            others = recorded - {fitter_class}
            if others:
                return (
                    f"holds results from {', '.join(sorted(others))}, not from "
                    f"{fitter_class}"
                )
            if recorded:
                return None
        registered = dict(
            cursor.execute(
                "SELECT name, table_name FROM columns "
                "WHERE table_name IN ('events', 'sublevels');"
            ).fetchall()
        )
        if not registered:
            return None
        declared = [(name, "events") for name in fitter.get_event_metadata_units()] + [
            (name, "sublevels") for name in fitter.get_sublevel_metadata_units()
        ]
        misplaced = [
            f"{name} is a {registered[name]} column here, where {fitter_class} writes it to {table}"
            for name, table in declared
            if name in registered and registered[name] != table
        ]
        missing = [name for name, _table in declared if name not in registered]
        if not misplaced and not missing:
            return None
        details = misplaced + (
            [f"it has no {', '.join(missing)} column(s), which {fitter_class} writes"]
            if missing
            else []
        )
        return f"holds another fitter's results: {'; '.join(details)}"

    @log(logger=logger)
    def _provenance_json(self) -> str:
        """
        Describe, as JSON, the plugins that produced the events this writer is writing.

        Stored in ``channels.provenance`` with the channel's row: this writer, its event
        fitter and the fitter's event loader, each by class, key and setting values,
        with the Poriscope version and the time of the write in UTC.

        :return: the provenance record as a JSON object
        :rtype: str
        """
        record: Dict[str, Any] = {
            "poriscope_version": __VERSION__,
            "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "writer": self._describe_plugin(self),
            "fitter": self._describe_plugin(self.eventfitter),
            "event_loader": (
                self._describe_plugin(self.eventfitter.eventloader)
                if self.eventfitter.eventloader is not None
                else None
            ),
        }
        # Applied settings hold a plugin they refer to by its key, so every value is
        # already JSON; str() is the fallback for a type no plugin uses today, so that a
        # setting this record did not foresee never stops a write.
        return json.dumps(record, default=str)

    @log(logger=logger)
    def _describe_plugin(self, plugin: BaseDataPlugin) -> Dict[str, Any]:
        """
        Name a plugin and the values of its settings, for the provenance record.

        :param plugin: the plugin to describe
        :type plugin: BaseDataPlugin
        :return: its class, key and setting values
        :rtype: Dict[str, Any]
        """
        return {
            "class": type(plugin).__name__,
            "key": plugin.get_key(),
            "settings": {
                name: setting.get("Value")
                for name, setting in plugin.get_raw_settings().items()
            },
        }

    @log(logger=logger)
    def _column_exists(
        self, cursor: sqlite3.Cursor, table_name: str, column_name: str
    ) -> bool:
        """
        Check whether a given column exists in the specified database table.

        :param cursor: SQLite database cursor used to execute the query.
        :type cursor: sqlite3.Cursor
        :param table_name: Name of the table to inspect.
        :type table_name: str
        :param column_name: Name of the column to check for existence.
        :type column_name: str
        :return: True if the column exists, False otherwise.
        :rtype: bool
        """
        cursor.execute(f"PRAGMA table_info({table_name});")
        existing_columns = [
            row[1] for row in cursor.fetchall()
        ]  # Column names are in the second position
        return column_name in existing_columns
