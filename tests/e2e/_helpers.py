"""
Shared helpers for poriscope end-to-end UI tests.

These utilities are used by all tab suites under ``tests/e2e/`` (raw_data,
clustering, event_analysis, metadata, protein). They fall into four groups:

1. **Configuration** -- env-var-overridable plugin names and Qt timeouts.
2. **Menu navigation** -- driving the application menubar to open tabs.
3. **Dialog automation** -- filling in modal settings dialogs, which block
   the calling thread and therefore must be handled from the Qt event loop.
4. **Widget inspection** -- locating and reading state from the controls
   that make up an analysis tab.

Anything specific to a single tab belongs in that tab's own directory, not
here.
"""

from __future__ import annotations

import os
from typing import Callable, Optional, Sequence

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

# ==========================================================================
# Configuration
# ==========================================================================
# Plugin class names the tests instantiate through the UI. Overridable via
# environment so the same tests can be pointed at alternative plugins
# without editing code.

READER_NAME = os.getenv("E2E_READER_NAME", "ChimeraReader20240501")
FINDER_NAME = os.getenv("E2E_EVENTFINDER_NAME", "ClassicBlockageFinder")
WRITER_NAME = os.getenv("E2E_WRITER_NAME", "SQLiteEventWriter")

# How long to wait for asynchronous UI state to settle. Generous by default:
# these are full-application tests where a single action can trigger file
# I/O, worker threads, and replotting.
QT_WAIT_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "30000"))

# A short settle pause, used after actions whose completion isn't worth
# polling for (e.g. letting a file-picker click register before reading the
# resulting state back).
QT_SHORT_PAUSE_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "250"))

# Interval between attempts when polling for a modal dialog to appear.
DIALOG_POLL_MS = int(os.getenv("E2E_DIALOG_POLL_MS", "50"))


# ==========================================================================
# Test isolation
# ==========================================================================


@pytest.fixture(autouse=True)
def close_stray_dialogs():
    """
    Close any modal dialog still open when a test finishes.

    Applied automatically to every test in the suite. A dialog left open
    (typically because a test failed partway through its interaction with
    one) would otherwise remain in the shared QApplication and interfere
    with the next test's attempt to find *its* dialog.
    """
    yield
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, QtWidgets.QDialog):
            widget.close()


# ==========================================================================
# Menu navigation
# ==========================================================================


def _normalize_label(text: str) -> str:
    """
    Strip Qt keyboard-accelerator markers from a menu label.

    Qt encodes the underlined access key as an ampersand in the label text
    (``"&Analysis"``), which isn't part of what the user sees. Removing it
    lets tests match on the visible text.
    """
    return (text or "").replace("&", "").strip()


