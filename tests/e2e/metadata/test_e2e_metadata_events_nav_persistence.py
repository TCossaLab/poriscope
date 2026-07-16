"""
E2E/UX flow for Metadata tab: Plot Events + navigation + RAW checkbox + SQL
filter save/load/edit/delete persistence round-trip. CSV export (accept
and cancel paths) is covered separately in test_e2e_metadata_csv_export.py.
 
Run with:
    pytest tests/e2e/metadata/test_e2e_metadata_events_nav_persistence.py -v -s
 
Stages (no SQL filter active for stages 1-4; SQL filters only enter at stage 5):
1) Open tab, add loader, scope select-all.
2) Plot Events: event_id=0, n_events=4 -> expect 2 lines/event (filtered
   + fit; MetadataView._update_event_plot plots these UNCONDITIONALLY,
   confirmed from source - unlike EventAnalysisView, filter state doesn't
   gate them). Then event_id=3, n_events=2 -> expect 4 lines total.
3) Navigation/wraparound: 1x RIGHT then 3x LEFT (back). Rather than
   hardcoding an expected landing event_id (manual debug output shows
   "24 total | first:0 | last:24", meaning the id set has a GAP somewhere (19)
   - hardcoding "23" would be a guess), we read the real
   md_view.filtered_event_ids cache and SIMULATE the exact same
   bisect-based shift algorithm the app uses (_shift_range_and_update_plot)
   to compute the expected final event_id, then assert the UI matches
   that computed value exactly.
4) RAW checkbox, still no filter: checking it should ADD a third line per
   event (raw_data), going from 2x to 3x lines/event - confirmed possible
   from source (use_raw always adds the raw line when checked, regardless
   of filter state - different from EventAnalysisView's filter-gated
   behavior).
5) Filters: create two assisted filters (filter_a: "duration>100",
   filter_b: "duration>200") -> Save Filter (writes both to a real JSON
   file) -> Load Filter immediately (filters still in memory) -> expect a
   "Duplicate filter names" warning, filters UNCHANGED -> Edit filter_a's
   text to "duration>150" -> Delete both filters -> Load Filter again from
   the same saved file -> assert both filters come back with their
   ORIGINAL pre-edit text (duration>100 / duration>200), proving Save
   captured the pre-edit state and the later in-memory edit never touched
   the saved file.
6) Reset -> Histogram/duration -> Save Plot Configuration -> Reset ->
   Load Plot Configuration -> assert the reloaded plot's legend labels
   and bar count exactly match what was saved.
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
from tests.e2e._helpers import open_menu_hybrid

# tests/e2e/metadata/this_file.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---- Env knobs --------------------------------------------------------
METADATA_DB_NAME = os.getenv("E2E_METADATA_DB", "DB.db")
LOADER_SUBCLASS_NAME = os.getenv("E2E_DBLOADER_NAME", "SQLiteDBLoader")

E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "180"))
QT_WAIT_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "60000"))
QT_WAIT_SHORT_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "300"))


# ------------- helpers (kept local to this file) --------------------------


def _first_modal_dialog():
    w = QtWidgets.QApplication.activeModalWidget()
    if isinstance(w, QtWidgets.QDialog):
        return w
    w = QtWidgets.QApplication.activePopupWidget()
    if isinstance(w, QtWidgets.QDialog):
        return w
    for tw in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(tw, QtWidgets.QDialog) and tw.isVisible():
            return tw
    return None


def _find_button(dlg, label_lower: str):
    for b in dlg.findChildren(QtWidgets.QPushButton):
        if (b.text() or "").lower() == (label_lower or "").lower():
            return b
    return None


def _find_button_contains(dlg, snippet: str):
    needle = (snippet or "").lower()
    for b in (dlg.findChildren(QtWidgets.QPushButton) if dlg else []):
        if needle in (b.text() or "").lower():
            return b
    return None


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
    """Histogram uses ax.bar(), which populates ax.patches, not ax.lines."""
    return sum(len(ax.patches) for ax in getattr(fig, "axes", []) or [])


def _get_legend_labels(fig):
    """Actual legend label text (sorted) - lets us check Save/Load Plot
    Configuration genuinely restores the SAME plot, not just any plot."""
    labels = []
    for ax in getattr(fig, "axes", []) or []:
        _, ax_labels = ax.get_legend_handles_labels()
        labels.extend(ax_labels)
    if not labels and getattr(fig, "legends", None):
        for leg in fig.legends:
            labels.extend(t.get_text() for t in leg.get_texts())
    return sorted(labels)


# ------------- Test -------------------------------------------------------


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_metadata_events_and_filters(qtbot, tmp_path, monkeypatch, caplog):
    metadata_db = (
        REPO_ROOT / "tests" / "data" / METADATA_DB_NAME
        if (REPO_ROOT / "tests" / "data" / METADATA_DB_NAME).exists()
        else REPO_ROOT / "data" / METADATA_DB_NAME
    )
    assert metadata_db.exists(), f"Missing test file: {metadata_db}"

    filters_json_path = tmp_path / "saved_filters.json"
    plot_config_json_path = tmp_path / "saved_plot_config.json"

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(_fake_get_item_exact_then_substring(LOADER_SUBCLASS_NAME)),
        raising=False,
    )

    # File-dialog dispatch by explicit context flag rather than sniffing
    # dialog content: three separate flows all write JSON via
    # getOpenFileName/getSaveFileName (loader file-picker, filter
    # save/load, plot config save/load), and "filter string contains
    # json" alone can't tell filter-JSON apart from plot-config-JSON. Set
    # _dialog_purpose["value"] explicitly right before each relevant
    # click.
    _dialog_purpose = {"value": "loader"}

    def _smart_get_open_filename(*args, **kwargs):
        purpose = _dialog_purpose["value"]
        if purpose == "filters":
            return (str(filters_json_path), "JSON Files (*.json)")
        if purpose == "plot_config":
            return (str(plot_config_json_path), "JSON Files (*.json)")
        return (str(metadata_db), "All Files (*)")

    def _smart_get_save_filename(*args, **kwargs):
        purpose = _dialog_purpose["value"]
        if purpose == "plot_config":
            return (str(plot_config_json_path), "JSON Files (*.json)")
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

    # QMessageBox safety net (see test_e2e_metadata_flow.py for rationale)
    for _mb_method, _mb_return in (
        ("warning", QtWidgets.QMessageBox.Ok),
        ("critical", QtWidgets.QMessageBox.Ok),
        ("information", QtWidgets.QMessageBox.Ok),
        ("question", QtWidgets.QMessageBox.Yes),
    ):

        def _make_patch(method_name, ret_value):
            def _patched(*args, **kwargs):
                print(f"[DEBUG] QMessageBox.{method_name} auto-dismissed: {args}")
                return ret_value

            return _patched

        monkeypatch.setattr(
            f"PySide6.QtWidgets.QMessageBox.{_mb_method}",
            staticmethod(_make_patch(_mb_method, _mb_return)),
            raising=False,
        )

    # SelectionTree.show_dialog() bypass (Qt.Popup hangs under offscreen -
    # see test_e2e_metadata_flow.py for full rationale)
    import poriscope.plugins.analysistabs.MetadataView as metadata_view_mod

    def _patched_show_dialog(self, structure, loader_name, title="Select Channels", selected=None):
        selection_widget = metadata_view_mod.SelectionTree()
        selection_widget.populate_tree(structure, loader_name, selected)
        select_all_btn = selection_widget.select_all_button
        if select_all_btn.text() == "Select All":
            QTest.mouseClick(select_all_btn, Qt.LeftButton)
        result = selection_widget.get_selected()
        self.selection_by_loader[loader_name] = result
        return result

    monkeypatch.setattr(
        metadata_view_mod.SelectionTree, "show_dialog", _patched_show_dialog, raising=True
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

    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "MetadataController"],
        qtbot,
        timeout_ms=QT_WAIT_TIMEOUT_MS,
    )
    qtbot.waitUntil(lambda: "MetadataView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("MetadataView")
    md_view = view.pages["MetadataView"]["widget"]
    controls = md_view.metadatacontrols

    # =========================================================
    # STAGE 1: loader + scope
    # =========================================================
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
                w.setText("db_loader_e2e")
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_loader_settings)

    QtCore.QTimer.singleShot(0, auto_complete_loader_settings)
    QTest.mouseClick(controls.db_loader_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    qtbot.wait(QT_WAIT_SHORT_MS)
    QTest.mouseClick(controls.selection_tree_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    print(f"[DEBUG] Selected scope: {md_view.selected_experiment_and_channels_by_loader}")

    # =========================================================
    # STAGE 2: Plot Events, no filter. Confirmed from source:
    # _update_event_plot always plots filtered_data + fit_data
    # unconditionally -> 2 lines/event baseline, regardless of filter.
    # =========================================================
    controls.event_id_lineEdit.setText("0")
    controls.n_events_lineEdit.setText("4")
    qtbot.waitUntil(
        lambda: controls.plot_events_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    before = _count_lines(md_view.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(md_view.figure) > before, timeout=QT_WAIT_TIMEOUT_MS
    )
    lines_4events = _count_lines(md_view.figure)
    print(f"[DEBUG] event_id=0, n_events=4: {lines_4events} lines (expect 8)")
    assert lines_4events == 8, (
        f"Expected 2 lines/event x 4 events = 8, got {lines_4events}"
    )

    controls.event_id_lineEdit.setText("3")
    controls.n_events_lineEdit.setText("2")
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(md_view.figure) != lines_4events, timeout=QT_WAIT_TIMEOUT_MS
    )
    lines_2events = _count_lines(md_view.figure)
    print(f"[DEBUG] event_id=3, n_events=2: {lines_2events} lines (expect 4)")
    assert lines_2events == 4, (
        f"Expected 2 lines/event x 2 events = 4, got {lines_2events}"
    )

    # =========================================================
    # STAGE 3: navigation - 1x RIGHT, then 3x LEFT (back). Compute the
    # expected final event_id by simulating the SAME bisect-based
    # algorithm _shift_range_and_update_plot uses, rather than hardcoding
    # a guessed target (the real id set has a gap - "24 total | first:0 |
    # last:24" - so ids aren't a clean contiguous 0..23 range).
    # =========================================================
    ids = list(md_view.filtered_event_ids)
    n = len(ids)
    print(f"[DEBUG] filtered_event_ids: n={n}, first={ids[0] if ids else None}, last={ids[-1] if ids else None}")
    assert n > 0, "Expected a non-empty filtered_event_ids cache after plotting"

    n_events = 2  # matches n_events_lineEdit set above
    current_event_id = 3

    def _simulate_shift(event_id, direction):
        idx = bisect.bisect_left(ids, event_id)
        idx = min(idx, n - 1)
        if direction == "right":
            next_idx = idx + n_events
            if next_idx >= n:
                next_idx = 0
        else:
            next_idx = idx - n_events
            if next_idx < 0:
                next_idx = max(0, n - n_events)
        return ids[next_idx]

    expected_event_id = current_event_id
    expected_event_id = _simulate_shift(expected_event_id, "right")
    print(f"[DEBUG] simulated RIGHT: {current_event_id} -> {expected_event_id}")
    for i in range(3):
        prev = expected_event_id
        expected_event_id = _simulate_shift(expected_event_id, "left")
        print(f"[DEBUG] simulated LEFT #{i + 1}: {prev} -> {expected_event_id}")

    print(f"[DEBUG] Final simulated expected event_id: {expected_event_id}")

    if controls.right_arrow_button.isEnabled():
        QTest.mouseClick(controls.right_arrow_button, Qt.LeftButton)
        qtbot.wait(QT_WAIT_SHORT_MS)
    for i in range(3):
        if controls.left_arrow_button.isEnabled():
            QTest.mouseClick(controls.left_arrow_button, Qt.LeftButton)
            qtbot.wait(QT_WAIT_SHORT_MS)
            print(
                f"[DEBUG] After LEFT click #{i + 1}: event_id_lineEdit="
                f"{controls.event_id_lineEdit.text()!r}"
            )

    actual_event_id = int(controls.event_id_lineEdit.text().strip())
    actual_n_events = int(controls.n_events_lineEdit.text().strip() or "1")
    print(
        f"[DEBUG] After 1xRIGHT + 3xLEFT: event_id={actual_event_id}, "
        f"n_events={actual_n_events} (expected event_id={expected_event_id})"
    )
    assert actual_n_events == n_events, (
        f"Expected n_events to stay {n_events} through navigation, got {actual_n_events}"
    )
    assert actual_event_id == expected_event_id, (
        f"Expected navigation to land on event_id={expected_event_id} "
        f"(computed via the same bisect-shift algorithm the app uses), "
        f"got {actual_event_id}"
    )

    # =========================================================
    # STAGE 4: RAW checkbox, still no filter -> checking it adds a THIRD
    # line per event (raw_data), regardless of filter state (confirmed:
    # unlike EventAnalysisView, MetadataView's use_raw isn't gated on a
    # filter being active).
    # =========================================================
    lines_before_raw = _count_lines(md_view.figure)
    controls.raw_checkbox.setChecked(True)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(md_view.figure) > lines_before_raw, timeout=QT_WAIT_TIMEOUT_MS
    )
    lines_with_raw = _count_lines(md_view.figure)
    print(f"[DEBUG] RAW checked: {lines_before_raw} -> {lines_with_raw} lines")
    assert lines_with_raw == lines_before_raw + n_events, (
        f"Expected +1 line/event ({n_events} events) when RAW checked with "
        f"no filter active, got {lines_before_raw} -> {lines_with_raw}"
    )

    controls.raw_checkbox.setChecked(False)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_lines(md_view.figure) < lines_with_raw, timeout=QT_WAIT_TIMEOUT_MS
    )
    lines_after_uncheck = _count_lines(md_view.figure)
    print(f"[DEBUG] RAW unchecked: {lines_with_raw} -> {lines_after_uncheck} lines")
    assert lines_after_uncheck == lines_before_raw, (
        f"Expected line count to drop back to {lines_before_raw} after "
        f"unchecking RAW, got {lines_after_uncheck}"
    )

    # =========================================================
    # STAGE 5: filters - create, save, load (duplicate warning), edit,
    # delete, reload, verify original pre-edit values persisted.
    # =========================================================
    def _add_assisted_filter(name, filter_text):
        def auto_complete():
            dlg = _first_modal_dialog()
            if dlg is None:
                QtCore.QTimer.singleShot(50, auto_complete)
                return
            if not dlg.name_input.text().strip():
                dlg.name_input.setText(name)
            if not dlg.filter_input.toPlainText().strip():
                dlg.filter_input.setPlainText(filter_text)
            ok_btn = dlg.button_box.button(QtWidgets.QDialogButtonBox.Ok)
            if ok_btn.isEnabled():
                QTest.mouseClick(ok_btn, Qt.LeftButton)
            else:
                QtCore.QTimer.singleShot(50, auto_complete)

        QtCore.QTimer.singleShot(0, auto_complete)
        QTest.mouseClick(controls.filter_add_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: any(name in n for n in md_view.subset_filters), timeout=QT_WAIT_TIMEOUT_MS
        )
        full_name = next(n for n in md_view.subset_filters if name in n)
        print(f"[DEBUG] Filter added: {full_name!r} = {md_view.subset_filters[full_name]!r}")
        return full_name

    filter_a_name = _add_assisted_filter("filter_a", "duration>100")
    filter_b_name = _add_assisted_filter("filter_b", "duration>200")

    original_values = {
        filter_a_name: md_view.subset_filters[filter_a_name],
        filter_b_name: md_view.subset_filters[filter_b_name],
    }
    print(f"[DEBUG] Original filter values (pre-edit, pre-save): {original_values}")

    # --- Save Filter ---
    _dialog_purpose["value"] = "filters"
    QTest.mouseClick(controls.save_filter_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: filters_json_path.exists(), timeout=QT_WAIT_TIMEOUT_MS)
    with open(filters_json_path) as f:
        saved_json = json.load(f)
    print(f"[DEBUG] Saved JSON contents: {saved_json}")
    assert saved_json == original_values, (
        f"Expected saved JSON to match original filter values, got {saved_json}"
    )

    # --- Load Filter while both still exist in memory -> expect a
    # "Duplicate filter names" warning and NO change to subset_filters ---
    caplog.clear()
    QTest.mouseClick(controls.load_filter_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    print(f"[DEBUG] subset_filters after duplicate-load attempt: {md_view.subset_filters}")
    assert md_view.subset_filters == original_values, (
        "Expected subset_filters unchanged after loading duplicates, got "
        f"{md_view.subset_filters}"
    )
    assert any("Duplicate filter names" in rec.message for rec in caplog.records), (
        "Expected a 'Duplicate filter names' warning when loading filters "
        "that already exist in memory"
    )

    # --- Edit filter_a's text (name unchanged, assisted mode locked) ---
    controls.filter_comboBox.selectItem(filter_a_name, select=True)
    controls.filter_comboBox.selectItem(filter_b_name, select=False)
    if hasattr(controls.filter_comboBox, "refreshDisplayText"):
        controls.filter_comboBox.refreshDisplayText()

    def auto_complete_edit():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_edit)
            return
        dlg.filter_input.setPlainText("duration>150")
        ok_btn = dlg.button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn.isEnabled():
            QTest.mouseClick(ok_btn, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_edit)

    QtCore.QTimer.singleShot(0, auto_complete_edit)
    QTest.mouseClick(controls.filter_info_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: md_view.subset_filters.get(filter_a_name) == "duration>150",
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    print(f"[DEBUG] filter_a after edit: {md_view.subset_filters[filter_a_name]!r}")

    # --- Delete both filters ---
    controls.filter_comboBox.selectItem(filter_a_name, select=True)
    controls.filter_comboBox.selectItem(filter_b_name, select=True)
    if hasattr(controls.filter_comboBox, "refreshDisplayText"):
        controls.filter_comboBox.refreshDisplayText()
    QTest.mouseClick(controls.filter_delete_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: md_view.subset_filters == {}, timeout=QT_WAIT_TIMEOUT_MS)
    print(f"[DEBUG] subset_filters after delete: {md_view.subset_filters}")

    # --- Load Filter again from the same saved file -> should restore
    # the ORIGINAL pre-edit values, not the edited "duration>150" ---
    QTest.mouseClick(controls.load_filter_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: len(md_view.subset_filters) == 2, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] subset_filters after reload: {md_view.subset_filters}")
    assert md_view.subset_filters == original_values, (
        f"Expected reloaded filters to match ORIGINAL pre-edit values "
        f"{original_values} (proving Save captured pre-edit state), got "
        f"{md_view.subset_filters}"
    )

    # =========================================================
    # STAGE 6: Reset everything, plot Histogram of duration, Save Plot
    # Configuration, Reset again, Load it back, verify the reloaded plot
    # matches (same legend labels + same bar count) what was saved.
    #
    # ASSUMPTION: _save_actions_to_json()/_load_actions_from_json()
    # aren't in the source I've seen - if either pops a settings dialog
    # (e.g. a name/folder prompt, similar to the CSV export flow's
    # DictDialog), the generic auto-dismiss below clicks OK/Save on
    # whatever appears rather than doing nothing and hanging.
    # =========================================================
    QTest.mouseClick(controls.reset_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    assert _count_bars(md_view.figure) == 0 and _get_legend_labels(md_view.figure) == [], (
        "Expected Reset to fully clear the plot before the save/load config check"
    )

    idx = controls.plot_type_comboBox.findText("Histogram")
    assert idx >= 0, "Histogram not found in plot_type_comboBox options"
    controls.plot_type_comboBox.setCurrentIndex(idx)

    x_idx = controls.x_axis_comboBox.findText("duration")
    assert x_idx >= 0, "'duration' not found in x_axis_comboBox options"
    controls.x_axis_comboBox.setCurrentIndex(x_idx)

    qtbot.waitUntil(
        lambda: controls.update_plot_button.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    QTest.mouseClick(controls.update_plot_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_bars(md_view.figure) > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    saved_bar_count = _count_bars(md_view.figure)
    saved_legend_labels = _get_legend_labels(md_view.figure)
    print(
        f"[DEBUG] Plot before saving config: {saved_bar_count} bars, "
        f"legend={saved_legend_labels}"
    )

    def _generic_dialog_dismiss():
        """Best-effort: if Save/Load Plot Configuration pops an unexpected
        settings dialog, click its OK/Save button rather than stalling."""
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, _generic_dialog_dismiss)
            return
        ok = _find_button(dlg, "ok") or _find_button(dlg, "save")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, _generic_dialog_dismiss)

    _dialog_purpose["value"] = "plot_config"
    QtCore.QTimer.singleShot(0, _generic_dialog_dismiss)
    QTest.mouseClick(controls.save_plot_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: plot_config_json_path.exists(), timeout=QT_WAIT_TIMEOUT_MS)
    print(f"[DEBUG] Plot config saved to {plot_config_json_path}")

    QTest.mouseClick(controls.reset_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    assert _count_bars(md_view.figure) == 0, "Expected Reset to clear the plot before reload"
    print("[DEBUG] Plot reset before reload")

    _dialog_purpose["value"] = "plot_config"
    QTest.mouseClick(controls.load_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_bars(md_view.figure) > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    reloaded_bar_count = _count_bars(md_view.figure)
    reloaded_legend_labels = _get_legend_labels(md_view.figure)
    print(
        f"[DEBUG] Plot after loading config: {reloaded_bar_count} bars, "
        f"legend={reloaded_legend_labels}"
    )

    assert reloaded_legend_labels == saved_legend_labels, (
        f"Expected reloaded plot legend to match what was saved "
        f"{saved_legend_labels}, got {reloaded_legend_labels}"
    )
    assert reloaded_bar_count == saved_bar_count, (
        f"Expected reloaded plot to have the same bar count as saved "
        f"({saved_bar_count}), got {reloaded_bar_count}"
    )

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()