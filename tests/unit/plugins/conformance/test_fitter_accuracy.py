"""
Ground truth for the event fitters: fitted values against planted ones.

The conformance suite asserts level *counts*. These tests plant a three-step staircase
with known currents and widths, pass it through the shipped Bessel filter so the edges
carry a realistic rise time, drive each fitter through the real loader, and compare what
it reports - sublevel current, blockage, duration and the level count - with what was
planted, event by event and sublevel by sublevel.

The bounds are the 2.1 tolerance policy (ruling A, re-measured on filtered data on
2026-10-05): fixtures Bessel-filtered at 100 kHz with Rise Time 16 µs, CUSUM step 100 pA and
ClassicCUSUM step 10 σ; current and blockage within 1.0 σ of the stored (post-filter) sigma
at 83-sample steps and 2.0 σ at 40-sample steps; duration within 2 samples at 15 pA drawn
noise and 12 samples at 50 pA; the level count exact on every event at 15 pA and on at
least 24 of 25 at 50 pA, the missing event named. A median over low-pass noise has far
fewer effective samples than the step is wide, which is why the bounds are wider than the
white-noise intuition and narrower at wider steps.

These tests name their plugins. They are parametrised over an explicit list - the CUSUM
family and NoFitter - and never over ``discover_concrete(MetaEventFitter)``: a planted
staircase is a statement about step-detection fitters, and a future fitter that models
events differently is not wrong for failing it. A new plugin opts in by being added to the
list; contract and failure-path tests stay family-wide (``DECISIONS.md``, 2026-10-06).

Bands a fitter was never meant for are recorded as strict expected failures rather than
left out: ClassicCUSUM at 100 pA (its 10 σ threshold exceeds the 150 pA step) and the
rest of the CUSUM family at 100 pA (an informative band). Three marks this file used to
carry are gone. ClassicCUSUM resolving fewer levels at *higher* SNR and every CUSUM
variant failing 20-sample steps were one defect: the detector did not restart its
statistics after a crossing the rise-time guard rejected, so a large edge left it blind
to the steps behind it. NoFitter's short-event failures were its walk to the baseline
*mean*, a coin flip per sample on low-pass noise that put both edges a random distance
early and cut the same random number of samples off the blockage median; its edges are
now walked by the slope of each edge.
"""

from typing import Callable, Dict, List, Tuple, Type

import numpy as np
import pytest

from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventfitters.ClassicCUSUM import ClassicCUSUM
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventfitters.IntraCUSUM import IntraCUSUM
from poriscope.plugins.eventfitters.NoFitter import NoFitter
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from tests.synthetic_data.base_synthetic_recording import SyntheticDataset
from tests.synthetic_data.synthetic_chimera import (
    ChimeraRecordingConfig,
    generate_chimera_dataset,
)
from tests.synthetic_data.synthetic_events_db import (
    SyntheticEventsDatabase,
    build_bessel_filter,
    generate_events_database,
)
from tests.unit.plugins.conformance._recipes import (
    build_event_finder,
    build_event_loader,
    build_reader,
    build_writer,
)

pytestmark = pytest.mark.conformance

# --- the planted recording ---------------------------------------------------------------
SAMPLERATE_HZ = 500_000.0
DT_US = 1e6 / SAMPLERATE_HZ
CHANNEL = 0
NUM_EVENTS = 25
PADDING_SAMPLES = 100
BASELINE_PA = 2000.0
AMPLITUDE_PA = -400.0
#: Three steps 150 pA apart inside the blockage.
STAIRCASE_PA = [0.0, -150.0, -300.0]
#: The shipped BesselFilter at this cutoff puts its -3 dB point near 53 kHz and gives a
#: 10-90% rise of about 3 samples at 500 kHz.
BESSEL_CUTOFF_HZ = 100_000.0

