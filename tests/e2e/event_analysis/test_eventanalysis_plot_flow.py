# Run with: pytest tests/e2e/event_analysis/test_eventanalysis_plot_flow.py -v -s
"""
E2E/UX: Open Event Analysis, add an EventLoader, select a channel, plot
events, navigate event-index right/left (shift-by-range-width semantics,
including rejection at the negative boundary), then walk the plotting
pathway matrix: filter on/off x RAW checkbox on/off, plus the post-fit
"Fit" overlay appearing on top of whichever combination was active.

Test data comes from the ``synthetic_events_database`` fixture (see
tests/synthetic_data/synthetic_events_db.py and
tests/e2e/event_analysis/conftest.py), which plants 25 known events on
channel 0 rather than depending on a checked-in real database. The
fitter's ``Step Size`` here (100.0 pA) is set below the planted event
depth (400 pA) so CUSUM registers a level change and successfully fits;
see test_e2e_eventanalysis_fit_events_flow.py's module docstring for how
that relationship was confirmed against the real CUSUM class.

Assertions:
- After Plot Events, something is plotted (any line on any axes).
- event_index_lineEdit text shifts by range width and rejects going negative.
- Plotting pathway matrix (5 events selected, so N lines per event):
    no filter,  raw off -> baseline line count (1x per event)
    no filter,  raw on  -> SAME as above (raw checkbox is a no-op
                            without an active filter)
    filter on,  raw off -> SAME line count (filtered "Data" replaces raw
                            "Data", count doesn't change)
    filter on,  raw on  -> MORE lines (Data + Raw overlay per event)
    filter on,  raw on, after successful fit -> MORE lines again
                            (Data + Raw + Fit overlay per event)
"""

import os
import sys
from pathlib import Path

import pytest
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import (
    QT_SHORT_PAUSE_MS,
    QT_WAIT_TIMEOUT_MS,
    ensure_name_filled,
    find_button,
    open_menu_hybrid,
    schedule_dialog_autofill,
)

# tests/e2e/event_analysis/this_file.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---- Env knobs, specific to this suite (not shared with raw_data) --------
LOADER_NAME = os.getenv("E2E_EVENTLOADER_NAME", "SQLiteEventLoader")
FILTER_NAME = os.getenv("E2E_FILTER_NAME", "BesselFilter")
FITTER_NAME = os.getenv("E2E_EVENTFITTER_NAME", "CUSUM")

EVENT_RANGE_START = "0-4"  # 5 events: indices 0,1,2,3,4
EVENT_RANGE_RIGHT = "5-9"


# ------------- helpers specific to this tab's controls --------------------
# EventAnalysisControls disables Plot/Fit if more than one channel is
# checked, unlike RawDataControls -- so channel selection here needs its
# own single-select logic rather than tests.e2e._helpers.select_any_channel.


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
            lw.item(i).setCheckState(Qt.CheckState.Unchecked)
        labels = [lw.item(i).text() for i in range(lw.count())]
        label = prefer if prefer in labels else labels[0]
        if hasattr(cb, "selectItem"):
            cb.selectItem(label)
            if hasattr(cb, "refreshDisplayText"):
                cb.refreshDisplayText()
        else:
            for i in range(lw.count()):
                if lw.item(i).text() == label:
                    lw.item(i).setCheckState(Qt.CheckState.Checked)
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
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    return _count_lines(ea_view.figure)


# ------------- Test -------------------------------------------------------


