from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

# Headless Qt for CI/offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure repo root importable for `import poriscope...`
_TESTS_DIR = Path(__file__).resolve().parent
for cand in [_TESTS_DIR, *_TESTS_DIR.parents]:
    if (cand / "poriscope").exists():
        if str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
        break


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


# Prevent AttributeError in RawDataView during first plugin refresh
@pytest.fixture(autouse=True)
def init_rawdataview_timer_channels(monkeypatch):
    """
    The view uses self.timer_channels in update_available_plugins() before
    it's guaranteed to be set. Give it a safe default to avoid Qt-loop exceptions.
    """
    try:
        from poriscope.plugins.analysistabs.RawDataView import RawDataView
    except ModuleNotFoundError:
        return

    original_init = RawDataView._init

    def _patched_init(self, *a, **kw):
        original_init(self, *a, **kw)
        if not hasattr(self, "timer_channels"):
            self.timer_channels = []

    monkeypatch.setattr(RawDataView, "_init", _patched_init, raising=True)
