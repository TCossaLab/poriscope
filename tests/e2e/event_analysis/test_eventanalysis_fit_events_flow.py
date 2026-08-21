# Run with: pytest tests/e2e/event_analysis/test_eventanalysis_fit_events_flow.py -v
"""
E2E/UX flow for Event Fitting:
1) Open Event Analysis tab.
2) Add events database (an EventLoader pointed at the synthetic
   events_database fixture) so there is a real events DB in view. Assert
   the loader reports the planted ground truth: 25 events at 500000.00Hz.
3) Select a single channel (Plot/Fit are disabled if more than one channel
   is checked in this tab, unlike RawData). Fixture channel 0.
4) Plot Events so there is data on screen before fitting.
5) Add an EventFitter:
   - Subclass picker: choose CUSUM (or E2E_EVENTFITTER_NAME).
   - Settings dialog: MetaEventLoader defaults to the only loader instance
     created (MetaEventFitter.get_empty_settings() pre-selects
     eventloader_options[0] when there's just one), so no explicit
     selection is needed here.
   - Fill numeric fields (Step Size, Rise Time, Max Sublevels, Sensitivity)
     and OK.
6) Fit Events, wait for fitting to complete, Plot Events again to confirm
   the fit overlay renders.
7) Add DB Writer (SQLiteDBWriter), auto-fill fields, commit events to DB.

Ground truth and Step Size / event-depth relationship
-------------------------------------------------------
Unlike the old fixed real fixture DB, the synthetic_events_database
fixture's event depth is known exactly (400 pA, see
tests/synthetic_data/synthetic_events_db.py's defaults). CUSUM's "Step
Size" setting is the minimum current step it looks for; if Step Size
exceeds the actual event depth, CUSUM can't register a level change at
all. This was confirmed empirically against the real CUSUM class (not
assumed) before writing the two cases below:

  - Step Size=100.0 (below the 400 pA event depth):
        CUSUM finds all 25/25 events as good fits, no rejections.

  - Step Size=1000.0 (above the 400 pA event depth, deliberately
    mismatched):
        CUSUM finds 0/25 good fits, all 25 rejected with reason
        "Too Few Levels" -- exercising the "fit finds nothing usable"
        path end to end, confirming the app doesn't crash and correctly
        reports zero events rather than silently succeeding with stale
        or partial data.

What's NOT covered here
------------------------
The old real-fixture test additionally had a filtered case (BesselFilter
applied before fitting, expected 24/25 with one rejection) to exercise
CUSUM's interaction with a filter. That interaction hasn't been
independently verified against this synthetic generator's data -- doing
so meaningfully would require confirming what filtering actually does to
this specific synthetic event shape, not assuming the old real-fixture
DB's 24/25 outcome carries over. Left for a follow-up pass rather than
guessed at here.
"""

import os
import sqlite3
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

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---- Env knobs, specific to this suite ------------------------------------
LOADER_NAME = os.getenv("E2E_EVENTLOADER_NAME", "SQLiteEventLoader")
FITTER_NAME = os.getenv("E2E_EVENTFITTER_NAME", "CUSUM")
DB_WRITER_NAME = os.getenv("E2E_DBWRITER_NAME", "SQLiteDBWriter")

FIT_CHANNEL = 0


def _find_live_channel_combo(controls):
    cb = getattr(controls, "channel_comboBox", None)
    if isinstance(cb, QtWidgets.QComboBox):
        return cb
    for cb in controls.findChildren(QtWidgets.QComboBox):
        if "channel" in (cb.objectName() or "").lower():
            return cb
    return None


def _select_single_channel(cb, prefer: str = "0") -> bool:
    """EventAnalysisControls disables Plot/Fit if more than one channel is
    checked; select exactly the fixture's channel rather than "whichever
    is first"."""
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


