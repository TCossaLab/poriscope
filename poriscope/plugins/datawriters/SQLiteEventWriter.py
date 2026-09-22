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

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, override

import numpy as np
import numpy.typing as npt

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaWriter import MetaWriter


@inherit_docstrings
class SQLiteEventWriter(MetaWriter):
    """
    Save events into a single file with baseline between them discarded
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    @override
    def _finalize_initialization(self) -> None:
        """
        Apply the provided paramters and intialize any internal structures needed
        Should Raise if initialization fails.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        self.eventfinder = self.settings["MetaEventFinder"]["Value"]
        self.samplerate = self.eventfinder.get_samplerate()
        self.channel_db_id: Dict[int, Any] = {}

    @log(logger=logger)
    @override
    def _initialize_database(self, channel: int) -> None:
        """
        Open a database or file handle for writing events - this function will be called from every channel in the reader

        :param channel: the channel for which to initialize the database
        :type channel: int
        :raises ValueError: if the output file path is not set in settings
        :raises RuntimeError: if database initialization fails at the SQL level
        :raises sqlite3.Error: if a database operation fails
        :raises Exception: if an unexpected error occurs during initialization
        """
        table_creation_queries = [
            # channel_id is the physical channel the events came from; channel_db_id in
            # events is channels.id, this file's row for that channel. They are
            # different columns, and renaming either would be a schema migration.
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                voltage REAL NOT NULL,
                thickness REAL NOT NULL,
                conductivity REAL NOT NULL,
                samplerate REAL NOT NULL,
                data_format TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                absolute_start INTEGER NOT NULL,
                padding_before INTEGER NOT NULL,
                padding_after INTEGER NOT NULL,
                baseline_mean REAL NOT NULL,
                baseline_std REAL NOT NULL,
                raw_data BLOB NOT NULL,
                UNIQUE (channel_id, event_id),
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE
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
            # versions installed an unscoped form, and IF NOT EXISTS is a no-op
            # against a database that already carries one, so every existing file
            # would keep it. _initialize_database runs against existing databases
            # too, so this migrates them in place.
            """
            DROP TRIGGER IF EXISTS delete_childless_channels;
            """,
            # Scoped to OLD.channel_db_id. The unscoped form this replaces deleted
            # every childless channel in the file on any event deletion, so
            # resetting one channel could remove channels belonging to unrelated
            # runs that happened to hold no events.
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
        ]

        conn = None
        cursor = None
        try:
            if (
                not self.settings
                or "Output File" not in self.settings
                or self.settings["Output File"].get("Value") is None
            ):
                raise ValueError("Output file path not set in settings.")

            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")  # Start a transaction
            # Create tables if they do not exist
            for query in table_creation_queries:
                cursor.execute(query)

            base_settings = self.get_empty_settings()
            metadata = {
                "voltage": (base_settings["Voltage"]["Units"], "channels"),
                "thickness": (base_settings["Membrane Thickness"]["Units"], "channels"),
                "conductivity": (base_settings["Conductivity"]["Units"], "channels"),
                "samplerate": ("Hz", "channels"),
                "absolute_start": ("Index", "events"),
                "padding_before": ("Index", "events"),
                "padding_after": ("Index", "events"),
                "baseline_mean": ("pA", "events"),
                "baseline_std": ("pA", "events"),
                "raw_data": ("pA", "events"),
            }
            for name, (units, table) in metadata.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, table, units),
                )

        except (sqlite3.Error, RuntimeError, ValueError) as e:
            if conn:
                conn.rollback()  # Rollback all changes if any operation fails
            self.logger.error(f"Failed to initialize database: {e}")
            raise
        except Exception as e:  # Fallback for truly unexpected errors
            if conn:
                conn.rollback()
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            raise
        else:
            if conn:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Declare the settings this event writer exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to build
        the settings dialog and to sanity-check whatever the user enters; the accepted
        values are then readable through ``self.settings``. See
        :py:meth:`~poriscope.utils.MetaWriter.MetaWriter.get_empty_settings`
        for the structure of the dict and what ``Type``, ``Value``, ``Min``, ``Max``, ``Options`` and
        ``Units`` mean in it, and for the reserved keys the GUI builds file pickers
        from.

        The ``super()`` call supplies the mandatory ``"MetaEventFinder"`` key, which is how
        this plugin is wired to its data source.

        The keys this plugin adds:

        - ``Output File`` - the SQLite database to write events into.
        - ``Experiment Name`` - the label these events are filed under, so one database
          can hold several runs.
        - ``Voltage`` (mV) - the applied bias, stored with the experiment.
        - ``Membrane Thickness`` (nm) and ``Conductivity`` (S/m) - stored with the
          experiment so that downstream analysis can convert blockage depths into pore
          and molecule geometry.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaEventFinder" as a key, with explicitly set Type MetaEventFinder.
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

    @log(logger=logger)
    @override
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Permanently delete the given channel's row (and, via cascading foreign keys,
        its associated event rows) from the database, so a subsequent write starts
        from a clean slate. This is destructive, not a resource-cleanup step.

        :param channel: channel ID. Note that `channel=None` does not reset all
            channels; SQL `channel_id = NULL` never matches, so no rows are deleted.
        :type channel: Optional[int]
        :raises ValueError: if settings have not been initialized or the output
            file path is not set in settings
        :raises sqlite3.Error: if the delete fails, so that the caller cannot treat an
            unreset channel as a clean slate
        """
        conn: Optional[sqlite3.Connection] = None
        cursor: Optional[sqlite3.Cursor] = None

        if self.settings is None:
            raise ValueError("Settings have not been initialized.")

        settings: dict[str, dict[str, Any]] = self.settings
        output_file_setting = settings.get("Output File")

        if (
            not isinstance(output_file_setting, dict)
            or output_file_setting.get("Value") is None
        ):
            raise ValueError("Output file path is not set in settings.")

        try:
            conn = sqlite3.connect(Path(output_file_setting["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("SAVEPOINT reset_channel")

            cursor.execute(
                "DELETE FROM channels WHERE channel_id = ?",
                (channel,),
            )

            self.logger.info(f"Deleted channel_id={channel} from channels.")
        except sqlite3.Error as e:
            if conn is not None:
                conn.execute("ROLLBACK TO SAVEPOINT reset_channel")
                conn.rollback()
            # Raised rather than swallowed. This is a destructive operation the
            # caller relies on having happened - MetaWriter.commit_events follows
            # an abort with `self.written[channel] = 0`, which claims a clean slate
            # - so returning normally after a failed delete left the writer's
            # bookkeeping disagreeing with the database. The abort path that calls
            # this guards against the raise so it cannot mask an in-flight error.
            self.logger.error(
                f"Failed to delete channel_id={channel}: {e}, channel not reset"
            )
            raise
        else:
            if conn is not None:
                conn.execute("RELEASE SAVEPOINT reset_channel")
                conn.commit()
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Do whatever needs doing to gracefully shut down on app exit

        :param channel: channel ID
        :type channel: Optional[int]
        """
        if self.cursor:
            try:
                self.cursor.close()
                self.logger.info("SQLiteEventWriter: cursor closed.")
            except Exception as e:
                self.logger.info(f"Failed to close cursor cleanly: {e}")
            self.cursor = None

        if self.conn:
            try:
                self.conn.commit()
                self.conn.close()
                self.logger.info("SQLiteEventWriter: connection closed.")
            except Exception:
                # ERROR rather than INFO, but deliberately not re-raised. For a
                # batch that ends via commit_events' `finally` this is the only
                # commit, so a failure here discards every event in the batch -
                # which the user has to be told about, and at INFO they never were.
                # ERROR is what surfaces it, since QtHandler floors there.
                #
                # It stays non-raising because close_resources is a cleanup method
                # with many callers, several of which invoke it inline immediately
                # before raising the error they actually want reported (see the
                # early-exit arms of MetaDatabaseWriter.write_events). Raising here
                # replaced those errors rather than adding to them - measured - and
                # guarding all of them would be a lot of machinery for no gain the
                # user can see, since the ERROR dialog already says the data was
                # not saved.
                self.logger.error(
                    f"Failed to commit and close the output for channel {channel}; "
                    "events written in this batch may not have been saved.",
                    exc_info=True,
                )
            self.conn = None

    @log(logger=logger)
    def get_output_file_name(self) -> Path:
        """
        get the name of the output file
        """
        return Path(self.settings["Output File"]["Value"])

    # private API, MUST be implemented by subclasses

    @log(logger=logger)
    @override
    def _write_channel_metadata(self, channel: int) -> None:
        """
        Write any information you need to save about the channel.

        :param channel: int indicating which output to flush
        :type channel: int
        :raises ValueError: if settings are not initialized or required settings are missing
        :raises RuntimeError: if the channel's database ID cannot be determined after insertion
        :raises sqlite3.Error: if a database operation fails
        """
        conn: Optional[sqlite3.Connection] = None
        cursor: Optional[sqlite3.Cursor] = None

        if self.settings is None:
            raise ValueError("Expected settings to be initialized.")

        settings: dict[str, dict[str, Any]] = self.settings

        # Ensure all required settings are present and valid
        required_keys = [
            "Experiment Name",
            "Voltage",
            "Membrane Thickness",
            "Conductivity",
            "Output File",
        ]
        for key in required_keys:
            if (
                key not in settings
                or not isinstance(settings[key], dict)
                or settings[key].get("Value") is None
            ):
                raise ValueError(f"Missing or invalid setting: {key}")

        experiment_name = settings["Experiment Name"]["Value"]
        voltage = settings["Voltage"]["Value"]
        thickness = settings["Membrane Thickness"]["Value"]
        conductivity = settings["Conductivity"]["Value"]
        output_file = settings["Output File"]["Value"]
        samplerate = self.eventfinder.get_samplerate()

        try:
            conn = sqlite3.connect(Path(output_file))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")

            cursor.execute(
                """INSERT OR IGNORE INTO channels 
                (name, channel_id, voltage, thickness, conductivity, samplerate, data_format) 
                VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (
                    experiment_name,
                    channel,
                    voltage,
                    thickness,
                    conductivity,
                    samplerate,
                    self.output_dtype,
                ),
            )

            if cursor.lastrowid != 0:
                self.channel_db_id[channel] = cursor.lastrowid
                self.logger.info(
                    f"Inserted new channel {channel} for experiment '{experiment_name}' with DB ID: {self.channel_db_id[channel]}"
                )
            else:
                cursor.execute(
                    "SELECT id FROM channels WHERE channel_id = ?;", (channel,)
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    self.channel_db_id[channel] = existing_row[0]
                    self.logger.info(
                        f"Channel {channel} already exists, using existing DB ID: {self.channel_db_id[channel]}"
                    )
                else:
                    raise RuntimeError(
                        f"Failed to get DB ID for channel {channel} after INSERT OR IGNORE."
                    )

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(
                f"Failed to write channel metadata for '{experiment_name}' on channel {channel}: {e}"
            )
            raise
        else:
            if conn:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def _write_data(
        self,
        event: Dict[str, Any],
        channel: int,
        index: int,
        raw_data: bool = False,
        abort: Optional[bool] = False,
        last_call: Optional[bool] = False,
    ) -> bool:
        """
        Append one event's samples and metadata to the active database file.

        The event's keys are the contract, and are documented on
        ``MetaWriter._write_data``. This writer stores whatever ``data`` already is, so
        it reads neither ``scale`` nor ``offset``.

        :param event: One event, as ``get_single_event_data`` builds it.
        :type event: Dict[str, Any]
        :param channel: Int indicating the channel from which it was acquired.
        :type channel: int
        :param index: event index
        :type index: int
        :param raw_data: True when the samples are unscaled ADC codes rather than pA.
        :type raw_data: bool
        :param abort: True to discard the channel's uncommitted batch and stop.
        :type abort: Optional[bool]
        :param last_call: True when this is the final event of the channel.
        :type last_call: Optional[bool]
        :return: success of the write operation.
        :rtype: bool
        :raises ValueError: if a database connection cannot be opened, or if start_sample, padding_before, or padding_after is None
        :raises sqlite3.Error: if a database operation fails
        :raises Exception: if an unexpected error occurs during the write
        """
        if abort is True:
            # Discarding the channel's whole uncommitted batch is intended on
            # abort; MetaWriter follows it with reset_channel() and written = 0.
            # No ROLLBACK TO SAVEPOINT here because no event is in progress.
            if self.conn:
                self.conn.rollback()
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.conn:
                self.conn.close()
                self.conn = None
            return False

        # Unpacked here rather than taken as thirteen parameters; the keys are the
        # contract, documented on MetaWriter._write_data.
        data = event["data"]
        # scale and offset are deliberately not read: this writer stores whatever
        # `data` already is. They were parameters 4 and 5 of the old thirteen and were
        # ignored there too - see `_rescale_data_to_adc`, which nothing calls.
        start_sample = event["start_sample"]
        padding_before = event["padding_before"]
        padding_after = event["padding_after"]
        baseline_mean = event["baseline_mean"]
        baseline_std = event["baseline_std"]

        if start_sample is None or padding_before is None or padding_after is None:
            raise ValueError(
                f"start_sample, padding_before, and padding_after must all be provided to write an event (got start_sample={start_sample}, padding_before={padding_before}, padding_after={padding_after})"
            )

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
                raise ValueError("Unable to open database connection in _write_data")
            # One savepoint per event, not one per batch. Previously this was taken
            # only when the connection was first opened, so rolling back to it
            # discarded every event written since - and the conn.rollback() that
            # followed destroyed the savepoint, so the next failure raised "no such
            # savepoint" from inside the handler and masked the real error. The
            # batch is still a single transaction, committed once at last_call.
            self.conn.execute("SAVEPOINT write_event")
            savepoint_active = True

            data_blob = data.astype(self.output_dtype).tobytes()

            self.cursor.execute(
                """INSERT OR IGNORE INTO events (
                    channel_id, channel_db_id, event_id,
                    absolute_start, padding_before, padding_after,
                    baseline_mean, baseline_std, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    channel,
                    self.channel_db_id[channel],
                    index,
                    int(start_sample),
                    int(padding_before),
                    int(padding_after),
                    baseline_mean,
                    baseline_std,
                    data_blob,
                ),
            )
            success = self.cursor.rowcount == 1

        except sqlite3.Error as e:
            # Undo only this event. Deliberately no conn.rollback() here - the
            # caller files this as a per-event rejection and continues, so the
            # events already written in this batch must survive.
            if self.conn and savepoint_active:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.execute("RELEASE SAVEPOINT write_event")
            raise e
        except Exception as e:  # Fallback for truly unexpected errors
            if self.conn and savepoint_active:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.execute("RELEASE SAVEPOINT write_event")
            raise e
        else:
            # Released unconditionally: unlike SQLiteDBWriter, an event here is a
            # single INSERT OR IGNORE, so success is False only when the statement
            # wrote nothing at all and there is no partial state to undo.
            if self.conn and savepoint_active:
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
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises KeyError: If the settings dict does not contain the correct information.
        """
        if "MetaEventFinder" not in settings.keys():
            raise KeyError(
                """settings must include a 'MetaEventFinder' key with value equal to the key of the vent finder from which to pull event data"""
            )

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    def _rescale_data_to_adc(
        self,
        data: npt.NDArray[np.number],
        scale: Optional[float] = None,
        offset: Optional[float] = None,
        raw_data: bool = False,
        dtype: npt.DTypeLike = np.uint16,
        adc_min: int = np.iinfo(np.int16).min,
        adc_max: int = np.iinfo(np.int16).max,
    ) -> tuple[npt.NDArray[np.number], Optional[float], Optional[float]]:
        """
        Not used by this writer

        :param data: 1D numpy array of data to write to the active file in the specified channel.
        :type data: npt.NDArray[np.number]
        :param scale: Scaling between provided data type and encoded form for storage. If None, scale is calculated based on the data to maximally use the available adc range.
        :type scale: Optional[float]
        :param offset: Offset between provided data type and encoded form for storage. If None, offset is calculated based on the data to maximally use the available adc range.
        :type offset: Optional[float]
        :param raw_data: True means to simply write data as-is to file, False indicates to first rescale it. Default False.
        :type raw_data: bool
        :param dtype: Numpy dtype to use for storage. Defaults to 16-bit unsigned int.
        :type dtype: npt.DTypeLike
        :param adc_min: Integer encoding the minimum adc code for the adc conversion.
        :type adc_min: int
        :param adc_max: Integer encoding the maximum adc code for the adc conversion.
        :type adc_max: int

        :return: Rescaled data as numpy array, scale factor, and offset.
        :rtype: tuple[npt.NDArray[np.number], Optional[float], Optional[float]]
        """
        return data, scale, offset

    @log(logger=logger)
    @override
    def _set_output_dtype(self) -> str:
        """
        set the output dtype - should be a numpy numeric type:

        self.output_dtype = '<u2'
        """
        return "<f8"

    # private API continued, can be implemented by subclasses, but default behavior is suitable for most use cases

    # Utility functions, specific to subclasses as needed
