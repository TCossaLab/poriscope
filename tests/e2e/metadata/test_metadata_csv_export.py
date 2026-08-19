"""
E2E/UX test for Metadata tab's "Export Subset - CSV" dialog: accept and
cancel paths.

Scope is intentionally minimal - a loader, scope selection, and a single
filter - since export doesn't depend on navigation, RAW checkbox state,
or plot-config save/load. Keeping this focused gives fast iteration and
clean failure isolation: a break in export shows up as exactly that,
not buried inside a longer combined flow.

Key behaviors this test relies on:
- _export_csv_subset requires <=1 filter selected or it silently refuses
  to even open the dialog ("Select a single filter to export a subset").
- The "Folder" field in the export DictDialog is a QPushButton
  (folder-picker), not a QLineEdit.
- export_subset_to_csv writes one file per event plus several table-dump
  CSVs (channels/events/experiments/columns/sublevels/data), not a
  single combined CSV.
- Export runs asynchronously via run_generators, so the accept-path
  wait must wait for the file COUNT to STABILIZE (unchanged across
  several consecutive polls), not just "any file appears" - otherwise a
  still-finishing export can look like the cancel path incorrectly
  created files.
- dlg.result is a DictDialog instance attribute (a tuple), not QDialog's
  built-in .result() method.
- Requires the None-check in _export_csv_subset (dialog.get_result()
  returns None on Cancel; the unguarded "result, name = result" unpack
  crashes without it).

Run with:
    pytest tests/e2e/metadata/test_metadata_csv_export.py -v -s
"""

import os
import sys
import time
from pathlib import Path

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import open_menu_hybrid

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

METADATA_DB_NAME = os.getenv("E2E_METADATA_DB", "DB.db")
LOADER_SUBCLASS_NAME = os.getenv("E2E_DBLOADER_NAME", "SQLiteDBLoader")

E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "120"))
QT_WAIT_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "60000"))
QT_WAIT_SHORT_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "300"))
_MAX_DIALOG_POLL_ATTEMPTS = 100  # 100 x 50ms = 5s before giving up loudly


# ------------- helpers -------------------------------------------------


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


def _wait_for_stable_export(
    qtbot, get_files_fn, stable_polls=3, poll_ms=200, timeout_ms=QT_WAIT_TIMEOUT_MS
):
    """Wait for the exported-file COUNT to stabilize (unchanged across
    stable_polls consecutive checks), not just "any file appears" - export
    writes ~29 files asynchronously (one per event + table dumps), and
    waiting for only the first one leaves the generator still writing the
    rest in the background."""
    deadline = time.monotonic() + timeout_ms / 1000
    last_count = -1
    stable_count = 0
    while time.monotonic() < deadline:
        current = get_files_fn()
        n = len(current)
        if n > 0 and n == last_count:
            stable_count += 1
            if stable_count >= stable_polls:
                return current
        else:
            stable_count = 0
        last_count = n
        qtbot.wait(poll_ms)
    raise TimeoutError(
        f"Export never stabilized within {timeout_ms}ms "
        f"(last count={last_count}, stable_count={stable_count})"
    )


