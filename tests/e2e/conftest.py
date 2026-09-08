from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from PySide6.QtWidgets import QApplication

# Headless Qt for CI/offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure repo root importable for `import poriscope...` and
# `import tests...`. MUST run before the tests.synthetic_data import below
# -- conftest.py files are imported by pytest before any sys.path setup
# that individual test modules perform themselves, and unlike
# `python -m pytest`, the bare `pytest` command does not add the current
# directory to sys.path automatically. Without this running first, `from
# tests.synthetic_data... import ...` fails with ModuleNotFoundError:
# "No module named 'tests'" the moment pytest tries to load this file.
_TESTS_DIR = Path(__file__).resolve().parent
for cand in [_TESTS_DIR, *_TESTS_DIR.parents]:
    if (cand / "poriscope").exists():
        if str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
        break

from tests.synthetic_data.synthetic_metadata_db import (  # noqa: E402
    SyntheticMetadataDatabase,
    generate_metadata_database,
)


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end UI tests")
    config.addinivalue_line("markers", "e2e_ux: end-to-end UI tests with real clicks")


# Single QApplication for the whole session
@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


# Sandbox appdata dir so MainModel writes into pytest tmp_path
@pytest.fixture(autouse=True)
def sandbox_appdata(monkeypatch, tmp_path):
    """
    Make Poriscope write to:
      <tmp>/appdata/Poriscope/{session,config,logs}
    instead of the real user profile.
    """
    appdata_root = tmp_path / "appdata"
    poriscope_root = appdata_root / "Poriscope"
    (poriscope_root / "session").mkdir(parents=True, exist_ok=True)
    (poriscope_root / "config").mkdir(parents=True, exist_ok=True)
    (poriscope_root / "logs").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "poriscope.models.main_model.user_data_dir",
        lambda *a, **k: str(appdata_root),
        raising=True,
    )


# Opt-in: auto-dismiss any QMessageBox popped during a test instead of
# letting it block forever - real .exec() on a QMessageBox is modal, and
# unless something is actively watching for/dismissing it, the test hangs.
# NOT autouse: request it explicitly (fixture arg `auto_dismiss_message_boxes`)
# in tests that need it, so tests wanting to exercise real Cancel/No
# behavior on a QMessageBox aren't silently short-circuited.


@pytest.fixture
def auto_dismiss_message_boxes(monkeypatch):
    from PySide6 import QtWidgets

    for _mb_method, _mb_return in (
        ("warning", QtWidgets.QMessageBox.Ok),
        ("critical", QtWidgets.QMessageBox.Ok),
        ("information", QtWidgets.QMessageBox.Ok),
        ("question", QtWidgets.QMessageBox.Yes),
    ):

        def _make_patch(method_name, ret_value):
            def _patched(*args, **kwargs):
                print(f"[DEBUG] QMessageBox.{method_name} auto-dismissed: {args}")
                return ret_value

            return _patched

        monkeypatch.setattr(
            f"PySide6.QtWidgets.QMessageBox.{_mb_method}",
            staticmethod(_make_patch(_mb_method, _mb_return)),
            raising=False,
        )


# ==========================================================================
# Synthetic metadata database fixtures
# ==========================================================================
# Moved here from tests/e2e/metadata/conftest.py: originally metadata-only,
# but now also consumed by tests/e2e/clustering (both tabs load through the
# same SQLiteDBLoader-compatible schema). conftest.py fixtures only apply
# to their own directory and subdirectories -- a metadata-scoped conftest
# is invisible to a sibling clustering/ directory -- so this needs to live
# at the tests/e2e/ level shared by both, not in either tab's own conftest.

DEFAULT_BASELINE_PA = 2000.0
DEFAULT_NOISE_STD_PA = 15.0
DEFAULT_EVENT_AMPLITUDE_PA = -400.0
DEFAULT_EVENT_LENGTH_RANGE_SAMPLES = (100, 500)
DEFAULT_SAMPLERATE_HZ = 500_000.0
DEFAULT_STEP_SIZE_PA = 100.0  # confirmed below DEFAULT_EVENT_AMPLITUDE_PA's
# magnitude, so CUSUM registers every planted event -- see
# tests/synthetic_data/synthetic_metadata_db.py's module docstring.