# --- fitter settings a user would choose for data filtered like this ---------------------
RISE_TIME_US = 16.0
_CUSUM_COMMON = {"Rise Time": RISE_TIME_US, "Sensitivity": 1.0, "Max Sublevels": 10}
FITTER_SETTINGS: Dict[str, Dict[str, object]] = {
    "CUSUM": {**_CUSUM_COMMON, "Step Size": 100.0},  # pA
    "ClassicCUSUM": {**_CUSUM_COMMON, "Step Size": 10.0},  # sigma
    "IntraCUSUM": {
        **_CUSUM_COMMON,
        "Step Size": 100.0,
        "Intraevent Threshold": 0.0,
        "Intraevent Hysteresis": 0.0,
    },
    "NoFitter": {},
}

CUSUM_FAMILY: List[Type[MetaEventFitter]] = [CUSUM, ClassicCUSUM, IntraCUSUM]

# --- bands ------------------------------------------------------------------------------
#: (drawn noise in pA, event length in samples). 250 -> 83/83/84-sample steps,
#: 120 -> 40/40/40, 60 -> 20/20/20. The 20-sample band is required since the detector
#: learned to restart after a rejected crossing: every CUSUM variant resolves it.
Band = Tuple[float, int]
REQUIRED_BANDS: List[Band] = [
    (15.0, 250),
    (50.0, 250),
    (15.0, 120),
    (50.0, 120),
    (15.0, 60),
]
INFORMATIVE_BANDS: List[Band] = [(100.0, 250)]


def step_width(length: int) -> int:
    """
    Return the width of the first planted step for an event length.

    :param length: the blockage length in samples
    :type length: int
    :return: ``length // 3``
    :rtype: int
    """
    return length // len(STAIRCASE_PA)


def current_bound_sigma(length: int) -> float:
    """
    Return the current and blockage bound, in stored sigmas, for a step width.

    :param length: the blockage length in samples
    :type length: int
    :return: 1.0 at 83-sample steps, 2.0 at 40-sample steps
    :rtype: float
    """
    return 1.0 if step_width(length) >= 80 else 2.0


def duration_bound_samples(noise: float) -> int:
    """
    Return the duration bound, in samples, for a drawn noise level.

    :param noise: the drawn (pre-filter) noise sigma in pA
    :type noise: float
    :return: 2 at 15 pA, 12 at 50 pA
    :rtype: int
    """
    return 2 if noise <= 15.0 else 12


def allowed_count_misses(noise: float) -> int:
    """
    Return how many events may miss the planted level count at a noise level.

    :param noise: the drawn (pre-filter) noise sigma in pA
    :type noise: float
    :return: 0 at 15 pA, 1 at 50 pA
    :rtype: int
    """
    return 0 if noise <= 15.0 else 1


# --- fixtures ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def filtered_staircase(
    tmp_path_factory: pytest.TempPathFactory,
) -> Dict[Band, SyntheticEventsDatabase]:
    """
    Generate one Bessel-filtered staircase database per band, once per session.

    :param tmp_path_factory: pytest's session temporary-directory factory
    :type tmp_path_factory: pytest.TempPathFactory
    :return: the ground-truth database object per ``(noise, length)`` band
    :rtype: Dict[Tuple[float, int], SyntheticEventsDatabase]
    """
    out = tmp_path_factory.mktemp("filtered_staircases")
    databases: Dict[Band, SyntheticEventsDatabase] = {}
    for noise, length in REQUIRED_BANDS + INFORMATIVE_BANDS:
        databases[(noise, length)] = generate_events_database(
            out / f"noise{int(noise)}_len{length}.sqlite",
            channel_id=CHANNEL,
            num_events=NUM_EVENTS,
            samplerate=SAMPLERATE_HZ,
            baseline_mean_pA=BASELINE_PA,
            baseline_std_pA=noise,
            event_amplitude_pA=AMPLITUDE_PA,
            event_length_samples=length,
            padding_samples=PADDING_SAMPLES,
            sublevel_amplitudes_pA=STAIRCASE_PA,
            bessel_cutoff_hz=BESSEL_CUTOFF_HZ,
        )
    return databases