def open_menu_hybrid(
    main_view: QtWidgets.QMainWindow,
    menu_path_labels: Sequence[str],
    qtbot,
    timeout_ms: int = QT_WAIT_TIMEOUT_MS,
) -> QtGui.QAction:
    """
    Open a nested menu item by label path and trigger it.

    Takes a "hybrid" approach: the top-level menubar entry is opened with a
    real synthetic mouse click (so the menu is genuinely shown, as a user
    would see it), but nested submenus are then traversed through Qt's
    ``QAction`` object tree rather than by clicking popup coordinates.
    Popup windows have unreliable geometry under offscreen/headless
    rendering, so coordinate-based clicking into them is flaky; walking the
    action tree is deterministic.

    :param main_view: the application's main window.
    :param menu_path_labels: labels from the menubar down to the target,
        e.g. ``["Analysis", "New Analysis Tab", "RawDataController"]``.
        Ampersand accelerators may be omitted.
    :param qtbot: pytest-qt bot, used to let the event loop run between steps.
    :param timeout_ms: how long to wait for a menu to become available.
    :return: the ``QAction`` that was triggered.
    :raises AssertionError: if any label in the path has no matching entry;
        the message lists the labels that *were* available at that level.
    """
    assert menu_path_labels, "menu path is empty"

    # Step 1: click the top-level menubar entry.
    menu_bar = main_view.menuBar()
    top_level_label = menu_path_labels[0]
    try:
        top_level_action = next(
            action
            for action in menu_bar.actions()
            if _normalize_label(action.text()) == _normalize_label(top_level_label)
        )
    except StopIteration:
        available = [_normalize_label(a.text()) for a in menu_bar.actions()]
        raise AssertionError(f"No top-level menu {top_level_label!r} found; available: {available}")

    action_rect = menu_bar.actionGeometry(top_level_action)
    QTest.mouseClick(menu_bar, Qt.LeftButton, Qt.NoModifier, action_rect.center())
    qtbot.wait(10)

    # Step 2: descend through intermediate submenus via the action tree.
    current_menu = top_level_action.menu()
    qtbot.waitUntil(lambda: current_menu is not None, timeout=timeout_ms)

    for intermediate_label in menu_path_labels[1:-1]:
        try:
            intermediate_action = next(
                action
                for action in current_menu.actions()
                if _normalize_label(action.text()) == _normalize_label(intermediate_label)
            )
        except StopIteration:
            available = [_normalize_label(a.text()) for a in current_menu.actions()]
            raise AssertionError(f"No submenu {intermediate_label!r} found; available: {available}")
        next_menu = intermediate_action.menu()
        if next_menu is None:
            # Some submenus are populated on demand rather than up front;
            # triggering the parent action forces them to be built.
            intermediate_action.trigger()
            next_menu = intermediate_action.menu()
        current_menu = next_menu
        qtbot.wait(10)

    # Step 3: trigger the leaf action.
    final_label = menu_path_labels[-1]
    try:
        final_action = next(
            action
            for action in current_menu.actions()
            if _normalize_label(action.text()) == _normalize_label(final_label)
        )
    except StopIteration:
        available = [_normalize_label(a.text()) for a in current_menu.actions()]
        raise AssertionError(f"No menu action {final_label!r} found; available: {available}")
    final_action.trigger()
    qtbot.wait(20)

    return final_action


# ==========================================================================
# Dialog automation
# ==========================================================================


def first_modal_dialog() -> Optional[QtWidgets.QDialog]:
    """Return the currently active modal dialog, or ``None`` if there isn't one."""
    widget = QtWidgets.QApplication.activeModalWidget()
    return widget if isinstance(widget, QtWidgets.QDialog) else None


def find_button(
    dlg: QtWidgets.QDialog, text_contains: str, exact: bool = False
) -> Optional[QtWidgets.QPushButton]:
    """
    Find a button in a dialog by its visible text, case-insensitively.

    :param dlg: dialog to search.
    :param text_contains: text to match against the button label.
    :param exact: match the whole label instead of a substring. Use this for
        short labels like "OK" that would otherwise also match longer ones
        such as "Look up".
    :return: the first matching button, or ``None``.
    """
    needle = (text_contains or "").lower()
    for btn in dlg.findChildren(QtWidgets.QPushButton):
        label = (btn.text() or "").lower()
        if (label == needle) if exact else (needle in label):
            return btn
    return None


def ensure_name_filled(dlg: QtWidgets.QDialog, default_name: str = "e2e_instance") -> None:
    """
    Make sure a plugin settings dialog has a non-empty instance name.

    ``DictDialog`` refuses to enable its OK button while the name field is
    blank, so this must hold before the dialog can be accepted. The field is
    normally pre-filled from the dialog's constructor, so this is a
    safeguard rather than the usual path.

    Looks for ``DictDialog``'s known ``name_entry`` attribute first, and
    falls back to scanning for a line edit that looks name-like, so the
    helper also works with other dialog classes.
    """
    name_entry = getattr(dlg, "name_entry", None)
    if isinstance(name_entry, QtWidgets.QLineEdit):
        if not name_entry.text().strip():
            name_entry.setText(default_name)
        return

    name_edit = next(
        (
            w
            for w in dlg.findChildren(QtWidgets.QLineEdit)
            if "name" in (w.objectName() or "").lower()
            or (w.placeholderText() or "").lower().startswith("name")
        ),
        None,
    )
    if name_edit and not name_edit.text().strip():
        name_edit.setText(default_name)


