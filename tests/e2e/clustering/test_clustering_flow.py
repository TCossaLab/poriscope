# Run with: pytest tests/e2e/clustering/test_clustering_flow.py -v -s
"""
E2E/UX flow for Clustering tab: load a synthetic multi-experiment metadata
database, run Gaussian Mixtures clustering, merge two cluster labels,
switch to HDBSCAN with and without a SQL filter, and commit the result to
the database.

Test data comes from the synthetic_metadata_database fixture (see
tests/synthetic_data/synthetic_metadata_db.py and
tests/e2e/metadata/conftest.py) rather than a checked-in real database.
This sidesteps a real constraint the original real-DB version of this
test had to work around: Commit performs a genuine ALTER TABLE plus a
write of cluster_label/cluster_confidence into every row, permanently
mutating whatever file it's pointed at. The old test copied
tutorial_DB2.sqlite3 into tmp_path before every run for exactly that
reason. The synthetic fixture is already private and disposable -- a
fresh file per test, already living in tmp_path -- so no copy step is
needed here at all.

Row-count expectations (unfiltered total, and the count after a
"duration > X" filter) are computed directly from the fixture's ground
truth rather than hardcoded, the same way median_duration_us() was
verified against a real live SQL filter earlier: X is picked as this
database's own median_duration_us(), and the expected filtered count is
the literal number of planted events whose ground-truth duration exceeds
it, counted in Python -- not assumed to be "about half" the total.

Cluster assignments themselves (which points land in which
Gaussian-Mixtures/HDBSCAN cluster) are NOT and cannot be predicted from
ground truth -- that's the actual output of the clustering algorithms
under test. What's asserted is structural: the requested cluster COUNT
for Gaussian Mixtures, the row COUNT clustered before/after filtering,
and that Commit writes to the database exactly what was in memory at
commit time.
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


def _count_collections(fig):
    """ClusteringView.update_plot calls ax.scatter() ONCE PER CLUSTER LABEL
    in a loop, so the number of collections equals the number of distinct
    cluster labels currently plotted."""
    return sum(len(ax.collections) for ax in getattr(fig, "axes", []) or [])


def _combobox_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def _fake_get_item_exact_then_substring(*wants):
    """Build a QInputDialog.getItem replacement that tries an exact match
    against each of wants first, then falls back to a substring match --
    avoids a shorter name matching inside a longer unrelated one (e.g.
    "CUSUM" matching "ClassicCUSUM") when only substring matching is used.
    Kept local to this file rather than in tests.e2e._helpers, matching
    the pattern already established in the metadata and event_analysis
    suites, since the specific "wants" tuple differs per tab."""

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
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_clustering_flow(
    qtbot,
    tmp_path,
    monkeypatch,
    caplog,
    auto_dismiss_message_boxes,
    synthetic_metadata_database,
):
    db = synthetic_metadata_database

    # Duration threshold and its exact expected filtered count, computed
    # from this database's own ground truth rather than assumed.
    duration_threshold_us = db.median_duration_us()
    all_durations_us = [
        d
        for exp in db.experiments.values()
        for ch in exp.channels.values()
        for d in ch.event_durations_us
    ]
    expected_filtered_count = sum(
        1 for d in all_durations_us if d > duration_threshold_us
    )
    expected_total_count = db.total_num_events
    print(
        f"[DEBUG] Ground truth: {expected_total_count} total events, "
        f"duration_threshold_us={duration_threshold_us:.1f}, "
        f"{expected_filtered_count} events above threshold"
    )

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(_fake_get_item_exact_then_substring(LOADER_SUBCLASS_NAME)),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(db.db_path), "All Files (*)")),
        raising=False,
    )

    # QMessageBox auto-dismissal is handled by the auto_dismiss_message_boxes
    # fixture (tests/e2e/conftest.py) requested above -- no need to
    # hand-roll the same monkeypatch here.

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

    # Capture every add_text_to_display message so assertions check the
    # real displayed strings (row counts, method names, commit status)
    # rather than guessing at log output.
    #
    # ClusteringView.add_text_to_display and
    # ClusteringController.add_text_to_display are TWO SEPARATE Signal
    # objects on two separate instances. "Gaussian Mixtures applied
    # to..."/"HDBSCAN applied to..." are emitted from the view's own
    # signal; the commit success/failure message lives on the
    # controller's own signal. Connect to both, or commit messages are
    # missed entirely.
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
    def fill_loader_dialog(dlg) -> bool:
        pick_btn = find_button(dlg, "select input file")
        if pick_btn:
            QTest.mouseClick(pick_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(QT_SHORT_PAUSE_MS)
        ensure_name_filled(dlg, "db_loader_e2e")
        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_loader_dialog)
    QTest.mouseClick(controls.db_loader_add_button, Qt.MouseButton.LeftButton)
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
        checkboxes -- required on every open since defaults are NOT
        reliably pre-filled (empty on first open, only restored from a
        matching prior config on later opens)."""
        rows = dlg.default_row_widgets
        assert len(rows) >= 2, f"Expected 2 default_row_widgets, got {len(rows)}"
        rows[0]["combo"].setCurrentText(col0)
        rows[0]["plot_cb"].setChecked(True)
        rows[1]["combo"].setCurrentText(col1)
        rows[1]["plot_cb"].setChecked(True)

    def _set_line_edit_by_object_name(dlg, name, value):
        w = dlg.findChild(QtWidgets.QLineEdit, name)
        if w is not None:
            w.setText(value)
            w.editingFinished.emit()
            return True
        return False

    def auto_complete_gaussian_settings():
        dlg = first_modal_dialog()
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

        set_clusters = _set_line_edit_by_object_name(
            dlg, "Gaussian Mixtures_Number_of_Clusters_input", "3"
        )
        assert (
            set_clusters
        ), "Could not find 'Gaussian Mixtures_Number_of_Clusters_input'"

        _set_default_columns(dlg, "duration", "num_sublevels")

        if dlg.apply_button.isEnabled():
            QTest.mouseClick(dlg.apply_button, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_gaussian_settings)

    QtCore.QTimer.singleShot(0, auto_complete_gaussian_settings)
    QTest.mouseClick(controls.cluster_settings_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: any("Gaussian Mixtures applied to" in m for m in displayed_messages),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    gaussian_msg = next(
        m for m in displayed_messages if "Gaussian Mixtures applied to" in m
    )
    print(f"[DEBUG] Display message: {gaussian_msg!r}")
    assert f"{expected_total_count} rows" in gaussian_msg, (
        f"Expected 'Gaussian Mixtures applied to {expected_total_count} rows' "
        f"(this fixture's total planted events), got: {gaussian_msg!r}"
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
    assert set(label_x_items) == {
        "0",
        "1",
        "2",
    }, f"Expected KEEP LABEL combobox to contain 0/1/2, got {label_x_items}"
    print(
        f"[DEBUG] KEEP LABEL items: {label_x_items}, MERGE WITH items: {label_y_items}"
    )

    # =========================================================
    # STAGE 3: merge label 2 into label 1 -> expect only labels {0, 1}
    # =========================================================
    keep_idx = controls.label_x_comboBox.findText("1")
    merge_idx = controls.label_y_comboBox.findText("2")
    assert keep_idx >= 0 and merge_idx >= 0, (
        f"Expected '1' and '2' in KEEP/MERGE comboboxes, got keep_idx={keep_idx}, "
        f"merge_idx={merge_idx}"
    )
    controls.label_x_comboBox.setCurrentIndex(keep_idx)
    controls.label_y_comboBox.setCurrentIndex(merge_idx)

    QTest.mouseClick(controls.merge_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_collections(clustering_view.figure) == 2,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    label_x_items_after = _combobox_items(controls.label_x_comboBox)
    assert set(label_x_items_after) == {"0", "1"}, (
        f"Expected KEEP LABEL combobox to only show 0/1 after merge, got "
        f"{label_x_items_after}"
    )

    # =========================================================
    # STAGE 4: HDBSCAN with filter "duration>THRESHOLD" -> expect the
    # exact filtered count computed from ground truth above.
    # =========================================================
    def auto_complete_hdbscan_filtered():
        dlg = first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_filtered)
            return

        idx = dlg.method_combo.findText("HDBSCAN")
        assert (
            idx >= 0
        ), f"'HDBSCAN' not in METHOD options: {_combobox_items(dlg.method_combo)}"
        dlg.method_combo.setCurrentIndex(idx)
        qtbot.wait(50)

        _set_line_edit_by_object_name(dlg, "HDBSCAN_Cluster_Size_input", "40")
        _set_line_edit_by_object_name(dlg, "HDBSCAN_Min_Points_input", "1")
        _set_line_edit_by_object_name(dlg, "HDBSCAN_Sensitivity_input", "1.0")

        dlg.filter_text.setPlainText(f"duration>{duration_threshold_us}")
        _set_default_columns(dlg, "duration", "num_sublevels")

        if dlg.apply_button.isEnabled():
            QTest.mouseClick(dlg.apply_button, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_filtered)

    QtCore.QTimer.singleShot(0, auto_complete_hdbscan_filtered)
    QTest.mouseClick(controls.cluster_settings_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: any("HDBSCAN applied to" in m for m in displayed_messages),
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    hdbscan_filtered_msgs = [m for m in displayed_messages if "HDBSCAN applied to" in m]
    assert hdbscan_filtered_msgs, "Expected an 'HDBSCAN applied to' message"
    assert f"{expected_filtered_count} rows" in hdbscan_filtered_msgs[0], (
        f"Expected 'HDBSCAN applied to {expected_filtered_count} rows' with filter "
        f"duration>{duration_threshold_us}, got: {hdbscan_filtered_msgs[0]!r}"
    )

    # =========================================================
    # STAGE 5: HDBSCAN, filter cleared -> expect the full total again.
    # =========================================================
    def auto_complete_hdbscan_unfiltered():
        dlg = first_modal_dialog()
        if dlg is None:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_unfiltered)
            return

        idx = dlg.method_combo.findText("HDBSCAN")
        if idx >= 0:
            dlg.method_combo.setCurrentIndex(idx)
        qtbot.wait(50)

        dlg.filter_text.setPlainText("")
        _set_default_columns(dlg, "duration", "num_sublevels")

        if dlg.apply_button.isEnabled():
            QTest.mouseClick(dlg.apply_button, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_hdbscan_unfiltered)

    QtCore.QTimer.singleShot(0, auto_complete_hdbscan_unfiltered)
    QTest.mouseClick(controls.cluster_settings_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: len([m for m in displayed_messages if "HDBSCAN applied to" in m]) >= 2,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    hdbscan_all_msgs = [m for m in displayed_messages if "HDBSCAN applied to" in m]
    assert f"{expected_total_count} rows" in hdbscan_all_msgs[-1], (
        f"Expected 'HDBSCAN applied to {expected_total_count} rows' with no filter, "
        f"got: {hdbscan_all_msgs[-1]!r}"
    )

    # =========================================================
    # STAGE 6: Commit -> expect "Successfully wrote clustering data",
    # and verify the DB genuinely mirrors what was in memory at commit
    # time -- the success message alone only confirms
    # add_columns_to_table() returned truthy, not that the right values
    # landed in the right rows.
    #
    # Labels being committed here come from the LAST clustering run
    # (HDBSCAN, no filter), not the earlier Gaussian Mixtures + merge
    # result -- switching methods replaces self.cluster_data entirely.
    # HDBSCAN doesn't take a fixed cluster count and can produce any
    # label set including -1 (noise), so this deliberately does not
    # assert a specific label set -- only that the DB exactly mirrors
    # whatever was actually in memory at commit time.
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
        f"[DEBUG] Target table for commit: {table_name!r}, {len(expected_by_id)} rows "
        f"with in-memory cluster assignments"
    )

    QTest.mouseClick(controls.commit_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: any(
            "Successfully wrote clustering data" in m for m in displayed_messages
        ),
        timeout=QT_WAIT_TIMEOUT_MS,
    )

    conn = sqlite3.connect(str(db.db_path))
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        column_names = [c[1] for c in cur.fetchall()]
        assert (
            "cluster_label" in column_names
        ), f"Expected 'cluster_label' column in {table_name!r}, got {column_names}"
        assert (
            "cluster_confidence" in column_names
        ), f"Expected 'cluster_confidence' column in {table_name!r}, got {column_names}"

        cur.execute(f"SELECT id, cluster_label, cluster_confidence FROM {table_name}")
        rows = cur.fetchall()
        db_by_id = {int(r[0]): (r[1], r[2]) for r in rows}
        missing_ids = set(expected_by_id) - set(db_by_id)
        assert not missing_ids, f"Expected ids {missing_ids} to exist in {table_name!r}"

        label_mismatches = [
            (row_id, exp_label, db_by_id[row_id][0])
            for row_id, (exp_label, _exp_conf) in expected_by_id.items()
            if db_by_id[row_id][0] is None or int(db_by_id[row_id][0]) != exp_label
        ]
        assert not label_mismatches, (
            f"cluster_label in DB doesn't match in-memory result at commit time: "
            f"{label_mismatches}"
        )
        print(
            f"[DEBUG] Verified {len(expected_by_id)} committed rows match in-memory state"
        )
    finally:
        conn.close()

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
