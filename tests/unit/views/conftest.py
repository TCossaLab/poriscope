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

4. Matplotlib canvas GC segfaults. Matplotlib figures wrapping PySide6
   widgets trigger C++ segfaults when garbage collected asynchronously
   after Qt widgets have been destroyed.
   -> Fixed by forcing the 'Agg' backend and explicitly closing figures and
      running garbage collection at teardown.
"""

import gc
import os

# Set headless Qt platform AND non-GUI Matplotlib backend BEFORE module imports
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

# A full gc.collect() walks every generation, including the long-lived one holding
# PySide6, numpy, pandas, sklearn and matplotlib. That traversal cost 129 ms per test
# and 55% of this directory's runtime, and it is not where per-test garbage lives.
# A collection still runs after *every* test - see _close_leftover_widgets and
# DECISIONS.md, "Generation-limited GC in the view-test teardown".
_GC_FULL_SWEEP_EVERY = 50
_gc_tick = 0


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
    Safety net: destroy any top-level widgets left open by a test, close all
    Matplotlib figures, and force a GC sweep while Qt is still active.

    Widgets must be *destroyed*, not merely closed. QWidget.close() only hides
    a widget; it stays alive and stays in QApplication.topLevelWidgets() for
    the life of the process. Closing alone therefore leaks every widget every
    test creates, and since this fixture is autouse over the whole directory,
    each subsequent teardown walks a longer list and hands gc.collect() a
    larger heap. Measured before this was fixed: teardown cost grew from
    ~0.09s early in the session to 9-13s in tests/unit/views/widgets, which
    run last alphabetically - roughly 90% of the suite's wall-clock, spent
    entirely in teardown.

    deleteLater() alone is not enough either: it only posts a DeferredDelete
    event, and QApplication.processEvents() does not dispatch those. They have
    to be flushed explicitly via sendPostedEvents, otherwise the widgets are
    scheduled for deletion that never happens and the leak is unchanged.

    The gc.collect() at the end is the fix for the Matplotlib/PySide segfaults
    described in point 4 above and must not be dropped. It is generation-limited
    for cost; read the comment at the call site before changing it.
    """
    yield
    # Close all Matplotlib figures to disown C++ Qt bindings explicitly
    plt.close("all")

    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        app.processEvents()
        # Actually dispatch the DeferredDelete events queued by deleteLater();
        # processEvents() above deliberately does not deliver them.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    # Force Python GC to clean up Shiboken/PySide wrappers before the session
    # advances. This is load-bearing: it is what stopped the repeated Matplotlib/
    # PySide segfaults in CI (commits 06679373, cc2fd863, d829d688). Do not remove it.
    #
    # It is generation-limited rather than full, which is a cost reduction and NOT a
    # relaxation of the cadence: a collection still happens after every single test,
    # exactly as before. Only the full-generation sweep is periodic. gc.collect(1)
    # covers generations 0 and 1, which is where a widget or canvas built during a
    # test lives; the periodic full sweep reclaims anything promoted to generation 2.
    global _gc_tick
    _gc_tick += 1
    if _gc_tick % _GC_FULL_SWEEP_EVERY == 0:
        gc.collect()
    else:
        gc.collect(1)
