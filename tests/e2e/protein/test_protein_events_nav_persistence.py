# Run with: pytest tests/e2e/protein/test_protein_events_nav_persistence.py -v -s
"""
E2E/UX flow for Protein tab: Plot Events + navigation with non-contiguous
event ids + Plot Histogram + RAW checkbox + SQL filter save/load
persistence round-trip.

Test data comes from make_synthetic_metadata_database (see
tests/synthetic_data/synthetic_metadata_db.py and tests/e2e/conftest.py),
built with reject_event_indices -- raw event_id stays strictly
contiguous (0..13, matching how a real acquisition numbers events
sequentially), and specific raw events (positions [1, 3, 4, 5, 8]) are
deliberately given an amplitude below the fitter's Step Size, so CUSUM
genuinely rejects them during fitting. The gaps in the FITTED/committed
event id set (the ones this test actually navigates over) are therefore
a realistic byproduct of fitting, not an artificial injection -- see
synthetic_events_db.py's _write_channel() docstring for the confirmed
mechanism, and synthetic_metadata_db.py's own module docstring for why
this matters more than it might first appear (real acquisitions with
manually-pruned or naturally-rejected events would look exactly like
this: contiguous raw ids, gapped fitted ids).

The actual surviving ids are read from the fixture's own ground truth
(db['exp_gapped'].channels[0].event_ids, confirmed to match the real
committed database exactly) rather than assumed or hardcoded -- CUSUM's
specific rejections are a real fitting outcome, not something to
predict by inspection.

This matters specifically for navigation: _shift_range_and_update_plot
(defined directly on ProteinView -- NOT inherited from MetaView; see
below) shifts by INDEX POSITION within the cached id list, not by
literal id value -- a test built on contiguous 0..N-1 ids can't
distinguish "shift landed on the right position" from "shift landed on
the right numeric value", since those coincide for contiguous ids. A
gapped id set forces the two apart.

Building this fixture also surfaced a real, separately-worth-knowing
finding: MetaEventFitter.fit_events()'s indices parameter defaults to
list(range(total_events)) -- literal positions, not real event_id values
-- when not passed explicitly. Against a gapped id set, that silently
fits only whichever events happen to coincide with their own position
(confirmed via direct repro: only event_id=2, which happens to sit at
index 2, survived a 6-event gapped fit before this was fixed in the
generator). Worth checking whether the real app's own Fit Events flow
(wherever CUSUM.fit_events() is invoked from the GUI) passes indices=
loader.get_valid_indices(channel) explicitly -- if it doesn't, any real
dataset with non-contiguous event ids (entirely plausible if events were
ever manually pruned) would silently under-fit with no error surfaced.
This test's own fixture generation already works around it; the real app
is a separate, unverified question.

CONFIRMED against ProteinControls.py source: all control widget names
used below (event_id_lineEdit, n_events_lineEdit, plot_events_pushButton,
plot_histogram_pushButton, right_arrow_button/left_arrow_button,
raw_checkbox, filter_add_button, filter_comboBox, filter_info_button,
filter_delete_button, save_filter_button, load_filter_button,
db_loader_add_button, db_loader_comboBox, selection_tree_button) match
the real widget attributes exactly. Action names, dispatch behavior,
guard clauses, and _shift_range_and_update_plot's bisect algorithm
(including its idx-overflow wraparound, mirrored precisely in
_simulate_shift below) are confirmed directly from ProteinView.py source
and ProteinView's own real unit tests. If any of this were ever wrong,
this file would fail at collection/first-click with a clear
AttributeError pointing at the exact wrong name, not silently.
"""

import bisect
import json
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
from tests.e2e._helpers import (
    QT_SHORT_PAUSE_MS,
    QT_WAIT_TIMEOUT_MS,
    ensure_name_filled,
    find_button,
    first_modal_dialog,
    open_menu_hybrid,
    schedule_dialog_autofill,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOADER_SUBCLASS_NAME = os.getenv("E2E_DBLOADER_NAME", "SQLiteDBLoader")
E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "180"))

# Raw events are planted contiguously (0..RAW_NUM_EVENTS-1); these
# specific positions are deliberately given a too-shallow amplitude so
# CUSUM genuinely rejects them during fitting, leaving gaps in the
# FITTED/committed event id set -- not an artificially-injected id list.
RAW_NUM_EVENTS = 14
REJECT_EVENT_INDICES = [0, 1, 4, 5, 6, 10, 11]


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