def build_fitter(
    fitter_cls: Type[MetaEventFitter], loader: MetaEventLoader
) -> MetaEventFitter:
    """
    Build a fitter standalone with the filtered-data settings above.

    Mirrors the conformance recipe builder, but with settings chosen for a filtered
    recording rather than the sharp-edged one the conformance fixtures plant.

    :param fitter_cls: the fitter class under test
    :type fitter_cls: Type[MetaEventFitter]
    :param loader: the event loader opened on the band's database
    :type loader: MetaEventLoader
    :return: a fitter with settings applied, ready for ``fit_events``
    :rtype: MetaEventFitter
    """
    fitter = fitter_cls()
    settings = fitter.get_empty_settings(standalone=True)
    settings["MetaEventLoader"]["Value"] = loader
    settings["MetaEventLoader"]["Type"] = None
    for key, value in FITTER_SETTINGS[fitter_cls.__name__].items():
        settings[key]["Value"] = value
    fitter.apply_settings(settings)
    return fitter


class Fit:
    """One fitter run over one band's database, with the planted truth beside it."""

    def __init__(
        self, fitter_cls: Type[MetaEventFitter], database: SyntheticEventsDatabase
    ) -> None:
        """
        Fit every event of the database with the given fitter.

        :param fitter_cls: the fitter class under test
        :type fitter_cls: Type[MetaEventFitter]
        :param database: the band's ground-truth database
        :type database: SyntheticEventsDatabase
        """
        self.database = database
        self.events = database[CHANNEL].events
        self.sigma = self.events[0].baseline_std  # stored, post-filter
        self.loader = build_event_loader(str(database.db_path))
        self.fitter = build_fitter(fitter_cls, self.loader)
        for _progress in self.fitter.fit_events(CHANNEL):
            pass

    def close(self) -> None:
        """
        Release the fitter and loader.

        :return: None
        :rtype: None
        """
        self.fitter.close_resources()
        self.loader.close_resources()

    def fitted_ids(self) -> List[int]:
        """
        Return the ids of the events the fitter kept, in order.

        :return: event ids with metadata
        :rtype: List[int]
        """
        return sorted(self.fitter.event_metadata[CHANNEL].keys())

    def inner(self, event_id: int, key: str) -> np.ndarray:
        """
        Return one sublevel metadata column for an event, paddings excluded.

        :param event_id: the event
        :type event_id: int
        :param key: the sublevel metadata key
        :type key: str
        :return: the values for the inner sublevels only
        :rtype: numpy.ndarray
        """
        _event_meta, sublevel_meta, _f, _r, _fit = (
            self.fitter.get_single_event_metadata(CHANNEL, event_id)
        )
        return np.asarray(sublevel_meta[key], dtype=float)[1:-1]

    def miscounted(self, expected: int) -> List[int]:
        """
        Return the ids of events whose inner sublevel count is not ``expected``.

        :param expected: the planted inner sublevel count
        :type expected: int
        :return: offending event ids
        :rtype: List[int]
        """
        return [
            event_id
            for event_id in self.fitted_ids()
            if self.inner(event_id, "sublevel_current").size != expected
        ]


# --- parametrisation --------------------------------------------------------------------
def _band_id(band: Band) -> str:
    noise, length = band
    return f"noise{int(noise)}pA-steps{step_width(length)}"


def _xfail(reason: str) -> pytest.MarkDecorator:
    # raises=AssertionError: a strict xfail otherwise accepts any exception, so a test that
    # cannot even run - a typo, a fixture that fails to build - would pass as the
    # accuracy limit it names.
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)


CLASSIC_THRESHOLD_ABOVE_STEP = _xfail(
    "ClassicCUSUM at Step Size 10 sigma: 416 pA threshold exceeds the 150 pA planted step"
)


def cusum_cases() -> List[object]:
    """
    Build the (fitter, band) parameters for the CUSUM family with the expected failures marked.

    :return: ``pytest.param`` entries
    :rtype: List[object]
    """
    cases: List[object] = []
    for fitter_cls in CUSUM_FAMILY:
        for band in REQUIRED_BANDS + INFORMATIVE_BANDS:
            noise, length = band
            marks: List[pytest.MarkDecorator] = []
            if fitter_cls is ClassicCUSUM and noise == 100.0:
                marks.append(CLASSIC_THRESHOLD_ABOVE_STEP)
            elif noise == 100.0:
                marks.append(
                    _xfail(
                        "100 pA drawn noise is an informative band: 11/25 level counts"
                    )
                )
            cases.append(
                pytest.param(
                    fitter_cls,
                    band,
                    marks=marks,
                    id=f"{fitter_cls.__name__}-{_band_id(band)}",
                )
            )
    return cases


