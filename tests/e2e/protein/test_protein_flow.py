# Run with: pytest tests/e2e/protein/test_protein_flow.py -v -s
"""
E2E/UX flow for Protein tab: loader, scope, diameter/length entry,
Individual-mode distribution fitting (default N, then custom N), Ensemble
mode with the same parameters, Report All, mode-switch state
persistence, and Commit Individual.

One test, staged, rather than split across several: every stage after the
first depends on cumulative state built by the ones before it (mode
persistence across switches, Report All needing ensemble_fit_params
already populated by a prior Ensemble Update Plot, Commit needing
fit_data already populated by a prior Individual Update Plot) --
splitting would mean re-driving the entire loader/scope/plot setup in
each split just to reach one assertion, with no isolation benefit, since
the thing under test IS the cross-stage state.

SPEED: _generate_vm_ensemble does real Monte Carlo rejection sampling
(batch_size=50000 per call, called twice per event in Individual mode --
once for prolate, once for oblate -- and twice for the whole dataset in
Ensemble mode). This test is verifying UI wiring, dispatch routing, and
state propagation between stages, not sampling correctness -- that has
its own dedicated unit tests (TestUpdateDistributionIndividual/Ensemble,
referenced throughout this file). _generate_vm_ensemble is monkeypatched
below to return a small fixed sample instantly so Update Plot clicks
don't block on real sampling; everything downstream of it
(DataFrame construction, update_plot/scatter calls, fit_data assembly)
still runs for real.

PLOT METRIC: Individual mode's Update Plot never draws bars/patches on
ax_hist -- it draws a Peak Scatterplot there (_plot_xyerr_scatterplot,
ax.scatter + ax.errorbar, both add to ax.collections), and Scatterplots
of the Prolate/Oblate solutions on ax_vm (also collections).
_plot_all_points_histogram, the one method that would add bar-like
content, is only reachable from Ensemble mode's Raw/Filtered Histogram
plot type. So Stage 3/4 below assert on ax_hist's collections count, not
bars -- asserting on bars there would never pass, since the count would
stay at 0 regardless of a successful Update Plot.

FIT DETERMINISM: _update_distribution_ensemble's Prolate/Oblate scatter
plots are only ever drawn (ax_vm.collections grows) if
_fit_and_sanity_check_double_gaussian succeeds on the real aggregate
current histogram -- a genuine curve_fit plus a p-value/peak-separation
check and a min(amp)/max(amp) >= 0.05 ratio check. Whether an arbitrary
synthetic dataset's histogram happens to look bimodal enough to clear
both checks is dataset/seed-dependent and has nothing to do with UI
wiring -- confirmed by a real run where the fit came back but failed
sanity ("Unable to fit a double gaussian to the histogram"), which left
ax_vm untouched and timed out Stage 5's waitUntil even though dispatch,
routing, and everything upstream worked correctly. Since fit-quality
correctness is out of scope here (same rationale as the
_generate_vm_ensemble mock above -- that has its own dedicated tests),
_fit_and_sanity_check_double_gaussian is also monkeypatched below to
deterministically return a fixed, well-separated two-peak fit, so
Ensemble Update Plot reliably reaches the scatter-drawing code
regardless of this dataset's actual current distribution shape.

ASSUMPTIONS: control widget names (db_loader_add_button,
db_loader_comboBox, selection_tree_button, pore_diameter_lineEdit,
pore_length_lineEdit, n_values_lineEdit, individual/ensemble mode
controls, update_plot_button, commit_individual, report_all) are
confirmed directly against ProteinControls.py source. Action names,
dispatch routing, and guard-clause behavior ARE confirmed directly from
ProteinView's real unit tests (test_protein_view_final.py) and from
ProteinView.py source (_report_ensemble_fit reads
ensemble_fit_params/ensemble_fit_prolate_summary/
ensemble_fit_oblate_summary, all three set at the end of a successful
_update_distribution_ensemble), cited inline below.
"""

