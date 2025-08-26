import os
import sys
from pathlib import Path

import pytest
from tests.e2e._helpers import (
    open_menu_hybrid,
)  # stable helper to open menus in headless CI

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView

# Make sure the repo root is on sys.path so `poriscope.*` imports resolve when running tests directly
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Global timeouts to keep flaky tests from hanging forever
E2E_TIMEOUT = int(os.getenv("E2E_TIMEOUT", "60"))  # seconds for whole test
QT_WAIT_TIMEOUT_MS = int(
    os.getenv("E2E_QT_TIMEOUT_MS", "10000")
)  # ms for waitUntil polls


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT)  # hard cap for the entire test run
def test_open_rawdata_tab_via_clicks(qtbot, tmp_path):
    """
    E2E/UX smoke test: start the MVC shell and open the Raw Data tab via the menu.

    Steps:
      1) Boot MVC with a sandboxed config (no App(); qtbot owns QApplication).
      2) Use a stable “hybrid” menu opener to navigate: Analysis → New Analysis Tab → RawDataController.
      3) Assert swithed to page and that the view has its expected controls attribute.
    """

    # 1) Boot MVC using a throwaway/sandboxed config rooted under pytest’s tmp_path
    app_config = {
        "Parent Folder": str(tmp_path),  # shared data folder (kept isolated)
        "User Plugin Folder": str(tmp_path),  # user plugin search path (isolated)
        "Log Level": 20,  # INFO level
    }
    model = MainModel(app_config)
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)  # noqa: F841

    # Show the top-level window under Qt’s test runner
    qtbot.addWidget(view)
    view.show()

    # 2) Open Raw Data tab via menu using the hybrid helper:
    # Click the menubar top-level item (“Analysis”), then logically traverse submenus
    # and trigger the final QAction (stable in headless/offscreen CI).
    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "RawDataController"],
        qtbot,
        timeout_ms=10_000,
    )

    # Optional: Wait for the RawDataView page to be registered, then switch focus to it (redundant when a page is instantiated thorugh top menu)
    # qtbot.waitUntil(lambda: "RawDataView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    # view.switch_to_page("RawDataView")

    # 3) Basic sanity: the page exists and exposes its controls object
    raw_view = view.pages["RawDataView"]["widget"]
    assert hasattr(raw_view, "rawdatacontrols"), "RawDataView controls missing"
