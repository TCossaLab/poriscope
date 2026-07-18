"""
E2E/UX flow for Clustering tab: load a multi-experiment DB, run Gaussian
Mixtures clustering, merge two cluster labels, switch to HDBSCAN with and
without a SQL filter, and commit the result to the database.

Real, confirmed reference values (from manual testing against
tutorial_DB2.sqlite3):
    SQLiteDBLoader_0: 2 experiments
    tutorial:   Channel 3: 18 events
    tutorial2:  Channel 1: 6 events, Channel 3: 15 events
    (18 + 6 + 15 = 39 total rows)

    "ClusteringView: Gaussian Mixtures applied to 39 rows"  (no filter)
    "ClusteringView: HDBSCAN applied to 35 rows"            (duration>100)
    "ClusteringView: HDBSCAN applied to 39 rows"            (no filter)
    "ClusteringController: Successfully wrote clustering data"  (commit)

IMPORTANT: Commit actually ALTERs the database (adds cluster_label /
cluster_confidence columns), so this test copies tutorial_DB2.sqlite3 into
tmp_path first rather than pointing the loader at the real repo fixture -
otherwise every run would permanently mutate shared test data.


Run with:
    pytest tests/e2e/clustering/test_e2e_clustering_flow.py -v -s
"""

import os
import shutil
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
from tests.e2e._helpers import (
    _fake_get_item_exact_then_substring,
    _find_button,
    _find_button_contains,
    _first_modal_dialog,
    open_menu_hybrid,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CLUSTERING_DB_NAME = os.getenv("E2E_CLUSTERING_DB", "tutorial_DB2.sqlite3")
LOADER_SUBCLASS_NAME = os.getenv("E2E_DBLOADER_NAME", "SQLiteDBLoader")

E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "180"))
QT_WAIT_TIMEOUT_MS = int(os.getenv("E2E_QT_TIMEOUT_MS", "60000"))
QT_WAIT_SHORT_MS = int(os.getenv("E2E_QT_WAIT_SHORT_MS", "300"))


def _count_collections(fig):
    """ClusteringView.update_plot calls ax.scatter() ONCE PER CLUSTER LABEL
    in a loop, so the number of collections equals the number of distinct
    cluster labels currently plotted."""
    return sum(len(ax.collections) for ax in getattr(fig, "axes", []) or [])