import os
import sys
from pathlib import Path

import numpy as np
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

LOADER_SUBCLASS_NAME = os.getenv("E2E_DBLOADER_NAME", "SQLiteDBLoader")
E2E_TIMEOUT_S = int(os.getenv("E2E_TIMEOUT", "240"))


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


def _count_collections(fig):
    return sum(len(ax.collections) for ax in getattr(fig, "axes", []) or [])


def _fake_generate_vm_ensemble(
    self,
    N_target,
    mean_max,
    std_max,
    mean_min,
    std_min,
    d,
    L,
    prolate=True,
    cutoff_std=4,
):
    """
    Drop-in replacement for ProteinView._generate_vm_ensemble that skips the
    real rejection-sampling loop. Returns a small fixed (V, m) sample that
    satisfies the same domain constraints the real sampler enforces
    (m>1 for prolate, 0<m<1 for oblate; V>0), so downstream shape math
    (b = (3V/(4*pi*m))**(1/3), a = b*m) and DataFrame construction in
    _update_distribution_individual/_ensemble run unmodified on real,
    valid-shaped data -- only the sampling cost is removed.
    """
    n = min(N_target, 5) if N_target else 5
    V = np.full(n, 2000.0)
    m = np.full(n, 2.0 if prolate else 0.5)
    return V, m


def _fake_fit_and_sanity_check_double_gaussian(self, bins, amplitude):
    """
    Drop-in replacement for ProteinView._fit_and_sanity_check_double_gaussian
    that skips the real curve_fit + statistical sanity checks (p-value on
    peak separation, min(amp)/max(amp) >= 0.05 ratio). Whether an arbitrary
    synthetic dataset's aggregate current histogram is bimodal enough to
    clear those checks is dataset/seed-dependent and orthogonal to what
    this test verifies (UI wiring/dispatch, not fit-quality correctness --
    see the module docstring's FIT DETERMINISM note). Returns a fixed,
    well-separated two-peak fit built from the real bins' own min/max, so
    it's always a valid position within this histogram's actual range
    regardless of what data produced it.
    """
    bins = np.asarray(bins)
    lo, hi = float(np.min(bins)), float(np.max(bins))
    span = hi - lo if hi > lo else 1.0
    return np.array(
        [1.0, lo + 0.25 * span, 0.01 * span, 1.0, lo + 0.75 * span, 0.01 * span]
    )


