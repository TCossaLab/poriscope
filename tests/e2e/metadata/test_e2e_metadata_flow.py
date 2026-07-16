"""
E2E/UX flow for Metadata tab.

Run with:
    pytest tests/e2e/metadata/test_e2e_metadata_flow.py -v -s

Stages:
1) Open Metadata tab, add a MetaDatabaseLoader (SQLiteDBLoader) pointed at
   tests/data/DB.db (or E2E_METADATA_DB).
2) Open Scope dialog (SelectionTree), exercise Deselect All / re-select,
   confirm experiment/channel structure is real (not empty).
3) Add an assisted filter "duration>100" -> expect it to appear suffixed
   "_assisted" (confirmed real behavior from screenshots).
4) Add the same filter via raw SQL -> expect "_raw" suffix.
5) Plot a Histogram of "duration" for Full Dataset, then also select the
   assisted filter and re-plot -> expect an OVERLAY (2 legend entries),
   confirmed real behavior from screenshot.
6) Toggle x-axis log scale -> expect the x-axis label to switch to
   "log10(...)" (real logic in MetadataView.format_axis_label /
   _plot_1d_histogram).
7) Click Undo -> expect the overlay to drop back to fewer legend entries.
8) Click Reset -> expect the plot to be fully cleared.
9) Switch plot type to Scatterplot, x=duration, y=num_sublevels, Update
   Plot -> expect a real scatter collection (ax.collections, NOT
   ax.lines - _plot_scatterplot uses ax.scatter()).
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
    # Fallback: SelectionTree.show_dialog() uses Qt.Popup window flags on
    # non-Linux platforms, which don't reliably register via
    # activeModalWidget()/activePopupWidget() under the offscreen platform
    # plugin used in headless test runs. Scan visible top-level dialogs
    # directly as a last resort.
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
    for b in dlg.findChildren(QtWidgets.QPushButton) if dlg else []:
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


def _count_collections(fig):
    """Scatterplot uses ax.scatter(), which populates ax.collections."""
    return sum(len(ax.collections) for ax in getattr(fig, "axes", []) or [])


def _legend_label_count(fig):
    total = 0
    for ax in getattr(fig, "axes", []) or []:
        handles, labels = ax.get_legend_handles_labels()
        total += len(labels)
    # MetadataView also builds a figure-level legend in some paths; count
    # that too if present and axes-level legends came back empty.
    if total == 0 and getattr(fig, "legends", None):
        for leg in fig.legends:
            total += len(leg.get_texts())
    return total


def _get_legend_labels(fig):
    """Actual legend label text (sorted), not just a count - lets us check
    Undo genuinely returns to the SAME plot state, not just the same
    number of datasets."""
    labels = []
    for ax in getattr(fig, "axes", []) or []:
        _, ax_labels = ax.get_legend_handles_labels()
        labels.extend(ax_labels)
    if not labels and getattr(fig, "legends", None):
        for leg in fig.legends:
            labels.extend(t.get_text() for t in leg.get_texts())
    return sorted(labels)


def _get_x_label(fig):
    for ax in getattr(fig, "axes", []) or []:
        lbl = ax.get_xlabel()
        if lbl:
            return lbl
    return ""


# ------------- Test -------------------------------------------------------


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_metadata_flow(qtbot, tmp_path, monkeypatch, caplog):
    metadata_db = (
        REPO_ROOT / "tests" / "data" / METADATA_DB_NAME
        if (REPO_ROOT / "tests" / "data" / METADATA_DB_NAME).exists()
        else REPO_ROOT / "data" / METADATA_DB_NAME
    )
    assert metadata_db.exists(), f"Missing test file: {metadata_db}"

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(_fake_get_item_exact_then_substring(LOADER_SUBCLASS_NAME)),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(metadata_db), "All Files (*)")),
        raising=False,
    )

    # Safety net: if anything pops an uncaught QMessageBox (e.g. a SQL
    # error from the raw filter's full SELECT statement being spliced
    # into a WHERE clause elsewhere), auto-dismiss it instead of letting
    # it block the test forever - real .exec() on a QMessageBox is modal
    # and nothing else in this test watches for/dismisses it.
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

    # SelectionTree.show_dialog() wraps its widget in a QDialog with
    # Qt.Popup window flags on non-Linux. Qt.Popup relies on keyboard/mouse
    # grabbing to detect focus-loss-to-dismiss, which the offscreen
    # platform plugin explicitly does not support ("This plugin does not
    # support grabbing the keyboard") - confirmed via a real hung run.
    # Bypass the native popup/exec() entirely, same pattern as the
    # TimeWidget monkeypatch in test_events_flow_clicks.py, but keep
    # exercising the REAL populate_tree/select_all_button/get_selected
    # logic on a plain (non-popup) widget instance instead of faking the
    # whole class.
    import poriscope.plugins.analysistabs.MetadataView as metadata_view_mod

    def _patched_show_dialog(
        self, structure, loader_name, title="Select Channels", selected=None
    ):
        selection_widget = metadata_view_mod.SelectionTree()
        selection_widget.populate_tree(structure, loader_name, selected)

        select_all_btn = selection_widget.select_all_button
        initial_text = select_all_btn.text()
        QTest.mouseClick(select_all_btn, Qt.LeftButton)
        toggled_text = select_all_btn.text()
        print(
            f"[DEBUG] Scope select_all_button toggled: {initial_text!r} -> "
            f"{toggled_text!r}"
        )
        assert toggled_text != initial_text, (
            "Expected Select All/Deselect All button label to change after "
            f"toggling, stayed {initial_text!r}"
        )
        if toggled_text == "Select All":
            # we just deselected everything - restore full selection so
            # later plotting stages have scope to work with
            QTest.mouseClick(select_all_btn, Qt.LeftButton)

        result = selection_widget.get_selected()
        self.selection_by_loader[loader_name] = result
        return result

    monkeypatch.setattr(
        metadata_view_mod.SelectionTree,
        "show_dialog",
        _patched_show_dialog,
        raising=True,
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

    # Open Metadata tab
    # ASSUMPTION: menu action key is "MetadataController", matching the
    # RawDataController/EventAnalysisController naming convention. Not
    # independently confirmed.
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
    # STAGE 1: add loader
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
    # Confirmed real (MetadataControls.py source): db_loader_comboBox.
    qtbot.waitUntil(
        lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    # =========================================================
    # STAGE 2: Scope dialog (SelectionTree). The real interaction (toggle
    # select_all_button, confirm label change, restore full selection)
    # happens synchronously inside the monkeypatched show_dialog() above -
    # clicking selection_tree_button triggers it directly, no async
    # dialog-polling needed since we never enter a real Qt.Popup exec().
    # =========================================================
    qtbot.wait(QT_WAIT_SHORT_MS)  # let request_experiment_structure land
    QTest.mouseClick(controls.selection_tree_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)

    assert md_view.selected_experiment_and_channels_by_loader.get(
        controls.db_loader_comboBox.currentText()
    ) not in (
        None,
        {},
    ), "Expected a non-empty experiment/channel selection after the Scope dialog"
    print(
        f"[DEBUG] Selected scope: "
        f"{md_view.selected_experiment_and_channels_by_loader}"
    )

    # =========================================================
    # STAGE 3: assisted filter "duration>100" - CONFIRMED real widget
    # attrs from BaseSubsetFilterDialog source: name_input (QLineEdit),
    # filter_input (QTextEdit, NOT QLineEdit), assisted_radio/raw_radio,
    # button_box (QDialogButtonBox). assisted_radio is checked by default.
    # =========================================================
    def auto_complete_assisted_filter_dialog():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_assisted_filter_dialog)
            return
        if not dlg.name_input.text().strip():
            dlg.name_input.setText("duration_filter")
        if not dlg.filter_input.toPlainText().strip():
            dlg.filter_input.setPlainText("duration>100")
        ok_btn = dlg.button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn.isEnabled():
            QTest.mouseClick(ok_btn, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_assisted_filter_dialog)

    QtCore.QTimer.singleShot(0, auto_complete_assisted_filter_dialog)
    QTest.mouseClick(controls.filter_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: any("_assisted" in name for name in md_view.subset_filters.keys()),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    assisted_filter_name = next(
        name for name in md_view.subset_filters if "_assisted" in name
    )
    print(f"[DEBUG] Assisted filter added: {assisted_filter_name!r}")
    assert md_view.subset_filters[assisted_filter_name] == "duration>100", (
        f"Expected filter text 'duration>100', got "
        f"{md_view.subset_filters[assisted_filter_name]!r}"
    )

    # =========================================================
    # STAGE 4: same filter via raw SQL -> expect "_raw" suffix.
    # _show_add_filter_dialog requires the raw text to start with SELECT.
    # =========================================================
    def auto_complete_raw_filter_dialog():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_raw_filter_dialog)
            return
        if not dlg.raw_radio.isChecked():
            dlg.raw_radio.setChecked(True)
        if not dlg.name_input.text().strip():
            dlg.name_input.setText("duration_filter_raw")
        if not dlg.filter_input.toPlainText().strip():
            dlg.filter_input.setPlainText(
                "SELECT duration FROM events WHERE duration > 100"
            )
        ok_btn = dlg.button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn.isEnabled():
            QTest.mouseClick(ok_btn, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_raw_filter_dialog)

    QtCore.QTimer.singleShot(0, auto_complete_raw_filter_dialog)
    QTest.mouseClick(controls.filter_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: any("_raw" in name for name in md_view.subset_filters.keys()),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    raw_filter_name = next(name for name in md_view.subset_filters if "_raw" in name)
    print(f"[DEBUG] Raw SQL filter added: {raw_filter_name!r}")

    # Both filters auto-select themselves on add (confirmed:
    # MetadataController.relay_query -> replace_filter_item / and
    # on_raw_filter_validated both call filter_comboBox.selectItem(name,
    # select=True)). Deselect both explicitly so the upcoming "Full
    # Dataset" baseline plot genuinely has no filter selected, and so we
    # don't accidentally feed the raw filter's full SELECT statement into
    # a query builder that expects a WHERE-clause fragment.
    for _name in (assisted_filter_name, raw_filter_name):
        controls.filter_comboBox.selectItem(_name, select=False)
    if hasattr(controls.filter_comboBox, "refreshDisplayText"):
        controls.filter_comboBox.refreshDisplayText()
    print(
        f"[DEBUG] Selected filters after explicit deselect: "
        f"{md_view.get_selected_filters()!r}"
    )

    # =========================================================
    # STAGE 5: plot Full Dataset, then overlay the assisted filter
    # =========================================================
    idx = controls.plot_type_comboBox.findText("Histogram")
    print(f"[DEBUG] plot_type_comboBox findText('Histogram') = {idx}")
    controls.plot_type_comboBox.setCurrentIndex(idx if idx >= 0 else 0)
    print(
        f"[DEBUG] plot_type_comboBox now: "
        f"{controls.plot_type_comboBox.currentText()!r}"
    )

    x_idx = controls.x_axis_comboBox.findText("duration")
    all_x_options = [
        controls.x_axis_comboBox.itemText(i)
        for i in range(controls.x_axis_comboBox.count())
    ]
    print(f"[DEBUG] x_axis_comboBox options: {all_x_options}")
    assert x_idx >= 0, f"'duration' not found in x_axis options: {all_x_options}"
    controls.x_axis_comboBox.setCurrentIndex(x_idx)
    print(f"[DEBUG] x_axis_comboBox now: {controls.x_axis_comboBox.currentText()!r}")

    print(
        f"[DEBUG] update_plot_button.isEnabled() = "
        f"{controls.update_plot_button.isEnabled()}"
    )
    print(
        f"[DEBUG] Selected filters before plot: " f"{md_view.get_selected_filters()!r}"
    )

    # Plot with no filter selected first (Full Dataset)
    QTest.mouseClick(controls.update_plot_button, Qt.LeftButton)
    print("[DEBUG] update_plot_button clicked, entering waitUntil...")
    qtbot.waitUntil(
        lambda: _count_bars(md_view.figure) > 0 or _count_lines(md_view.figure) > 0,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    print("[DEBUG] waitUntil returned - plot has bars/lines")
    legend_after_full = _legend_label_count(md_view.figure)
    initial_plot_labels = _get_legend_labels(md_view.figure)
    print(f"[DEBUG] Legend entries after Full Dataset plot: {legend_after_full}")
    print(
        f"[DEBUG] Initial plot legend labels (for Undo check later): {initial_plot_labels}"
    )

    # Now select the assisted filter too and re-plot -> overlay
    controls.filter_comboBox.selectItem(assisted_filter_name, select=True)
    if hasattr(controls.filter_comboBox, "refreshDisplayText"):
        controls.filter_comboBox.refreshDisplayText()

    QTest.mouseClick(controls.update_plot_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _legend_label_count(md_view.figure) > legend_after_full,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    legend_after_overlay = _legend_label_count(md_view.figure)
    print(f"[DEBUG] Legend entries after overlay: {legend_after_overlay}")
    assert legend_after_overlay > legend_after_full, (
        "Expected MORE legend entries after adding the assisted filter and "
        f"re-plotting ({legend_after_full} -> {legend_after_overlay})"
    )

    # =========================================================
    # STAGE 6: toggle x-axis log scale -> label should show "log10(...)"
    # =========================================================
    label_before_log = _get_x_label(md_view.figure)
    controls.x_axis_logscale_checkbox.setChecked(True)
    QTest.mouseClick(controls.reset_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    QTest.mouseClick(controls.update_plot_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: "log10(" in _get_x_label(md_view.figure), timeout=QT_WAIT_TIMEOUT_MS
    )
    label_after_log = _get_x_label(md_view.figure)
    print(
        f"[DEBUG] X label before log: {label_before_log!r}, after: "
        f"{label_after_log!r}"
    )
    assert "log10(" in label_after_log, (
        f"Expected x-axis label to contain 'log10(' once log scale is "
        f"checked, got {label_after_log!r}"
    )
    controls.x_axis_logscale_checkbox.setChecked(False)

    # =========================================================
    # STAGE 7: Undo -> repeatedly click until the plot's legend labels
    # match the VERY FIRST plot exactly (not just "a different count").
    # Bounded retry since the exact undo-stack depth back to that state
    # isn't confirmed (Reset itself may or may not count as a step).
    # =========================================================
    MAX_UNDO_ATTEMPTS = 6
    current_labels = _get_legend_labels(md_view.figure)
    print(f"[DEBUG] Legend labels before any Undo: {current_labels}")

    matched = current_labels == initial_plot_labels
    attempts = 0
    while not matched and attempts < MAX_UNDO_ATTEMPTS:
        QTest.mouseClick(controls.undo_button, Qt.LeftButton)
        qtbot.wait(QT_WAIT_SHORT_MS)
        attempts += 1
        current_labels = _get_legend_labels(md_view.figure)
        print(
            f"[DEBUG] After Undo click #{attempts}: legend labels = "
            f"{current_labels}"
        )
        matched = current_labels == initial_plot_labels

    assert matched, (
        f"Expected Undo to eventually return to the initial plot's legend "
        f"labels {initial_plot_labels} within {MAX_UNDO_ATTEMPTS} clicks, "
        f"last seen: {current_labels}"
    )
    print(f"[DEBUG] Undo returned to initial plot state after {attempts} click(s)")

    # =========================================================
    # STAGE 8: Reset -> expect a fully cleared plot
    # =========================================================
    QTest.mouseClick(controls.reset_button, Qt.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    assert (
        _legend_label_count(md_view.figure) == 0
    ), "Expected Reset to fully clear the plot (0 legend entries)"
    assert md_view.hist_data == [], "Expected Reset to clear cached hist_data"
    assert (
        md_view.plotted_datasets == set()
    ), "Expected Reset to clear plotted_datasets bookkeeping"
    print("[DEBUG] Reset confirmed: plot and bookkeeping cleared")

    # =========================================================
    # STAGE 9: switch to Scatterplot, duration vs num_sublevels
    # =========================================================
    idx = controls.plot_type_comboBox.findText("Scatterplot")
    assert idx >= 0, "Scatterplot not found in plot_type_comboBox options"
    controls.plot_type_comboBox.setCurrentIndex(idx)

    x_idx = controls.x_axis_comboBox.findText("duration")
    y_idx = controls.y_axis_comboBox.findText("num_sublevels")
    assert x_idx >= 0 and y_idx >= 0, (
        f"Expected 'duration' and 'num_sublevels' in axis options, got x="
        f"{x_idx}, y={y_idx}"
    )
    controls.x_axis_comboBox.setCurrentIndex(x_idx)
    controls.y_axis_comboBox.setCurrentIndex(y_idx)

    before_collections = _count_collections(md_view.figure)
    QTest.mouseClick(controls.update_plot_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_collections(md_view.figure) > before_collections,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    print(
        f"[DEBUG] Scatterplot collections: "
        f"{_count_collections(md_view.figure)} (duration vs num_sublevels)"
    )

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