def _combobox_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_clustering_flow(
    qtbot, tmp_path, monkeypatch, auto_dismiss_message_boxes, caplog
):
    # ---- Locate and copy the DB (writable - Commit mutates it) ----
    _candidate_dirs = [REPO_ROOT / "tests" / "data", REPO_ROOT / "data"]
    _candidate_names = [CLUSTERING_DB_NAME] + [
        f"{CLUSTERING_DB_NAME}{ext}"
        for ext in (".db", ".sqlite3", ".sqlite")
        if not CLUSTERING_DB_NAME.endswith(ext)
    ]
    source_db = None
    _tried = []
    for _dir in _candidate_dirs:
        for _name in _candidate_names:
            candidate = _dir / _name
            _tried.append(str(candidate))
            if candidate.exists():
                source_db = candidate
                break
        if source_db is not None:
            break
    assert source_db is not None, f"Could not find clustering test DB. Tried: {_tried}"

    working_db = tmp_path / source_db.name
    shutil.copy(source_db, working_db)
    print(f"[DEBUG] Using writable DB copy: {working_db}")

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(_fake_get_item_exact_then_substring(LOADER_SUBCLASS_NAME)),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(working_db), "All Files (*)")),
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
    controller = MainController(model, view)
    qtbot.addWidget(view)
    view.show()

    open_menu_hybrid(
        view,
        ["Analysis", "New Analysis Tab", "ClusteringController"],
        qtbot,
        timeout_ms=QT_WAIT_TIMEOUT_MS,
    )
    qtbot.waitUntil(lambda: "ClusteringView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("ClusteringView")
    clustering_view = view.pages["ClusteringView"]["widget"]
    controls = clustering_view.clusteringcontrols

    # Capture every add_text_to_display message so we can assert on the
    # real confirmed strings (row counts, method names, commit status)
    # rather than guessing at log output.
    #
    # IMPORTANT: ClusteringView.add_text_to_display and
    # ClusteringController.add_text_to_display are TWO SEPARATE Signal
    # objects on two separate instances - confirmed from source.
    # "Gaussian Mixtures applied to..."/"HDBSCAN applied to..." are
    # emitted from ClusteringView._handle_clustering_settings (the
    # view's own signal), but display_write_status (the commit
    # success/failure message) lives on ClusteringController and emits
    # on ITS OWN add_text_to_display - connecting only to the view's
    # signal misses commit messages entirely. Connect to both.
    displayed_messages = []
    clustering_view.add_text_to_display.connect(
        lambda text, source: displayed_messages.append(text)
    )
    clustering_controller = controller.analysis_tabs["ClusteringController"]
    clustering_controller.add_text_to_display.connect(
        lambda text, source: displayed_messages.append(text)
    )

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
    qtbot.waitUntil(
        lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    # =========================================================
    # STAGE 2: Cluster Settings -> Gaussian Mixtures, 3 clusters, no
    # filter, default columns (duration, num_sublevels), Apply.
    # =========================================================
    def _set_default_columns(dlg, col0, col1):
        """Explicitly set both default column rows and check their PLOT
        checkboxes - required on every open since defaults are NOT
        reliably pre-filled (empty on first open, only restored from a
        matching prior config on later opens)."""
        rows = dlg.default_row_widgets
        assert len(rows) >= 2, f"Expected 2 default_row_widgets, got {len(rows)}"
        rows[0]["combo"].setCurrentText(col0)
        rows[0]["plot_cb"].setChecked(True)
        rows[1]["combo"].setCurrentText(col1)
        rows[1]["plot_cb"].setChecked(True)
        print(
            f"[DEBUG] Default rows set: "
            f"[{rows[0]['combo'].currentText()!r} plot={rows[0]['plot_cb'].isChecked()}], "
            f"[{rows[1]['combo'].currentText()!r} plot={rows[1]['plot_cb'].isChecked()}]"
        )

    def _set_line_edit_by_object_name(dlg, name, value):
        w = dlg.findChild(QtWidgets.QLineEdit, name)
        if w is not None:
            w.setText(value)
            w.editingFinished.emit()
            return True
        return False

    def auto_complete_gaussian_settings():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_gaussian_settings)
            return

        idx = dlg.method_combo.findText("Gaussian Mixtures")
        assert idx >= 0, (
            f"'Gaussian Mixtures' not in METHOD options: "
            f"{_combobox_items(dlg.method_combo)}"
        )
        dlg.method_combo.setCurrentIndex(idx)
        qtbot.wait(50)  # let update_method_parameters rebuild param fields

        all_line_edits = [
            (w.objectName(), w.text()) for w in dlg.findChildren(QtWidgets.QLineEdit)
        ]
        print(f"[DEBUG] Gaussian dialog QLineEdits: {all_line_edits}")

        set_clusters = _set_line_edit_by_object_name(
            dlg, "Gaussian Mixtures_Number_of_Clusters_input", "3"
        )
        print(
            f"[DEBUG] Set Number of Clusters via confirmed objectName: {set_clusters}"
        )
        assert set_clusters, (
            "Could not find 'Gaussian Mixtures_Number_of_Clusters_input' - "
            f"available QLineEdits: {all_line_edits}"
        )

        _set_default_columns(dlg, "duration", "num_sublevels")

        print(f"[DEBUG] apply_button.isEnabled() = {dlg.apply_button.isEnabled()}")
        if dlg.apply_button.isEnabled():
            QTest.mouseClick(dlg.apply_button, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_gaussian_settings)

    QtCore.QTimer.singleShot(0, auto_complete_gaussian_settings)
    QTest.mouseClick(controls.cluster_settings_button, Qt.LeftButton)

    qtbot.waitUntil(
        lambda: any("Gaussian Mixtures applied to" in m for m in displayed_messages),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    gaussian_msg = next(
        m for m in displayed_messages if "Gaussian Mixtures applied to" in m
    )
    print(f"[DEBUG] Display message: {gaussian_msg!r}")
    assert "39 rows" in gaussian_msg, (
        f"Expected 'Gaussian Mixtures applied to 39 rows' (18+6+15 from "
        f"tutorial+tutorial2), got: {gaussian_msg!r}"
    )

    collections_after_gaussian = _count_collections(clustering_view.figure)
    print(
        f"[DEBUG] Scatter collections after Gaussian Mixtures: {collections_after_gaussian}"
    )
    assert collections_after_gaussian == 3, (
        f"Expected 3 scatter collections (3 requested clusters), got "
        f"{collections_after_gaussian}"
    )

    label_x_items = _combobox_items(controls.label_x_comboBox)
    label_y_items = _combobox_items(controls.label_y_comboBox)
    print(
        f"[DEBUG] KEEP LABEL items: {label_x_items}, MERGE WITH items: {label_y_items}"
    )
    assert set(label_x_items) == {
        "0",
        "1",
        "2",
    }, f"Expected KEEP LABEL combobox to contain 0/1/2, got {label_x_items}"

    # =========================================================
    # STAGE 3: merge label 2 into label 1 -> expect only labels {0, 1}
    # =========================================================
    keep_idx = controls.label_x_comboBox.findText("1")
    merge_idx = controls.label_y_comboBox.findText("2")
    assert keep_idx >= 0 and merge_idx >= 0, (
        f"Expected '1' and '2' in KEEP/MERGE comboboxes, got "
        f"keep_idx={keep_idx}, merge_idx={merge_idx}"
    )
    controls.label_x_comboBox.setCurrentIndex(keep_idx)
    controls.label_y_comboBox.setCurrentIndex(merge_idx)

    QTest.mouseClick(controls.merge_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _count_collections(clustering_view.figure) == 2,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    collections_after_merge = _count_collections(clustering_view.figure)
    label_x_items_after = _combobox_items(controls.label_x_comboBox)
    label_y_items_after = _combobox_items(controls.label_y_comboBox)
    print(
        f"[DEBUG] After merge: {collections_after_merge} collections, "
        f"KEEP LABEL items={label_x_items_after}, "
        f"MERGE WITH items={label_y_items_after}"
    )
    assert collections_after_merge == 2, (
        f"Expected exactly 2 clusters (0, 1) remaining after merging 2 "
        f"into 1, got {collections_after_merge} collections"
    )
    assert set(label_x_items_after) == {"0", "1"}, (
        f"Expected KEEP LABEL combobox to only show 0/1 after merge, got "
        f"{label_x_items_after}"
    )

    # =========================================================
    # STAGE 4: HDBSCAN with filter "duration>100" -> expect "35 rows"
    # (39 total - 4 rows with duration<=100, per real manual testing).
    # =========================================================
    def auto_complete_hdbscan_filtered():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_filtered)
            return

        idx = dlg.method_combo.findText("HDBSCAN")
        assert (
            idx >= 0
        ), f"'HDBSCAN' not in METHOD options: {_combobox_items(dlg.method_combo)}"
        dlg.method_combo.setCurrentIndex(idx)
        qtbot.wait(50)  # let update_method_parameters rebuild param fields

        all_line_edits = [
            (w.objectName(), w.text()) for w in dlg.findChildren(QtWidgets.QLineEdit)
        ]
        print(f"[DEBUG] HDBSCAN dialog QLineEdits: {all_line_edits}")

        _set_line_edit_by_object_name(dlg, "HDBSCAN_Cluster_Size_input", "40")
        _set_line_edit_by_object_name(dlg, "HDBSCAN_Min_Points_input", "1")
        _set_line_edit_by_object_name(dlg, "HDBSCAN_Sensitivity_input", "1.0")

        dlg.filter_text.setPlainText("duration>100")
        _set_default_columns(dlg, "duration", "num_sublevels")

        print(f"[DEBUG] apply_button.isEnabled() = {dlg.apply_button.isEnabled()}")
        if dlg.apply_button.isEnabled():
            QTest.mouseClick(dlg.apply_button, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_filtered)

    QtCore.QTimer.singleShot(0, auto_complete_hdbscan_filtered)
    QTest.mouseClick(controls.cluster_settings_button, Qt.LeftButton)

    qtbot.waitUntil(
        lambda: any("HDBSCAN applied to" in m for m in displayed_messages),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    hdbscan_filtered_msgs = [m for m in displayed_messages if "HDBSCAN applied to" in m]
    print(f"[DEBUG] HDBSCAN messages so far: {hdbscan_filtered_msgs}")
    assert hdbscan_filtered_msgs, "Expected an 'HDBSCAN applied to' message"
    assert "35 rows" in hdbscan_filtered_msgs[0], (
        f"Expected 'HDBSCAN applied to 35 rows' with filter duration>100, "
        f"got: {hdbscan_filtered_msgs[0]!r}"
    )

    # =========================================================
    # STAGE 5: HDBSCAN, filter cleared -> expect "39 rows" again.
    # =========================================================
    def auto_complete_hdbscan_unfiltered():
        dlg = _first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_unfiltered)
            return

        idx = dlg.method_combo.findText("HDBSCAN")
        if idx >= 0:
            dlg.method_combo.setCurrentIndex(idx)
        qtbot.wait(50)

        dlg.filter_text.setPlainText("")  # clear the filter
        _set_default_columns(dlg, "duration", "num_sublevels")

        print(f"[DEBUG] apply_button.isEnabled() = {dlg.apply_button.isEnabled()}")
        if dlg.apply_button.isEnabled():
            QTest.mouseClick(dlg.apply_button, Qt.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_unfiltered)

    QtCore.QTimer.singleShot(0, auto_complete_hdbscan_unfiltered)
    QTest.mouseClick(controls.cluster_settings_button, Qt.LeftButton)

    qtbot.waitUntil(
        lambda: len([m for m in displayed_messages if "HDBSCAN applied to" in m]) >= 2,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    hdbscan_all_msgs = [m for m in displayed_messages if "HDBSCAN applied to" in m]
    print(f"[DEBUG] HDBSCAN messages (both runs): {hdbscan_all_msgs}")
    assert "39 rows" in hdbscan_all_msgs[-1], (
        f"Expected 'HDBSCAN applied to 39 rows' with no filter, got: "
        f"{hdbscan_all_msgs[-1]!r}"
    )

    # =========================================================
    # STAGE 6: Commit -> expect "Successfully wrote clustering data".
    # =========================================================
    #
    # DB VERIFICATION: Commit permanently mutates the database file
    # (ALTER TABLE + writes cluster_label/cluster_confidence per row) -
    # the success message alone only confirms add_columns_to_table()
    # returned something truthy, not that the right values landed in
    # the right rows. Capture the in-memory cluster assignments right
    # before clicking Commit, then read them back directly from the
    # writable DB copy afterward and assert an exact match.
    #
    # NOTE: the labels being committed here come from the LAST
    # clustering run (HDBSCAN, no filter) - NOT the earlier Gaussian
    # Mixtures + merge result, since switching methods replaces
    # self.cluster_data entirely. HDBSCAN doesn't take a fixed cluster
    # count and can produce any label set, including -1 for noise
    # points (standard HDBSCAN convention) - so this deliberately does
    # NOT assert a specific hardcoded label set, only that the DB
    # exactly mirrors whatever was actually in memory at commit time.
    # =========================================================
    expected_cluster_data = clustering_view.cluster_data[
        ["id", "cluster_label", "cluster_confidence"]
    ].copy()
    expected_by_id = {
        int(row["id"]): (int(row["cluster_label"]), float(row["cluster_confidence"]))
        for _, row in expected_cluster_data.iterrows()
    }
    table_name = clustering_view.table_name
    print(
        f"[DEBUG] Target table for commit: {table_name!r}, "
        f"{len(expected_by_id)} rows with in-memory cluster assignments, "
        f"distinct labels: {sorted({v[0] for v in expected_by_id.values()})}"
    )

    QTest.mouseClick(controls.commit_button, Qt.LeftButton)
    try:
        qtbot.waitUntil(
            lambda: any(
                "Successfully wrote clustering data" in m for m in displayed_messages
            ),
            timeout=QT_WAIT_TIMEOUT_MS,
        )
    except Exception:
        print(
            f"[DEBUG] Commit timed out. Full displayed_messages so far: {displayed_messages}"
        )
        print(f"[DEBUG] Full captured log output:\n{caplog.text}")
        raise
    commit_msg = next(
        m for m in displayed_messages if "Successfully wrote clustering data" in m
    )
    print(f"[DEBUG] Commit message: {commit_msg!r}")

    # --- Direct DB verification ---
    conn = sqlite3.connect(str(working_db))
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        column_names = [c[1] for c in cur.fetchall()]
        print(f"[DEBUG] Table {table_name!r} columns after commit: {column_names}")
        assert (
            "cluster_label" in column_names
        ), f"Expected 'cluster_label' column in {table_name!r}, got {column_names}"
        assert (
            "cluster_confidence" in column_names
        ), f"Expected 'cluster_confidence' column in {table_name!r}, got {column_names}"

        cur.execute(f"SELECT id, cluster_label, cluster_confidence FROM {table_name}")
        rows = cur.fetchall()
        print(f"[DEBUG] {len(rows)} total rows in {table_name!r} after commit")

        db_by_id = {int(r[0]): (r[1], r[2]) for r in rows}
        missing_ids = set(expected_by_id) - set(db_by_id)
        assert (
            not missing_ids
        ), f"Expected ids {missing_ids} to exist in {table_name!r} but they don't"

        label_mismatches = [
            (row_id, exp_label, db_by_id[row_id][0])
            for row_id, (exp_label, _exp_conf) in expected_by_id.items()
            if db_by_id[row_id][0] is None or int(db_by_id[row_id][0]) != exp_label
        ]
        print(
            f"[DEBUG] cluster_label mismatches (id, expected, got in DB): {label_mismatches}"
        )
        assert not label_mismatches, (
            f"cluster_label in DB doesn't match in-memory result at commit time: "
            f"{label_mismatches}"
        )

        db_labels_present = sorted({r[1] for r in rows if r[1] is not None})
        print(
            f"[DEBUG] Distinct cluster_label values actually in DB: {db_labels_present}"
        )
    finally:
        conn.close()

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