@pytest.mark.e2e_ux
@pytest.mark.timeout(180)
def test_event_analysis_nav_and_plotting_matrix(
    qtbot, tmp_path, monkeypatch, caplog, synthetic_events_database
):
    db = synthetic_events_database

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(
            _fake_get_item_exact_then_substring(LOADER_NAME, FILTER_NAME, FITTER_NAME)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(db.db_path), "All Files (*)")),
        raising=False,
    )

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

    open_menu_hybrid(
        view, ["Analysis", "New Analysis Tab", "EventAnalysisController"], qtbot
    )
    qtbot.waitUntil(
        lambda: "EventAnalysisView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS
    )
    view.switch_to_page("EventAnalysisView")
    ea_view = view.pages["EventAnalysisView"]["widget"]
    controls = ea_view.eventAnalysisControls

    def fill_loader_dialog(dlg) -> bool:
        pick_btn = find_button(dlg, "select input file")
        if pick_btn:
            QTest.mouseClick(pick_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(QT_SHORT_PAUSE_MS)
        ensure_name_filled(dlg, "loader_e2e")
        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_loader_dialog)
    QTest.mouseClick(controls.loaders_add_button, Qt.MouseButton.LeftButton)
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
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(ea_view.figure) > before_lines, timeout=QT_WAIT_TIMEOUT_MS
    )
    baseline_lines_no_filter_raw_off = _count_lines(ea_view.figure)

    assert controls.event_index_lineEdit.text().strip() == EVENT_RANGE_START

    if controls.right_arrow_button.isEnabled():
        QTest.mouseClick(controls.right_arrow_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: controls.event_index_lineEdit.text().strip() == EVENT_RANGE_RIGHT,
            timeout=QT_WAIT_TIMEOUT_MS,
        )

    if controls.left_arrow_button.isEnabled():
        QTest.mouseClick(controls.left_arrow_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: controls.event_index_lineEdit.text().strip() == EVENT_RANGE_START,
            timeout=QT_WAIT_TIMEOUT_MS,
        )

    # One more LEFT from 0-4 would go negative -- expected to be rejected
    # (stays at 0-4, logs "Indices must be positive"), not crash and not
    # silently accept a negative range.
    if controls.left_arrow_button.isEnabled():
        caplog.clear()
        QTest.mouseClick(controls.left_arrow_button, Qt.MouseButton.LeftButton)
        qtbot.wait(QT_SHORT_PAUSE_MS)
        assert controls.event_index_lineEdit.text().strip() == EVENT_RANGE_START
        assert any("Indices must be positive" in rec.message for rec in caplog.records)

    # =========================================================
    # STAGE 2: no filter, raw ON -> should be a no-op (same count)
    # =========================================================
    controls.raw_checkbox.setChecked(True)
    lines_no_filter_raw_on = _replot_and_count(qtbot, controls, ea_view)
    assert lines_no_filter_raw_on == baseline_lines_no_filter_raw_off

    controls.raw_checkbox.setChecked(False)

    # =========================================================
    # STAGE 3: add + select filter, raw off -> same count, different data
    # =========================================================
    def fill_filter_dialog(dlg) -> bool:
        ensure_name_filled(dlg, f"{FILTER_NAME}_e2e")
        filterset = getattr(dlg, "entrywidgets", {})

        def _set_and_commit(widget, text):
            widget.setText(text)
            widget.editingFinished.emit()

        if "Cutoff" in filterset and hasattr(filterset["Cutoff"], "setText"):
            _set_and_commit(filterset["Cutoff"], "100000.0")
        if "Samplerate" in filterset and hasattr(filterset["Samplerate"], "setText"):
            _set_and_commit(filterset["Samplerate"], str(db[0].samplerate))
        if "Poles" in filterset:
            poles_widget = filterset["Poles"]
            if hasattr(poles_widget, "setText"):
                _set_and_commit(poles_widget, "8")
            elif hasattr(poles_widget, "setValue"):
                poles_widget.setValue(8)
        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_filter_dialog)
    QTest.mouseClick(controls.filters_add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: controls.filters_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    assert controls.filters_comboBox.currentText() != "No Filter"

    lines_with_filter_raw_off = _replot_and_count(qtbot, controls, ea_view)
    assert lines_with_filter_raw_off == baseline_lines_no_filter_raw_off

    # =========================================================
    # STAGE 4: filter ON, raw ON -> more lines (Data + Raw overlay)
    # =========================================================
    controls.raw_checkbox.setChecked(True)
    lines_with_filter_raw_on = _replot_and_count(qtbot, controls, ea_view)
    assert lines_with_filter_raw_on > lines_with_filter_raw_off

    # =========================================================
    # STAGE 5: add + fit an EventFitter, then re-plot -> even more lines
    # (Data + Raw + Fit overlay per event), on top of stage 4's state.
    #
    # Step Size (100 pA) is set below the planted event depth (400 pA) so
    # CUSUM registers a level change -- confirmed against the real CUSUM
    # class in test_e2e_eventanalysis_fit_events_flow.py. Using the
    # documented real-fixture value (1000 pA) here would fail to fit
    # against this synthetic data's shallower default events.
    # =========================================================
    def fill_fitter_dialog(dlg) -> bool:
        ensure_name_filled(dlg, f"{FITTER_NAME}_e2e")
        fitterset = getattr(dlg, "entrywidgets", {})

        def _set_and_commit(widget, text):
            widget.setText(text)
            widget.editingFinished.emit()

        if "Step Size" in fitterset and hasattr(fitterset["Step Size"], "setText"):
            _set_and_commit(fitterset["Step Size"], "100.0")
        if "Rise Time" in fitterset and hasattr(fitterset["Rise Time"], "setText"):
            _set_and_commit(fitterset["Rise Time"], "10.0")
        if "Max Sublevels" in fitterset and hasattr(
            fitterset["Max Sublevels"], "setText"
        ):
            _set_and_commit(fitterset["Max Sublevels"], "1000")
        if "Sensitivity" in fitterset and hasattr(fitterset["Sensitivity"], "setText"):
            _set_and_commit(fitterset["Sensitivity"], "1.0")
        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_fitter_dialog)
    QTest.mouseClick(controls.eventfitters_add_button, Qt.MouseButton.LeftButton)
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
    QTest.mouseClick(controls.fit_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(fitting_complete, timeout=QT_WAIT_TIMEOUT_MS)

    lines_after_fit = _replot_and_count(qtbot, controls, ea_view)
    assert lines_after_fit > lines_with_filter_raw_on

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()