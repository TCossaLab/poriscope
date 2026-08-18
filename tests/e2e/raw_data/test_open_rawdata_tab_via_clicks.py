"""
Smoke test for opening the Raw Data tab.

The cheapest possible check that the application assembles and responds to
input: boot the MVC stack, navigate the menus, confirm the tab appears. If
this fails, every other test in the suite will fail too, and for a reason
that has nothing to do with what they're testing -- so it's worth having as
a separate, fast signal.

Boot app → menu → tab exists. No data, no plugins. If this fails, everything fails; check it first.

Uses no test data and adds no plugins.
"""

import os
import sys
from pathlib import Path

import pytest

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import QT_WAIT_TIMEOUT_MS, open_menu_hybrid

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

E2E_TIMEOUT = int(os.getenv("E2E_TIMEOUT", "60"))

@pytest.mark.smoke
@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT)
def test_open_rawdata_tab_via_clicks(qtbot, tmp_path):
    """
    Launching the app and choosing the menu entry creates a working Raw Data tab.

    Builds the MVC stack against a throwaway config rooted in ``tmp_path``
    so nothing touches real user data, drives the menubar to create the tab,
    and checks the resulting page exposes the controls panel the rest of the
    suite depends on.
    """
    app_config = {
        "Parent Folder": str(tmp_path),
        "User Plugin Folder": str(tmp_path),
        "Log Level": 20,
    }
    model = MainModel(app_config)
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)  # noqa: F841  (kept alive for the test's duration)

    qtbot.addWidget(view)
    view.show()

    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "RawDataController"],
        qtbot,
        timeout_ms=QT_WAIT_TIMEOUT_MS,
    )

    assert "RawDataView" in view.pages, "RawDataView page was not registered after menu navigation"
    raw_view = view.pages["RawDataView"]["widget"]
    assert hasattr(raw_view, "rawdatacontrols"), "RawDataView controls missing"
