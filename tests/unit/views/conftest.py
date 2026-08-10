"""
conftest.py for tests/unit/views

Why this exists
----------------
PySide6/Qt GUI tests commonly *stall* (hang forever, no error, no timeout)
rather than fail, because:

1. Qt tries to open a real window on a real display. On a headless CI box
   or when window-manager focus gets stolen, window creation can block.
   -> Fixed by forcing the "offscreen" platform plugin.

2. Something under test calls a real *blocking* dialog (QMessageBox.exec(),
   QFileDialog.exec(), QDialog.exec()). exec() starts its own nested event
   loop and waits for a user click that will never come in a test run.
   -> Fixed by monkeypatching exec()/exec_() to return immediately.

3. More than one QApplication gets constructed. Qt only allows a single
   QApplication per process; a second one can hang or crash depending on
   platform. pytest-qt already provides a session-scoped `qapp` fixture -
   if view code creates its own QApplication instead of reusing that
   one, we will hit this.
"""

import os

# Must be set BEFORE any Qt module is imported anywhere in the process,
# which is why this happens at module scope, at the very top of this file,
# rather than inside a fixture.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402


@pytest.fixture(scope="session")
def qapp_args():
    """Extra args pytest-qt passes when constructing the shared QApplication."""
    return []


@pytest.fixture(autouse=True)
def _prevent_blocking_dialogs(monkeypatch):
    """
    Auto-applied to every test in this directory: makes any modal dialog
    return immediately instead of opening a real blocking event loop.

    If a test specifically wants to assert dialog *content* (e.g. the text
    in a QMessageBox), prefer pytest-qt's qtbot + monkeypatching the
    specific dialog class in that test instead of relying on this default.
    """
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QDialog, "exec_", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(
        QMessageBox, "exec_", lambda self: QMessageBox.StandardButton.Ok
    )


@pytest.fixture(autouse=True)
def _close_leftover_widgets():
    """
    Safety net: close any top-level widgets left open by a test (e.g. a
    view that was shown but never closed) so they can't keep an event loop
    alive into the next test.
    """
    yield
    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            widget.close()
