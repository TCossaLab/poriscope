"""
E2E/UX: Open Raw Data, add a Chimera reader, pick a file, select a channel,
update the trace, navigate right/left, click baseline + PSD.

Assertions:
- After Update Trace, something is plotted (any line on any axes).
- Time range in start_time_lineEdit is:
    0–2  -> after RIGHT -> 2–4 -> after LEFT -> 0–2
- Baseline/PSD: only check that the corresponding actions were emitted.
"""

import os
import sys
from pathlib import Path

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QDialog, QLineEdit, QPushButton

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import open_menu_hybrid

# Make repo imports work when running directly
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


READER_DISPLAY_NAME = os.getenv("E2E_READER_NAME", "ChimeraReader20240501")
TEST_LOG_NAME = os.getenv("E2E_TEST_LOG", "2kbp_n200mV_HS3_20240604_122657.log")

E2E_TEST_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "120"))
QT_POLL_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "15000"))
QT_SHORT_PAUSE_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "250"))
DEFAULT_SAMPLERATE = os.getenv("E2E_SAMPLERATE", "4000000")  # 4e6 as str


#  utilities


def _find_button(dlg: QDialog, text_contains: str) -> QPushButton | None:
    """Return the first QPushButton whose text contains the given substring (case-insensitive)."""
    needle = (text_contains or "").lower()
    for btn in dlg.findChildren(QPushButton):
        if needle in (btn.text() or "").lower():
            return btn
    return None


def _ensure_name_filled(dlg: QDialog, default_name: str = "reader_e2e") -> None:
    """Ensure the dialog's 'Name' QLineEdit is non-empty so OK can enable."""
    name_edit = next(
        (
            w
            for w in dlg.findChildren(QLineEdit)
            if "name" in w.objectName().lower()
            or (w.placeholderText() or "").lower().startswith("name")
        ),
        None,
    )
    if name_edit and not name_edit.text().strip():
        name_edit.setText(default_name)


def _set_required_reader_fields(dlg: QDialog) -> None:
    """
    Fill required fields in DictDialog before OK (e.g., samplerate).
    If a Channel combobox is present in the dialog, pick index 0.
    """
    entrywidgets = getattr(dlg, "entrywidgets", {})
    for key, widget in entrywidgets.items():
        norm_key = (key or "").lower().replace(" ", "")
        if (
            ("samplerate" in norm_key)
            or ("samplingrate" in norm_key)
            or (norm_key in {"fs", "rate"})
        ):
            if hasattr(widget, "setText"):
                widget.setText(str(DEFAULT_SAMPLERATE))
        if "channel" in norm_key and isinstance(widget, QComboBox):
            if widget.count() > 0 and widget.currentIndex() < 0:
                widget.setCurrentIndex(0)


def _find_live_channel_combo(controls) -> QComboBox | None:
    """
    RawDataControls uses MultiSelectComboBox assigned to .channel_comboBox (subclass of QComboBox).
    Return that if present; else fall back to any child whose objectName contains 'channel'.
    """
    cb = getattr(controls, "channel_comboBox", None)
    if isinstance(cb, QComboBox):
        return cb
    for cb in controls.findChildren(QComboBox):
        if "channel" in cb.objectName().lower():
            return cb
    return None


def _round(val: float, ndigits=6) -> float:
    """Convenience to compare floats by value while avoiding tiny binary noise."""
    return round(float(val), ndigits)