@pytest.fixture(scope="module")
def fits() -> Dict[Tuple[str, Band], Fit]:
    """
    Cache one fit per (fitter, band) for the module, closing them at the end.

    :return: a mutable cache the tests fill through :func:`fit_for`
    :rtype: Dict[Tuple[str, Tuple[float, int]], Fit]
    """
    cache: Dict[Tuple[str, Band], Fit] = {}
    yield cache
    for fit in cache.values():
        fit.close()


def fit_for(
    fits: Dict[Tuple[str, Band], Fit],
    filtered_staircase: Dict[Band, SyntheticEventsDatabase],
    fitter_cls: Type[MetaEventFitter],
    band: Band,
) -> Fit:
    """
    Return the cached fit for a (fitter, band), running it on first use.

    :param fits: the module cache
    :type fits: Dict[Tuple[str, Tuple[float, int]], Fit]
    :param filtered_staircase: the per-band databases
    :type filtered_staircase: Dict[Tuple[float, int], SyntheticEventsDatabase]
    :param fitter_cls: the fitter class
    :type fitter_cls: Type[MetaEventFitter]
    :param band: ``(noise, length)``
    :type band: Tuple[float, int]
    :return: the fit
    :rtype: Fit
    """
    key = (fitter_cls.__name__, band)
    if key not in fits:
        fits[key] = Fit(fitter_cls, filtered_staircase[band])
    return fits[key]


# --- the CUSUM family -------------------------------------------------------------------
@pytest.mark.parametrize("fitter_cls, band", cusum_cases())
def test_the_level_count_matches_the_planted_staircase(
    fits, filtered_staircase, fitter_cls: Type[MetaEventFitter], band: Band
) -> None:
    """
    Every event has the three planted inner sublevels, with the one allowance the policy
    makes at 50 pA named by event id.
    """
    noise, _length = band
    fit = fit_for(fits, filtered_staircase, fitter_cls, band)
    assert fit.fitter.get_eventfitting_status(CHANNEL) is True
    assert fit.fitter.rejected.get(CHANNEL, {}) == {}, fit.fitter.report_channel_status(
        CHANNEL
    )
    assert len(fit.fitted_ids()) == NUM_EVENTS
    misses = fit.miscounted(len(STAIRCASE_PA))
    assert len(misses) <= allowed_count_misses(
        noise
    ), f"{fitter_cls.__name__} missed the planted level count on events {misses}"


@pytest.mark.parametrize("fitter_cls, band", cusum_cases())
def test_sublevel_currents_and_blockages_match_the_planted_levels(
    fits, filtered_staircase, fitter_cls: Type[MetaEventFitter], band: Band
) -> None:
    """
    On every event with the right level count, each sublevel's current is within the
    bound of its planted level and its blockage within the bound of the planted drop.
    """
    _noise, length = band
    fit = fit_for(fits, filtered_staircase, fitter_cls, band)
    bound = current_bound_sigma(length) * fit.sigma
    misses = set(fit.miscounted(len(STAIRCASE_PA)))
    checked = 0
    for event_id in fit.fitted_ids():
        if event_id in misses:
            continue
        planted = fit.events[event_id].planted_sublevels()
        currents = fit.inner(event_id, "sublevel_current")
        blockages = fit.inner(event_id, "sublevel_blockage")
        for (_start, _width, level), current, blockage in zip(
            planted, currents, blockages, strict=True
        ):
            assert abs(current - level) <= bound, (
                f"event {event_id}: current {current:.1f} vs planted {level:.1f} pA, "
                f"bound {bound:.1f} pA ({current_bound_sigma(length)} sigma of {fit.sigma:.2f})"
            )
            assert abs(blockage - (BASELINE_PA - level)) <= bound, (
                f"event {event_id}: blockage {blockage:.1f} vs planted "
                f"{BASELINE_PA - level:.1f} pA, bound {bound:.1f} pA"
            )
        checked += 1
    assert checked >= NUM_EVENTS - allowed_count_misses(band[0])


