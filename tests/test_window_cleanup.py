"""
The window cleanup the root conftest runs after every test.

A window that is closed but never deleted stays alive for the rest of the session. In
November 2026 the integration flows left about 9,300 of them behind, and every later
test paid for them: the suite took 1,650 s, and 493 s once they were destroyed. These
tests pin what the cleanup must do, so a harness that hides windows instead of deleting
them is caught by the cleanup rather than by a slow suite.
"""

from pathlib import Path
from typing import Any

import shiboken6
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from tests._window_cleanup import destroy_leftover_windows
from tests.integration.flows._triad import build_triad


def test_a_closed_window_is_deleted(qapp: Any) -> None:
    window = QMainWindow()
    window.show()
    window.close()
    assert shiboken6.isValid(window), "close() alone should leave the window alive"
    assert destroy_leftover_windows() == []
    assert not shiboken6.isValid(window)


def test_a_closed_triad_leaves_no_window(qapp: Any, tmp_path: Path) -> None:
    triad = build_triad("RawDataController", tmp_path)
    triad.close()
    assert QApplication.topLevelWidgets(), "a closed triad's windows are still alive"
    assert destroy_leftover_windows() == []
    assert QApplication.topLevelWidgets() == []


class _Stubborn(QWidget):
    """A window whose deferred deletion never happens."""

    def deleteLater(self) -> None:
        """Ignore the request, so the window survives the cleanup."""


def test_a_window_that_survives_is_named(qapp: Any) -> None:
    window = _Stubborn()
    try:
        assert destroy_leftover_windows() == ["_Stubborn"]
    finally:
        shiboken6.delete(window)