# Test


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TEST_TIMEOUT_S)
def test_trace_load_navigate_psd(qtbot, tmp_path, monkeypatch):
    # --- Patch subclass picker so the reader selection dialog auto-chooses our reader
    def fake_get_item(parent, title, label, items, current=0, editable=False):
        for text in items:
            if READER_DISPLAY_NAME in text:
                return text, True
        for text in items:
            if "chimera" in (text or "").lower():
                return text, True
        return (items[0] if items else READER_DISPLAY_NAME), True

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )
    try:
        # also patch the symbol as imported inside app (covers cached references)
        monkeypatch.setattr(
            "poriscope.utils.MetaView.QInputDialog.getItem",
            staticmethod(fake_get_item),
            raising=True,
        )
    except Exception:
        pass

    # Patch file dialog to return test log path
    data_file = REPO_ROOT / "tests" / "data" / TEST_LOG_NAME
    if not data_file.exists():
        data_file = REPO_ROOT / "data" / TEST_LOG_NAME
    assert data_file.exists(), f"Missing test file: {data_file}"

    def fake_file_open(*_a, **_k):
        return (str(data_file), "All Files (*)")

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(fake_file_open),
        raising=False,
    )
    try:
        # patch module-local reference used by DictDialog
        monkeypatch.setattr(
            "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getOpenFileName",
            staticmethod(fake_file_open),
            raising=True,
        )
    except Exception:
        pass

    # Boot MVC in a sandboxed temp dir
    model = MainModel(
        {
            "Parent Folder": str(tmp_path),
            "User Plugin Folder": str(tmp_path),
            "Log Level": 20,
        }
    )
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)  # noqa: F841

    qtbot.addWidget(view)
    view.show()

    # Open Raw Data tab
    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "RawDataController"],
        qtbot,
        timeout_ms=QT_POLL_TIMEOUT_MS,
    )
    qtbot.waitUntil(lambda: "RawDataView" in view.pages, timeout=QT_POLL_TIMEOUT_MS)
    view.switch_to_page("RawDataView")
    raw_view = view.pages["RawDataView"]["widget"]
    controls = raw_view.rawdatacontrols

    # Auto-complete the reader settings dialog when it pops
    def auto_complete_reader_settings():
        dlg = QtWidgets.QApplication.activeModalWidget()
        if not isinstance(dlg, QDialog):
            QtCore.QTimer.singleShot(50, auto_complete_reader_settings)
            return
        pick = _find_button(dlg, "select input file")
        if pick:
            QTest.mouseClick(pick, Qt.LeftButton)
            qtbot.wait(QT_SHORT_PAUSE_MS)
        _ensure_name_filled(dlg)
        _set_required_reader_fields(dlg)
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_reader_settings)

    QtCore.QTimer.singleShot(0, auto_complete_reader_settings)

    # Click "+ Add reader"
    QTest.mouseClick(controls.readers_add_button, Qt.LeftButton)

    # Reader appears in combobox
    qtbot.waitUntil(
        lambda: controls.readers_comboBox.count() > 0, timeout=QT_POLL_TIMEOUT_MS
    )
    idx = controls.readers_comboBox.findText(READER_DISPLAY_NAME)
    controls.readers_comboBox.setCurrentIndex(idx if idx >= 0 else 0)

    # Wait for channels to load (MultiSelectComboBox may rebuild)
    def channels_have_loaded() -> bool:
        cb = _find_live_channel_combo(controls)
        if not cb:
            return False
        lw = getattr(cb, "listWidget", None)
        return (lw.count() > 0) if lw is not None else (cb.count() > 0)

    qtbot.waitUntil(channels_have_loaded, timeout=QT_POLL_TIMEOUT_MS)

    # Pick at least one channel
    chan_cb = _find_live_channel_combo(controls)
    if hasattr(chan_cb, "selectItem"):
        lw = getattr(chan_cb, "listWidget", None)
        labels = (
            [lw.item(i).text() for i in range(lw.count())]
            if lw is not None
            else [chan_cb.itemText(i) for i in range(chan_cb.count())]
        )
        chosen = "3" if "3" in labels else (labels[0] if labels else None)
        assert chosen, "No channel options available"
        chan_cb.selectItem(chosen)
        if hasattr(chan_cb, "refreshDisplayText"):
            chan_cb.refreshDisplayText()
    else:
        chan_cb.setCurrentIndex(0)

    # Set time range and click Update Trace
    controls.set_range_inputs(0, 2.0)
    qtbot.waitUntil(
        lambda: controls.update_trace_pushButton.isEnabled(), timeout=QT_POLL_TIMEOUT_MS
    )
    QTest.mouseClick(controls.update_trace_pushButton, Qt.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)

    # Assert: something plotted
    assert raw_view.figure.axes and any(
        ax.lines for ax in raw_view.figure.axes
    ), "No plotted lines detected after 'Update Trace'"

    # Wiretap actions to verify baseline/PSD clicks later
    emitted_actions: list[str] = []
    controls.actionTriggered.connect(
        lambda sub, action, args: emitted_actions.append(action)
    )

    # Assert: range is 0–2 initially
    assert (
        _round(controls.start_time_lineEdit.get_start()) == 0.0
    ), "Expected start_time=0.0 initially"
    assert (
        _round(controls.start_time_lineEdit.get_duration()) == 2.0
    ), "Expected duration=2.0 initially"

    # RIGHT arrow: expect 2–4
    if controls.right_trace_arrow_button.isEnabled():
        QTest.mouseClick(controls.right_trace_arrow_button, Qt.LeftButton)
        # wait until the start/duration text boxes reflect the new window
        qtbot.waitUntil(
            lambda: _round(controls.start_time_lineEdit.get_start()) == 2.0
            and _round(controls.start_time_lineEdit.get_duration()) == 2.0,
            timeout=QT_POLL_TIMEOUT_MS,
        )

    # LEFT arrow: expect back to 0–2
    if controls.left_trace_arrow_button.isEnabled():
        QTest.mouseClick(controls.left_trace_arrow_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: _round(controls.start_time_lineEdit.get_start()) == 0.0
            and _round(controls.start_time_lineEdit.get_duration()) == 2.0,
            timeout=QT_POLL_TIMEOUT_MS,
        )

    # Baseline/PSD: just confirm actions were emitted (doesn’t assert plotting details)
    if hasattr(controls, "calculate_baseline_button"):
        QTest.mouseClick(controls.calculate_baseline_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: "get_baseline_stats" in emitted_actions, timeout=QT_POLL_TIMEOUT_MS
        )

    if hasattr(controls, "update_psd_pushButton"):
        QTest.mouseClick(controls.update_psd_pushButton, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: "load_data_and_update_psd" in emitted_actions,
            timeout=QT_POLL_TIMEOUT_MS,
        )