@pytest.mark.parametrize("fitter_cls, band", cusum_cases())
def test_sublevel_durations_match_the_planted_widths(
    fits, filtered_staircase, fitter_cls: Type[MetaEventFitter], band: Band
) -> None:
    """Each sublevel's duration is within the band's bound of its planted width."""
    noise, _length = band
    fit = fit_for(fits, filtered_staircase, fitter_cls, band)
    bound = duration_bound_samples(noise)
    misses = set(fit.miscounted(len(STAIRCASE_PA)))
    checked = 0
    for event_id in fit.fitted_ids():
        if event_id in misses:
            continue
        checked += 1
        planted = fit.events[event_id].planted_sublevels()
        durations = fit.inner(event_id, "sublevel_duration") / DT_US
        for (_start, width, _level), duration in zip(planted, durations, strict=True):
            assert abs(duration - width) <= bound, (
                f"event {event_id}: duration {duration:.1f} vs planted {width} samples, "
                f"bound {bound}"
            )
    # A band where no event had the planted level count must not pass vacuously.
    assert checked >= NUM_EVENTS - allowed_count_misses(noise)


# --- NoFitter ---------------------------------------------------------------------------
def nofitter_cases() -> List[object]:
    """
    Build NoFitter's band parameters: every band, none expected to fail.

    :return: ``pytest.param`` entries
    :rtype: List[object]
    """
    return [
        pytest.param(band, id=_band_id(band))
        for band in REQUIRED_BANDS + INFORMATIVE_BANDS
    ]


@pytest.mark.parametrize("band", nofitter_cases())
def test_nofitter_reports_the_whole_blockage_at_its_planted_mean(
    fits, filtered_staircase, band: Band
) -> None:
    """
    NoFitter sees one inner sublevel; its current is the width-weighted mean of the
    planted steps within the policy's bound for the step width (a median over 40
    correlated samples has about five effective ones, the same reason the CUSUM family
    gets 2.0 sigma there), its duration the blockage length within three samples, and its
    reported baseline sigma the planted one within 30% per event and 10% on average: a
    100-sample padding of low-pass noise holds about a dozen effective samples, so each
    event's estimate scatters low, where the edge used to inflate it threefold.
    """
    _noise, length = band
    fit = fit_for(fits, filtered_staircase, NoFitter, band)
    assert fit.fitter.rejected.get(CHANNEL, {}) == {}
    assert fit.miscounted(1) == []
    bound = current_bound_sigma(length) * fit.sigma
    sigma_ratios = []
    for event_id in fit.fitted_ids():
        planted = fit.events[event_id].planted_sublevels()
        mean_level = sum(width * level for _s, width, level in planted) / length
        current = fit.inner(event_id, "sublevel_current")[0]
        duration = fit.inner(event_id, "sublevel_duration")[0] / DT_US
        event_meta, _s, _f, _r, _fit = fit.fitter.get_single_event_metadata(
            CHANNEL, event_id
        )
        assert abs(current - mean_level) <= bound, (
            f"event {event_id}: whole-blockage current {current:.1f} vs planted mean "
            f"{mean_level:.1f} pA, bound {bound:.1f} pA"
        )
        assert abs(duration - length) <= 3, (event_id, duration, length)
        sigma_ratios.append(event_meta["baseline_stdev"] / fit.sigma)
        assert abs(sigma_ratios[-1] - 1.0) <= 0.3, (
            f"event {event_id}: baseline_stdev {event_meta['baseline_stdev']:.2f} vs "
            f"planted sigma {fit.sigma:.2f}"
        )
    assert abs(float(np.mean(sigma_ratios)) - 1.0) <= 0.1, sigma_ratios