def schedule_dialog_autofill(
    fill_fn: Callable[[QtWidgets.QDialog], bool], poll_ms: int = DIALOG_POLL_MS
) -> None:
    """
    Arrange for a modal dialog to be filled in and accepted automatically.

    Modal dialogs block the thread that opens them: the call that triggers
    one (e.g. clicking "add reader") does not return until the dialog
    closes. A test therefore cannot open a dialog and *then* interact with
    it -- the interaction has to already be queued on the event loop before
    the dialog appears.

    This schedules ``fill_fn`` to run on the event loop and retry on a timer
    until it succeeds, so it fires from inside the dialog's own nested event
    loop. Call it immediately *before* the action that opens the dialog::

        schedule_dialog_autofill(fill_reader_dialog)
        QTest.mouseClick(controls.readers_add_button, Qt.LeftButton)
        qtbot.waitUntil(reader_is_present, timeout=QT_WAIT_TIMEOUT_MS)

    ``fill_fn`` receives the active dialog and returns ``True`` once it has
    populated the fields and clicked OK, or ``False`` to be retried (for
    example when the OK button isn't enabled yet). Retries continue
    indefinitely; success or failure is determined by the caller's own wait
    on the observable result of the dialog being accepted, which is what
    should time out and fail the test if something goes wrong.
    """

    def _try_fill():
        dlg = first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(poll_ms, _try_fill)
            return
        if fill_fn(dlg):
            return
        QtCore.QTimer.singleShot(poll_ms, _try_fill)

    QtCore.QTimer.singleShot(0, _try_fill)


# ==========================================================================
# Widget inspection
# ==========================================================================


def find_channel_combo(controls) -> Optional[QtWidgets.QComboBox]:
    """
    Return the channel selector from a tab's controls widget.

    This is a ``MultiSelectComboBox`` (from ``poriscope.views.widgets.multiselect``)
    exposed as ``controls.channel_comboBox``. Falls back to searching child
    combo boxes by object name.
    """
    cb = getattr(controls, "channel_comboBox", None)
    if isinstance(cb, QtWidgets.QComboBox):
        return cb
    for cb in controls.findChildren(QtWidgets.QComboBox):
        if "channel" in (cb.objectName() or "").lower():
            return cb
    return None


def channels_have_loaded(controls) -> bool:
    """
    Report whether the channel selector has been populated with channels.

    Selecting a reader causes its channel list to be fetched asynchronously,
    so the selector exists (empty) well before it holds anything. Use this
    as the wait predicate before selecting a channel; checking merely that
    the widget exists would pass immediately and select from an empty list.
    """
    cb = find_channel_combo(controls)
    if cb is None:
        return False
    lw = getattr(cb, "listWidget", None)
    return (lw.count() > 0) if lw is not None else (cb.count() > 0)


def select_any_channel(cb: QtWidgets.QComboBox, prefer: Optional[str] = None) -> bool:
    """
    Tick one channel in the channel selector.

    :param cb: the channel ``MultiSelectComboBox``.
    :param prefer: channel label to select if present; otherwise the first
        available channel is used.
    :return: ``False`` if there are no channels to choose from, else ``True``.
    """
    lw = getattr(cb, "listWidget", None)
    if lw is None or lw.count() == 0:
        return False
    labels = [lw.item(i).text() for i in range(lw.count())]
    chosen = prefer if prefer in labels else labels[0]
    cb.selectItem(chosen, select=True)
    if hasattr(cb, "refreshDisplayText"):
        cb.refreshDisplayText()
    return True


def count_plot_lines(fig) -> int:
    """Total number of plotted lines across every axes in a matplotlib figure."""
    return sum(len(ax.lines) for ax in getattr(fig, "axes", []) or [])