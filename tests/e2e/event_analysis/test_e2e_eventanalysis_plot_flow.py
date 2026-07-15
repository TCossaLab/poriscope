"""
E2E/UX: Open Event Analysis, add an EventLoader, select a channel, plot
events, navigate event-index right/left (confirmed shift-by-range-width
semantics, including rejection at the negative boundary), then walk the
full plotting pathway matrix: filter on/off x RAW checkbox on/off, plus
the post-fit "Fit" overlay appearing on top of whichever combination was
active.

Assertions:
- After Plot Events, something is plotted (any line on any axes).
- event_index_lineEdit text is:
    "0-4" -> RIGHT -> "5-9" -> LEFT -> "0-4" -> LEFT again -> REJECTED,
    stays "0-4", logs "Indices must be positive" (confirmed real
    behavior; range shifts by its own width, not a fixed offset).
- Plotting pathway matrix (5 events selected, so N lines per event):
    no filter,  raw off -> baseline line count (1x per event)
    no filter,  raw on  -> SAME as above (raw checkbox is a no-op
                            without an active filter - confirmed real)
    filter on,  raw off -> SAME line count as above (filtered "Data"
                            replaces raw "Data", count doesn't change)
    filter on,  raw on  -> MORE lines (Data + Raw overlay per event)
    filter on,  raw on, after successful fit -> MORE lines again
                            (Data + Raw + Fit overlay per event)

Run with:
    pytest tests/e2e/event_analysis/test_e2e_eventanalysis_plot_flow.py -v -s
"""

import os
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

# tests/e2e/event_analysis/this_file.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---- Env knobs --------------------------------------------------------
EVENTS_DB_NAME = os.getenv("E2E_EVENTS_DB", "events.sqlite3")
LOADER_SUBCLASS_NAME = os.getenv("E2E_EVENTLOADER_NAME", "SQLiteEventLoader")
FILTER_SUBCLASS_NAME = os.getenv("E2E_FILTER_NAME", "BesselFilter")
FITTER_SUBCLASS_NAME = os.getenv("E2E_EVENTFITTER_NAME", "CUSUM")

E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "180"))
QT_WAIT_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "60000"))
QT_WAIT_SHORT_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "300"))

EVENT_RANGE_START = "0-4"  # 5 events: indices 0,1,2,3,4
EVENT_RANGE_RIGHT = "5-9"  # confirmed real shift-by-width behavior
NUM_EVENTS = 5


# ------------- helpers (kept local to this file) --------------------------


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


def _select_single_channel(cb, prefer: str = "0") -> bool:
    lw = getattr(cb, "listWidget", None)
    if lw is not None:
        if lw.count() == 0:
            return False
        for i in range(lw.count()):
            lw.item(i).setCheckState(Qt.Unchecked)
        labels = [lw.item(i).text() for i in range(lw.count())]
        label = prefer if prefer in labels else labels[0]
        if hasattr(cb, "selectItem"):
            cb.selectItem(label)
            if hasattr(cb, "refreshDisplayText"):
                cb.refreshDisplayText()
        else:
            for i in range(lw.count()):
                if lw.item(i).text() == label:
                    lw.item(i).setCheckState(Qt.Checked)
        return True
    if cb.count() > 0:
        idx = cb.findText(prefer)
        cb.setCurrentIndex(idx if idx >= 0 else 0)
        return True
    return False


def _count_lines(fig):
    return sum(len(ax.lines) for ax in getattr(fig, "axes", []) or [])


def _fake_get_item_exact_then_substring(*wants):
    """Prefer exact match over substring match to avoid ambiguous
    collisions (e.g. "CUSUM" also matching "ClassicCUSUM")."""

    def fake_get_item(_parent, _title, _label, items, *_a, **_k):
        for want in wants:
            if not want:
                continue
            for it in items:
                if it == want:
                    return it, True
        for want in wants:
            if want and any(want in it for it in items):
                for it in items:
                    if want in it:
                        return it, True
        return (items[0] if items else "No Selection"), True

    return fake_get_item


def _replot_and_count(qtbot, controls, ea_view):
    """Click Plot Events and return the resulting total line count."""
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)  # allow figure to settle even if count is unchanged
    return _count_lines(ea_view.figure)