@pytest.fixture(scope="module")
def slow_edge_database(
    tmp_path_factory: pytest.TempPathFactory,
) -> SyntheticEventsDatabase:
    """
    A flat blockage filtered at 20 kHz, whose edges rise over about 16 samples.

    Slow enough that where a fitter puts each edge is unambiguous in the data.

    :param tmp_path_factory: pytest's session temporary-directory factory
    :type tmp_path_factory: pytest.TempPathFactory
    :return: the ground-truth database
    :rtype: SyntheticEventsDatabase
    """
    return generate_events_database(
        tmp_path_factory.mktemp("slow_edges") / "slow_edges.sqlite",
        channel_id=CHANNEL,
        num_events=10,
        samplerate=SAMPLERATE_HZ,
        baseline_mean_pA=BASELINE_PA,
        baseline_std_pA=15.0,
        event_amplitude_pA=AMPLITUDE_PA,
        event_length_samples=250,
        padding_samples=PADDING_SAMPLES,
        bessel_cutoff_hz=20_000.0,
    )


def test_nofitter_places_its_edges_where_each_edge_begins(
    slow_edge_database: SyntheticEventsDatabase,
) -> None:
    """
    The start sits where the signal leaves baseline and the end where the return begins.

    The filter is zero-phase, so the planted boundary is the 50% point of each edge, and
    both of NoFitter's edges should sit before their planted boundary by the same amount:
    less than the edge's full extent (about 30 samples top to foot at this cutoff) and
    equal to each other within four samples, so the duration is the planted one.
    """
    fit = Fit(NoFitter, slow_edge_database)
    try:
        for event_id in fit.fitted_ids():
            (planted_start, width, _level) = fit.events[event_id].planted_sublevels()[0]
            start = fit.inner(event_id, "sublevel_start_times")[0] / DT_US
            end = fit.inner(event_id, "sublevel_end_times")[0] / DT_US
            start_offset = start - planted_start
            end_offset = end - (planted_start + width)
            assert -30 <= start_offset <= 0, (event_id, start_offset)
            assert -30 <= end_offset <= 0, (event_id, end_offset)
            assert abs(start_offset - end_offset) <= 4, (
                f"event {event_id}: start offset {start_offset:+.1f}, "
                f"end offset {end_offset:+.1f} samples - the edges do not shift alike"
            )
    finally:
        fit.close()


# --- NoFitter behind a real finder --------------------------------------------------------
@pytest.fixture(scope="module")
def found_recording(
    tmp_path_factory: pytest.TempPathFactory,
) -> Tuple[SyntheticDataset, str, Callable[[np.ndarray], np.ndarray]]:
    """
    A synthetic Chimera recording found by ``ClassicBlockageFinder`` at a 20 kHz cutoff and written out.

    This is the chain a user runs - reader, finder with a filter, event writer - so the
    events database carries exactly the boundaries the finder reports, at the tops of
    the edges, and the loader hands NoFitter the windows the finder cut.

    :param tmp_path_factory: pytest's session temporary-directory factory
    :type tmp_path_factory: pytest.TempPathFactory
    :return: the planted recording, the events database path and the filter the finder used
    :rtype: Tuple[SyntheticDataset, str, Callable[[numpy.ndarray], numpy.ndarray]]
    """
    out = tmp_path_factory.mktemp("found_recording")
    samplerate = 500_000.0
    dataset = generate_chimera_dataset(
        out / "recording",
        ChimeraRecordingConfig(
            base_name="synthetic",
            samplerate=samplerate,
            duration_s=0.5,
            baseline=BASELINE_PA,
            noise_std=15.0,
            event_amplitude=AMPLITUDE_PA,
            event_duration_s=0.0005,
        ),
        channel=3,
        num_events=10,
    )
    bessel = build_bessel_filter(samplerate, 20_000.0, 8).filter_data
    reader = build_reader(str(dataset.data_path))
    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(3, [(0.0, 0.0)], 0.5, bessel):
        pass
    db_path = out / "events.sqlite"
    writer = build_writer(SQLiteEventWriter, finder, str(db_path))
    for _progress in writer.commit_events(3):
        pass
    writer.close_resources()
    finder.close_resources()
    reader.close_resources()
    return dataset, str(db_path), bessel