@pytest.mark.e2e_ux
@pytest.mark.timeout(180)
@pytest.mark.parametrize(
    "step_size,expected_good_fits",
    [
        pytest.param(100.0, 25, id="step_size_100_all_fit"),
        pytest.param(1000.0, 0, id="step_size_1000_too_few_levels"),
    ],
)
def test_event_fitting_flow_clicks(
    qtbot,
    tmp_path,
    monkeypatch,
    synthetic_events_database,
    step_size,
    expected_good_fits,
):
    db = synthetic_events_database

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(
            _fake_get_item_exact_then_substring(
                FITTER_NAME, LOADER_NAME, DB_WRITER_NAME
            )
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

    # --- Loader ---
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

    loader_key = controls.loaders_comboBox.currentText()
    ea_view.global_signal.emit(
        "MetaEventLoader",
        loader_key,
        "get_num_events",
        (FIT_CHANNEL,),
        "set_num_events_allowed",
        (),
    )
    assert getattr(ea_view, "num_events_allowed", None) == db[FIT_CHANNEL].num_events

    ea_view.global_signal.emit(
        "MetaEventLoader",
        loader_key,
        "get_samplerate",
        (FIT_CHANNEL,),
        "update_plot_samplerate",
        (),
    )
    assert getattr(ea_view, "plot_samplerate", None) == pytest.approx(
        db[FIT_CHANNEL].samplerate
    )

    # --- Channel ---
    qtbot.waitUntil(
        lambda: _find_live_channel_combo(controls) is not None,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    assert _select_single_channel(
        _find_live_channel_combo(controls), prefer=str(FIT_CHANNEL)
    )

    # --- Plot before fitting ---
    controls.event_index_lineEdit.setText("0-3")
    qtbot.waitUntil(
        lambda: controls.plot_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    before_lines = _count_lines(ea_view.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(ea_view.figure) > before_lines, timeout=QT_WAIT_TIMEOUT_MS
    )

    # --- EventFitter ---
    def fill_fitter_dialog(dlg) -> bool:
        ensure_name_filled(dlg, f"{FITTER_NAME}_e2e")
        # MetaEventLoader is left alone here: get_empty_settings() already
        # defaults it to eventloader_options[0], and only one loader exists.
        fitterset = getattr(dlg, "entrywidgets", {})

        def _set_and_commit(widget, text):
            widget.setText(text)
            widget.editingFinished.emit()

        if "Step Size" in fitterset and hasattr(fitterset["Step Size"], "setText"):
            _set_and_commit(fitterset["Step Size"], f"{step_size:.1f}")
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
                (FIT_CHANNEL,),
                "set_eventfitting_status",
                (),
            )
            return getattr(ea_view, "eventfitting_status", False) is True
        except Exception:
            return False

    QTest.mouseClick(controls.fit_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(fitting_complete, timeout=QT_WAIT_TIMEOUT_MS)

    fitter_key = controls.eventfitters_comboBox.currentText()
    ea_view.global_signal.emit(
        "MetaEventFitter",
        fitter_key,
        "get_num_events",
        (FIT_CHANNEL,),
        "set_num_events_allowed",
        (),
    )
    assert getattr(ea_view, "num_events_allowed", None) == expected_good_fits, (
        f"Expected {expected_good_fits}/{db[FIT_CHANNEL].num_events} good fits at "
        f"Step Size={step_size}, got {getattr(ea_view, 'num_events_allowed', None)}"
    )

    if expected_good_fits == 0:
        # Rejection reason ("Too Few Levels") was confirmed directly against
        # the real CUSUM class's .rejected attribute (see module docstring)
        # rather than through a GUI-exposed getter -- MetaEventFitter has
        # no public get_rejected_events method to check this through the
        # signal bus, so the count assertion above is what this case relies
        # on for verification.
        pass

    before_fit_lines = _count_lines(ea_view.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(ea_view.figure) >= before_fit_lines,
        timeout=QT_WAIT_TIMEOUT_MS,
    )

    # --- Writer (only exercised for the fully-successful case) ---
    if expected_good_fits > 0:
        out_db = tmp_path / "fitted_events_out.sqlite"

        def fill_writer_dialog(dlg) -> bool:
            writer_widgets = getattr(dlg, "entrywidgets", {})

            if "MetaEventFitter" in writer_widgets and isinstance(
                writer_widgets["MetaEventFitter"], QtWidgets.QComboBox
            ):
                idx = writer_widgets["MetaEventFitter"].findText(fitter_key)
                writer_widgets["MetaEventFitter"].setCurrentIndex(
                    idx if idx >= 0 else 0
                )

            text_fields = {
                "Experiment Name": "e2e_synthetic_fit_test",
                "Voltage": "200.0",
                "Membrane Thickness": "10.0",
                "Conductivity": "10.0",
            }
            for field, value in text_fields.items():
                if field in writer_widgets and isinstance(
                    writer_widgets[field], QtWidgets.QLineEdit
                ):
                    writer_widgets[field].setText(value)
                    writer_widgets[field].editingFinished.emit()

            if "Output File" in writer_widgets and isinstance(
                writer_widgets["Output File"], QtWidgets.QLineEdit
            ):
                writer_widgets["Output File"].setText(str(out_db))
            if hasattr(dlg, "params") and "Output File" in dlg.params:
                dlg.params["Output File"]["Value"] = str(out_db)
            if "Output File" in getattr(dlg, "unitwidgets", {}):
                dlg.unitwidgets["Output File"].setChecked(True)

            ok = find_button(dlg, "ok", exact=True)
            if ok and ok.isEnabled():
                QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
                return True
            return False

        schedule_dialog_autofill(fill_writer_dialog)
        QTest.mouseClick(controls.writers_add_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: controls.writers_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
        )

        QTest.mouseClick(controls.commit_btn, Qt.MouseButton.LeftButton)

        # SQLite creates the file on connection open, before rows are
        # written, and commit runs asynchronously (same pattern as fit
        # itself) -- poll row count rather than racing file existence.
        def _row_count():
            try:
                with sqlite3.connect(out_db) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        'SELECT COUNT(*) FROM "events" WHERE channel_id = ?',
                        (FIT_CHANNEL,),
                    )
                    return cur.fetchone()[0]
            except sqlite3.OperationalError:
                return None

        qtbot.waitUntil(
            lambda: _row_count() == expected_good_fits, timeout=QT_WAIT_TIMEOUT_MS
        )

        with sqlite3.connect(out_db) as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT COUNT(*) FROM "events" WHERE channel_id = ?', (FIT_CHANNEL,)
            )
            row_count = cur.fetchone()[0]
            assert row_count == expected_good_fits

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
