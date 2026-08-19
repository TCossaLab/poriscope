"""
E2E/UX flow for Metadata tab.

Run with:
    pytest tests/e2e/metadata/test_metadata_flow.py -v -s

Stages:
1) Open Metadata tab, add a MetaDatabaseLoader (SQLiteDBLoader) pointed at
   tests/data/DB.db (or E2E_METADATA_DB).
2) Open Scope dialog (SelectionTree): verification against the real
   QTreeWidget state (not just the button label) - default-all-checked,
   Deselect All / Select All both directions, and (if the DB has more
   than one experiment/channel leaf) individual select-deselect plus
   PartiallyChecked parent-node behavior. Narrows down to exactly one
   experiment/channel afterward since downstream plotting stages in this
   file assume a single dataset per plot.
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
# DB with 2+ experiments and/or 2+ channels, for genuinely testing
# Select All / individual select-deselect / partial-selection behavior
# in the Scope dialog. With a single-experiment/single-channel DB,
# Select All and individual selection are indistinguishable, so
# partial-selection assertions below are skipped automatically when
# there's only one leaf node.
METADATA_MULTI_DB_NAME = os.getenv("E2E_METADATA_MULTI_DB", "tutorial_DB2.sqlite3")
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
    _candidate_dirs = [REPO_ROOT / "tests" / "data", REPO_ROOT / "data"]
    _candidate_names = [METADATA_MULTI_DB_NAME] + [
        f"{METADATA_MULTI_DB_NAME}{ext}"
        for ext in (".db", ".sqlite3", ".sqlite")
        if not METADATA_MULTI_DB_NAME.endswith(ext)
    ]
    metadata_db = None
    _tried = []
    for _dir in _candidate_dirs:
        for _name in _candidate_names:
            candidate = _dir / _name
            _tried.append(str(candidate))
            if candidate.exists():
                metadata_db = candidate
                break
        if metadata_db is not None:
            break
    assert metadata_db is not None, (
        f"Could not find multi-experiment test DB. Tried: {_tried}. "
        f"Set E2E_METADATA_MULTI_DB if it's named differently."
    )
    print(f"[DEBUG] Using multi-experiment DB: {metadata_db}")

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
        tree = selection_widget.tree
        select_all_btn = selection_widget.select_all_button

        print(f"[DEBUG] Scope dialog structure: {structure}")

        def _checked_leaves():
            checked = {}
            for i in range(tree.topLevelItemCount()):
                parent = tree.topLevelItem(i)
                exp_name = parent.text(0)
                for j in range(parent.childCount()):
                    child = parent.child(j)
                    if child.checkState(0) == Qt.Checked:
                        checked.setdefault(exp_name, []).append(child.text(0))
            return checked

        total_leaves = sum(
            tree.topLevelItem(i).childCount() for i in range(tree.topLevelItemCount())
        )
        print(
            f"[DEBUG] Scope dialog total leaf nodes (experiment x channel "
            f"pairs): {total_leaves}"
        )

        initial_checked = _checked_leaves()
        initial_count = sum(len(v) for v in initial_checked.values())
        print(
            f"[DEBUG] Initial checked leaves: {initial_count}/{total_leaves} "
            f"-> {initial_checked}"
        )
        assert initial_count == total_leaves, (
            f"Expected all {total_leaves} leaves checked by default, got "
            f"{initial_count}: {initial_checked}"
        )
        assert select_all_btn.text() == "Deselect All", (
            f"Expected 'Deselect All' label when everything is checked by "
            f"default, got {select_all_btn.text()!r}"
        )

        QTest.mouseClick(select_all_btn, Qt.MouseButton.LeftButton)
        after_deselect = _checked_leaves()
        after_deselect_count = sum(len(v) for v in after_deselect.values())
        print(
            f"[DEBUG] After Deselect All click: {after_deselect_count}/"
            f"{total_leaves} checked, label={select_all_btn.text()!r}"
        )
        assert after_deselect_count == 0, (
            f"Expected Deselect All to uncheck every leaf, "
            f"{after_deselect_count} still checked: {after_deselect}"
        )
        assert select_all_btn.text() == "Select All", (
            f"Expected label to flip to 'Select All' after deselecting "
            f"everything, got {select_all_btn.text()!r}"
        )

        QTest.mouseClick(select_all_btn, Qt.MouseButton.LeftButton)
        after_select = _checked_leaves()
        after_select_count = sum(len(v) for v in after_select.values())
        print(
            f"[DEBUG] After re-clicking Select All: {after_select_count}/"
            f"{total_leaves} checked, label={select_all_btn.text()!r}"
        )
        assert after_select_count == total_leaves, (
            f"Expected Select All to re-check every leaf, got "
            f"{after_select_count}/{total_leaves}: {after_select}"
        )
        assert select_all_btn.text() == "Deselect All", (
            f"Expected label to flip back to 'Deselect All', got "
            f"{select_all_btn.text()!r}"
        )

        if total_leaves > 1:
            first_parent = tree.topLevelItem(0)
            target_child = first_parent.child(0)
            target_exp = first_parent.text(0)
            target_chan = target_child.text(0)
            print(
                f"[DEBUG] Partial-selection test: unchecking "
                f"{target_exp}/{target_chan}"
            )
            target_child.setCheckState(0, Qt.Unchecked)

            partial_checked = _checked_leaves()
            partial_count = sum(len(v) for v in partial_checked.values())
            print(
                f"[DEBUG] After unchecking one leaf: {partial_count}/"
                f"{total_leaves} checked -> {partial_checked}"
            )
            assert partial_count == total_leaves - 1, (
                f"Expected exactly {total_leaves - 1} leaves checked after "
                f"unchecking one, got {partial_count}"
            )
            assert target_chan not in partial_checked.get(target_exp, []), (
                f"Expected {target_exp}/{target_chan} excluded from checked "
                f"leaves, got {partial_checked}"
            )

            if first_parent.childCount() > 1:
                parent_state = first_parent.checkState(0)
                print(
                    f"[DEBUG] Parent '{target_exp}' checkstate after partial "
                    f"uncheck: {parent_state} (PartiallyChecked="
                    f"{Qt.PartiallyChecked})"
                )
                assert parent_state == Qt.PartiallyChecked, (
                    f"Expected parent '{target_exp}' to show "
                    f"PartiallyChecked with {first_parent.childCount() - 1}/"
                    f"{first_parent.childCount()} children checked, got "
                    f"{parent_state}"
                )

            assert select_all_btn.text() == "Select All", (
                f"Expected 'Select All' label with a partial selection, "
                f"got {select_all_btn.text()!r}"
            )

            target_child.setCheckState(0, Qt.Checked)
            restored = _checked_leaves()
            restored_count = sum(len(v) for v in restored.values())
            assert restored_count == total_leaves, (
                f"Expected full selection restored, got "
                f"{restored_count}/{total_leaves}"
            )
        else:
            print(
                "[DEBUG] Only one leaf node in Scope dialog - "
                "partial-selection test skipped (nothing to partially "
                "select). Set E2E_METADATA_MULTI_DB to a DB with 2+ "
                "experiments/channels to exercise this properly."
            )

        first_exp_name = tree.topLevelItem(0).text(0)
        first_chan_name = tree.topLevelItem(0).child(0).text(0)
        for i in range(tree.topLevelItemCount()):
            parent = tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                keep = (
                    parent.text(0) == first_exp_name
                    and child.text(0) == first_chan_name
                )
                child.setCheckState(0, Qt.Checked if keep else Qt.Unchecked)

        result = selection_widget.get_selected()
        print(f"[DEBUG] Final narrowed selection for downstream stages: {result}")
        assert result == {first_exp_name: [first_chan_name]}, (
            f"Expected narrowed selection to be exactly one "
            f"experiment/channel, got {result}"
        )

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
    # Confirmed real (MetadataControls.py source): db_loader_comboBox.
    qtbot.waitUntil(
        lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    # =========================================================
    # STAGE 2: Scope dialog (SelectionTree). The real verification (Select
    # All both directions, individual select/deselect, PartiallyChecked
    # parent state, then narrowing to one experiment/channel) happens
    # synchronously inside the monkeypatched show_dialog() above - clicking
    # selection_tree_button triggers it directly, no async dialog-polling
    # needed since we never enter a real Qt.Popup exec().
    # =========================================================
    qtbot.wait(QT_WAIT_SHORT_MS)
    QTest.mouseClick(controls.selection_tree_button, Qt.MouseButton.LeftButton)
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
            QTest.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_assisted_filter_dialog)

    QtCore.QTimer.singleShot(0, auto_complete_assisted_filter_dialog)
    QTest.mouseClick(controls.filter_add_button, Qt.MouseButton.LeftButton)
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
            QTest.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
        else:
            QtCore.QTimer.singleShot(50, auto_complete_raw_filter_dialog)

    QtCore.QTimer.singleShot(0, auto_complete_raw_filter_dialog)
    QTest.mouseClick(controls.filter_add_button, Qt.MouseButton.LeftButton)
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
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
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

    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
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
    # STAGE 6: toggle x-axis log scale -> label should show "log10(...)".
    # No Reset click here (removed) - confirmed via real manual testing
    # that Undo tracks PLOT TYPE changes specifically, not filter/overlay/
    # event changes within the same plot type, so a Reset+replot with the
    # same Histogram type here would never have exercised Undo
    # meaningfully anyway - that's covered properly in Stage 7 below.
    # =========================================================
    label_before_log = _get_x_label(md_view.figure)
    controls.x_axis_logscale_checkbox.setChecked(True)
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
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
    # STAGE 7: Undo, tested against a genuine PLOT TYPE change. Confirmed
    # via real manual testing: Undo specifically tracks switching between
    # different plot types (e.g. Histogram <-> Scatterplot) - it does NOT
    # track navigating events, changing filter selection, or adding
    # overlays within the same plot type. So the correct way to exercise
    # it is: change to a genuinely different plot type, then Undo should
    # reveal the previous plot type again (bars back, no scatter
    # collections) - not any specific filter/legend-label state.
    # =========================================================
    bars_before_type_change = _count_bars(md_view.figure)
    assert (
        bars_before_type_change > 0
    ), "Expected a Histogram (bars) before switching plot type"

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
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_collections(md_view.figure) > before_collections,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    collections_after_scatter = _count_collections(md_view.figure)
    print(
        f"[DEBUG] Scatterplot collections: {collections_after_scatter} "
        f"(duration vs num_sublevels)"
    )
    assert (
        collections_after_scatter > 0
    ), "Expected a real scatter collection after switching to Scatterplot"

    QTest.mouseClick(controls.undo_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_WAIT_SHORT_MS)
    bars_after_undo = _count_bars(md_view.figure)
    collections_after_undo = _count_collections(md_view.figure)
    print(
        f"[DEBUG] After Undo: bars={bars_after_undo}, "
        f"collections={collections_after_undo}"
    )
    assert bars_after_undo > 0, (
        f"Expected Undo to reveal the previous Histogram (bars present) "
        f"after undoing the Scatterplot type change, got {bars_after_undo} bars"
    )
    assert collections_after_undo == 0, (
        f"Expected Undo to remove the Scatterplot's scatter collection, "
        f"got {collections_after_undo}"
    )
    print("[DEBUG] Undo correctly reverted the plot-type change back to Histogram")

    # =========================================================
    # STAGE 8: Reset -> expect a fully cleared plot
    # =========================================================
    QTest.mouseClick(controls.reset_button, Qt.MouseButton.LeftButton)
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
    # STAGE 9: fresh Scatterplot from a clean post-Reset state, confirming
    # scatter rendering still works normally after Reset (independent of
    # Stage 7's Undo-based scatter test above)
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
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
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