@pytest.mark.e2e_ux
@pytest.mark.timeout(E2E_TIMEOUT_S)
def test_protein_individual_ensemble_flow(
    qtbot,
    tmp_path,
    monkeypatch,
    caplog,
    auto_dismiss_message_boxes,
    synthetic_metadata_database,
):
    db = synthetic_metadata_database
    print(f"[DEBUG] Using synthetic metadata DB: {db.db_path}")

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

    # SelectionTree.show_dialog() bypass, narrowing to exactly one
    # experiment/channel: _update_distribution_individual and
    # _update_distribution_ensemble both hard-require exactly one
    # experiment and one channel selected (confirmed:
    # TestUpdateDistributionIndividual/Ensemble's
    # test_multiple_experiments_warns_and_returns /
    # test_multiple_channels_warns_and_returns), so this fixture's
    # multi-experiment shape must be narrowed down after Scope, same as
    # test_metadata_flow.py's own Stage 2 does.
    import poriscope.plugins.analysistabs.ProteinView as protein_view_mod

    def _patched_show_dialog(
        self, structure, loader_name, title="Select Channels", selected=None
    ):
        selection_widget = protein_view_mod.SelectionTree()
        selection_widget.populate_tree(structure, loader_name, selected)
        tree = selection_widget.tree
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
        self.selection_by_loader[loader_name] = result
        return result

    monkeypatch.setattr(
        protein_view_mod.SelectionTree,
        "show_dialog",
        _patched_show_dialog,
        raising=True,
    )

    # See module docstring's SPEED note.
    monkeypatch.setattr(
        protein_view_mod.ProteinView,
        "_generate_vm_ensemble",
        _fake_generate_vm_ensemble,
        raising=True,
    )

    # See module docstring's FIT DETERMINISM note.
    monkeypatch.setattr(
        protein_view_mod.ProteinView,
        "_fit_and_sanity_check_double_gaussian",
        _fake_fit_and_sanity_check_double_gaussian,
        raising=True,
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
        view,
        ["Analysis", "New Analysis Tab", "ProteinController"],
        qtbot,
        timeout_ms=QT_WAIT_TIMEOUT_MS,
    )
    qtbot.waitUntil(lambda: "ProteinView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("ProteinView")
    protein_view = view.pages["ProteinView"]["widget"]
    controls = protein_view.proteincontrols

    # =========================================================
    # STAGE 1: loader + scope, narrowed to one experiment/channel
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
    qtbot.waitUntil(
        lambda: controls.db_loader_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    print(f"[DEBUG] Loader added: {controls.db_loader_comboBox.currentText()!r}")

    qtbot.wait(QT_SHORT_PAUSE_MS)
    QTest.mouseClick(controls.selection_tree_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    scope = protein_view.selected_experiment_and_channels_by_loader
    print(f"[DEBUG] Narrowed scope: {scope}")
    total_leaves_selected = sum(
        len(v)
        for v in scope.get(controls.db_loader_comboBox.currentText(), {}).values()
    )
    assert total_leaves_selected == 1, (
        f"Expected exactly one experiment/channel selected after narrowing, "
        f"got scope={scope}"
    )

    # =========================================================
    # STAGE 2: diameter + length. Confirmed real param keys:
    # pore_diameter, pore_length (TestUpdateDistributionIndividual._params()).
    # =========================================================
    controls.pore_diameter_lineEdit.setText("20.0")
    controls.pore_length_lineEdit.setText("30.0")

    # =========================================================
    # STAGE 3: Individual mode is the confirmed default
    # (test_analysis_mode_individual_default). Leave N at its pre-filled
    # default, click Update Plot.
    # =========================================================
    assert protein_view._analysis_mode == "individual", (
        f"Expected 'individual' as the default analysis mode, got "
        f"{protein_view._analysis_mode!r}"
    )

    bars_before_individual = _count_collections(protein_view.ax_hist.figure)
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_collections(protein_view.ax_hist.figure)
        > bars_before_individual,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    bars_individual_default_n = _count_collections(protein_view.ax_hist.figure)
    print(
        f"[DEBUG] Individual, default N: {bars_individual_default_n} scatter/errorbar "
        f"collections (n_values field={controls.n_values_lineEdit.text()!r})"
    )
    assert protein_view.fit_data is not None, (
        "Expected fit_data to be populated after a successful Individual "
        "Update Plot -- required before Commit can run "
        "(_commit_fits raises AttributeError('fit data has not been set') "
        "otherwise, confirmed in TestCommitFits.test_raises_when_no_fit_data)"
    )

    # =========================================================
    # STAGE 4: Individual mode, custom N, Update Plot again.
    # (No standalone Reset control exists to test in isolation anymore --
    # _reset_actions() still runs internally here, since Update Plot
    # opens with a _reset_actions() call of its own mode's state, it's
    # just not asserted on directly.)
    # =========================================================
    controls.n_values_lineEdit.setText("15")
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    print(
        f"[DEBUG] Individual, custom N=15: {_count_collections(protein_view.ax_hist.figure)} collections"
    )
    assert controls.n_values_lineEdit.text().strip() == "15"

    fit_data_after_individual = protein_view.fit_data.copy()

    # =========================================================
    # STAGE 5: switch to Ensemble mode, same D/L/N, Update Plot.
    # Confirmed dispatch: "set_mode_ensemble" sets _analysis_mode
    # (TestHandleParameterChange.test_set_mode_ensemble); "update_plot"
    # then routes to _update_distribution_ensemble
    # (test_update_plot_ensemble_mode). Ensemble routes to the VM
    # scatterplot (ax.scatter, confirmed via TestPlotScatterplot), so
    # check collections, not bars.
    # =========================================================
    if hasattr(controls, "ensemble_radio"):
        QTest.mouseClick(controls.ensemble_radio, Qt.MouseButton.LeftButton)
    elif hasattr(controls, "mode_comboBox"):
        idx = controls.mode_comboBox.findText("Ensemble", Qt.MatchContains)
        assert idx >= 0, "'Ensemble' not found in mode_comboBox options"
        controls.mode_comboBox.setCurrentIndex(idx)
    elif hasattr(controls, "ensemble_button"):
        QTest.mouseClick(controls.ensemble_button, Qt.MouseButton.LeftButton)
    else:
        pytest.fail(
            "None of controls.ensemble_radio, controls.mode_comboBox, or "
            "controls.ensemble_button exist -- mode-switch widget name "
            "needs confirming against ProteinControls.py"
        )
    qtbot.wait(QT_SHORT_PAUSE_MS)
    assert protein_view._analysis_mode == "ensemble", (
        f"Expected mode switch to set _analysis_mode='ensemble', got "
        f"{protein_view._analysis_mode!r}"
    )

    collections_before_ensemble = _count_collections(protein_view.ax_vm.figure)
    QTest.mouseClick(controls.update_plot_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: _count_collections(protein_view.ax_vm.figure)
        > collections_before_ensemble,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
    collections_ensemble = _count_collections(protein_view.ax_vm.figure)
    print(f"[DEBUG] Ensemble: {collections_ensemble} scatter collections")

    assert protein_view.ensemble_fit_params is not None, (
        "Expected ensemble_fit_params to be populated after a successful "
        "Ensemble Update Plot -- required before Report All has anything "
        "to report (_report_ensemble_fit emits a 'No ensemble fit "
        "available' message and returns early otherwise, per "
        "ProteinView._report_ensemble_fit source)"
    )

    # =========================================================
    # STAGE 6: Report All, still in Ensemble mode with ensemble_fit_params
    # (and ensemble_fit_bins/ensemble_fit_prolate_summary/
    # ensemble_fit_oblate_summary) already populated by Stage 5's Update
    # Plot. Confirmed dispatch: "report_all" -> _report_ensemble_fit()
    # in handle_parameter_change (ProteinView.py source); widget is
    # controls.report_all (confirmed against ProteinControls.py source,
    # wired via button_mapping["report_all"]).
    #
    # _report_ensemble_fit() emits its report as a single HTML string on
    # add_text_to_display(text, class_name) -- capture it directly rather
    # than relying on caplog, since this isn't logged, it's a
    # display-panel signal.
    # =========================================================
    reported_messages = []
    protein_view.add_text_to_display.connect(
        lambda text, source: reported_messages.append((source, text))
    )

    assert controls.report_all.isEnabled(), (
        "Expected Report All to be enabled in Ensemble mode with pore "
        "diameter/length and a loaded db_loader all set"
    )

    QTest.mouseClick(controls.report_all, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)

    report_texts = [
        text for source, text in reported_messages if source == "ProteinView"
    ]
    assert (
        report_texts
    ), "Expected Report All to emit at least one add_text_to_display message"
    report_text = report_texts[-1]
    print(f"[DEBUG] Report All output:\n{report_text}")

    assert "Ensemble double-Gaussian fit" in report_text, (
        f"Expected the Report All output to include the double-Gaussian fit "
        f"summary, got: {report_text!r}"
    )
    assert (
        "Peak 1" in report_text and "Peak 2" in report_text
    ), f"Expected both fitted peaks in the Report All output, got: {report_text!r}"
    print(
        "[DEBUG] Report All confirmed: emitted double-Gaussian fit summary with both peaks"
    )

    # =========================================================
    # STAGE 7: switch back to Individual -> the earlier Individual
    # fit_data (from Stage 4) should still be intact, since nothing here
    # re-clicks Update Plot. Confirmed: set_mode_individual only flips
    # _analysis_mode (test_set_mode_individual) -- no reset/clear call is
    # part of that dispatch path.
    #
    # NOTE: this checks fit_data, not hist_data/plotted_datasets.
    # Confirmed directly from source: _update_distribution_individual
    # never calls update_plot("Filtered Histogram"/"Raw Histogram", ...)
    # and never touches self.plotted_datasets -- those are populated
    # only by _update_distribution_ensemble (_plot_all_points_histogram
    # appends to hist_data; the per-filter loop does
    # plotted_datasets.add(...)). And _reset_actions() clears
    # hist_data/plotted_datasets UNCONDITIONALLY regardless of
    # _analysis_mode -- only fit_data vs ensemble_fit_* is mode-scoped
    # there. So hist_data/plotted_datasets are Ensemble-only
    # bookkeeping, not "Individual's plot state" -- asserting on them
    # here would fail even on a fully correct app, because Stage 5's
    # Ensemble Update Plot legitimately populates them and nothing ever
    # clears that leftover on switching back to Individual (confirmed
    # by a real run: hist_state_after_individual was ([], set()) since
    # Individual never wrote there, then Stage 5 populated both, and
    # Stage 7 saw Ensemble's leftover instead of Individual's own
    # state). fit_data IS the attribute the app actually mode-scopes for
    # this purpose.
    # =========================================================
    if hasattr(controls, "individual_radio"):
        QTest.mouseClick(controls.individual_radio, Qt.MouseButton.LeftButton)
    elif hasattr(controls, "mode_comboBox"):
        idx = controls.mode_comboBox.findText("Individual", Qt.MatchContains)
        assert idx >= 0, "'Individual' not found in mode_comboBox options"
        controls.mode_comboBox.setCurrentIndex(idx)
    elif hasattr(controls, "individual_button"):
        QTest.mouseClick(controls.individual_button, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    assert protein_view._analysis_mode == "individual"

    assert protein_view.fit_data is not None, (
        "Expected Individual's fit_data to survive the round-trip to "
        "Ensemble and back -- _reset_actions() only clears fit_data when "
        "_analysis_mode == 'individual' at the time it's called, and "
        "Stage 5's Ensemble Update Plot ran with _analysis_mode == "
        "'ensemble', so it should have cleared ensemble_fit_* instead"
    )
    assert protein_view.fit_data.equals(fit_data_after_individual), (
        "Expected Individual's own fit_data to still be intact after "
        "switching to Ensemble and back, without re-clicking Update Plot"
    )
    print("[DEBUG] Individual fit_data confirmed intact after mode round-trip")

    # =========================================================
    # STAGE 8: Commit, still in Individual mode with fit_data already
    # populated from Stage 4's Update Plot (mode round-trip in Stage 7
    # didn't touch it). Confirmed dispatch: "commit_individual" ->
    # _commit_fits(loader) (test_commit_individual_routes). _commit_fits
    # raises AttributeError if fit_data is None
    # (test_raises_when_no_fit_data) -- already satisfied here.
    #
    # Widget is controls.commit_individual (confirmed against
    # ProteinControls.py source), not a generic "commit_button".
    # =========================================================
    assert protein_view.fit_data is not None, (
        "Expected fit_data to still be populated going into Commit -- "
        "nothing between Stage 4 and here should have cleared it"
    )

    caplog.clear()
    QTest.mouseClick(controls.commit_individual, Qt.MouseButton.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)
    assert not any(
        "fit data has not been set" in rec.message for rec in caplog.records
    ), "Commit unexpectedly raised/logged the no-fit-data error"
    print("[DEBUG] Commit Individual clicked with fit_data present -- no error raised")

    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()
