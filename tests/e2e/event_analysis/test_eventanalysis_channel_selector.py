# Run with: pytest tests/e2e/event_analysis/test_eventanalysis_channel_selector.py -v
"""
E2E/UX: channel selector population and gating behavior in Event Analysis.

Two things this tab does that are specific to EventAnalysisControls, not to
the MultiSelectComboBox widget itself (that widget's own mechanics --
select-all, deselect-all, select-one, signal emission -- are covered once,
for both tabs, in tests/unit/views/widgets/test_multiselect.py):

1. After adding a loader, the channel selector populates with exactly the
   channels the database actually has.
2. Plot Events is enabled only when exactly one channel is checked.
   Zero channels or two-or-more channels both leave it disabled --
   EventAnalysisControls' own restriction, confirmed in this repo's
   existing test docstrings ("Plot/Fit are disabled if more than one
   channel is checked in this tab, unlike RawData"). RawDataControls has
   no equivalent restriction, so this test has no raw_data counterpart.

Test data comes from the synthetic_multichannel_events_database fixture
(three channels, 0/1/2, five events each) -- see
tests/synthetic_data/synthetic_events_db.py and
tests/e2e/event_analysis/conftest.py.

Fit Events is not exercised here: it depends on an EventFitter existing in
addition to channel selection, which is a separate precondition from the
one this test isolates. Plot Events alone is sufficient to observe the
channel-count gating in isolation.
"""

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


# ------------- helpers specific to this tab's channel combo ---------------
# Same shape as the other event_analysis files' local helpers: this tab's
# channel_comboBox behavior (uncheck-then-select, Plot/Fit gating) isn't
# shared with raw_data's, so it isn't in tests.e2e._helpers.


def _find_live_channel_combo(controls):
    cb = getattr(controls, "channel_comboBox", None)
    if isinstance(cb, QtWidgets.QComboBox):
        return cb
    for cb in controls.findChildren(QtWidgets.QComboBox):
        if "channel" in (cb.objectName() or "").lower():
            return cb
    return None


def _available_channel_labels(cb) -> list[str]:
    lw = getattr(cb, "listWidget", None)
    if lw is not None:
        return [lw.item(i).text() for i in range(lw.count())]
    return [cb.itemText(i) for i in range(cb.count())]


def _set_checked_channels(controls, labels_to_check: set[str]) -> None:
    """
    Set the channel selector to have exactly labels_to_check checked.

    Re-fetches the live combo box immediately before acting on it (via
    _find_live_channel_combo(controls), not a cached reference), and
    selects via the widget's own selectItem() method rather than setting
    check states directly in a mixed pass -- matching the pattern already
    proven to work in this suite's other files' _select_single_channel
    helper, rather than a custom approach that turned out not to reliably
    trigger the app's reactive wiring in a real (non-offscreen) Qt session.
    """
    cb = _find_live_channel_combo(controls)
    lw = getattr(cb, "listWidget", None)
    if lw is not None:
        for i in range(lw.count()):
            lw.item(i).setCheckState(Qt.CheckState.Unchecked)
        if hasattr(cb, "selectItem"):
            for label in labels_to_check:
                cb.selectItem(label, select=True)
        else:
            for i in range(lw.count()):
                if lw.item(i).text() in labels_to_check:
                    lw.item(i).setCheckState(Qt.CheckState.Checked)
        if hasattr(cb, "refreshDisplayText"):
            cb.refreshDisplayText()
        return
    if labels_to_check:
        idx = cb.findText(next(iter(labels_to_check)))
        cb.setCurrentIndex(idx if idx >= 0 else 0)


@pytest.mark.e2e_ux
@pytest.mark.timeout(120)
def test_channel_selector_population_and_plot_gating(
    qtbot, tmp_path, monkeypatch, synthetic_multichannel_events_database
):
    db = synthetic_multichannel_events_database

    def fake_get_item(_parent, _title, _label, items, *_a, **_k):
        for it in items:
            if "SQLiteEventLoader" in it:
                return it, True
        return (items[0] if items else "No Selection"), True

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(fake_get_item),
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

    # --- 1. Channel selector populates with exactly the database's channels ---
    qtbot.waitUntil(
        lambda: _find_live_channel_combo(controls) is not None,
        timeout=QT_WAIT_TIMEOUT_MS,
    )

    def channels_loaded() -> bool:
        cb = _find_live_channel_combo(controls)
        lw = getattr(cb, "listWidget", None)
        return (lw.count() > 0) if lw is not None else (cb.count() > 0)

    qtbot.waitUntil(channels_loaded, timeout=QT_WAIT_TIMEOUT_MS)

    expected_labels = {str(ch_id) for ch_id in db.channels.keys()}
    actual_labels = set(_available_channel_labels(_find_live_channel_combo(controls)))
    assert actual_labels == expected_labels, (
        f"Expected channel selector to show {sorted(expected_labels)}, "
        f"got {sorted(actual_labels)}"
    )

    # Plot Events is gated on more than channel count alone -- it also
    # needs a valid event-range string in event_index_lineEdit. Confirmed
    # directly against the real RangeValidator._validate_final() source
    # (poriscope/views/integer_range_line_edit.py): validation is STRICT,
    # requiring start < end, not start <= end -- "0-0" is therefore
    # invalid regardless of channel selection, which is what caused this
    # test to hang on every previous attempt. "0-4" satisfies 0 < 4 and
    # matches this fixture's 5 events (ids 0-4) on every channel.
    controls.event_index_lineEdit.setText("0-4")

    # --- 2. Zero channels selected -> Plot Events disabled ---
    _set_checked_channels(controls, set())
    qtbot.wait(QT_SHORT_PAUSE_MS)
    assert (
        not controls.plot_events_pushButton.isEnabled()
    ), "Expected Plot Events disabled with no channels selected"

    # --- 3. Exactly one channel selected -> Plot Events enabled ---
    _set_checked_channels(controls, {"0"})
    qtbot.waitUntil(
        lambda: controls.plot_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )

    # --- 4. Two channels selected -> Plot Events disabled again ---
    _set_checked_channels(controls, {"0", "1"})
    qtbot.wait(QT_SHORT_PAUSE_MS)
    assert (
        not controls.plot_events_pushButton.isEnabled()
    ), "Expected Plot Events disabled with two channels selected"

    # --- 5. All three channels selected -> still disabled ---
    _set_checked_channels(controls, {"0", "1", "2"})
    qtbot.wait(QT_SHORT_PAUSE_MS)
    assert (
        not controls.plot_events_pushButton.isEnabled()
    ), "Expected Plot Events disabled with every channel selected"

    # --- 6. Back down to exactly one -> enabled again, confirming this is
    # reactive rather than a one-time check evaluated only at load time ---
    _set_checked_channels(controls, {"2"})
    qtbot.waitUntil(
        lambda: controls.plot_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