def test_nofitter_edges_do_not_depend_on_where_the_finder_put_its_boundaries(
    found_recording: Tuple[SyntheticDataset, str, Callable[[np.ndarray], np.ndarray]],
) -> None:
    """
    Behind a real finder, NoFitter's edges sit where the signal leaves and rejoins the
    blocked level, not where the finder's noisy boundary walk stopped.

    The finder's boundaries here are tens of samples outside the planted edges (the test
    checks that, so it is testing what it claims); NoFitter's start and end must both sit
    within the edge's extent before the planted 50% points, within six samples of each
    other, and the blocked current within a sigma of the planted level.
    """
    dataset, db_path, bessel = found_recording
    loader = build_event_loader(db_path)
    fitter = build_fitter(NoFitter, loader)
    try:
        for _progress in fitter.fit_events(3, data_filter=bessel):
            pass
        assert fitter.rejected.get(3, {}) == {}
        finder_offsets = []
        for index in sorted(fitter.event_metadata[3]):
            event = loader.load_event(3, index, None)
            window_start = int(event["absolute_start"])
            planted = min(
                dataset.events,
                key=lambda p: abs(
                    p.start_index - (window_start + event["padding_before"])
                ),
            )
            planted_start = planted.start_index - window_start
            planted_end = planted_start + planted.length_samples
            finder_offsets.append(event["padding_before"] - planted_start)
            finder_offsets.append(
                len(event["data"]) - event["padding_after"] - planted_end
            )
            _event_meta, sublevel_meta, _f, _r, _fit = fitter.get_single_event_metadata(
                3, index
            )
            start = sublevel_meta["sublevel_start_times"][1] * 500_000.0 / 1e6
            end = sublevel_meta["sublevel_end_times"][1] * 500_000.0 / 1e6
            start_offset = start - planted_start
            end_offset = end - planted_end
            assert -30 <= start_offset <= 0, (index, start_offset)
            assert -30 <= end_offset <= 0, (index, end_offset)
            assert abs(start_offset - end_offset) <= 6, (
                index,
                start_offset,
                end_offset,
            )
            current = sublevel_meta["sublevel_current"][1]
            assert (
                abs(current - (BASELINE_PA + AMPLITUDE_PA)) <= event["baseline_std"]
            ), (
                index,
                current,
            )
        # the finder marks where the signal rejoins the baseline, after the trailing edge;
        # NoFitter marks where the return begins, before it - the two mean different things
        assert np.mean(finder_offsets[1::2]) > 5, finder_offsets
    finally:
        fitter.close_resources()
        loader.close_resources()


def test_the_finder_places_its_boundaries_where_the_signal_leaves_and_rejoins_the_baseline(
    found_recording: Tuple[SyntheticDataset, str, Callable[[np.ndarray], np.ndarray]],
) -> None:
    """
    Behind a 20 kHz filter the finder's start sits at the top of the leading edge and its
    end at the top of the trailing edge, each within the edge's extent of the planted
    boundary and consistent from event to event, where the +1 sigma walk used to run up to
    hundreds of samples into the baseline.
    """
    dataset, db_path, _bessel = found_recording
    loader = build_event_loader(db_path)
    try:
        starts, ends = [], []
        for index in range(loader.get_num_events(3)):
            event = loader.load_event(3, index, None)
            window_start = int(event["absolute_start"])
            planted = min(
                dataset.events,
                key=lambda p: abs(
                    p.start_index - (window_start + event["padding_before"])
                ),
            )
            planted_start = planted.start_index - window_start
            planted_end = planted_start + planted.length_samples
            starts.append(event["padding_before"] - planted_start)
            ends.append(len(event["data"]) - event["padding_after"] - planted_end)
        assert len(starts) == len(dataset.events)
        assert all(-30 <= s <= 0 for s in starts), starts
        assert all(0 <= e <= 30 for e in ends), ends
        assert max(starts) - min(starts) <= 10, starts
        assert max(ends) - min(ends) <= 10, ends
    finally:
        loader.close_resources()
