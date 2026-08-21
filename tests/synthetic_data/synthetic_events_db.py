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

Multichannel
------------
``generate_multichannel_events_database()`` writes several channels into
ONE database file, as separate ``channel_id`` rows -- not one file per
channel the way raw-data multichannel generation works. That difference
is structural, not a style choice: raw-data readers like
ChimeraReader20240501 assemble a multichannel experiment by globbing a
directory for sibling files, so multichannel there has to mean "several
files". SQLiteEventLoader instead queries a single file's ``channels``/
``events`` tables filtered by ``channel_id``, so a single file already
supports many channels natively -- confirmed via
``SQLiteEventLoader.get_channels()``'s query, ``SELECT channel_id FROM
channels``, which returns every channel present in one file, not just
one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _create_schema(cursor: sqlite3.Cursor) -> None:
    """
    Create the channels/events/columns tables and the cascade-delete
    trigger, if they don't already exist. Shared by single- and
    multi-channel generation so the schema can't drift between the two.

    :param cursor: An open cursor on the target database.
    :type cursor: sqlite3.Cursor
    """
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


def _write_channel(
    cursor: sqlite3.Cursor,
    rng: np.random.Generator,
    *,
    channel_id: int,
    num_events: int,
    samplerate: float,
    baseline_mean_pA: float,
    baseline_std_pA: float,
    event_amplitude_pA: float,
    event_length_samples: int,
    padding_samples: int,
    event_gap_samples: int,
    experiment_name: str,
    voltage: float,
    thickness: float,
    conductivity: float,
    event_length_range_samples: Optional[Tuple[int, int]] = None,
    event_amplitudes_pA: Optional[List[float]] = None,
) -> SyntheticEventsChannel:
    """
    Insert one channel's row and all of its planted events into an
    already-open connection with the schema already created. Shared by
    generate_events_database() (one call) and
    generate_multichannel_events_database() (one call per channel, same
    open connection) so a multichannel database can't drift out of sync
    with what the single-channel path produces.

    :param cursor: An open cursor on the target database, with
        _create_schema() already run on it.
    :type cursor: sqlite3.Cursor
    :param rng: Random generator to draw this channel's noise from. Pass
        a distinct generator (or one seeded distinctly) per channel so
        multiple channels in one database don't share identical noise.
    :type rng: numpy.random.Generator
    :param channel_id: Channel identifier for this channel's rows.
    :type channel_id: int
    :param num_events: How many events to plant on this channel.
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
        Ignored if event_length_range_samples is given.
    :type event_length_samples: int
    :param padding_samples: Baseline samples stored before and after each
        blockage.
    :type padding_samples: int
    :param event_gap_samples: Nominal sample spacing between successive
        events' absolute_start values.
    :type event_gap_samples: int
    :param experiment_name: Name recorded in the channels table.
    :type experiment_name: str
    :param voltage: Voltage recorded in the channels table.
    :type voltage: float
    :param thickness: Membrane thickness recorded in the channels table.
    :type thickness: float
    :param conductivity: Conductivity recorded in the channels table.
    :type conductivity: float
    :param event_length_range_samples: If given, (min, max) inclusive
        range each event's length is drawn uniformly from, instead of
        every event sharing event_length_samples. Use this when a test
        needs genuinely varied event durations -- e.g. so a "duration >
        X" filter selects a real subset rather than being all-or-nothing.
    :type event_length_range_samples: Optional[Tuple[int, int]]
    :param event_amplitudes_pA: If given, the exact amplitude used for
        each planted event, in order (length must equal num_events),
        overriding the single shared event_amplitude_pA. Setting a
        specific event's magnitude below the fitter's Step Size makes
        that one event deliberately unfittable -- confirmed via a real
        CUSUM run that an event whose depth doesn't clear Step Size gets
        rejected with "Too Few Levels" while shallower ones around it
        still fit. This is how a metadata database ends up with
        non-contiguous event ids realistically: raw event_id stays
        strictly contiguous (real acquisition numbers events
        sequentially), and gaps in the FITTED set emerge because some
        raw events genuinely fail to fit -- not because raw ids were
        artificially skipped.
    :type event_amplitudes_pA: Optional[List[float]]

    :return: Ground truth for the channel just written.
    :rtype: SyntheticEventsChannel
    """
    if event_amplitudes_pA is not None and len(event_amplitudes_pA) != num_events:
        raise ValueError(
            f"event_amplitudes_pA has {len(event_amplitudes_pA)} entries but "
            f"num_events={num_events}; they must match"
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
        this_amplitude = (
            event_amplitudes_pA[event_id] if event_amplitudes_pA is not None else event_amplitude_pA
        )
        this_event_length = (
            int(rng.integers(event_length_range_samples[0], event_length_range_samples[1] + 1))
            if event_length_range_samples is not None
            else event_length_samples
        )
        trace = _build_event_trace(
            rng,
            padding_before=padding_samples,
            event_length=this_event_length,
            padding_after=padding_samples,
            baseline_mean=baseline_mean_pA,
            baseline_std=baseline_std_pA,
            amplitude=this_amplitude,
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
                event_length=this_event_length,
                baseline_mean=baseline_mean_pA,
                baseline_std=baseline_std_pA,
                amplitude=this_amplitude,
            )
        )
        absolute_start += padding_samples + this_event_length + padding_samples + event_gap_samples

    return channel


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
    event_length_range_samples: Optional[Tuple[int, int]] = None,
    event_amplitudes_pA: Optional[List[float]] = None,
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
        Ignored if event_length_range_samples is given.
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
    :param event_length_range_samples: If given, (min, max) inclusive
        range each event's length is drawn uniformly from, instead of
        every event sharing event_length_samples.
    :type event_length_range_samples: Optional[Tuple[int, int]]
    :param event_amplitudes_pA: If given, the exact amplitude used for
        each planted event, in order (length must equal num_events),
        overriding the single shared event_amplitude_pA. Use this to
        make specific events deliberately unfittable (magnitude below a
        fitter's Step Size) while event_id stays strictly contiguous --
        see _write_channel()'s docstring for why that's the realistic
        way to end up with gaps in a fitted-event set.
    :type event_amplitudes_pA: Optional[List[float]]

    :return: A SyntheticEventsDatabase describing the file and its
        planted events.
    :rtype: SyntheticEventsDatabase
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(out_path)
    try:
        cursor = conn.cursor()
        _create_schema(cursor)
        channel = _write_channel(
            cursor,
            np.random.default_rng(seed),
            channel_id=channel_id,
            num_events=num_events,
            samplerate=samplerate,
            baseline_mean_pA=baseline_mean_pA,
            baseline_std_pA=baseline_std_pA,
            event_amplitude_pA=event_amplitude_pA,
            event_length_range_samples=event_length_range_samples,
            event_amplitudes_pA=event_amplitudes_pA,
            event_length_samples=event_length_samples,
            padding_samples=padding_samples,
            event_gap_samples=event_gap_samples,
            experiment_name=experiment_name,
            voltage=voltage,
            thickness=thickness,
            conductivity=conductivity,
        )
        conn.commit()
    finally:
        conn.close()

    return SyntheticEventsDatabase(db_path=out_path, channels={channel_id: channel})


def generate_multichannel_events_database(
    out_path: Path,
    *,
    channels: List[int],
    num_events_per_channel: Dict[int, int] | int = 25,
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
    seed_base: int = 100,
) -> SyntheticEventsDatabase:
    """
    Write a multi-channel synthetic events database with known events.

    Unlike raw-data multichannel generation (one file per channel,
    because that's how a reader like ChimeraReader20240501 finds sibling
    files by globbing), this writes every channel into ONE database
    file, as separate channel_id rows -- confirmed against the real
    SQLiteEventLoader, whose queries already filter by channel_id within
    a single file (see this module's docstring). There is no analogous
    multichannel *wrapper* module here the way
    tests/synthetic_data/multichannel_chimera.py wraps
    tests/synthetic_data/synthetic_chimera.py: the schema itself already
    supports many channels per file, so this is one function here rather
    than a separate module calling a single-channel one repeatedly.

    Each channel gets its own random seed (seed_base + its position in
    channels), so channels don't share identical noise.

    :param out_path: Path to write the ``.sqlite3`` file to; parent
        directories are created if absent. Overwrites any existing file
        at this path.
    :type out_path: Path
    :param channels: Channel identifiers to write, e.g. [0, 1, 2].
    :type channels: List[int]
    :param num_events_per_channel: Either one count used for every
        channel, or a dict mapping channel id to its own count. Channels
        absent from the dict fall back to 25 events.
    :type num_events_per_channel: Union[Dict[int, int], int]
    :param samplerate: Sample rate in Hz, shared by every channel (as the
        real SQLiteEventLoader requires -- see MetaReader's analogous
        _set_sample_rate() check for readers, though the events-loader
        equivalent of that constraint hasn't itself been re-traced here).
    :type samplerate: float
    :param baseline_mean_pA: Baseline current for every event on every
        channel, in picoamps.
    :type baseline_mean_pA: float
    :param baseline_std_pA: Baseline noise standard deviation, in
        picoamps.
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
        events' absolute_start values, within each channel.
    :type event_gap_samples: int
    :param experiment_name: Name recorded in the channels table, shared
        by every channel.
    :type experiment_name: str
    :param voltage: Voltage recorded in the channels table.
    :type voltage: float
    :param thickness: Membrane thickness recorded in the channels table.
    :type thickness: float
    :param conductivity: Conductivity recorded in the channels table.
    :type conductivity: float
    :param seed_base: First random seed; each channel uses the next
        value up.
    :type seed_base: int

    :return: A SyntheticEventsDatabase describing the file and every
        channel's planted events.
    :rtype: SyntheticEventsDatabase
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    result = SyntheticEventsDatabase(db_path=out_path)

    conn = sqlite3.connect(out_path)
    try:
        cursor = conn.cursor()
        _create_schema(cursor)
        for offset, channel_id in enumerate(channels):
            n_events = (
                num_events_per_channel
                if isinstance(num_events_per_channel, int)
                else num_events_per_channel.get(channel_id, 25)
            )
            result.channels[channel_id] = _write_channel(
                cursor,
                np.random.default_rng(seed_base + offset),
                channel_id=channel_id,
                num_events=n_events,
                samplerate=samplerate,
                baseline_mean_pA=baseline_mean_pA,
                baseline_std_pA=baseline_std_pA,
                event_amplitude_pA=event_amplitude_pA,
                event_length_samples=event_length_samples,
                padding_samples=padding_samples,
                event_gap_samples=event_gap_samples,
                experiment_name=experiment_name,
                voltage=voltage,
                thickness=thickness,
                conductivity=conductivity,
            )
        conn.commit()
    finally:
        conn.close()

    return result


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db = generate_events_database(Path(tmp) / "synthetic_events.sqlite3", num_events=25)
        ch = db[0]
        print("db:", db.db_path, db.db_path.stat().st_size, "bytes")
        print("channel 0 events:", ch.num_events, "at", ch.samplerate, "Hz")
        print("first event:", ch.events[0])

    with tempfile.TemporaryDirectory() as tmp:
        mdb = generate_multichannel_events_database(
            Path(tmp) / "synthetic_events_multi.sqlite3",
            channels=[0, 1, 2],
            num_events_per_channel={0: 5, 1: 10, 2: 25},
        )
        print()
        print("multichannel db:", mdb.db_path, mdb.db_path.stat().st_size, "bytes")
        for ch_id, ch in mdb.channels.items():
            print(f"  channel {ch_id}: {ch.num_events} events at {ch.samplerate} Hz")