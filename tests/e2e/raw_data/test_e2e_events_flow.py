"""
E2E/UX flow for Events (Phase C):
1) Open RawData tab.
2) Add a reader and draw a trace (so there is data in view).
3) Add an EventFinder:
   - Subclass picker: choose ClassicBlockageFinder (or E2E_EVENTFINDER_NAME).
   - Settings dialog: set MetaReader to the reader instance we created.
   - Fill numeric fields (Threshold, Min/Max Duration, Min Separation) and OK.
4) Start timer, Find Events, Plot Events, and poke event nav arrows.
5) Add Writer (SQLiteEventWriter), auto-fill fields, commit events to DB.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import open_menu_hybrid

# Repo root path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---- Env knobs ---------------------------------------------------------

READER_NAME = os.getenv("E2E_READER_NAME", "ChimeraReader20240501")
FINDER_SUBCLASS_NAME = os.getenv("E2E_EVENTFINDER_NAME", "ClassicBlockageFinder")
WRITER_SUBCLASS_NAME = os.getenv("E2E_WRITER_NAME", "SQLiteEventWriter")
TEST_LOG_NAME = os.getenv("E2E_TEST_LOG", "2kbp_n200mV_HS3_20240604_122657.log")
DEFAULT_SAMPLERATE_HZ = os.getenv("E2E_SAMPLERATE", "4000000")  # 4e6

E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "180"))
QT_WAIT_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "60000"))
QT_WAIT_SHORT_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "300"))

# ------------- helpers -----------------------------------------------------


def _first_modal_dialog():
    w = QtWidgets.QApplication.activeModalWidget()
    return w if isinstance(w, QtWidgets.QDialog) else None


def _find_button(dlg: QtWidgets.QDialog, label_lower: str):
    for b in dlg.findChildren(QtWidgets.QPushButton):
        if (b.text() or "").lower() == (label_lower or "").lower():
            return b
    return None


def _find_button_contains(dlg: QtWidgets.QDialog, snippet: str):
    needle = (snippet or "").lower()
    for b in dlg.findChildren(QtWidgets.QPushButton):
        if needle in (b.text() or "").lower():
            return b
    return None


def _find_live_channel_combo(controls):
    cb = getattr(controls, "channel_comboBox", None)
    if isinstance(cb, QtWidgets.QComboBox):
        return cb
    for cb in controls.findChildren(QtWidgets.QComboBox):
        if "channel" in (cb.objectName() or "").lower():
            return cb
    return None


def _select_any_channel(cb) -> bool:
    lw = getattr(cb, "listWidget", None)
    if lw is not None:  # MultiSelectComboBox
        if lw.count() == 0:
            return False
        label = lw.item(0).text()
        if hasattr(cb, "selectItem"):
            cb.selectItem(label)
            if hasattr(cb, "refreshDisplayText"):
                cb.refreshDisplayText()
        else:
            lw.item(0).setCheckState(Qt.Checked)
        return True
    if cb.count() > 0:
        cb.setCurrentIndex(0)
        return True
    return False


def _count_lines(fig):
    return sum(len(ax.lines) for ax in getattr(fig, "axes", []) or [])


# -----------Test ----------------------------------------------------------


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_events_flow_clicks(qtbot, tmp_path, monkeypatch):
    # --- Patch subclass picker
    def fake_get_item(_parent, _title, _label, items, *_a, **_k):
        for want in [FINDER_SUBCLASS_NAME, READER_NAME, WRITER_SUBCLASS_NAME]:
            if want and any(want in it for it in items):
                for it in items:
                    if want in it:
                        return it, True
        return (items[0] if items else "No Selection"), True

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )

    # Patch file dialog
    data_file = (
        REPO_ROOT / "tests" / "data" / TEST_LOG_NAME
        if (REPO_ROOT / "tests" / "data" / TEST_LOG_NAME).exists()
        else REPO_ROOT / "data" / TEST_LOG_NAME
    )
    assert data_file.exists(), f"Missing test file: {data_file}"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(data_file), "All Files (*)")),
        raising=False,
    )

    # Patch TimeWidget so it doesn’t block
    import poriscope.plugins.analysistabs.RawDataView as rawdataview_mod
    import poriscope.views.widgets.time_widget as time_widget_mod

    class _FakeTimeWidget:
        def __init__(self, *a, **k):
            self._res = {3: {"ranges": [(0.0, 5.0)]}}

        def exec(self):
            return 1

        def get_result(self):
            return self._res

    monkeypatch.setattr(time_widget_mod, "TimeWidget", _FakeTimeWidget)
    monkeypatch.setattr(rawdataview_mod, "TimeWidget", _FakeTimeWidget)

    # Boot MVC
    app_config = {
        "Parent Folder": str(tmp_path),
        "User Plugin Folder": str(tmp_path),
        "Log Level": 20,
    }
    model = MainModel(app_config)
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)  # noqa
    qtbot.addWidget(view)
    view.show()

    # Open RawData tab
    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "RawDataController"],
        qtbot,
        timeout_ms=QT_WAIT_TIMEOUT_MS,
    )
    qtbot.waitUntil(lambda: "RawDataView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("RawDataView")
    raw_view = view.pages["RawDataView"]["widget"]
    controls = raw_view.rawdatacontrols

    # Reader autofill
    def auto_complete_reader_settings():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_reader_settings)
            return
        pick_btn = _find_button_contains(dlg, "select input file")
        if pick_btn:
            QTest.mouseClick(pick_btn, Qt.LeftButton)
            qtbot.wait(QT_WAIT_SHORT_MS)
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower() and not w.text().strip():
                w.setText("reader_e2e")
        for key, w in getattr(dlg, "entrywidgets", {}).items():
            if "rate" in (key or "").lower() and hasattr(w, "setText"):
                w.setText(str(DEFAULT_SAMPLERATE_HZ))
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_reader_settings)

    QtCore.QTimer.singleShot(0, auto_complete_reader_settings)

    # Add reader
    QTest.mouseClick(controls.readers_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.readers_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    reader_key = controls.readers_comboBox.currentText()

    # Select channel
    qtbot.waitUntil(
        lambda: _find_live_channel_combo(controls) is not None,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    assert _select_any_channel(_find_live_channel_combo(controls))

    # Draw a trace
    controls.set_range_inputs(0, 2.0)
    qtbot.waitUntil(
        lambda: controls.update_trace_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    before_lines = _count_lines(raw_view.figure)
    QTest.mouseClick(controls.update_trace_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(raw_view.figure) > before_lines, timeout=QT_WAIT_TIMEOUT_MS
    )

    # EventFinder autofill
    def auto_complete_eventfinder_settings(expected_reader_key: str):
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(
                50, lambda: auto_complete_eventfinder_settings(expected_reader_key)
            )
            return
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower() and not w.text().strip():
                w.setText(f"{FINDER_SUBCLASS_NAME}_e2e")
        for key, cb in getattr(dlg, "entrywidgets", {}).items():
            if key.lower().replace(" ", "") in {"metareader", "reader"}:
                if isinstance(cb, QtWidgets.QComboBox):
                    idx = cb.findText(expected_reader_key)
                    cb.setCurrentIndex(idx if idx >= 0 else 0)
        finderset = getattr(dlg, "entrywidgets", {})
        if "Threshold" in finderset and hasattr(finderset["Threshold"], "setText"):
            finderset["Threshold"].setText("2000.0")
        if "Min Duration" in finderset and hasattr(
            finderset["Min Duration"], "setText"
        ):
            finderset["Min Duration"].setText("1.0")
        if "Max Duration" in finderset and hasattr(
            finderset["Max Duration"], "setText"
        ):
            finderset["Max Duration"].setText("1000000.0")
        if "Min Separation" in finderset and hasattr(
            finderset["Min Separation"], "setText"
        ):
            finderset["Min Separation"].setText("1.0")
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(
                50, lambda: auto_complete_eventfinder_settings(expected_reader_key)
            )

    QtCore.QTimer.singleShot(0, lambda: auto_complete_eventfinder_settings(reader_key))

    # Add EventFinder
    QTest.mouseClick(controls.eventfinders_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.eventfinders_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )

    # Wait for events
    def events_found():
        try:
            finder_key = controls.eventfinders_comboBox.currentText()
            raw_view.global_signal.emit(
                "MetaEventFinder",
                finder_key,
                "get_num_events_found",
                (3,),
                "set_num_events_allowed",
                (),
            )
            return getattr(raw_view, "num_events_allowed", 0) > 0
        except Exception:
            return False

    QTest.mouseClick(controls.timer_pushButton, Qt.LeftButton)
    QTest.mouseClick(controls.find_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(events_found, timeout=QT_WAIT_TIMEOUT_MS)

    # Plot events
    controls.event_index_lineEdit.setText("0-3")
    before = _count_lines(raw_view.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(raw_view.figure) > before, timeout=QT_WAIT_TIMEOUT_MS
    )

    # Writer autofill
    out_db = tmp_path / "events_out.sqlite"

    def auto_complete_writer_settings(expected_finder_key: str):
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(
                50, lambda: auto_complete_writer_settings(expected_finder_key)
            )
            return

        writer_widgets = getattr(dlg, "entrywidgets", {})

        # Select finder
        if "MetaEventFinder" in writer_widgets:
            cb = writer_widgets["MetaEventFinder"]
            if isinstance(cb, QtWidgets.QComboBox):
                idx = cb.findText(expected_finder_key)
                cb.setCurrentIndex(idx if idx >= 0 else 0)

        # Fill known writer fields
        if "Experiment Name" in writer_widgets and isinstance(
            writer_widgets["Experiment Name"], QtWidgets.QLineEdit
        ):
            writer_widgets["Experiment Name"].setText("chimera_integration_test")

        if "Voltage" in writer_widgets and isinstance(
            writer_widgets["Voltage"], QtWidgets.QLineEdit
        ):
            writer_widgets["Voltage"].setText("200.0")

        if "Membrane Thickness" in writer_widgets and isinstance(
            writer_widgets["Membrane Thickness"], QtWidgets.QLineEdit
        ):
            writer_widgets["Membrane Thickness"].setText("10.0")

        if "Conductivity" in writer_widgets and isinstance(
            writer_widgets["Conductivity"], QtWidgets.QLineEdit
        ):
            writer_widgets["Conductivity"].setText("1.0")

        if "Output File" in writer_widgets and isinstance(
            writer_widgets["Output File"], QtWidgets.QLineEdit
        ):
            writer_widgets["Output File"].setText(str(out_db))

        # force Value into params too
        if hasattr(dlg, "params") and "Output File" in dlg.params:
            dlg.params["Output File"]["Value"] = str(out_db)

        # Tick the unitwidget
        if "Output File" in getattr(dlg, "unitwidgets", {}):
            dlg.unitwidgets["Output File"].setChecked(True)

        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(
                50, lambda: auto_complete_writer_settings(expected_finder_key)
            )

    QtCore.QTimer.singleShot(
        0, lambda: auto_complete_writer_settings(f"{FINDER_SUBCLASS_NAME}_0")
    )

    # Add Writer
    QTest.mouseClick(controls.writers_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.writers_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )

    # Commit events
    QTest.mouseClick(controls.commit_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: out_db.exists(), timeout=QT_WAIT_TIMEOUT_MS)

    with sqlite3.connect(out_db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        assert any(
            "event" in t.lower() for t in tables
        ), f"No event tables in DB: {tables}"

    # Nav arrows
    if hasattr(controls, "right_plot_arrow_button"):
        QTest.mouseClick(controls.right_plot_arrow_button, Qt.LeftButton)
        qtbot.wait(QT_WAIT_SHORT_MS)
        QTest.mouseClick(controls.left_plot_arrow_button, Qt.LeftButton)
        qtbot.wait(QT_WAIT_SHORT_MS)

    # Cleanup stray dialogs
    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
