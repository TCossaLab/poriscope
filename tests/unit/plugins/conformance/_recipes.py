"""
Settings recipes for driving real data plugins against synthetic data.

The conformance suite needs a *valid* settings dict for every plugin it drives.
That cannot be derived from ``get_empty_settings()`` alone, for three reasons
worth stating here so nobody re-attempts it:

- ``Options`` on a file parameter is a Qt file-dialog filter glob
  (``['SQLite3 Files (*.sqlite3)']``), not a set of permitted values.
  ``BaseDataPlugin._validate_param_ranges`` exempts ``Input File``/``Output File``
  from its ``Options`` membership check for exactly this reason.
- Most numeric parameters declare ``Max`` as ``None``, so there is no midpoint to
  pick.
- A parameter naming a parent plugin declares ``Type`` ``str`` - describing the
  pre-resolution dropdown key - while the family validator requires a live object
  inheriting the ``Meta*`` base, and the caller must also reset ``Type`` to
  ``None``. ``DataPluginController`` does this in the app; the builders below
  mirror it.

Values are not invented here either. The CUSUM numbers are the ones
``tests/integration/flows/`` and ``tests/e2e/event_analysis/`` already establish
against this same synthetic signal.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Type

from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from poriscope.utils.MetaFilter import MetaFilter
from poriscope.utils.MetaReader import MetaReader
from poriscope.utils.MetaWriter import MetaWriter
from poriscope.utils.plugin_schemas import discover_plugin_classes
from tests.synthetic_data.base_synthetic_recording import SyntheticDataset
from tests.synthetic_data.synthetic_abf2 import (
    Abf2RecordingConfig,
    generate_abf2_legacy_dataset,
    generate_abf2_modern_dataset,
)
from tests.synthetic_data.synthetic_binary import (
    BinaryReader1XConfig,
    SingleBinaryConfig,
    generate_binary_1x_dataset,
    generate_single_binary_dataset,
)
from tests.synthetic_data.synthetic_chimera import (
    ChimeraRecordingConfig,
    generate_chimera_20240101_dataset,
    generate_chimera_dataset,
)
from tests.synthetic_data.synthetic_chimera_vc100 import (
    ChimeraVC100RecordingConfig,
    generate_chimera_vc100_dataset,
)


def discover_concrete(base: type) -> List[type]:
    """
    Collect every instantiable subclass of a ``Meta*`` base, however deeply nested.

    Filters :func:`poriscope.utils.plugin_schemas.discover_plugin_classes` rather than
    walking ``__subclasses__()`` directly, so a plugin whose class name doesn't match its
    filename - which ``MainModel.populate_available_plugins`` would never actually load -
    is not silently included here either. That sweep already imports every module under
    ``poriscope.plugins``, which is what makes a deeply-nested subclass like
    ``BoundedBlockageFinder`` (extends ``ClassicBlockageFinder``) or
    ``ClassicCUSUM``/``IntraCUSUM`` (extend ``CUSUM``) visible in the first place.

    :param base: The ``Meta*`` base class to search beneath.
    :type base: type
    :return: Concrete subclasses, ordered by name so parametrised ids are stable.
    :rtype: List[type]
    """
    return sorted(
        (cls for cls in discover_plugin_classes().values() if issubclass(cls, base)),
        key=lambda cls: cls.__name__,
    )


# ===========================================================================
# Synthetic fixture parameters
# ===========================================================================
#
# Declared here rather than in conftest.py so that test modules and the fixtures
# can both import them as an ordinary module-level import. They match
# tests/integration/conftest.py and tests/e2e/raw_data/conftest.py deliberately, so
# a plugin behaves the same here as in those suites.
BASELINE_PA = 2000.0
NOISE_STD_PA = 15.0
EVENT_AMPLITUDE_PA = -400.0

# Events database: event loaders and event fitters
EVENTS_CHANNEL = 0
EVENTS_COUNT = 25
EVENTS_SAMPLERATE_HZ = 500_000.0

# A second events database, for peak-based fitters only (Basic_PeakFinder). A
# flat blockage has no resolvable local extremum for scipy.signal.find_peaks to
# find, so those fitters need a smooth sublevel dip inside the blockage - see
# generate_events_database's sublevel_dip_pA/sublevel_dip_width_samples and
# _build_event_trace's docstring for why the dip is a smooth taper rather than
# a rectangle. Kept as a separate database rather than added to the shared one
# above so the five fitters that already pass against a flat blockage are not
# put at any risk of a behaviour change from this.
PEAKED_EVENTS_DIP_PA = -150.0
PEAKED_EVENTS_DIP_WIDTH_SAMPLES = 60

# A third events database, for step-detection fitters only (the CUSUM family). A
# flat blockage has no internal transitions for a changepoint detector to count,
# so those fitters need a known number of discrete, resolvable levels instead -
# see generate_events_database's sublevel_amplitudes_pA and
# _build_event_trace's docstring for why this is a staircase of flat steps
# rather than PEAKED_EVENTS_DIP_PA's single smooth taper (which suits a
# peak-finder, not a step detector). Kept as a separate database rather than
# added to either existing one, for the same non-interference reason as
# PEAKED_EVENTS_DIP_PA above.
#
# 150 pA between consecutive levels was measured, not assumed: with 15 pA
# noise, spacing has to clear CUSUM/IntraCUSUM's Step Size (100 pA - the
# family's least sensitive setting) with real margin, and 4-5 levels measured
# one persistent single-event miss for ClassicCUSUM at this signal, so 3
# levels is what's used.
STAIRCASE_LEVEL_AMPLITUDES_PA = [0.0, -150.0, -300.0]

# Chimera recording: event finders (and the reader they hang off)
CHIMERA_CHANNEL = 3
CHIMERA_EVENTS = 5
CHIMERA_DURATION_S = 2.0
CHIMERA_SAMPLERATE_HZ = 4_000_000.0
CHIMERA_EVENT_DURATION_S = 0.0005

# Metadata database: database loaders
METADATA_EXPERIMENT = "exp_a"
METADATA_CHANNELS = (0, 1)
METADATA_EVENT_COUNTS = (25, 15)


# ===========================================================================
# Bookkeeping columns the base class adds to produced metadata
# ===========================================================================
#
# MetaEventFitter.fit_events injects identity columns into every event's and
# every sublevel's metadata (see MetaEventFitter.py, the assignments around the
# event_id/channel_id and level_id/levels_left writes). Of these, only
# "event_id" is added to the declared types/units dicts by
# _define_metadata_types/_define_metadata_units - the rest are structural, and
# SQLiteDBWriter carries channel_id on its own table rather than reading it out
# of metadata.
#
# Conformance therefore asks that every produced column *other than* these is
# declared, which is the part a subclass is responsible for.
INJECTED_EVENT_COLUMNS = frozenset({"channel_id", "event_id"})
INJECTED_SUBLEVEL_COLUMNS = frozenset(
    {"event_id", "channel_id", "level_id", "levels_left"}
)

# ===========================================================================
# Event fitters
# ===========================================================================

# Step Size is in pA for CUSUM and IntraCUSUM but in sigma for ClassicCUSUM
# (note its "Units" entry), so the same number cannot serve both: against this
# signal - 15 pA noise, 400 pA events, so roughly 27 sigma - 100.0 pA detects
# every step while 100.0 sigma detects none.
_CUSUM_COMMON: Dict[str, Any] = {
    "Rise Time": 10.0,
    "Sensitivity": 1.0,
    "Max Sublevels": 10,
}

EVENT_FITTER_SETTINGS: Dict[str, Dict[str, Any]] = {
    "CUSUM": dict(_CUSUM_COMMON, **{"Step Size": 100.0}),
    "ClassicCUSUM": dict(_CUSUM_COMMON, **{"Step Size": 3.0}),
    "IntraCUSUM": dict(
        _CUSUM_COMMON,
        **{
            "Step Size": 100.0,
            "Intraevent Threshold": 0.0,
            "Intraevent Hysteresis": 0.0,
        },
    ),
    "NanoTrees": {"Smallest Significant Sublevel": 200.0},
    "NoFitter": {},
    # Against the peaked-events database (PEAKED_EVENTS_DIP_PA/_WIDTH_SAMPLES,
    # FITTERS_USING_PEAKED_EVENTS below), not the shared flat one.
    "Basic_PeakFinder": {
        "Min Height": 100.0,
        "Min Prominence": 50.0,
        "Min Distance": 5.0,
    },
}

# Fitters that need the peaked-events database (a smooth intra-event dip, per
# PEAKED_EVENTS_DIP_PA/_WIDTH_SAMPLES) rather than the shared flat one. A flat
# blockage has no resolvable local extremum for a peak-based fitter to find.
FITTERS_USING_PEAKED_EVENTS = frozenset({"Basic_PeakFinder"})

# Fitters checked against a known planted *sublevel* count (the staircase
# database, STAIRCASE_LEVEL_AMPLITUDES_PA) rather than only a known *event*
# count - the step-detection family, whose whole job is counting internal
# level transitions.
FITTERS_USING_STAIRCASE_EVENTS = frozenset({"CUSUM", "ClassicCUSUM", "IntraCUSUM"})

# PeakFinder has no recipe above and is skipped, with the reason below
# surfaced by pytest_generate_tests. It was tried against the same peaked-events
# database Basic_PeakFinder uses and rejected all 25 events as "No Peaks Found"
# under every setting combination attempted - not a missing-fixture problem in
# the same sense as the other five originally were. Its internal minimum peak
# prominence, in PeakFinder._locate_sublevel_transitions, is derived from
# carrier_blockage - the depth of the blockage itself, ~400 pA here - not from
# the "Min Carrier Blockage" setting, which only gates whether the blockage
# qualifies as a carrier at all. A sublevel needs prominence comparable to the
# *full blockage depth* to register, so a modest internal dip can never clear
# it regardless of tuning. Making PeakFinder fit needs a structurally different
# fixture - something closer to a genuine two-level signal with both levels
# comparable in depth - and even that would only reach the entry point to its
# own downstream folded/unfolded and translocation-direction classification
# stages, which are unexplored.
FITTERS_SKIPPED = {
    "PeakFinder": (
        "needs a two-level signal comparable to the full blockage depth, not "
        "a modest intra-event dip - see FITTERS_SKIPPED in _recipes.py"
    ),
}


def build_event_loader(db_path: str) -> SQLiteEventLoader:
    """
    Build a ``SQLiteEventLoader`` over a synthetic events database.

    :param db_path: Path to the ``.sqlite3`` events database to open.
    :type db_path: str
    :return: A loader with settings applied and channel status initialised.
    :rtype: SQLiteEventLoader
    """
    loader = SQLiteEventLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(db_path)
    loader.apply_settings(settings)
    loader.report_channel_status(init=True)
    return loader


def build_event_fitter(
    fitter_cls: Type[MetaEventFitter], loader: MetaEventLoader
) -> MetaEventFitter:
    """
    Build an event fitter attached to a live event loader.

    Every parameter this plugin leaves unset must be covered by
    ``EVENT_FITTER_SETTINGS``; anything still ``None`` after applying the recipe
    raises rather than reaching ``apply_settings``, so a new fitter shows up as a
    missing recipe instead of an obscure validator error.

    :param fitter_cls: The event fitter class to instantiate.
    :type fitter_cls: Type[MetaEventFitter]
    :param loader: A configured event loader to attach as the fitter's parent.
    :type loader: MetaEventLoader
    :raises KeyError: If the class has no recipe in EVENT_FITTER_SETTINGS.
    :raises ValueError: If the recipe leaves a required parameter unset.
    :return: A fitter with settings applied, ready to fit.
    :rtype: MetaEventFitter
    """
    name = fitter_cls.__name__
    if name not in EVENT_FITTER_SETTINGS:
        raise KeyError(
            f"No conformance recipe for {name}. Add one to EVENT_FITTER_SETTINGS "
            f"(add its name to FITTERS_USING_PEAKED_EVENTS too if it needs a "
            f"resolvable intra-event dip rather than a flat blockage), or to "
            f"FITTERS_SKIPPED with a reason if the fixtures genuinely cannot "
            f"exercise it yet."
        )
    overrides = EVENT_FITTER_SETTINGS[name]

    fitter = fitter_cls()
    settings = fitter.get_empty_settings(standalone=True)
    settings["MetaEventLoader"]["Value"] = loader
    settings["MetaEventLoader"]["Type"] = None

    _fill(settings, overrides, name, parent_key="MetaEventLoader")
    fitter.apply_settings(settings)
    return fitter


def _fill(
    settings: Dict[str, Dict[str, Any]],
    overrides: Dict[str, Any],
    name: str,
    parent_key: str = "",
) -> None:
    """
    Apply ``overrides`` onto ``settings`` and refuse to leave anything unset.

    A parameter still ``None`` after the recipe has been applied would reach the
    validator as a type error naming nothing useful, so it is raised here instead:
    a plugin added without a recipe fails with a message saying so.

    :param settings: The schema returned by ``get_empty_settings``, modified in place.
    :type settings: Dict[str, Dict[str, Any]]
    :param overrides: Values to write into it, keyed by parameter name.
    :type overrides: Dict[str, Any]
    :param name: The plugin class name, for error messages.
    :type name: str
    :param parent_key: A parameter holding a live parent plugin, already set.
    :type parent_key: str
    :raises ValueError: If any parameter is left without a usable value.
    """
    unset = []
    for key, entry in settings.items():
        if key == parent_key:
            continue
        if key in overrides:
            entry["Value"] = overrides[key]
        elif entry.get("Value") is None:
            # .get(), not entry["Value"]: omitting the key and setting it to None
            # are both valid "no default" spellings (see settings_schema.py), and
            # real plugins use both - indexing directly would KeyError on the ones
            # that omit it.
            unset.append(key)
    if unset:
        raise ValueError(
            f"{name}'s conformance recipe leaves {sorted(unset)} unset and they have "
            f"no default. Add them to this module's recipe for that family."
        )


def _attach(settings: Dict[str, Dict[str, Any]], parent_key: str, parent: Any) -> None:
    """
    Point a settings entry at a live parent plugin instance.

    ``Type`` is reset to ``None`` because the declared ``str`` describes the
    pre-resolution dropdown key, not the resolved value; ``DataPluginController``
    does the same before calling ``apply_settings``.

    :param settings: The schema to modify in place.
    :type settings: Dict[str, Dict[str, Any]]
    :param parent_key: Name of the parameter naming the parent's Meta* family.
    :type parent_key: str
    :param parent: The live parent plugin instance.
    :type parent: Any
    """
    settings[parent_key]["Value"] = parent
    settings[parent_key]["Type"] = None


# ===========================================================================
# Filters
# ===========================================================================

# Filters are driven over an array built in the test rather than a file, so the
# sample rate is declared here and the test builds its data to match.
FILTER_SAMPLERATE_HZ = 4_000_000.0

FILTER_SETTINGS: Dict[str, Dict[str, Any]] = {
    "BesselFilter": {
        "Cutoff": 200_000.0,
        "Samplerate": FILTER_SAMPLERATE_HZ,
        "Poles": 8,
    },
    "WaveletFilter": {"Wavelet": "bior1.5"},
}


def build_filter(filter_cls: Type[MetaFilter]) -> MetaFilter:
    """
    Build a filter from its recipe.

    :param filter_cls: The filter class to instantiate.
    :type filter_cls: Type[MetaFilter]
    :raises KeyError: If the class has no recipe in FILTER_SETTINGS.
    :return: A filter with settings applied.
    :rtype: MetaFilter
    """
    name = filter_cls.__name__
    if name not in FILTER_SETTINGS:
        raise KeyError(f"No conformance recipe for {name}. Add one to FILTER_SETTINGS.")
    plugin = filter_cls()
    settings = plugin.get_empty_settings(standalone=True)
    _fill(settings, FILTER_SETTINGS[name], name)
    plugin.apply_settings(settings)
    return plugin


# ===========================================================================
# Readers and event finders
# ===========================================================================

# ThresholdBlockageFinder's Threshold is in sigma while its two siblings' is in pA
# (see its get_empty_settings, which overwrites the inherited "Units"). Against
# this signal - 15 pA noise, 400 pA events, so roughly 27 sigma - the pA-scaled
# 200.0 would be an unreachable threshold.
#
# 8.0 sigma rather than 3.0: at 3.0 the detector also trips on noise excursions, and
# although each is discarded as Too Short or Too Close, one of them landing beside a
# real event costs that event too - it found 4 of 5 on this recording. 8.0 is well
# clear of the noise and still far below the 27 sigma the events actually reach.
_BLOCKAGE_COMMON: Dict[str, Any] = {
    "Min Duration": 100.0,
    "Max Duration": 1_000_000.0,
    "Min Separation": 10.0,
}

EVENT_FINDER_SETTINGS: Dict[str, Dict[str, Any]] = {
    "ClassicBlockageFinder": dict(_BLOCKAGE_COMMON, **{"Threshold": 200.0}),
    "BoundedBlockageFinder": dict(
        _BLOCKAGE_COMMON,
        **{"Threshold": 200.0, "Min Baseline": 1_500.0, "Max Baseline": 2_500.0},
    ),
    "ThresholdBlockageFinder": dict(_BLOCKAGE_COMMON, **{"Threshold": 8.0}),
}


def build_reader(log_path: str) -> MetaReader:
    """
    Build a ``ChimeraReader20240501`` over a synthetic recording.

    Readers are not yet a conformance family of their own - that needs one synthetic
    writer per on-disk format - so this returns the single reader the other families
    need as a parent rather than being parametrised.

    :param log_path: Path to the synthetic Chimera ``.log``.
    :type log_path: str
    :return: A reader with settings applied and channel status initialised.
    :rtype: MetaReader
    """
    reader = ChimeraReader20240501()
    settings = reader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(log_path)
    reader.apply_settings(settings)
    reader.report_channel_status(init=True)
    return reader


def build_event_finder(
    finder_cls: Type[MetaEventFinder], reader: MetaReader
) -> MetaEventFinder:
    """
    Build an event finder attached to a live reader.

    :param finder_cls: The event finder class to instantiate.
    :type finder_cls: Type[MetaEventFinder]
    :param reader: A configured reader to attach as the finder's parent.
    :type reader: MetaReader
    :raises KeyError: If the class has no recipe in EVENT_FINDER_SETTINGS.
    :return: A finder with settings applied, ready to find events.
    :rtype: MetaEventFinder
    """
    name = finder_cls.__name__
    if name not in EVENT_FINDER_SETTINGS:
        raise KeyError(
            f"No conformance recipe for {name}. Add one to EVENT_FINDER_SETTINGS."
        )
    finder = finder_cls()
    settings = finder.get_empty_settings(standalone=True)
    _attach(settings, "MetaReader", reader)
    _fill(settings, EVENT_FINDER_SETTINGS[name], name, parent_key="MetaReader")
    finder.apply_settings(settings)
    return finder


# ===========================================================================
# Writers
# ===========================================================================

# Both writer families ask for the same four experiment-metadata parameters.
_EXPERIMENT_METADATA: Dict[str, Any] = {
    "Experiment Name": "conformance",
    "Voltage": 200.0,
    "Membrane Thickness": 10.0,
    "Conductivity": 1.0,
}


def build_writer(
    writer_cls: Type[MetaWriter], finder: MetaEventFinder, out_path: str
) -> MetaWriter:
    """
    Build an event writer attached to a live event finder.

    :param writer_cls: The writer class to instantiate.
    :type writer_cls: Type[MetaWriter]
    :param finder: A finder that has already located events.
    :type finder: MetaEventFinder
    :param out_path: Path the writer should write its database to.
    :type out_path: str
    :return: A writer with settings applied, ready to commit.
    :rtype: MetaWriter
    """
    writer = writer_cls()
    settings = writer.get_empty_settings(standalone=True)
    _attach(settings, "MetaEventFinder", finder)
    overrides = dict(_EXPERIMENT_METADATA, **{"Output File": str(out_path)})
    _fill(settings, overrides, writer_cls.__name__, parent_key="MetaEventFinder")
    writer.apply_settings(settings)
    return writer


def build_db_writer(
    writer_cls: Type[MetaDatabaseWriter], fitter: MetaEventFitter, out_path: str
) -> MetaDatabaseWriter:
    """
    Build a database writer attached to a live event fitter.

    :param writer_cls: The database writer class to instantiate.
    :type writer_cls: Type[MetaDatabaseWriter]
    :param fitter: A fitter that has already fitted events.
    :type fitter: MetaEventFitter
    :param out_path: Path the writer should write its database to.
    :type out_path: str
    :return: A writer with settings applied, ready to write.
    :rtype: MetaDatabaseWriter
    """
    writer = writer_cls()
    settings = writer.get_empty_settings(standalone=True)
    _attach(settings, "MetaEventFitter", fitter)
    overrides = dict(_EXPERIMENT_METADATA, **{"Output File": str(out_path)})
    _fill(settings, overrides, writer_cls.__name__, parent_key="MetaEventFitter")
    writer.apply_settings(settings)
    return writer


# ===========================================================================
# Loaders over an existing database
# ===========================================================================


def build_db_loader(
    loader_cls: Type[MetaDatabaseLoader], db_path: str
) -> MetaDatabaseLoader:
    """
    Build a database loader over a metadata database.

    :param loader_cls: The database loader class to instantiate.
    :type loader_cls: Type[MetaDatabaseLoader]
    :param db_path: Path to the metadata database to open.
    :type db_path: str
    :return: A loader with settings applied and channel status initialised.
    :rtype: MetaDatabaseLoader
    """
    loader = loader_cls()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(db_path)
    loader.apply_settings(settings)
    loader.report_channel_status(init=True)
    return loader


def build_any_event_loader(
    loader_cls: Type[MetaEventLoader], db_path: str
) -> MetaEventLoader:
    """
    Build any event loader over an events database.

    ``build_event_loader`` returns the concrete ``SQLiteEventLoader`` the fitter
    family needs as a parent; this one is parametrised for the loader family's own
    conformance checks.

    :param loader_cls: The event loader class to instantiate.
    :type loader_cls: Type[MetaEventLoader]
    :param db_path: Path to the events database to open.
    :type db_path: str
    :return: A loader with settings applied and channel status initialised.
    :rtype: MetaEventLoader
    """
    loader = loader_cls()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(db_path)
    loader.apply_settings(settings)
    loader.report_channel_status(init=True)
    return loader


# ===========================================================================
# Readers
# ===========================================================================
#
# Unlike every other family, a reader's fixture is not "settings tuned against
# a shared database" - it is a different *file format* per plugin, since that
# is the entire thing a reader varies over. Each entry below is a synthetic
# writer from tests/synthetic_data, covering one on-disk format; several
# readers can and do share one (ChimeraReader20240501 and ChimeraReader20240101
# read the identical ADC-code/gain-stack encoding, only the metadata's location
# differs). See each synthetic writer module's docstring for the full format
# derivation - most of it was reverse-engineered directly from the real parser
# rather than guessed, since a byte-format mismatch fails in ways ranging from
# a clear exception to a silently wrong signal.
#
# One shared signal shape (baseline, noise, amplitude) across every reader, so
# a plugin's behaviour is comparable format to format and consistent with
# every other synthetic fixture in this suite.
READER_BASELINE_PA = 2000.0
READER_NOISE_STD_PA = 15.0
READER_EVENT_AMPLITUDE_PA = -400.0
READER_EVENT_DURATION_S = 0.0005


def _chimera_20240501_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a ChimeraReader20240501 (.log + sidecar .json) fixture."""
    config = ChimeraRecordingConfig(
        samplerate=4_000_000.0,
        duration_s=0.5,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_chimera_dataset(out_dir, config, channel=3, num_events=5)


def _chimera_20240101_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a ChimeraReader20240101 (.log with embedded header) fixture."""
    config = ChimeraRecordingConfig(
        samplerate=4_000_000.0,
        duration_s=0.5,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_chimera_20240101_dataset(out_dir, config, channel=3, num_events=5)


def _chimera_vc100_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a ChimeraReaderVC100 (.log + sidecar .mat) fixture."""
    config = ChimeraVC100RecordingConfig(
        samplerate=1_000_000.0,
        duration_s=0.2,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_chimera_vc100_dataset(out_dir, config, num_events=5)


def _binary_1x_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a BinaryReader1X (headerless, interleaved big-endian f64) fixture."""
    config = BinaryReader1XConfig(
        samplerate=500_000.0,
        duration_s=0.2,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_binary_1x_dataset(out_dir, config, num_events=5)


def _single_binary_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a SingleBinaryDecoder (headerless little-endian f64) fixture."""
    config = SingleBinaryConfig(
        samplerate=500_000.0,
        duration_s=0.2,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_single_binary_dataset(out_dir, config, num_events=5)


def _abf2_modern_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a TCossaLabABFReader (2-channel ABF2) fixture."""
    config = Abf2RecordingConfig(
        samplerate=500_000.0,
        duration_s=0.2,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_abf2_modern_dataset(out_dir, config, num_events=5)


def _abf2_legacy_dataset(out_dir: Path) -> SyntheticDataset:
    """Build a LegacyElementsReader (1-channel ABF2) fixture."""
    config = Abf2RecordingConfig(
        samplerate=500_000.0,
        duration_s=0.2,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    return generate_abf2_legacy_dataset(out_dir, config, num_events=5)


READER_DATASET_BUILDERS: Dict[str, Callable[[Path], SyntheticDataset]] = {
    "ChimeraReader20240501": _chimera_20240501_dataset,
    "ChimeraReader20240101": _chimera_20240101_dataset,
    "ChimeraReaderVC100": _chimera_vc100_dataset,
    "BinaryReader1X": _binary_1x_dataset,
    "SingleBinaryDecoder": _single_binary_dataset,
    "TCossaLabABFReader": _abf2_modern_dataset,
    "LegacyElementsReader": _abf2_legacy_dataset,
}

# Settings beyond "Input File" a reader needs filled, computed from the
# dataset that was built for it. Only SingleBinaryDecoder needs one: its
# sample rate is a setting rather than something inferred from the file, and
# it has no default (the caller must supply it).
READER_EXTRA_SETTINGS: Dict[str, Callable[[SyntheticDataset], Dict[str, Any]]] = {
    "SingleBinaryDecoder": lambda dataset: {"Sampling Rate": dataset.samplerate},
}


def build_reader_dataset(
    reader_cls: Type[MetaReader], out_dir: Path
) -> SyntheticDataset:
    """
    Build the synthetic recording a reader class needs to open.

    :param reader_cls: The reader class under test.
    :type reader_cls: Type[MetaReader]
    :param out_dir: Directory to write the recording into.
    :type out_dir: Path
    :raises KeyError: If the class has no fixture in READER_DATASET_BUILDERS.
    :return: The dataset describing what was written and its ground truth.
    :rtype: SyntheticDataset
    """
    name = reader_cls.__name__
    if name not in READER_DATASET_BUILDERS:
        raise KeyError(
            f"No conformance fixture for {name}. Add one to "
            f"READER_DATASET_BUILDERS - see tests/synthetic_data for the "
            f"existing per-format writers, or add a new one if this reader's "
            f"on-disk format isn't covered yet."
        )
    return READER_DATASET_BUILDERS[name](out_dir)


def build_any_reader(
    reader_cls: Type[MetaReader], dataset: SyntheticDataset
) -> MetaReader:
    """
    Build a reader over a synthetic recording already written for it.

    :param reader_cls: The reader class to instantiate.
    :type reader_cls: Type[MetaReader]
    :param dataset: The recording to open, from build_reader_dataset.
    :type dataset: SyntheticDataset
    :return: A reader with settings applied and channel status initialised.
    :rtype: MetaReader
    """
    reader = reader_cls()
    settings = reader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(dataset.data_path)
    extra = READER_EXTRA_SETTINGS.get(reader_cls.__name__)
    if extra is not None:
        for key, value in extra(dataset).items():
            settings[key]["Value"] = value
    reader.apply_settings(settings)
    reader.report_channel_status(init=True)
    return reader