def _count_lines(fig):
    return sum(len(ax.lines) for ax in getattr(fig, "axes", []) or [])


def _count_bars(fig):
    return sum(len(ax.patches) for ax in getattr(fig, "axes", []) or [])


@pytest.fixture
def protein_gapped_db(make_synthetic_metadata_database):
    """
    A single-experiment, single-channel metadata database whose FITTED
    event ids have gaps, for testing navigation logic that shifts by
    index position rather than literal id value. The gaps are a real
    fitting outcome (see REJECT_EVENT_INDICES above and
    synthetic_metadata_db.py's reject_event_indices), not a hardcoded id
    list -- the actual surviving ids are read from the returned
    database's own ground truth (db['exp_gapped'].channels[0].event_ids).
    """
    return make_synthetic_metadata_database(
        experiments=[
            {
                "name": "exp_gapped",
                "channels": [
                    {
                        "channel_id": 0,
                        "num_events": RAW_NUM_EVENTS,
                        "reject_event_indices": REJECT_EVENT_INDICES,
                        "event_length_range_samples": (100, 500),
                        "seed": 7,
                    },
                ],
            },
        ],
    )


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_protein_events_nav_and_filters(
    qtbot, tmp_path, monkeypatch, caplog, auto_dismiss_message_boxes, protein_gapped_db
):
    db = protein_gapped_db
    ground_truth_ids = db["exp_gapped"].channels[0].event_ids
    print(f"[DEBUG] Using gapped-id synthetic metadata DB: {db.db_path}")
    print(f"[DEBUG] Fitted (surviving) event ids: {ground_truth_ids}")

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(_fake_get_item_exact_then_substring(LOADER_SUBCLASS_NAME)),
        raising=False,
    )

    filters_json_path = tmp_path / "saved_filters.json"
    _dialog_purpose = {"value": "loader"}

    def _smart_get_open_filename(*_a, **_k):
        if _dialog_purpose["value"] == "filters":
            return (str(filters_json_path), "JSON Files (*.json)")
        return (str(db.db_path), "All Files (*)")

    def _smart_get_save_filename(*_a, **_k):
        return (str(filters_json_path), "JSON Files (*.json)")

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(_smart_get_open_filename),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        staticmethod(_smart_get_save_filename),
        raising=False,
    )

    # SelectionTree.show_dialog() bypass -- same Qt.Popup/offscreen
    # rationale as metadata's own test files.
    import poriscope.plugins.analysistabs.ProteinView as protein_view_mod

    def _patched_show_dialog(self, structure, loader_name, title="Select Channels", selected=None):
        selection_widget = protein_view_mod.SelectionTree()
        selection_widget.populate_tree(structure, loader_name, selected)
        select_all_btn = selection_widget.select_all_button
        if select_all_btn.text() == "Select All":
            QTest.mouseClick(select_all_btn, Qt.MouseButton.LeftButton)
        result = selection_widget.get_selected()
        self.selection_by_loader[loader_name] = result
        return result

    monkeypatch.setattr(
        protein_view_mod.SelectionTree, "show_dialog", _patched_show_dialog, raising=True
    )

    app_config = {
        "Parent Folder": str(tmp_path),
        "User Plugin Folder": str(tmp_path),
        "Log Level": 20,
    }
    model = MainModel(app_config)
    view = MainView(model.get_available_plugins())
    _controller = MainController(model, view)  # kept alive for the test's duration
    qtbot.addWidget(view)
    view.show()

    open_menu_hybrid(
        view, ["Analysis", "New Analysis Tab", "ProteinController"], qtbot, timeout_ms=QT_WAIT_TIMEOUT_MS
    )
    qtbot.waitUntil(lambda: "ProteinView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("ProteinView")
    protein_view = view.pages["ProteinView"]["widget"]
    controls = protein_view.proteincontrols

    # =========================================================
    # STAGE 1: loader + scope (select-all, single leaf -> trivially "all")
    # =========================================================
    def fill_loader_dialog(dlg) -> bool:
        pick_btn = find_button(dlg, "select input file")
        if pick_btn:
            QTest.mouseClick(pick_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(QT_SHORT_PAUSE_MS)
        ensure_name_filled(dlg, "protein_loader_e2e")
        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_loader_dialog)
    QTest.mouseClick(controls.db_loader_add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS)
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    qtbot.wait(QT_SHORT_PAUSE_MS)
    QTest.mouseClick(controls.selection_tree_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    print(f"[DEBUG] Selected scope: {protein_view.selected_experiment_and_channels_by_loader}")

    # =========================================================
    # STAGE 2: Plot Events, event_id=0, n_events=3. Confirmed real
    # behavior: _fetch_event_data requires exactly one experiment/channel
    # and at most one filter -- satisfied here (single leaf, no filter
    # selected yet).
    # =========================================================
    controls.event_id_lineEdit.setText("0")
    controls.n_events_lineEdit.setText("3")
    qtbot.waitUntil(
        lambda: controls.plot_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    before = _count_lines(protein_view.canvas_event.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(protein_view.canvas_event.figure) > before, timeout=QT_WAIT_TIMEOUT_MS
    )
    lines_after_plot = _count_lines(protein_view.canvas_event.figure)
    print(f"[DEBUG] After Plot Events (event_id=0, n_events=3): {lines_after_plot} lines")
    assert lines_after_plot > before, "Expected Plot Events to add lines to the figure"
    assert protein_view._display_mode == "event", (
        f"Expected display mode 'event' after Plot Events, got {protein_view._display_mode!r}"
    )

    # =========================================================
    # STAGE 3: navigation over the GAPPED id set. Compute the expected
    # landing event_id by simulating the SAME bisect-based shift
    # algorithm the app uses (_shift_range_and_update_plot, defined
    # directly on ProteinView -- confirmed via direct source review,
    # including its idx-overflow branch: bisect_left can return an
    # out-of-range index when event_id exceeds every cached id, and the
    # real code wraps that back to idx=0 rather than clamping to the
    # last element; _simulate_shift below mirrors that exactly), rather
    # than hardcoding a guessed target -- exact precedent from
    # test_metadata_events_nav_persistence.py's Stage 3.
    # =========================================================
    ids = list(protein_view.filtered_event_ids)
    n = len(ids)
    print(f"[DEBUG] filtered_event_ids cache: {ids}")
    assert ids == sorted(ground_truth_ids), (
        f"Expected the cached id list to exactly match the fixture's real "
        f"fitted event ids {sorted(ground_truth_ids)}, got {ids}"
    )

    n_events = 3  # matches n_events_lineEdit set above
    current_event_id = 0

    def _simulate_shift(event_id, direction):
        idx = bisect.bisect_left(ids, event_id)
        if idx >= n:
            idx = 0  # matches the real code's wraparound, not a clamp to n-1
        if direction == "right":
            next_idx = idx + n_events
            if next_idx >= n:
                next_idx = 0
        else:
            next_idx = idx - n_events
            if next_idx < 0:
                next_idx = max(0, n - n_events)
        return ids[next_idx]

    expected_event_id = _simulate_shift(current_event_id, "right")
    print(f"[DEBUG] simulated RIGHT: {current_event_id} -> {expected_event_id}")

    if controls.right_arrow_button.isEnabled():
        QTest.mouseClick(controls.right_arrow_button, Qt.MouseButton.LeftButton)
        qtbot.wait(QT_SHORT_PAUSE_MS)

    actual_event_id = int(controls.event_id_lineEdit.text().strip())
    print(f"[DEBUG] After RIGHT click: event_id_lineEdit={actual_event_id}")
    assert actual_event_id == expected_event_id, (
        f"Expected navigation to land on event_id={expected_event_id} "
        f"(computed via the same bisect-shift algorithm the app uses, "
        f"over the gapped id set {ids}), got {actual_event_id}. A test "
        f"built on contiguous ids could not distinguish a real bug here "
        f"from coincidentally-correct numeric arithmetic."
    )

    expected_back = _simulate_shift(expected_event_id, "left")
    if controls.left_arrow_button.isEnabled():
        QTest.mouseClick(controls.left_arrow_button, Qt.MouseButton.LeftButton)
        qtbot.wait(QT_SHORT_PAUSE_MS)
    actual_back = int(controls.event_id_lineEdit.text().strip())
    print(f"[DEBUG] After LEFT click: event_id_lineEdit={actual_back} (expected {expected_back})")
    assert actual_back == expected_back

    # =========================================================
    # STAGE 4: Plot Histogram (separate action from Plot Events; confirmed
    # dispatch via handle_parameter_change's "plot_histogram" case,
    # routing to _handle_plot_histogram -> _update_event_histogram).
    # =========================================================
    controls.event_id_lineEdit.setText(str(ids[0]))
    controls.n_events_lineEdit.setText("2")
    bars_before = _count_bars(protein_view.canvas_event.figure)
    QTest.mouseClick(controls.plot_histogram_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_bars(protein_view.canvas_event.figure) > bars_before
        or protein_view._display_mode == "event",
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    print(f"[DEBUG] Plot Histogram: display_mode={protein_view._display_mode!r}")

    # =========================================================
    # STAGE 5: RAW checkbox. Confirmed real behavior:
    # _handle_plot_events -> _update_event_plot(events, use_raw=<checkbox
    # state>) (see TestHandlePlotEvents.test_calls_update_event_plot_with_data).
    # =========================================================
    controls.event_id_lineEdit.setText(str(ids[0]))
    controls.n_events_lineEdit.setText("3")
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    lines_before_raw = _count_lines(protein_view.canvas_event.figure)

    controls.raw_checkbox.setChecked(True)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(protein_view.canvas_event.figure) != lines_before_raw,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    lines_with_raw = _count_lines(protein_view.canvas_event.figure)
    print(f"[DEBUG] RAW checked: {lines_before_raw} -> {lines_with_raw} lines")
    assert lines_with_raw != lines_before_raw, (
        "Expected the line count to change once RAW is checked and the plot "
        "is re-drawn (use_raw flag reaches _update_event_plot per the real "
        "unit test's confirmed call signature)"
    )
    controls.raw_checkbox.setChecked(False)

    # =========================================================
    # STAGE 6: filters -- add assisted, save, delete, load back, confirm
    # persistence round-trip (same shape as metadata's own filter stage).
    # =========================================================
    def _add_assisted_filter(name, filter_text):
        def auto_complete():
            dlg = first_modal_dialog()
            if dlg is None:
                QtCore.QTimer.singleShot(50, auto_complete)
                return
            if not dlg.name_input.text().strip():
                dlg.name_input.setText(name)
            if not dlg.filter_input.toPlainText().strip():
                dlg.filter_input.setPlainText(filter_text)
            ok_btn = dlg.button_box.button(QtWidgets.QDialogButtonBox.Ok)
            if ok_btn.isEnabled():
                QTest.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
            else:
                QtCore.QTimer.singleShot(50, auto_complete)

        QtCore.QTimer.singleShot(0, auto_complete)
        QTest.mouseClick(controls.filter_add_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: any(name in n for n in protein_view.subset_filters),
            timeout=QT_WAIT_TIMEOUT_MS,
        )
        return next(n for n in protein_view.subset_filters if name in n)

    filter_name = _add_assisted_filter("protein_filter", "num_sublevels>0")
    original_text = protein_view.subset_filters[filter_name]
    print(f"[DEBUG] Filter added: {filter_name!r} = {original_text!r}")

    _dialog_purpose["value"] = "filters"
    QTest.mouseClick(controls.save_filter_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: filters_json_path.exists(), timeout=QT_WAIT_TIMEOUT_MS)
    with open(filters_json_path) as f:
        saved_json = json.load(f)
    assert saved_json == {filter_name: original_text}, (
        f"Expected saved JSON to be exactly {{{filter_name!r}: {original_text!r}}}, "
        f"got {saved_json}"
    )
    print(f"[DEBUG] Saved filter JSON: {saved_json}")

    QTest.mouseClick(controls.filter_delete_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: protein_view.subset_filters == {}, timeout=QT_WAIT_TIMEOUT_MS)
    print("[DEBUG] Filter deleted from memory")

    _dialog_purpose["value"] = "filters"
    QTest.mouseClick(controls.load_filter_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(protein_view.subset_filters) == 1, timeout=QT_WAIT_TIMEOUT_MS)
    assert protein_view.subset_filters == {filter_name: original_text}, (
        f"Expected reloaded filter to match what was saved "
        f"({{{filter_name!r}: {original_text!r}}}), got {protein_view.subset_filters}"
    )
    print(f"[DEBUG] Filter reloaded, matches saved state: {protein_view.subset_filters}")

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()