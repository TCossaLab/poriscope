"""
Shared synthetic data for the conformance suite.

All fixtures here are session-scoped and read-only: the conformance checks drive
plugins *over* this data and write their own outputs to per-test paths, so building
each dataset once is safe and keeps the suite cheap. Every plugin instance is still
created per test, so no plugin state is shared.

The parameters live in ``_recipes.py`` rather than here, so that test modules can
import them as an ordinary module-level import instead of reaching into a conftest.
"""

from pathlib import Path

import pytest

from tests.synthetic_data.synthetic_chimera import (
    ChimeraRecordingConfig,
    generate_chimera_dataset,
)
from tests.synthetic_data.synthetic_events_db import generate_events_database
from tests.synthetic_data.synthetic_metadata_db import generate_metadata_database
from tests.unit.plugins.conformance._recipes import (
    BASELINE_PA,
    CHIMERA_CHANNEL,
    CHIMERA_DURATION_S,
    CHIMERA_EVENT_DURATION_S,
    CHIMERA_EVENTS,
    CHIMERA_SAMPLERATE_HZ,
    EVENT_AMPLITUDE_PA,
    EVENTS_CHANNEL,
    EVENTS_COUNT,
    EVENTS_SAMPLERATE_HZ,
    METADATA_CHANNELS,
    METADATA_EVENT_COUNTS,
    METADATA_EXPERIMENT,
    NOISE_STD_PA,
    PEAKED_EVENTS_DIP_PA,
    PEAKED_EVENTS_DIP_WIDTH_SAMPLES,
    PEAKFINDER_DIP_PA,
    PEAKFINDER_DIP_WIDTH_SAMPLES,
    STAIRCASE_LEVEL_AMPLITUDES_PA,
)


@pytest.fixture(scope="session")
def events_db_path(tmp_path_factory) -> str:
    """
    A single-channel events database with 25 known events at 500 kHz.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: Path to the written database.
    :rtype: str
    """
    out = tmp_path_factory.mktemp("conformance_events") / "events.sqlite3"
    database = generate_events_database(
        out,
        channel_id=EVENTS_CHANNEL,
        num_events=EVENTS_COUNT,
        samplerate=EVENTS_SAMPLERATE_HZ,
        baseline_mean_pA=BASELINE_PA,
        baseline_std_pA=NOISE_STD_PA,
        event_amplitude_pA=EVENT_AMPLITUDE_PA,
    )
    return str(database.db_path)


@pytest.fixture(scope="session")
def peaked_events_db_path(tmp_path_factory) -> str:
    """
    The same shape as ``events_db_path``, with a resolvable dip inside every
    blockage.

    For peak-based fitters (``FITTERS_USING_PEAKED_EVENTS`` in ``_recipes.py``):
    a flat blockage has no local extremum for ``scipy.signal.find_peaks`` to
    locate, so those fitters need this instead of the shared flat database.
    Kept as a second, separate database rather than added to the shared one so
    the fitters that already pass against a flat blockage are not put at any
    risk of a behaviour change from it.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: Path to the written database.
    :rtype: str
    """
    out = tmp_path_factory.mktemp("conformance_peaked_events") / "events.sqlite3"
    database = generate_events_database(
        out,
        channel_id=EVENTS_CHANNEL,
        num_events=EVENTS_COUNT,
        samplerate=EVENTS_SAMPLERATE_HZ,
        baseline_mean_pA=BASELINE_PA,
        baseline_std_pA=NOISE_STD_PA,
        event_amplitude_pA=EVENT_AMPLITUDE_PA,
        sublevel_dip_pA=PEAKED_EVENTS_DIP_PA,
        sublevel_dip_width_samples=PEAKED_EVENTS_DIP_WIDTH_SAMPLES,
    )
    return str(database.db_path)


