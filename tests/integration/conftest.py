from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Dict

import pytest

# Headless Qt for anything that might import Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Keep test logs quieter by default; change to INFO for debugging
logging.basicConfig(level=logging.WARNING)

# Ensure the repo root is importable for `from tests.synthetic_data...`. conftest
# files are imported before any sys.path setup a test module does for itself, and
# the bare `pytest` command (unlike `python -m pytest`) does not add the current
# directory. Without this, the import below fails with ModuleNotFoundError. Same
# shim as tests/e2e/conftest.py, for the same reason.
_TESTS_DIR = Path(__file__).resolve().parent
for _cand in [_TESTS_DIR, *_TESTS_DIR.parents]:
    if (_cand / "poriscope").exists():
        if str(_cand) not in sys.path:
            sys.path.insert(0, str(_cand))
        break

from tests.synthetic_data.synthetic_chimera import (  # noqa: E402
    ChimeraRecordingConfig,
    generate_chimera_dataset,
)
from tests.synthetic_data.synthetic_events_db import (  # noqa: E402
    generate_events_database,
)
from tests.synthetic_data.synthetic_metadata_db import (  # noqa: E402
    generate_metadata_database,
)

# Signal parameters shared with the e2e fixtures (tests/e2e/raw_data/conftest.py),
# so a plugin behaves the same way across both suites.
DEFAULT_BASELINE_PA = 2000.0
DEFAULT_NOISE_STD_PA = 15.0
DEFAULT_EVENT_AMPLITUDE_PA = -400.0
DEFAULT_EVENT_DURATION_S = 0.0005
DEFAULT_SAMPLERATE_HZ = 4_000_000.0

# The raw-data flow asserts on this channel and event count, so they are named
# here rather than buried in the fixture body.
CHIMERA_CHANNEL = 3
CHIMERA_NUM_EVENTS = 5
CHIMERA_DURATION_S = 2.0


@pytest.fixture
def sample_chimera(tmp_path) -> Dict[str, str]:
    """
    Generate a Chimera ``.log`` + ``.json`` pair and return their locations.

    Two seconds at 4 MHz on channel 3 with five evenly spaced events, written
    fresh into the test's own tmp_path. Previously this copied a checked-in
    recording out of ``tests/data/``; the event count and channel are now ground
    truth set here rather than properties of a fixture file.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Paths to the generated ``.log`` and ``.json`` and their folder.
    :rtype: Dict[str, str]
    """
    config = ChimeraRecordingConfig(
        base_name="synthetic",
        samplerate=DEFAULT_SAMPLERATE_HZ,
        duration_s=CHIMERA_DURATION_S,
        baseline=DEFAULT_BASELINE_PA,
        noise_std=DEFAULT_NOISE_STD_PA,
        event_amplitude=DEFAULT_EVENT_AMPLITUDE_PA,
        event_duration_s=DEFAULT_EVENT_DURATION_S,
    )
    dataset = generate_chimera_dataset(
        tmp_path,
        config,
        channel=CHIMERA_CHANNEL,
        num_events=CHIMERA_NUM_EVENTS,
    )
    assert dataset.metadata_path is not None, "Chimera writer must emit a .json sidecar"

    return {
        "log": str(dataset.data_path),
        "json": str(dataset.metadata_path),
        "folder": str(tmp_path),
        "channel": dataset.channel,
        "num_events": len(dataset.events),
        "duration_s": config.duration_s,
    }


@pytest.fixture
def sample_events_db(tmp_path) -> str:
    """
    Generate an events database for analysis-only tests.

    Single channel, 25 events at 500 kHz - the same shape the event_analysis
    e2e fixtures use, so the two suites exercise the fitter on equivalent data.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Path to the written database.
    :rtype: str
    """
    database = generate_events_database(
        tmp_path / "synthetic_events.sqlite3",
        channel_id=0,
        num_events=25,
        samplerate=500_000.0,
        baseline_mean_pA=DEFAULT_BASELINE_PA,
        baseline_std_pA=DEFAULT_NOISE_STD_PA,
        event_amplitude_pA=DEFAULT_EVENT_AMPLITUDE_PA,
    )
    return str(database.db_path)


@pytest.fixture
def sample_metadata_db(tmp_path) -> str:
    """
    Generate a metadata database for the loader/clustering flow.

    One experiment with two channels, so ``get_channels_by_experiment`` returns
    something a single-channel database could not distinguish from a stub.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Path to the written database.
    :rtype: str
    """
    database = generate_metadata_database(
        tmp_path / "synthetic_metadata.sqlite3",
        experiments=[
            {
                "name": "exp_a",
                "voltage": 200.0,
                "thickness": 10.0,
                "conductivity": 1.0,
                "channels": [
                    {"channel_id": 0, "num_events": 25},
                    {"channel_id": 1, "num_events": 15},
                ],
            }
        ],
    )
    return str(database.db_path)