def _default_channel_spec(
    channel_id: int, num_events: int, seed: int
) -> Dict[str, Any]:
    """
    Build one channel spec using this module's default signal shape.

    :param channel_id: Channel identifier for this channel.
    :type channel_id: int
    :param num_events: How many events to plant on this channel.
    :type num_events: int
    :param seed: Random seed for this channel's noise and event lengths.
    :type seed: int

    :return: A channel spec dict ready to pass into
        generate_metadata_database()'s experiments argument.
    :rtype: Dict[str, Any]
    """
    return {
        "channel_id": channel_id,
        "num_events": num_events,
        "samplerate": DEFAULT_SAMPLERATE_HZ,
        "baseline_mean_pA": DEFAULT_BASELINE_PA,
        "baseline_std_pA": DEFAULT_NOISE_STD_PA,
        "event_amplitude_pA": DEFAULT_EVENT_AMPLITUDE_PA,
        "event_length_range_samples": DEFAULT_EVENT_LENGTH_RANGE_SAMPLES,
        "seed": seed,
    }


@pytest.fixture
def synthetic_metadata_database(tmp_path) -> SyntheticMetadataDatabase:
    """
    A two-experiment metadata database, for genuinely testing the Scope
    dialog (SelectionTree)'s default-all-checked / Select-All / individual
    select-deselect / PartiallyChecked-parent behavior, which needs 2+
    experiments and/or 2+ channels to be meaningfully exercised (a
    single-leaf database makes Select-All and individual selection
    indistinguishable). Also usable by clustering tests, which need the
    same multi-row queryable metadata database, not anything Scope-dialog
    specific.

    Shape: "exp_a" with channels 0 (25 events) and 1 (15 events); "exp_b"
    with channel 0 (10 events). 50 events total. Event durations vary
    (100-500 sample range) so a "duration > X" filter selects a genuine
    subset rather than being all-or-nothing -- use
    db.median_duration_us() (or a per-experiment/per-channel variant) for
    a threshold confirmed to split the data non-trivially.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Database describing the file written and every
        experiment/channel's ground truth.
    :rtype: SyntheticMetadataDatabase
    """
    return generate_metadata_database(
        tmp_path / "synthetic_metadata.sqlite3",
        experiments=[
            {
                "name": "exp_a",
                "voltage": 200.0,
                "thickness": 10.0,
                "conductivity": 1.0,
                "channels": [
                    _default_channel_spec(channel_id=0, num_events=25, seed=1),
                    _default_channel_spec(channel_id=1, num_events=15, seed=2),
                ],
            },
            {
                "name": "exp_b",
                "voltage": 200.0,
                "thickness": 10.0,
                "conductivity": 1.0,
                "channels": [
                    _default_channel_spec(channel_id=0, num_events=10, seed=3),
                ],
            },
        ],
        step_size_pA=DEFAULT_STEP_SIZE_PA,
    )


@pytest.fixture
def make_synthetic_metadata_database(tmp_path):
    """
    Build metadata databases with a custom experiment/channel layout.

    Use when a test needs something the default fixture doesn't provide
    (a single experiment, more channels, different event counts per
    channel)::

        def test_single_experiment(make_synthetic_metadata_database):
            db = make_synthetic_metadata_database(
                experiments=[
                    {"name": "solo", "channels": [{"channel_id": 0, "num_events": 30}]},
                ],
            )

    Every keyword argument of generate_metadata_database() can be
    overridden; "experiments" is required (there's no meaningful default
    experiment layout to fall back to, unlike the single-channel raw
    events-database factory). Each channel spec dict only needs
    "channel_id"; every other field falls back to this module's defaults
    if omitted (see generate_metadata_database()'s own docstring for the
    full per-channel spec shape). Each call writes to its own file, so a
    test may create several databases without them colliding.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: A factory accepting "experiments" (required) plus any other
        keyword argument of generate_metadata_database().
    :rtype: Callable[..., SyntheticMetadataDatabase]
    """

    def _make(
        *, experiments: List[Dict[str, Any]], **overrides: Any
    ) -> SyntheticMetadataDatabase:
        filled_experiments = []
        for exp_spec in experiments:
            filled_channels = []
            for chan_spec in exp_spec.get("channels", []):
                if "channel_id" not in chan_spec:
                    raise ValueError(
                        f"Channel spec missing required 'channel_id': {chan_spec}"
                    )
                defaults = _default_channel_spec(
                    channel_id=chan_spec["channel_id"],
                    num_events=chan_spec.get("num_events", 25),
                    seed=chan_spec.get("seed", 42),
                )
                defaults.update(chan_spec)
                filled_channels.append(defaults)
            filled_exp = dict(exp_spec)
            filled_exp["channels"] = filled_channels
            filled_experiments.append(filled_exp)

        n_prior = len(list(tmp_path.glob("synthetic_metadata_*.sqlite3")))
        out_path = tmp_path / f"synthetic_metadata_{n_prior}.sqlite3"

        params: Dict[str, Any] = dict(step_size_pA=DEFAULT_STEP_SIZE_PA)
        params.update(overrides)
        return generate_metadata_database(
            out_path, experiments=filled_experiments, **params
        )

    return _make