@pytest.fixture(scope="session")
def staircase_events_db_path(tmp_path_factory) -> str:
    """
    The same shape as ``events_db_path``, with a known number of discrete,
    resolvable levels inside every blockage instead of one flat level.

    For step-detection fitters (``FITTERS_USING_STAIRCASE_EVENTS`` in
    ``_recipes.py``): a flat blockage has no internal transitions for a
    changepoint detector to count, so those fitters need this instead of the
    shared flat database. Kept as a third, separate database rather than
    added to the shared one so the fitters that already pass against a flat
    blockage are not put at any risk of a behaviour change from it.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: Path to the written database.
    :rtype: str
    """
    out = tmp_path_factory.mktemp("conformance_staircase_events") / "events.sqlite3"
    database = generate_events_database(
        out,
        channel_id=EVENTS_CHANNEL,
        num_events=EVENTS_COUNT,
        samplerate=EVENTS_SAMPLERATE_HZ,
        baseline_mean_pA=BASELINE_PA,
        baseline_std_pA=NOISE_STD_PA,
        event_amplitude_pA=EVENT_AMPLITUDE_PA,
        sublevel_amplitudes_pA=STAIRCASE_LEVEL_AMPLITUDES_PA,
    )
    return str(database.db_path)


@pytest.fixture(scope="session")
def peakfinder_events_db_path(tmp_path_factory) -> str:
    """
    The same shape as ``events_db_path``, with a dip deep and narrow enough
    for ``PeakFinder`` specifically to resolve.

    ``PEAKED_EVENTS_DIP_PA`` (used by ``Basic_PeakFinder``) does not work for
    ``PeakFinder`` - see ``PEAKFINDER_DIP_PA``'s comment in ``_recipes.py`` for
    why. Kept as a fourth, separate database rather than added to any existing
    one so the fitters that already pass are not put at any risk of a
    behaviour change from it.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: Path to the written database.
    :rtype: str
    """
    out = tmp_path_factory.mktemp("conformance_peakfinder_events") / "events.sqlite3"
    database = generate_events_database(
        out,
        channel_id=EVENTS_CHANNEL,
        num_events=EVENTS_COUNT,
        samplerate=EVENTS_SAMPLERATE_HZ,
        baseline_mean_pA=BASELINE_PA,
        baseline_std_pA=NOISE_STD_PA,
        event_amplitude_pA=EVENT_AMPLITUDE_PA,
        sublevel_dip_pA=PEAKFINDER_DIP_PA,
        sublevel_dip_width_samples=PEAKFINDER_DIP_WIDTH_SAMPLES,
    )
    return str(database.db_path)


@pytest.fixture(scope="session")
def chimera_log_path(tmp_path_factory) -> str:
    """
    A Chimera recording: two seconds at 4 MHz on channel 3, five planted events.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: Path to the written ``.log``; its ``.json`` sidecar sits beside it.
    :rtype: str
    """
    out = tmp_path_factory.mktemp("conformance_chimera")
    dataset = generate_chimera_dataset(
        out,
        ChimeraRecordingConfig(
            base_name="synthetic",
            samplerate=CHIMERA_SAMPLERATE_HZ,
            duration_s=CHIMERA_DURATION_S,
            baseline=BASELINE_PA,
            noise_std=NOISE_STD_PA,
            event_amplitude=EVENT_AMPLITUDE_PA,
            event_duration_s=CHIMERA_EVENT_DURATION_S,
        ),
        channel=CHIMERA_CHANNEL,
        num_events=CHIMERA_EVENTS,
    )
    assert dataset.metadata_path is not None, "Chimera writer must emit a .json sidecar"
    return str(dataset.data_path)


@pytest.fixture(scope="session")
def metadata_db_path(tmp_path_factory) -> str:
    """
    A metadata database with one experiment over two channels.

    Two channels rather than one, so ``get_channels_by_experiment`` returns something
    a single-channel database could not distinguish from a stub.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: Path to the written database.
    :rtype: str
    """
    out = tmp_path_factory.mktemp("conformance_metadata") / "metadata.sqlite3"
    database = generate_metadata_database(
        Path(out),
        experiments=[
            {
                "name": METADATA_EXPERIMENT,
                "voltage": 200.0,
                "thickness": 10.0,
                "conductivity": 1.0,
                "channels": [
                    {
                        "channel_id": METADATA_CHANNELS[0],
                        "num_events": METADATA_EVENT_COUNTS[0],
                    },
                    {
                        "channel_id": METADATA_CHANNELS[1],
                        "num_events": METADATA_EVENT_COUNTS[1],
                    },
                ],
            }
        ],
    )
    return str(database.db_path)
