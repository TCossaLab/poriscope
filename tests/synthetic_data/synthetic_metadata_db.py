"""
Generation of synthetic Poriscope metadata databases (DB.db-equivalent
files) for testing the Metadata tab's e2e suite, without depending on a
checked-in real database.

Why this drives the real pipeline instead of writing SQL directly
--------------------------------------------------------------------
The metadata database's schema (six tables: experiments, channels,
events, sublevels, data, columns, plus an event_counts trigger-maintained
table) is considerably richer than the raw events-database schema
synthetic_events_db.py hand-writes, and critically, part of it is NOT
static: SQLiteDBWriter dynamically ALTER TABLEs new columns onto
sublevels based on whatever the specific EventFitter used reports via
get_sublevel_metadata_types()/get_sublevel_metadata_units() (confirmed
directly in poriscope/plugins/dbwriters/SQLiteDBWriter.py). CUSUM alone
adds eight such columns (sublevel_current, sublevel_stdev,
sublevel_blockage, sublevel_duration, sublevel_start_times,
sublevel_end_times, sublevel_max_deviation, sublevel_raw_ecd,
sublevel_fitted_ecd) -- "duration" as plotted/filtered in the Metadata
tab is derived from sublevel_duration via a padding_before/padding_after
join in MetaDatabaseLoader, not a plain stored column.

Hand-reimplementing this SQL, the way synthetic_events_db.py does for the
much simpler raw-events schema, would risk silently missing or
mis-naming one of those dynamically-added columns -- a mistake that
might not even surface as an error, just as queries silently returning
wrong or empty results. Instead, this module drives the REAL classes
directly and headlessly (no Qt, no GUI -- same pattern as
headless_pipeline_result from the raw-data test suite):

    generate_events_database()  (this package's own raw events generator)
        -> real SQLiteEventLoader
        -> real CUSUM (fitted with Step Size below the planted event
           depth, confirmed to produce 100% good fits -- see
           tests/e2e/event_analysis/test_eventanalysis_fit_events_flow.py's
           module docstring for how that relationship was verified)
        -> real SQLiteDBWriter, driven via its actual write_events()
           generator

Every byte of the resulting file is produced by real poriscope code;
nothing here approximates the schema by hand. Confirmed end-to-end
against a real installed poriscope package: all 8 real tables present,
correct row counts, and every one of CUSUM's dynamically-added sublevel
columns present and populated.

Multiple experiments and channels
-----------------------------------
Unlike the raw events-database generator (built for single-channel
fitter tests), this generator's whole purpose is testing Metadata's
Scope dialog (SelectionTree) and its default-all-checked /
Select-All/Deselect-All / individual-select / PartiallyChecked-parent
behavior, which is only meaningfully exercisable with 2+ experiments
and/or 2+ channels. generate_metadata_database() therefore takes a list
of experiment specs, each with its own channels, rather than a single
flat channel list.

Variable event duration
------------------------
Each channel's events use generate_events_database()'s
event_length_range_samples option (added alongside this module) rather
than a fixed length, so "duration > X"-style SQL filters in the Metadata
tab select a genuine subset of events, not an all-or-nothing result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from poriscope.utils.MetaEventFitter import MetaEventFitter
from tests.synthetic_data.synthetic_events_db import generate_events_database

# CUSUM's own fitting produces incidental log output at INFO/DEBUG level
# for every event; suppress it while driving the pipeline so generating
# a fixture doesn't spam pytest's captured output. Restored afterward.
_PIPELINE_LOGGERS_TO_QUIET = (
    "poriscope.plugins.eventfitters.CUSUM",
    "poriscope.plugins.eventloaders.SQLiteEventLoader",
    "poriscope.plugins.dbwriters.SQLiteDBWriter",
    "poriscope.utils.MetaEventFitter",
    "poriscope.utils.MetaDatabaseWriter",
    "poriscope.utils.BaseDataPlugin",
)


@dataclass
class SyntheticMetadataChannel:
    """
    Ground truth for one channel within one experiment of a synthetic
    metadata database.

    :param channel_id: Channel identifier.
    :type channel_id: int
    :param samplerate: Sample rate in Hz.
    :type samplerate: float
    :param num_events: How many events were planted and successfully fit
        onto this channel.
    :type num_events: int
    :param event_lengths_samples: The planted length, in samples, of
        every SURVIVING (successfully fit) event on this channel,
        aligned by position with event_ids (event_lengths_samples[i]
        is the length of the event whose id is event_ids[i]).
    :type event_lengths_samples: List[int]
    :param event_ids: The real event_id of every SURVIVING event on this
        channel, in increasing order. May have gaps relative to the raw
        planted range (0..num_planted-1) if any events were rejected
        during fitting (see reject_event_indices in
        generate_metadata_database()'s channel spec).
    :type event_ids: List[int]
    """

    channel_id: int
    samplerate: float
    num_events: int
    event_lengths_samples: List[int] = field(default_factory=list)
    event_ids: List[int] = field(default_factory=list)

    @property
    def event_durations_us(self) -> List[float]:
        """
        Event lengths converted to microseconds (samples / samplerate *
        1e6) -- confirmed to match the real fitted "duration" column
        SQLiteDBLoader computes to within floating-point noise (~1e-14 us)
        for these clean, low-noise synthetic events, so this is a
        reliable proxy for the real values without needing to query a
        live database.

        :return: Event durations in microseconds, in event_id order.
        :rtype: List[float]
        """
        return [length / self.samplerate * 1e6 for length in self.event_lengths_samples]

    def median_duration_us(self) -> float:
        """
        Median event duration in microseconds, for choosing a
        "duration > X" filter threshold known to split this channel's
        events into two non-empty groups rather than an
        arbitrarily-guessed value that might select everything or
        nothing.

        :return: Median duration in microseconds.
        :rtype: float

        :raises ValueError: If this channel has no events.
        """
        durations = sorted(self.event_durations_us)
        if not durations:
            raise ValueError(
                f"Channel {self.channel_id} has no events to compute a median from"
            )
        mid = len(durations) // 2
        if len(durations) % 2 == 1:
            return durations[mid]
        return (durations[mid - 1] + durations[mid]) / 2.0


@dataclass
class SyntheticMetadataExperiment:
    """
    Ground truth for one experiment within a synthetic metadata database.

    :param name: Experiment name, as stored in the experiments table.
    :type name: str
    :param voltage: Voltage recorded for this experiment.
    :type voltage: float
    :param thickness: Membrane thickness recorded for this experiment.
    :type thickness: float
    :param conductivity: Conductivity recorded for this experiment.
    :type conductivity: float
    :param channels: Dict mapping channel_id to its
        SyntheticMetadataChannel.
    :type channels: Dict[int, SyntheticMetadataChannel]
    """

    name: str
    voltage: float
    thickness: float
    conductivity: float
    channels: Dict[int, SyntheticMetadataChannel] = field(default_factory=dict)

    @property
    def total_num_events(self) -> int:
        """
        Events successfully fit across every channel in this experiment.

        :return: Total event count.
        :rtype: int
        """
        return sum(ch.num_events for ch in self.channels.values())

    def median_duration_us(self) -> float:
        """
        Median event duration in microseconds across every channel in
        this experiment, for choosing a "duration > X" filter threshold
        known to split this experiment's events non-trivially.

        :return: Median duration in microseconds.
        :rtype: float

        :raises ValueError: If this experiment has no events.
        """
        all_durations = sorted(
            d for ch in self.channels.values() for d in ch.event_durations_us
        )
        if not all_durations:
            raise ValueError(
                f"Experiment '{self.name}' has no events to compute a median from"
            )
        mid = len(all_durations) // 2
        if len(all_durations) % 2 == 1:
            return all_durations[mid]
        return (all_durations[mid - 1] + all_durations[mid]) / 2.0


@dataclass
class SyntheticMetadataDatabase:
    """
    A generated metadata database and the ground truth about its
    contents.

    :param db_path: Path to the written database file.
    :type db_path: Path
    :param experiments: Dict mapping experiment name to its
        SyntheticMetadataExperiment.
    :type experiments: Dict[str, SyntheticMetadataExperiment]
    """

    db_path: Path
    experiments: Dict[str, SyntheticMetadataExperiment] = field(default_factory=dict)

    def __getitem__(self, experiment_name: str) -> SyntheticMetadataExperiment:
        return self.experiments[experiment_name]

    @property
    def total_num_events(self) -> int:
        """
        Events successfully fit across every channel of every experiment.

        :return: Total event count.
        :rtype: int
        """
        return sum(exp.total_num_events for exp in self.experiments.values())

    def median_duration_us(self) -> float:
        """
        Median event duration in microseconds across every channel of
        every experiment in this database, for choosing a global
        "duration > X" filter threshold known to split the FULL dataset
        non-trivially.

        :return: Median duration in microseconds.
        :rtype: float

        :raises ValueError: If this database has no events.
        """
        all_durations = sorted(
            d
            for exp in self.experiments.values()
            for ch in exp.channels.values()
            for d in ch.event_durations_us
        )
        if not all_durations:
            raise ValueError("Database has no events to compute a median from")
        mid = len(all_durations) // 2
        if len(all_durations) % 2 == 1:
            return all_durations[mid]
        return (all_durations[mid - 1] + all_durations[mid]) / 2.0


def _build_settings(
    cls: Type[Any], overrides: Dict[str, Any], standalone: bool = True
) -> Dict[str, Any]:
    """
    Build a settings dict via a plugin's own get_empty_settings(), filling
    in Value fields -- required because apply_settings()'s validation
    needs "Type" (and "Min"/"Max"/"Options" where applicable) present, not
    just "Value". Bypasses __init__ via object.__new__ to call
    get_empty_settings() without needing a constructed instance first.

    :param cls: The plugin class to build settings for.
    :type cls: Type[Any]
    :param overrides: Field values to set on top of the empty settings.
    :type overrides: Dict[str, Any]
    :param standalone: Passed through to get_empty_settings().
    :type standalone: bool

    :return: A settings dict ready to pass to the class's constructor.
    :rtype: Dict[str, Any]
    """
    probe: Any = object.__new__(cls)
    settings = probe.get_empty_settings(standalone=standalone)
    for key, value in overrides.items():
        if key not in settings:
            settings[key] = {"Type": type(value)}
        settings[key]["Value"] = value
    return settings


def _construct(cls: Type[Any], overrides: Dict[str, Any]) -> Any:
    """
    Construct a plugin instance with the correct pattern for its type.

    MetaEventFitter subclasses (e.g. CUSUM) have a confirmed bug in their
    real __init__: a trailing self.reader/self.eventloader-style
    assignment after super().__init__() silently overwrites what
    apply_settings() just set, when settings are passed to __init__
    directly. The workaround is two-step construction: cls() with no
    settings (so __init__'s post-super() code runs before apply_settings
    ever touches the relevant attribute), then a separate
    .apply_settings(settings) call. MetaReader/MetaWriter subclasses
    don't have this issue and use straightforward one-shot construction.

    :param cls: The plugin class to construct.
    :type cls: Type[Any]
    :param overrides: Field values for get_empty_settings()/apply_settings().
    :type overrides: Dict[str, Any]

    :return: A fully constructed, settings-applied plugin instance.
    :rtype: Any
    """
    settings = _build_settings(cls, overrides)
    if issubclass(cls, MetaEventFitter):
        instance = cls()
        instance.apply_settings(settings)
        return instance
    return cls(settings)


def generate_metadata_database(
    out_path: Path,
    *,
    experiments: List[Dict[str, Any]],
    step_size_pA: float = 100.0,
    rise_time_us: float = 10.0,
    max_sublevels: int = 1000,
    sensitivity: float = 1.0,
) -> SyntheticMetadataDatabase:
    """
    Write a synthetic metadata database by driving the real
    SQLiteEventLoader -> CUSUM -> SQLiteDBWriter pipeline for every
    channel of every experiment, all committed into one output file.

    Each entry in ``experiments`` describes one experiment as a dict:

    .. code-block:: python

        {
            "name": "exp_a",                     # required
            "voltage": 200.0,                    # optional, default 200.0
            "thickness": 10.0,                   # optional, default 10.0
            "conductivity": 1.0,                 # optional, default 1.0
            "channels": [                        # required, 1+ entries
                {
                    "channel_id": 0,              # required
                    "num_events": 25,             # optional, default 25
                    "samplerate": 500_000.0,      # optional
                    "baseline_mean_pA": 2000.0,   # optional
                    "baseline_std_pA": 15.0,      # optional
                    "event_amplitude_pA": -400.0, # optional
                    "event_length_range_samples": (100, 500),  # optional
                    "seed": 42,                   # optional
                },
                ...
            ],
        }

    :param out_path: Path to write the metadata database file to; parent
        directories are created if absent. Overwrites any existing file.
    :type out_path: Path
    :param experiments: Experiment specs, as described above.
    :type experiments: List[Dict[str, Any]]
    :param step_size_pA: CUSUM Step Size, in picoamps, used for every
        channel. Must be below each channel's event_amplitude_pA
        magnitude for CUSUM to register a level change at all --
        confirmed empirically (see this module's docstring); the default
        100 pA is well below the default -400 pA event depth.
    :type step_size_pA: float
    :param rise_time_us: CUSUM Rise Time setting, in microseconds, used
        for every channel.
    :type rise_time_us: float
    :param max_sublevels: CUSUM Max Sublevels setting, used for every
        channel.
    :type max_sublevels: int
    :param sensitivity: CUSUM Sensitivity setting, used for every
        channel.
    :type sensitivity: float

    :return: A SyntheticMetadataDatabase describing the file and every
        experiment/channel's ground truth.
    :rtype: SyntheticMetadataDatabase

    :raises ValueError: If an experiment spec is missing "name" or
        "channels", or a channel spec is missing "channel_id".
    :raises RuntimeError: If CUSUM fails to fit any events on a channel
        (num_events == 0 after fitting) -- almost always means
        step_size_pA wasn't set below that channel's event_amplitude_pA.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    quiet_loggers = []
    for name in _PIPELINE_LOGGERS_TO_QUIET:
        logger = logging.getLogger(name)
        quiet_loggers.append((logger, logger.level))
        logger.setLevel(logging.WARNING)

    result = SyntheticMetadataDatabase(db_path=out_path)

    try:
        for exp_spec in experiments:
            if "name" not in exp_spec:
                raise ValueError(f"Experiment spec missing required 'name': {exp_spec}")
            if "channels" not in exp_spec or not exp_spec["channels"]:
                raise ValueError(
                    f"Experiment spec missing required non-empty 'channels': {exp_spec}"
                )

            exp_name = exp_spec["name"]
            exp_result = SyntheticMetadataExperiment(
                name=exp_name,
                voltage=exp_spec.get("voltage", 200.0),
                thickness=exp_spec.get("thickness", 10.0),
                conductivity=exp_spec.get("conductivity", 1.0),
            )

            for chan_spec in exp_spec["channels"]:
                if "channel_id" not in chan_spec:
                    raise ValueError(
                        f"Channel spec missing required 'channel_id': {chan_spec}"
                    )

                channel_id = chan_spec["channel_id"]
                num_events = chan_spec.get("num_events", 25)
                samplerate = chan_spec.get("samplerate", 500_000.0)
                baseline_mean_pA = chan_spec.get("baseline_mean_pA", 2000.0)
                baseline_std_pA = chan_spec.get("baseline_std_pA", 15.0)
                event_amplitude_pA = chan_spec.get("event_amplitude_pA", -400.0)
                event_length_range_samples: Optional[Tuple[int, int]] = chan_spec.get(
                    "event_length_range_samples"
                )
                seed = chan_spec.get("seed", 42)

                # reject_event_indices: 0-indexed positions (matching the
                # RAW, contiguous event_id at that position) to make
                # deliberately unfittable, by giving just those events an
                # amplitude below step_size_pA's magnitude. Everything
                # else keeps this channel's normal event_amplitude_pA.
                # This is how a metadata database ends up with
                # non-contiguous fitted event ids realistically: the raw
                # event_id sequence stays strictly contiguous (real
                # acquisition numbers events sequentially); gaps appear
                # in the FITTED set because those specific raw events
                # genuinely fail to fit -- not because raw ids were
                # artificially skipped. See _write_channel()'s docstring
                # in synthetic_events_db.py for the confirmed mechanism.
                reject_event_indices = set(chan_spec.get("reject_event_indices", []))
                event_amplitudes_pA: Optional[List[float]] = None
                if reject_event_indices:
                    # 10% of step_size_pA, not 50%: confirmed empirically
                    # that a 50% margin isn't always robust to noise --
                    # a marginal event occasionally survived fitting
                    # anyway on some random draws. 10% is comfortably
                    # below the noise floor too, for reliable, repeatable
                    # rejection independent of seed.
                    reject_amplitude_pA = chan_spec.get(
                        "reject_amplitude_pA", -(step_size_pA * 0.1)
                    )
                    event_amplitudes_pA = [
                        (
                            reject_amplitude_pA
                            if i in reject_event_indices
                            else event_amplitude_pA
                        )
                        for i in range(num_events)
                    ]

                # Step 1: raw events, via this package's own generator.
                # event_id is always strictly contiguous (range(num_events))
                # here -- only the amplitude varies per-event when
                # reject_event_indices is given.
                raw_events_path = (
                    out_path.parent / f"_tmp_raw_{exp_name}_{channel_id}.sqlite3"
                )
                raw_db = generate_events_database(
                    raw_events_path,
                    channel_id=channel_id,
                    num_events=num_events,
                    samplerate=samplerate,
                    baseline_mean_pA=baseline_mean_pA,
                    baseline_std_pA=baseline_std_pA,
                    event_amplitude_pA=event_amplitude_pA,
                    event_length_range_samples=event_length_range_samples,
                    event_amplitudes_pA=event_amplitudes_pA,
                    seed=seed,
                )

                # Step 2: real loader.
                loader = SQLiteEventLoader(
                    _build_settings(
                        SQLiteEventLoader, {"Input File": str(raw_db.db_path)}
                    )
                )

                # Step 3: real CUSUM fit.
                fitter = _construct(
                    CUSUM,
                    {
                        "MetaEventLoader": loader,
                        "Step Size": step_size_pA,
                        "Rise Time": rise_time_us,
                        "Max Sublevels": max_sublevels,
                        "Sensitivity": sensitivity,
                    },
                )
                # MetaEventFitter.fit_events() defaults indices to
                # list(range(total_events)) when not given explicitly --
                # positional 0..N-1, NOT the real event_id values. For a
                # database with non-contiguous ids (event_ids=[2,7,8,...]),
                # that default silently fits only whichever events happen
                # to coincide with their own position, with no error.
                # Confirmed via a direct repro against the real CUSUM
                # class before writing this fix. Passing the loader's own
                # get_valid_indices() explicitly avoids that entirely.
                valid_indices = loader.get_valid_indices(channel_id)
                for _ in fitter.fit_events(channel=channel_id, indices=valid_indices):
                    pass

                n_good = fitter.get_num_events(channel_id)
                if n_good == 0:
                    raise RuntimeError(
                        f"CUSUM fit 0/{num_events} events for experiment "
                        f"'{exp_name}' channel {channel_id} -- step_size_pA "
                        f"({step_size_pA}) is likely not below this channel's "
                        f"event_amplitude_pA magnitude "
                        f"({abs(event_amplitude_pA)})."
                    )

                # Step 4: real writer, appending into the shared output file.
                # SQLiteDBWriter's own _write_experiment_metadata() uses
                # "INSERT OR IGNORE"-equivalent existence checks, so calling
                # write_events() once per channel against the same Output
                # File correctly accumulates multiple experiments/channels
                # into one database rather than overwriting it.
                writer = SQLiteDBWriter(
                    _build_settings(
                        SQLiteDBWriter,
                        {
                            "MetaEventFitter": fitter,
                            "Output File": str(out_path),
                            "Experiment Name": exp_name,
                            "Voltage": exp_result.voltage,
                            "Membrane Thickness": exp_result.thickness,
                            "Conductivity": exp_result.conductivity,
                        },
                    )
                )
                for _ in writer.write_events(channel_id):
                    pass

                # Ground truth must reflect only what's actually IN the
                # committed database. Before reject_event_indices existed,
                # every raw event always survived fitting (n_good ==
                # num_events always), so taking event_length from every
                # raw_db[channel_id].events entry happened to be correct
                # by coincidence. With some events now deliberately
                # rejected, n_good < num_events is possible, and blindly
                # keeping every raw event's length here would silently
                # include rejected events' data in ground truth queries
                # like median_duration_us() -- confirmed via a direct
                # check against fitter.event_metadata[channel][index]
                # (each entry's real "event_id" value, not the dict's
                # own index keys) that this is the correct, and only
                # reliable, way to know exactly which raw events actually
                # survived.
                surviving_ids = {
                    v["event_id"] for v in fitter.event_metadata[channel_id].values()
                }
                surviving_events = [
                    ev
                    for ev in raw_db[channel_id].events
                    if ev.event_id in surviving_ids
                ]
                event_lengths = [ev.event_length for ev in surviving_events]
                event_ids_list = [ev.event_id for ev in surviving_events]
                assert len(event_lengths) == n_good, (
                    f"Internal consistency check failed: {len(event_lengths)} "
                    f"surviving event lengths but fitter reports {n_good} good "
                    f"events for experiment '{exp_name}' channel {channel_id}"
                )
                exp_result.channels[channel_id] = SyntheticMetadataChannel(
                    channel_id=channel_id,
                    samplerate=samplerate,
                    num_events=n_good,
                    event_lengths_samples=event_lengths,
                    event_ids=event_ids_list,
                )

                raw_events_path.unlink(missing_ok=True)

            result.experiments[exp_name] = exp_result
    finally:
        for logger, original_level in quiet_loggers:
            logger.setLevel(original_level)

    return result


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db = generate_metadata_database(
            Path(tmp) / "synthetic_metadata.sqlite3",
            experiments=[
                {
                    "name": "exp_a",
                    "channels": [
                        {
                            "channel_id": 0,
                            "num_events": 25,
                            "event_length_range_samples": (100, 500),
                            "seed": 1,
                        },
                        {
                            "channel_id": 1,
                            "num_events": 15,
                            "event_length_range_samples": (100, 500),
                            "seed": 2,
                        },
                    ],
                },
                {
                    "name": "exp_b",
                    "channels": [
                        {
                            "channel_id": 0,
                            "num_events": 10,
                            "event_length_range_samples": (100, 500),
                            "seed": 3,
                        },
                    ],
                },
            ],
        )
        print("db:", db.db_path, db.db_path.stat().st_size, "bytes")
        for exp_name, exp in db.experiments.items():
            print(f"  experiment {exp_name}: {exp.total_num_events} total events")
            for ch_id, ch in exp.channels.items():
                print(
                    f"    channel {ch_id}: {ch.num_events} fit events, "
                    f"lengths range {min(ch.event_lengths_samples)}-"
                    f"{max(ch.event_lengths_samples)} samples"
                )