# ------------- Test -------------------------------------------------------


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_event_analysis_nav_and_plotting_matrix(qtbot, tmp_path, monkeypatch, caplog):
    events_db = (
        REPO_ROOT / "tests" / "data" / EVENTS_DB_NAME
        if (REPO_ROOT / "tests" / "data" / EVENTS_DB_NAME).exists()
        else REPO_ROOT / "data" / EVENTS_DB_NAME
    )
    assert events_db.exists(), f"Missing test file: {events_db}"

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(
            _fake_get_item_exact_then_substring(
                LOADER_SUBCLASS_NAME, FILTER_SUBCLASS_NAME, FITTER_SUBCLASS_NAME
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(events_db), "All Files (*)")),
        raising=False,
    )

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

    # Open Event Analysis tab
    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "EventAnalysisController"],
        qtbot,
        timeout_ms=QT_WAIT_TIMEOUT_MS,
    )
    qtbot.waitUntil(
        lambda: "EventAnalysisView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS
    )
    view.switch_to_page("EventAnalysisView")
    ea_view = view.pages["EventAnalysisView"]["widget"]
    controls = ea_view.eventAnalysisControls

    # Loader autofill
    def auto_complete_loader_settings():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_loader_settings)
            return
        pick_btn = _find_button_contains(dlg, "select input file")
        if pick_btn:
            QTest.mouseClick(pick_btn, Qt.LeftButton)
            qtbot.wait(QT_WAIT_SHORT_MS)
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower() and not w.text().strip():
                w.setText("loader_e2e")
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_loader_settings)

    QtCore.QTimer.singleShot(0, auto_complete_loader_settings)

    QTest.mouseClick(controls.loaders_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.loaders_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )

    qtbot.waitUntil(
        lambda: _find_live_channel_combo(controls) is not None,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    assert _select_single_channel(_find_live_channel_combo(controls))

    # =========================================================
    # STAGE 1: no filter, raw off -> baseline plot + navigation
    # =========================================================
    controls.event_index_lineEdit.setText(EVENT_RANGE_START)
    qtbot.waitUntil(
        lambda: controls.plot_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    before_lines = _count_lines(ea_view.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(ea_view.figure) > before_lines, timeout=QT_WAIT_TIMEOUT_MS
    )
    baseline_lines_no_filter_raw_off = _count_lines(ea_view.figure)
    print(
        f"[DEBUG] Stage 1 (no filter, raw off): "
        f"{baseline_lines_no_filter_raw_off} lines"
    )

    assert controls.event_index_lineEdit.text().strip() == EVENT_RANGE_START, (
        f"Expected event index {EVENT_RANGE_START!r} initially, got "
        f"{controls.event_index_lineEdit.text()!r}"
    )

    # --- Navigation: 0-4 -> RIGHT -> 5-9 -> LEFT -> 0-4 -> LEFT -> rejected ---
    if controls.right_arrow_button.isEnabled():
        QTest.mouseClick(controls.right_arrow_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: controls.event_index_lineEdit.text().strip()
            == EVENT_RANGE_RIGHT,
            timeout=QT_WAIT_TIMEOUT_MS,
        )

    if controls.left_arrow_button.isEnabled():
        QTest.mouseClick(controls.left_arrow_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: controls.event_index_lineEdit.text().strip()
            == EVENT_RANGE_START,
            timeout=QT_WAIT_TIMEOUT_MS,
        )

    # One more LEFT from 0-4 would go negative - confirmed real behavior is
    # rejection (stays at 0-4, logs "Indices must be positive"), not a
    # crash and not silently accepting a negative range.
    if controls.left_arrow_button.isEnabled():
        caplog.clear()
        QTest.mouseClick(controls.left_arrow_button, Qt.LeftButton)
        qtbot.wait(QT_WAIT_SHORT_MS)
        assert controls.event_index_lineEdit.text().strip() == EVENT_RANGE_START, (
            f"Expected shift past zero to be rejected and stay at "
            f"{EVENT_RANGE_START!r}, got "
            f"{controls.event_index_lineEdit.text()!r}"
        )
        assert any(
            "Indices must be positive" in rec.message for rec in caplog.records
        ), (
            "Expected a warning log containing 'Indices must be positive' "
            "when shifting past the negative boundary"
        )

    # =========================================================
    # STAGE 2: no filter, raw ON -> should be a no-op (same count)
    # =========================================================
    controls.raw_checkbox.setChecked(True)
    lines_no_filter_raw_on = _replot_and_count(qtbot, controls, ea_view)
    print(f"[DEBUG] Stage 2 (no filter, raw ON): {lines_no_filter_raw_on} lines")
    assert lines_no_filter_raw_on == baseline_lines_no_filter_raw_off, (
        "Expected RAW checkbox to be a no-op with no filter active "
        f"({baseline_lines_no_filter_raw_off} -> {lines_no_filter_raw_on})"
    )

    controls.raw_checkbox.setChecked(False)

    # =========================================================
    # STAGE 3: add + select filter, raw off -> same count, different data
    # =========================================================
    def auto_complete_filter_settings():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_filter_settings)
            return
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower() and not w.text().strip():
                w.setText(f"{FILTER_SUBCLASS_NAME}_e2e")
        filterset = getattr(dlg, "entrywidgets", {})

        def _set_and_commit(widget, text):
            widget.setText(text)
            widget.editingFinished.emit()

        if "Cutoff" in filterset and hasattr(filterset["Cutoff"], "setText"):
            _set_and_commit(filterset["Cutoff"], "100000.0")
        if "Samplerate" in filterset and hasattr(filterset["Samplerate"], "setText"):
            _set_and_commit(filterset["Samplerate"], "500000.0")
        if "Poles" in filterset:
            poles_widget = filterset["Poles"]
            if hasattr(poles_widget, "setText"):
                _set_and_commit(poles_widget, "8")
            elif hasattr(poles_widget, "setValue"):
                poles_widget.setValue(8)
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_filter_settings)

    QtCore.QTimer.singleShot(0, auto_complete_filter_settings)

    QTest.mouseClick(controls.filters_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.filters_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    assert controls.filters_comboBox.currentText() != "No Filter", (
        "Filter was not selected; later RAW-checkbox assertions depend on "
        "an active filter to have any visible effect"
    )

    lines_with_filter_raw_off = _replot_and_count(qtbot, controls, ea_view)
    print(
        f"[DEBUG] Stage 3 (filter ON, raw off): {lines_with_filter_raw_off} lines"
    )
    assert lines_with_filter_raw_off == baseline_lines_no_filter_raw_off, (
        "Expected the same line COUNT with filter active but RAW unchecked "
        "(filtered data replaces raw as the single 'Data' trace; content "
        "differs but count shouldn't) "
        f"({baseline_lines_no_filter_raw_off} -> {lines_with_filter_raw_off})"
    )

    # =========================================================
    # STAGE 4: filter ON, raw ON -> more lines (Data + Raw overlay)
    # =========================================================
    controls.raw_checkbox.setChecked(True)
    lines_with_filter_raw_on = _replot_and_count(qtbot, controls, ea_view)
    print(f"[DEBUG] Stage 4 (filter ON, raw ON): {lines_with_filter_raw_on} lines")
    assert lines_with_filter_raw_on > lines_with_filter_raw_off, (
        "Expected MORE lines with filter active AND RAW checked (Data + "
        f"Raw overlay per event) ({lines_with_filter_raw_off} -> "
        f"{lines_with_filter_raw_on})"
    )

    # =========================================================
    # STAGE 5: add + fit an EventFitter, then re-plot -> even more lines
    # (Data + Raw + Fit overlay per event), on top of stage 4's state.
    # =========================================================
    def auto_complete_eventfitter_settings():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_eventfitter_settings)
            return
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower() and not w.text().strip():
                w.setText(f"{FITTER_SUBCLASS_NAME}_e2e")
        fitterset = getattr(dlg, "entrywidgets", {})

        def _set_and_commit(widget, text):
            widget.setText(text)
            widget.editingFinished.emit()

        if "Step Size" in fitterset and hasattr(fitterset["Step Size"], "setText"):
            _set_and_commit(fitterset["Step Size"], "1000.0")
        if "Rise Time" in fitterset and hasattr(fitterset["Rise Time"], "setText"):
            _set_and_commit(fitterset["Rise Time"], "10.0")
        if "Max Sublevels" in fitterset and hasattr(
            fitterset["Max Sublevels"], "setText"
        ):
            _set_and_commit(fitterset["Max Sublevels"], "1000")
        if "Sensitivity" in fitterset and hasattr(fitterset["Sensitivity"], "setText"):
            _set_and_commit(fitterset["Sensitivity"], "1.0")
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_eventfitter_settings)

    QtCore.QTimer.singleShot(0, auto_complete_eventfitter_settings)

    QTest.mouseClick(controls.eventfitters_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.eventfitters_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )

    def fitting_complete():
        try:
            fitter_key = controls.eventfitters_comboBox.currentText()
            ea_view.global_signal.emit(
                "MetaEventFitter",
                fitter_key,
                "get_eventfitting_status",
                (0,),
                "set_eventfitting_status",
                (),
            )
            return getattr(ea_view, "eventfitting_status", False) is True
        except Exception:
            return False

    qtbot.waitUntil(
        lambda: controls.fit_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    QTest.mouseClick(controls.fit_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(fitting_complete, timeout=QT_WAIT_TIMEOUT_MS)

    lines_after_fit = _replot_and_count(qtbot, controls, ea_view)
    print(f"[DEBUG] Stage 5 (filter ON, raw ON, fit done): {lines_after_fit} lines")
    assert lines_after_fit > lines_with_filter_raw_on, (
        "Expected MORE lines after a successful fit, on top of filter+raw "
        f"(Data + Raw + Fit overlay per event) ({lines_with_filter_raw_on} "
        f"-> {lines_after_fit})"
    )

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()