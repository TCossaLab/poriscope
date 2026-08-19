"""
Generation of synthetic Poriscope events databases for testing
SQLiteEventLoader, and downstream MetaEventFitter subclasses (e.g. CUSUM),
without depending on a checked-in real database.

Schema
------
Confirmed directly against the real
poriscope.plugins.datawriters.SQLiteEventWriter (which produces this
format) and poriscope.plugins.eventloaders.SQLiteEventLoader (which reads
it):

* ``channels``: id, name, channel_id (unique), voltage, thickness,
  conductivity, samplerate, data_format.
* ``events``: id, channel_db_id (FK -> channels.id), channel_id, event_id,
  absolute_start, padding_before, padding_after, baseline_mean,
  baseline_std, raw_data (BLOB).
* ``columns``: id, name (unique), table_name, units. SQLiteEventLoader
  only checks that this table exists, not its contents, so it's created
  empty here.

Data encoding
-------------
``raw_data`` is written as ``SQLiteEventWriter._set_output_dtype()``'s
real value, ``"<f8"`` (little-endian float64) -- not the ``"<u2"`` shown
in that method's own docstring, which is an illustrative comment rather
than the actual returned value. ``SQLiteEventWriter._rescale_data_to_adc``
is explicitly documented as unused by this writer, so no scale/offset
conversion happens on write. Consequently, unlike a Chimera recording,
there is no ADC-code inversion to perform here: event traces are stored
already in physical units (picoamps), and this generator writes them the
same way, matching what ``SQLiteEventLoader.load_event()`` reads back via
``np.frombuffer(blob, dtype=data_format)``.

Event shape
-----------
Each planted event is a flat baseline segment, a blockage segment offset
by a fixed amplitude, and another flat baseline segment, with independent
Gaussian noise throughout. The noise-generation step itself
(``build_noisy_segment``) is imported from ``base_synthetic_recording``
rather than reimplemented here, since it's the same primitive
``BaseSyntheticRecordingWriter._build_trace`` uses for continuous
recordings -- only what happens around it differs: a continuous recording
embeds many such shifts in one long trace, while this module writes one
short padded snippet per event, as a separate database row.

There is deliberately no shared base *class* between this module and
``BaseSyntheticRecordingWriter``'s writer subclasses: that ABC exists to
let two-plus real formats (Chimera, BinaryReader1X) share a `_write()`
contract with genuinely different implementations. There is currently
only one events-database format (``SQLiteEventWriter``'s schema), so
there's no second implementation to abstract over yet -- introducing an
ABC for a single subclass would be speculative structure, the same
mistake as pre-building fixtures for a format nothing consumes. If a
second events-database format shows up later, that's the point to
extract one, from two working implementations rather than in advance of
them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np

from tests.synthetic_data.base_synthetic_recording import build_noisy_segment

RAW_DATA_DTYPE = "<f8"  # matches SQLiteEventWriter._set_output_dtype()'s real value


@dataclass
class SyntheticDbEvent:
    """
    Ground truth for one planted event within a synthetic events database.

    :param event_id: Identifier assigned to this event within its channel.
    :type event_id: int
    :param absolute_start: Sample index where the event starts, relative
        to the start of the (synthetic) experiment.
    :type absolute_start: int
    :param padding_before: Samples of baseline included before the
        blockage within this event's stored trace.
    :type padding_before: int
    :param padding_after: Samples of baseline included after the
        blockage within this event's stored trace.
    :type padding_after: int
    :param event_length: Samples spanned by the blockage itself,
        excluding padding.
    :type event_length: int
    :param baseline_mean: Local baseline current, in picoamps.
    :type baseline_mean: float
    :param baseline_std: Local baseline noise standard deviation, in
        picoamps.
    :type baseline_std: float
    :param amplitude: Signed current change during the blockage, in
        picoamps. Negative for a blockage.
    :type amplitude: float
    """

    event_id: int
    absolute_start: int
    padding_before: int
    padding_after: int
    event_length: int
    baseline_mean: float
    baseline_std: float
    amplitude: float

    @property
    def total_length(self) -> int:
        """
        Total samples stored for this event, padding included.

        :return: Sample count of the full stored trace.
        :rtype: int
        """
        return self.padding_before + self.event_length + self.padding_after


@dataclass
class SyntheticEventsChannel:
    """
    Ground truth for one channel of a synthetic events database.

    :param channel_id: Channel identifier.
    :type channel_id: int
    :param samplerate: Sample rate in Hz.
    :type samplerate: float
    :param events: Every planted event on this channel, in event_id order.
    :type events: List[SyntheticDbEvent]
    """

    channel_id: int
    samplerate: float
    events: List[SyntheticDbEvent] = field(default_factory=list)

    @property
    def num_events(self) -> int:
        """
        How many events were planted on this channel.

        :return: Event count.
        :rtype: int
        """
        return len(self.events)


@dataclass
class SyntheticEventsDatabase:
    """
    A generated events database and the ground truth about its contents.

    :param db_path: Path to the written ``.sqlite3`` file.
    :type db_path: Path
    :param channels: Dict mapping channel_id to its
        SyntheticEventsChannel.
    :type channels: Dict[int, SyntheticEventsChannel]
    """

    db_path: Path
    channels: Dict[int, SyntheticEventsChannel] = field(default_factory=dict)

    def __getitem__(self, channel_id: int) -> SyntheticEventsChannel:
        return self.channels[channel_id]

    @property
    def total_num_events(self) -> int:
        """
        Events planted across all channels combined.

        :return: Total event count.
        :rtype: int
        """
        return sum(ch.num_events for ch in self.channels.values())


def _build_event_trace(
    rng: np.random.Generator,
    *,
    padding_before: int,
    event_length: int,
    padding_after: int,
    baseline_mean: float,
    baseline_std: float,
    amplitude: float,
) -> np.ndarray:
    """
    Build one event's ground-truth trace: baseline, blockage, baseline.

    :param rng: Random generator to draw noise from.
    :type rng: numpy.random.Generator
    :param padding_before: Samples of baseline before the blockage.
    :type padding_before: int
    :param event_length: Samples spanned by the blockage.
    :type event_length: int
    :param padding_after: Samples of baseline after the blockage.
    :type padding_after: int
    :param baseline_mean: Baseline current, in picoamps.
    :type baseline_mean: float
    :param baseline_std: Baseline noise standard deviation, in picoamps.
    :type baseline_std: float
    :param amplitude: Signed current change during the blockage, in
        picoamps.
    :type amplitude: float

    :return: The event trace, in picoamps.
    :rtype: numpy.ndarray
    """
    total = padding_before + event_length + padding_after
    trace = build_noisy_segment(rng, total, baseline_mean, baseline_std)
    trace[padding_before : padding_before + event_length] += amplitude
    return trace


def generate_events_database(
    out_path: Path,
    *,
    channel_id: int = 0,
    num_events: int = 25,
    samplerate: float = 500_000.0,
    baseline_mean_pA: float = 2000.0,
    baseline_std_pA: float = 15.0,
    event_amplitude_pA: float = -400.0,
    event_length_samples: int = 250,
    padding_samples: int = 100,
    event_gap_samples: int = 2000,
    experiment_name: str = "synthetic",
    voltage: float = 200.0,
    thickness: float = 10.0,
    conductivity: float = 1.0,
    seed: int = 42,
) -> SyntheticEventsDatabase:
    """
    Write a single-channel synthetic events database with known events.

    Events are spaced ``event_gap_samples`` apart along a notional
    experiment timeline (via ``absolute_start``) purely for realism; the
    schema does not require them to be contiguous or non-overlapping the
    way a continuous recording would, since each event's trace is stored
    independently.

    :param out_path: Path to write the ``.sqlite3`` file to; parent
        directories are created if absent. Overwrites any existing file
        at this path.
    :type out_path: Path
    :param channel_id: Channel identifier to write events under.
    :type channel_id: int
    :param num_events: How many events to plant on the channel.
    :type num_events: int
    :param samplerate: Sample rate in Hz, recorded in the channels table.
    :type samplerate: float
    :param baseline_mean_pA: Baseline current for every event, in
        picoamps.
    :type baseline_mean_pA: float
    :param baseline_std_pA: Baseline noise standard deviation for every
        event, in picoamps.
    :type baseline_std_pA: float
    :param event_amplitude_pA: Signed current change during each
        blockage, in picoamps. Negative for a blockage.
    :type event_amplitude_pA: float
    :param event_length_samples: Length of each blockage, in samples.
    :type event_length_samples: int
    :param padding_samples: Baseline samples stored before and after each
        blockage.
    :type padding_samples: int
    :param event_gap_samples: Nominal sample spacing between successive
        events' ``absolute_start`` values.
    :type event_gap_samples: int
    :param experiment_name: Name recorded in the channels table.
    :type experiment_name: str
    :param voltage: Voltage recorded in the channels table.
    :type voltage: float
    :param thickness: Membrane thickness recorded in the channels table.
    :type thickness: float
    :param conductivity: Conductivity recorded in the channels table.
    :type conductivity: float
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: A SyntheticEventsDatabase describing the file and its
        planted events.
    :rtype: SyntheticEventsDatabase
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    rng = np.random.default_rng(seed)

    conn = sqlite3.connect(out_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                table_name TEXT NOT NULL,
                units TEXT
            );
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS delete_childless_channels
            AFTER DELETE ON events
            BEGIN
                DELETE FROM channels
                WHERE id NOT IN (SELECT DISTINCT channel_db_id FROM events);
            END;
            """
        )

        cursor.execute(
            """INSERT INTO channels
               (name, channel_id, voltage, thickness, conductivity, samplerate, data_format)
               VALUES (?, ?, ?, ?, ?, ?, ?);""",
            (
                experiment_name,
                channel_id,
                voltage,
                thickness,
                conductivity,
                samplerate,
                RAW_DATA_DTYPE,
            ),
        )
        channel_db_id = cursor.lastrowid

        channel = SyntheticEventsChannel(channel_id=channel_id, samplerate=samplerate)

        absolute_start = padding_samples
        for event_id in range(num_events):
            trace = _build_event_trace(
                rng,
                padding_before=padding_samples,
                event_length=event_length_samples,
                padding_after=padding_samples,
                baseline_mean=baseline_mean_pA,
                baseline_std=baseline_std_pA,
                amplitude=event_amplitude_pA,
            )
            raw_data = trace.astype(RAW_DATA_DTYPE).tobytes()

            cursor.execute(
                """INSERT INTO events
                   (channel_db_id, channel_id, event_id, absolute_start,
                    padding_before, padding_after, baseline_mean, baseline_std,
                    raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    channel_db_id,
                    channel_id,
                    event_id,
                    absolute_start,
                    padding_samples,
                    padding_samples,
                    baseline_mean_pA,
                    baseline_std_pA,
                    raw_data,
                ),
            )

            channel.events.append(
                SyntheticDbEvent(
                    event_id=event_id,
                    absolute_start=absolute_start,
                    padding_before=padding_samples,
                    padding_after=padding_samples,
                    event_length=event_length_samples,
                    baseline_mean=baseline_mean_pA,
                    baseline_std=baseline_std_pA,
                    amplitude=event_amplitude_pA,
                )
            )
            absolute_start += event_gap_samples

        conn.commit()
    finally:
        conn.close()

    return SyntheticEventsDatabase(db_path=out_path, channels={channel_id: channel})


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db = generate_events_database(
            Path(tmp) / "synthetic_events.sqlite3", num_events=25
        )
        ch = db[0]
        print("db:", db.db_path, db.db_path.stat().st_size, "bytes")
        print("channel 0 events:", ch.num_events, "at", ch.samplerate, "Hz")
        print("first event:", ch.events[0])