# ------------- Test -------------------------------------------------------


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_metadata_csv_export(qtbot, tmp_path, monkeypatch, caplog):
    metadata_db = (
        REPO_ROOT / "tests" / "data" / METADATA_DB_NAME
        if (REPO_ROOT / "tests" / "data" / METADATA_DB_NAME).exists()
        else REPO_ROOT / "data" / METADATA_DB_NAME
    )
    assert metadata_db.exists(), f"Missing test file: {metadata_db}"

    export_folder = tmp_path / "csv_export"
    export_folder.mkdir(exist_ok=True)

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
    # Folder-typed DictDialog fields render as a picker QPushButton, not
    # a QLineEdit (confirmed via a real AttributeError). Patch the
    # underlying folder-picker call.
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        staticmethod(lambda *_a, **_k: str(export_folder)),
        raising=False,
    )

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
    # see test_metadata_flow.py for full rationale)
    import poriscope.plugins.analysistabs.MetadataView as metadata_view_mod

    def _patched_show_dialog(
        self, structure, loader_name, title="Select Channels", selected=None
    ):
        selection_widget = metadata_view_mod.SelectionTree()
        selection_widget.populate_tree(structure, loader_name, selected)
        select_all_btn = selection_widget.select_all_button
        if select_all_btn.text() == "Select All":
            QTest.mouseClick(select_all_btn, Qt.MouseButton.LeftButton)
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
    # SETUP: loader + scope + one filter (export requires <=1 filter
    # selected or it silently refuses to open its dialog at all)
    # =========================================================
    def auto_complete_loader_settings():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_loader_settings)
            return
        pick_btn = _find_button_contains(dlg, "select input file")
        if pick_btn:
            QTest.mouseClick(pick_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(QT_WAIT_SHORT_MS)
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower() and not w.text().strip():
                w.setText("db_loader_e2e")
        ok = _find_button(dlg, "ok")
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_loader_settings)

    QtCore.QTimer.singleShot(0, auto_complete_loader_settings)
    QTest.mouseClick(controls.db_loader_add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    qtbot.wait(QT_WAIT_SHORT_MS)
    QTest.mouseClick(controls.selection_tree_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    print(
        f"[DEBUG] Selected scope: {md_view.selected_experiment_and_channels_by_loader}"
    )

    def auto_complete_filter_dialog():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_filter_dialog)
            return
        if not dlg.name_input.text().strip():
            dlg.name_input.setText("csv_export_filter")
        if not dlg.filter_input.toPlainText().strip():
            dlg.filter_input.setPlainText("duration>100")
        ok_btn = dlg.button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn.isEnabled():
            QTest.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_filter_dialog)

    QtCore.QTimer.singleShot(0, auto_complete_filter_dialog)
    QTest.mouseClick(controls.filter_add_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: any("csv_export_filter" in n for n in md_view.subset_filters),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    filter_name = next(n for n in md_view.subset_filters if "csv_export_filter" in n)
    print(
        f"[DEBUG] Filter added: {filter_name!r} = {md_view.subset_filters[filter_name]!r}"
    )
    print(
        f"[DEBUG] Filters selected before CSV export: {controls.filter_comboBox.getSelectedItems()}"
    )

    def _find_name_lineedit(dlg):
        for w in dlg.findChildren(QtWidgets.QLineEdit):
            if "name" in (w.objectName() or "").lower():
                return w
        return None

    # =========================================================
    # ACCEPT PATH: fill Folder, click OK, expect real CSV files
    # =========================================================
    before_files = set(export_folder.glob("*.csv"))
    _accept_attempts = {"n": 0}
    _accept_found_attempts = {"n": 0}

    def auto_complete_export_accept():
        dlg = _first_modal_dialog()
        if dlg is None:
            _accept_attempts["n"] += 1
            assert _accept_attempts["n"] < _MAX_DIALOG_POLL_ATTEMPTS, (
                "Export dialog never appeared after clicking "
                "export_csv_subset_button - likely >1 filter still "
                "selected (the dialog silently refuses to open in that "
                "case) or the button was disabled"
            )
            QtCore.QTimer.singleShot(50, auto_complete_export_accept)
            return
        entrywidgets = getattr(dlg, "entrywidgets", {})
        print(f"[DEBUG] Export dialog entrywidgets keys: {list(entrywidgets.keys())}")
        folder_widget = entrywidgets.get("Folder")
        print(f"[DEBUG] Folder widget type: {type(folder_widget).__name__}")
        if isinstance(folder_widget, QtWidgets.QPushButton):
            QTest.mouseClick(folder_widget, Qt.MouseButton.LeftButton)
            qtbot.wait(50)
        elif folder_widget is not None and hasattr(folder_widget, "setText"):
            folder_widget.setText(str(export_folder))
            folder_widget.editingFinished.emit()
        name_edit = _find_name_lineedit(dlg)
        if name_edit is not None and not name_edit.text().strip():
            name_edit.setText("csv_export_e2e")
            name_edit.editingFinished.emit()
        ok = _find_button(dlg, "ok")
        print(
            f"[DEBUG] Export dialog OK button found={ok is not None}, "
            f"enabled={ok.isEnabled() if ok else None}"
        )
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
            print("[DEBUG] Export dialog OK clicked")
        else:
            _accept_found_attempts["n"] += 1
            assert _accept_found_attempts["n"] < _MAX_DIALOG_POLL_ATTEMPTS, (
                "Export dialog's OK button never became enabled after "
                "filling Folder + forcing editingFinished"
            )
            QtCore.QTimer.singleShot(50, auto_complete_export_accept)

    QtCore.QTimer.singleShot(0, auto_complete_export_accept)
    QTest.mouseClick(controls.export_csv_subset_button, Qt.MouseButton.LeftButton)
    print("[DEBUG] export_csv_subset_button clicked, entering waitUntil...")

    def _get_new_csvs():
        return set(export_folder.glob("*.csv")) - before_files

    new_csv_files = _wait_for_stable_export(qtbot, _get_new_csvs)
    print(
        f"[DEBUG] CSV export (accept path) produced {len(new_csv_files)} file(s): {new_csv_files}"
    )
    assert (
        len(new_csv_files) > 0
    ), "Expected at least one new CSV file after accepting export"
    sample_csv = next(iter(new_csv_files))
    assert sample_csv.stat().st_size > 0, f"Expected {sample_csv} to be non-empty"
    with open(sample_csv) as f:
        header = f.readline().strip()
    print(f"[DEBUG] CSV header (from {sample_csv.name}): {header!r}")
    assert header, "Expected a non-empty header row in the exported CSV"

    # =========================================================
    # CANCEL PATH: no crash, no new file
    # =========================================================
    before_cancel_files = set(export_folder.glob("*.csv"))

    def auto_complete_export_cancel():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_export_cancel)
            return
        all_buttons = [b.text() for b in dlg.findChildren(QtWidgets.QPushButton)]
        print(f"[DEBUG] Cancel-path: all button labels found: {all_buttons}")
        cancel_btn = _find_button(dlg, "cancel")
        if cancel_btn:
            print(f"[DEBUG] Clicking real Cancel button: {cancel_btn.text()!r}")
            QTest.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)
        else:
            print(
                "[DEBUG] No 'Cancel'-labeled button found - falling back to dlg.reject()"
            )
            dlg.reject()

    QtCore.QTimer.singleShot(0, auto_complete_export_cancel)
    QTest.mouseClick(controls.export_csv_subset_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)

    after_cancel_files = set(export_folder.glob("*.csv"))
    print(
        f"[DEBUG] CSV export (cancel path): files before={before_cancel_files}, "
        f"after={after_cancel_files}"
    )
    assert after_cancel_files == before_cancel_files, (
        "Expected Cancel to produce no new CSV file, got "
        f"{after_cancel_files - before_cancel_files}"
    )

    # Reaching this line at all (no exception propagated up through
    # QTest.mouseClick) already proves Cancel no longer crashes the app -
    # that's the actual regression check for the fixed None-guard.
    print("[DEBUG] App remained responsive after Cancel path (no exception raised)")

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
