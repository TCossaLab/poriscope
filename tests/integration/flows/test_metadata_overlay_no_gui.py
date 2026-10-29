"""
Metadata tab, headless: what one recorded overlay plot draws, refuses and reports.

``MetadataController.overlay_plot`` is the recorded action behind Update Plot. These tests
call it the way a replay does, with the intent a click recorded, against a real Metadata
tab, a real ``SQLiteDBLoader`` and the synthetic database. They assert on what a user can
see - which datasets are on the figure, what was drawn, what the status panel said, what
the history recorded - so they hold whichever layer the loop, its reset-or-add decision
and its bookkeeping live in.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pytest

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.utils.MetaController import declared_actions
from poriscope.utils.MetaSubsetTabModel import FigureKind, OverlayState
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"
FILTERS = {
    "F0": "duration >= 0",
    "F1": "duration >= 1",
    "none": "duration >= 999999999",
    "few": "event_id < 5",
}
ALL_PLOT_TYPES = [
    "Histogram",
    "Normalized Histogram",
    "Categorical Histogram",
    "Kernel Density Plot",
    "Capture Rate",
    "Heatmap",
    "Scatterplot",
    "3D Scatterplot",
    "Raw Event Overlay",
    "Filtered Event Overlay",
    "Raw All Points Histogram",
    "Normalized Raw All Points Histogram",
    "Filtered All Points Histogram",
    "Normalized Filtered All Points Histogram",
]


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, sample_metadata_db: str, monkeypatch) -> Triad:
    """
    A Metadata tab with a real loader over the synthetic database, and a few filters.

    A warning box would block a headless run, so ``QMessageBox.warning`` records its
    calls instead of opening; ``tab.warnings`` holds them.
    """
    triad = build_triad("MetadataController", tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    for name, query in FILTERS.items():
        triad.tab_view.subset_filters[name] = query
        triad.tab_view._subset_controls.filter_comboBox.addItem(name)

    warnings: List[Tuple[Any, ...]] = []
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    said: List[str] = []
    triad.tab_view.add_text_to_display.connect(lambda text, source: said.append(text))
    triad.tab_controller.add_text_to_display.connect(
        lambda text, source: said.append(text)
    )
    triad.warnings = warnings  # type: ignore[attr-defined]
    triad.said = said  # type: ignore[attr-defined]

    yield triad

    triad.close()


def overlay(
    triad: Triad,
    plot_type: str = "Histogram",
    filters: Optional[List[str]] = None,
    channels: Optional[List[str]] = None,
    axes: Optional[List[str]] = None,
    logs: Optional[List[bool]] = None,
    bins: Any = "default",
    sizes: bool = False,
    scope: Optional[Dict[str, List[str]]] = None,
) -> bool:
    """Run the recorded overlay with this intent, as a replay does."""
    names = ["F0"] if filters is None else filters
    return triad.tab_controller.overlay_plot(
        loader=LOADER,
        plot_type=plot_type,
        axes=axes or ["max_deviation", "start_time", "max_blockage"],
        logs=logs or [False, False, False],
        bins=[20] if bins == "default" else bins,
        sizes=sizes,
        filters={name: FILTERS[name] for name in names},
        scope=({"exp_a": channels or ["0"]} if scope is None else scope),
    )


def event_grid(triad: Triad) -> bool:
    """Draw two events of channel 0 in a grid, as a replayed Plot Events does."""
    return triad.tab_controller.plot_events(
        loader=LOADER,
        event_ids=[0, 1],
        experiment="exp_a",
        channel="0",
        subset_name="F0",
        sql_filter=FILTERS["F0"],
        raw=False,
    )


def kept(triad: Triad) -> OverlayState:
    """What the Model keeps of the overlaid figure."""
    return triad.tab_controller.model.overlay


def on_figure(triad: Triad) -> Set[Tuple[Optional[int], str]]:
    """The datasets the figure holds, as (channel, filter name) pairs."""
    return {(entry[2], entry[4]) for entry in kept(triad).datasets}


def history(triad: Triad) -> List[str]:
    return [
        entry["action"] for entry in triad.tab_controller.tab_action_history.values()
    ]


def drawn(triad: Triad) -> int:
    """How many artists the figure's axes carry: lines, bars, images and points."""
    total = 0
    for ax in triad.tab_view.figure.axes:
        total += len(ax.lines) + len(ax.patches) + len(ax.images) + len(ax.collections)
    return total


# ------------------------------------------------------------------ every plot type


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "plot_type", [p for p in ALL_PLOT_TYPES if p != "Capture Rate"]
)
def test_every_plot_type_draws_one_dataset(tab: Triad, plot_type: str) -> None:
    """
    Columns that vary; every event has the same duration in the synthetic data. Capture
    Rate is in the failure test below: the synthetic events are evenly spaced, so every
    inter-event gap is the same and no bin count fits them.
    """
    axes = ["max_deviation", "start_time", "max_blockage"]
    if plot_type == "Categorical Histogram":
        axes = ["event_id", "start_time", "max_blockage"]

    assert overlay(tab, plot_type, axes=axes) is True

    assert on_figure(tab) == {(0, "F0")}
    assert drawn(tab) > 0


# ------------------------------------------------------------------ loop and labels


@pytest.mark.timeout(120)
def test_two_filters_are_two_datasets_on_one_figure(tab: Triad) -> None:
    overlay(tab, filters=["F0", "F1"])

    assert on_figure(tab) == {(0, "F0"), (0, "F1")}
    assert any("rows in subset loader | exp_a Ch 0: F0" in s for s in tab.said)


@pytest.mark.timeout(120)
def test_two_channels_are_two_datasets(tab: Triad) -> None:
    overlay(tab, channels=["0", "1"])

    assert on_figure(tab) == {(0, "F0"), (1, "F0")}


@pytest.mark.timeout(120)
def test_no_filter_means_the_full_dataset(tab: Triad) -> None:
    overlay(tab, filters=[])

    assert on_figure(tab) == {(0, "Full Dataset")}


@pytest.mark.timeout(120)
def test_no_scope_is_refused_by_the_loader_and_draws_nothing(tab: Triad) -> None:
    """
    An empty scope becomes one dataset with no experiment, which the loader cannot
    query. The panel fills the scope when a loader is chosen, so a click never sends one.
    """
    assert overlay(tab, scope={}) is False

    assert on_figure(tab) == set()
    assert any("Could not build the query for this subset" in s for s in tab.said)


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "plot_type, message",
    [
        ("Kernel Density Plot", "Unable to estimate the density"),
        ("Capture Rate", "Unable to fit the capture rate"),
    ],
)
def test_a_dataset_whose_computation_fails_is_not_counted_as_drawn(
    tab: Triad, plot_type: str, message: str
) -> None:
    """
    Every event has the same duration, so its density cannot be estimated, and the
    events are evenly spaced, so the capture rate has nothing to fit. That is said, and
    the dataset is not recorded as on the figure, or plotting it again would be skipped
    as already plotted.
    """
    axes = ["duration", "start_time", "max_deviation"]

    assert overlay(tab, plot_type, axes=axes, bins=None) is False

    assert on_figure(tab) == set()
    assert kept(tab).values == []
    assert any(message in s for s in tab.said)


@pytest.mark.timeout(120)
def test_a_subset_with_no_rows_is_said_and_skipped(tab: Triad) -> None:
    assert overlay(tab, filters=["none", "F0"]) is True

    assert on_figure(tab) == {(0, "F0")}
    assert any("No data matching the subset" in s for s in tab.said)


@pytest.mark.timeout(120)
def test_only_an_empty_subset_draws_nothing(tab: Triad) -> None:
    assert overlay(tab, filters=["none"]) is False

    assert on_figure(tab) == set()


@pytest.mark.timeout(120)
def test_a_dataset_already_on_the_figure_is_skipped(tab: Triad) -> None:
    overlay(tab)
    before = drawn(tab)

    assert overlay(tab) is False

    assert on_figure(tab) == {(0, "F0")}
    assert drawn(tab) == before


# ------------------------------------------------------------------ reset or add


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "change",
    [
        {"axes": ["start_time", "max_deviation", "max_blockage"]},
        {"logs": [True, False, False]},
        {"plot_type": "Kernel Density Plot"},
        {"bins": [7]},
        {"bins": [0.5], "sizes": True},
    ],
    ids=["column", "log flag", "plot type", "bins", "sizes"],
)
def test_a_changed_option_starts_a_new_figure(
    tab: Triad, change: Dict[str, Any]
) -> None:
    overlay(tab, filters=["F0"])

    overlay(tab, filters=["F1"], **change)

    assert on_figure(tab) == {(0, "F1")}
    assert history(tab)[-2:] == ["reset", "overlay_plot"]


@pytest.mark.timeout(120)
def test_an_overlay_on_an_event_grid_starts_a_new_figure(tab: Triad) -> None:
    """The grid Plot Events draws is reset first, and the reset is recorded."""
    overlay(tab, filters=["F0"])
    assert event_grid(tab)

    overlay(tab, filters=["F1"])

    assert on_figure(tab) == {(0, "F1")}
    assert history(tab)[-2:] == ["reset", "overlay_plot"]
    assert len(tab.tab_view.figure.axes) == 1


@pytest.mark.timeout(120)
def test_an_all_points_histogram_on_an_event_grid_starts_a_new_figure(
    tab: Triad,
) -> None:
    """The grid Plot Events draws is reset first, and the reset is recorded."""
    overlay(tab, "Raw All Points Histogram", filters=["F0"])
    assert event_grid(tab)

    overlay(tab, "Raw All Points Histogram", filters=["F1"])

    assert on_figure(tab) == {(0, "F1")}
    assert history(tab)[-2:] == ["reset", "overlay_plot"]
    assert len(tab.tab_view.figure.axes) == 1


@pytest.mark.timeout(120)
def test_the_decision_reads_what_the_model_keeps(tab: Triad) -> None:
    """The figure is untouched; only the Model says another plot type is up."""
    overlay(tab, filters=["F0"])
    kept(tab).plot_type = "Scatterplot"

    overlay(tab, filters=["F1"])

    assert on_figure(tab) == {(0, "F1")}


@pytest.mark.timeout(120)
def test_an_all_points_bins_change_starts_a_new_figure(tab: Triad) -> None:
    overlay(tab, "Raw All Points Histogram", filters=["F0"])

    overlay(tab, "Raw All Points Histogram", filters=["F1"], bins=[7])

    assert on_figure(tab) == {(0, "F1")}


@pytest.mark.timeout(120)
def test_a_bins_change_does_not_reset_a_plot_that_ignores_bins(tab: Triad) -> None:
    overlay(tab, "Scatterplot", filters=["F0"])

    overlay(tab, "Scatterplot", filters=["F1"], bins=[7])

    assert on_figure(tab) == {(0, "F0"), (0, "F1")}


@pytest.mark.timeout(120)
def test_an_event_overlay_after_another_plot_type_starts_a_new_figure(
    tab: Triad,
) -> None:
    overlay(tab, "Raw All Points Histogram")

    overlay(tab, "Raw Event Overlay", filters=["F1"])

    assert on_figure(tab) == {(0, "F1")}


@pytest.mark.timeout(120)
def test_a_second_event_overlay_of_the_same_type_adds_to_the_figure(
    tab: Triad,
) -> None:
    overlay(tab, "Raw Event Overlay", filters=["F0"])
    resets = history(tab).count("reset")

    overlay(tab, "Raw Event Overlay", filters=["F1"])

    assert on_figure(tab) == {(0, "F0"), (0, "F1")}
    assert history(tab).count("reset") == resets


# ------------------------------------------------------------------ a new figure starts with a reset


@pytest.mark.timeout(120)
def test_a_new_tab_s_figure_is_what_the_model_says_it_is(tab: Triad) -> None:
    """An empty 2-D figure with its axes ready, before anything is plotted."""
    assert kept(tab).figure is FigureKind.EMPTY_2D
    assert tab.tab_view.figure.axes == [tab.tab_view.axes]
    assert tab.tab_view.axes.name == "rectilinear"


#: Columns each plot type can draw from the synthetic data.
FIRST_FIGURE_AXES = {
    "Histogram": ["max_deviation", "start_time", "max_blockage"],
    "Scatterplot": ["max_deviation", "start_time", "max_blockage"],
    "Categorical Histogram": ["event_id", "start_time", "max_blockage"],
    "Raw Event Overlay": ["max_deviation", "start_time", "max_blockage"],
}


def reset_by_click(triad: Triad) -> None:
    triad.tab_view.handle_parameter_change("metadatacontrols", "reset_plot", ({},))


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", list(FIRST_FIGURE_AXES))
def test_the_first_dataset_on_a_new_figure_records_a_reset(
    tab: Triad, plot_type: str
) -> None:
    overlay(tab, plot_type, axes=FIRST_FIGURE_AXES[plot_type])

    assert history(tab) == ["reset", "overlay_plot"]


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", list(FIRST_FIGURE_AXES))
def test_undo_after_two_overlays_keeps_the_first(tab: Triad, plot_type: str) -> None:
    """Undo replays from the last reset, so the second dataset goes and the first stays."""
    axes = FIRST_FIGURE_AXES[plot_type]
    overlay(tab, plot_type, filters=["F0"], axes=axes)
    overlay(tab, plot_type, filters=["F1"], axes=axes)

    tab.tab_controller.update_tab_actions(None, True)

    assert on_figure(tab) == {(0, "F0")}
    assert history(tab) == ["reset", "overlay_plot"]


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", ["Histogram", "Scatterplot"])
def test_a_reset_followed_by_an_overlay_records_one_reset(
    tab: Triad, plot_type: str
) -> None:
    overlay(tab, plot_type, filters=["F0"])
    reset_by_click(tab)

    overlay(tab, plot_type, filters=["F1"])

    assert history(tab) == ["reset", "overlay_plot", "reset", "overlay_plot"]
    assert on_figure(tab) == {(0, "F1")}


@pytest.mark.timeout(120)
def test_a_3d_plot_after_a_reset_still_gets_three_dimensional_axes(tab: Triad) -> None:
    """The reset a click made was 2-D, so the 3-D plot records one of its own."""
    reset_by_click(tab)

    assert overlay(tab, "3D Scatterplot") is True

    assert history(tab) == ["reset", "reset", "overlay_plot"]
    assert kept(tab).figure is FigureKind.OVERLAY_3D


@pytest.mark.timeout(120)
def test_a_refused_click_on_a_new_figure_leaves_no_record(tab: Triad) -> None:
    """Nothing was drawn and the figure is as it was, so neither the reset nor the plot stays."""
    tab.tab_controller.request_overlay_plot(
        LOADER,
        "Scatterplot",
        ["max_deviation", "start_time", "max_blockage"],
        [False, False, False],
        [20],
        False,
        {"none": FILTERS["none"]},
        {"exp_a": ["0"]},
    )

    assert history(tab) == []


# ------------------------------------------------------------------ what is kept, and where


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "plot_type", ["Histogram", "Kernel Density Plot", "Raw All Points Histogram"]
)
def test_two_overlays_accumulate_in_the_model_and_the_view_keeps_none(
    tab: Triad, plot_type: str
) -> None:
    axes = ["max_deviation", "start_time", "max_blockage"]
    overlay(tab, plot_type, filters=["F0"], axes=axes)
    overlay(tab, plot_type, filters=["F1"], axes=axes)

    assert len(kept(tab).values) == 2
    assert len(kept(tab).labels) == 2
    assert kept(tab).hist_min is not None and kept(tab).hist_max is not None
    for name in (
        "hist_data",
        "hist_labels",
        "hist_min",
        "hist_max",
        "plotted_datasets",
        "allowed_plot_type",
        "allowed_columns",
        "allowed_logs",
        "allowed_bins",
        "allowed_sizes",
    ):
        assert not hasattr(tab.tab_view, name), name


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "plot_type, kind",
    [
        ("Histogram", FigureKind.OVERLAY_2D),
        ("3D Scatterplot", FigureKind.OVERLAY_3D),
        ("Raw All Points Histogram", FigureKind.OVERLAY_2D),
        ("Raw Event Overlay", FigureKind.OVERLAY_2D),
    ],
)
def test_the_model_records_the_figure_kind(
    tab: Triad, plot_type: str, kind: FigureKind
) -> None:
    assert kept(tab).figure is FigureKind.EMPTY_2D

    overlay(tab, plot_type)

    assert kept(tab).figure is kind


@pytest.mark.timeout(120)
def test_reset_is_recorded_on_the_controller_and_empties_what_is_kept(
    tab: Triad,
) -> None:
    overlay(tab, "3D Scatterplot")

    tab.tab_view.handle_parameter_change("metadatacontrols", "reset_plot", ({},))

    assert history(tab)[-1] == "reset"
    assert kept(tab) == OverlayState()
    assert len(tab.tab_view.figure.axes) == 1
    assert "reset" in {name for _, name in declared_actions(MetadataController)}
    assert "reset" not in {name for _, name in declared_actions(MetadataView)}


# ------------------------------------------------------------------ refusals


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", ["Heatmap", "Raw Event Overlay"])
def test_a_single_dataset_type_refuses_two_filters(tab: Triad, plot_type: str) -> None:
    assert overlay(tab, plot_type, filters=["F0", "F1"]) is False

    assert on_figure(tab) == set()
    assert any("Only a single subset" in s for s in tab.said)


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", ["Heatmap", "Filtered Event Overlay"])
def test_a_single_dataset_type_refuses_two_channels(tab: Triad, plot_type: str) -> None:
    assert overlay(tab, plot_type, channels=["0", "1"]) is False

    assert any("Only a single channel" in s for s in tab.said)


@pytest.mark.timeout(120)
def test_a_single_dataset_type_refuses_two_experiments(tab: Triad) -> None:
    assert overlay(tab, "Heatmap", scope={"exp_a": ["0"], "exp_b": ["0"]}) is False

    assert any("Only a single experiment" in s for s in tab.said)


@pytest.mark.timeout(120)
def test_an_unsupported_plot_type_is_refused(tab: Triad) -> None:
    assert overlay(tab, "Pie Chart") is False

    assert any("Unsupported Plot Type" in s for s in tab.said)


@pytest.mark.timeout(120)
def test_the_same_column_twice_is_refused_before_the_figure_is_touched(
    tab: Triad,
) -> None:
    """Said on the status panel, with no dialog, and the figure keeps what it had."""
    overlay(tab, "Histogram", filters=["F0"])

    refused = overlay(
        tab,
        "Scatterplot",
        filters=["F1"],
        axes=["duration", "duration", "max_deviation"],
    )

    assert refused is False
    assert on_figure(tab) == {(0, "F0")}
    assert tab.warnings == []  # type: ignore[attr-defined]
    assert any("All columns should be different" in s for s in tab.said)


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "plot_type", ["Histogram", "Kernel Density Plot", "Capture Rate"]
)
def test_an_empty_bins_entry_is_reported_and_draws_nothing(
    tab: Triad, plot_type: str
) -> None:
    """Typing only "," in Bins passes the panel's check and arrives as an empty list."""
    assert overlay(tab, plot_type, bins=[]) is False

    assert on_figure(tab) == set()
    assert any("Invalid bins entry" in s for s in tab.said)


# ------------------------------------------------------------------ categorical, from a click


@pytest.mark.timeout(120)
def test_a_click_for_a_categorical_histogram_of_a_real_column_is_refused_unrecorded(
    tab: Triad,
) -> None:
    before = history(tab)

    tab.tab_controller.request_overlay_plot(
        LOADER,
        "Categorical Histogram",
        ["duration", "duration", "duration"],
        [False, False, False],
        None,
        False,
        {"F0": FILTERS["F0"]},
        {"exp_a": ["0"]},
    )

    assert history(tab) == before
    assert on_figure(tab) == set()
    assert any("Categorical histograms can only be plotted" in s for s in tab.said)


@pytest.mark.timeout(120)
def test_a_click_for_a_categorical_histogram_of_an_integer_column_plots(
    tab: Triad,
) -> None:
    tab.tab_controller.request_overlay_plot(
        LOADER,
        "Categorical Histogram",
        ["event_id", "event_id", "event_id"],
        [False, False, False],
        None,
        False,
        {"F0": FILTERS["F0"]},
        {"exp_a": ["0"]},
    )

    assert on_figure(tab) == {(0, "F0")}
    assert history(tab)[-1] == "overlay_plot"


# ------------------------------------------------------------------ labels


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "plot_type, x_label, y_label",
    [
        ("Kernel Density Plot", "log10(max_deviation (pA))", "Probability Density"),
        ("Scatterplot", "log10(max_deviation (pA))", "start_time (s)"),
        ("Heatmap", "log10(max_deviation (pA))", "start_time (s)"),
        ("Normalized Raw All Points Histogram", "Current (pA)", "Normalized Count"),
    ],
)
def test_the_axis_labels_carry_units_and_the_log_scale(
    tab: Triad, plot_type: str, x_label: str, y_label: str
) -> None:
    overlay(tab, plot_type, logs=[True, False, False])

    ax = tab.tab_view.axes
    assert ax.get_xlabel() == x_label
    assert ax.get_ylabel() == y_label


# ------------------------------------------------------------------ what is exported


@pytest.mark.timeout(120)
def test_a_normalised_all_points_histogram_exports_what_it_draws(tab: Triad) -> None:
    overlay(tab, "Normalized Raw All Points Histogram")

    line = tab.tab_view.axes.get_lines()[0]
    exported = tab.tab_view.data_cache[1]
    np.testing.assert_allclose(np.asarray(exported), line.get_ydata())
    assert np.max(line.get_ydata()) == pytest.approx(1.0)


# ------------------------------------------------------------------ the requests are gone


@pytest.mark.parametrize(
    "signal",
    [
        "metadata_subset_requested",
        "column_type_requested",
        "histogram_bins_requested",
        "density_requested",
        "categorical_counts_requested",
        "heatmap_requested",
        "capture_rate_requested",
        "scatterplot_3d_requested",
        "all_points_histogram_requested",
        "event_overlay_requested",
    ],
)
def test_the_view_no_longer_asks_the_controller_for_each_dataset(signal: str) -> None:
    """The Controller runs the loop, so it calls the Model and the View directly."""
    assert not hasattr(MetadataView, signal)


def click(triad: Triad, plot_type: str, axes: List[str], filters: List[str]) -> None:
    """Press Update Plot with this intent, as the panel's click does."""
    triad.tab_controller.request_overlay_plot(
        LOADER,
        plot_type,
        axes,
        [False, False, False],
        [20],
        False,
        {name: FILTERS[name] for name in filters},
        {"exp_a": ["0"]},
    )


@pytest.mark.timeout(120)
@pytest.mark.parametrize("second", ["Heatmap", "Scatterplot", "Kernel Density Plot"])
def test_undo_after_another_plot_type_brings_the_first_back(
    tab: Triad, second: str
) -> None:
    axes = ["max_deviation", "start_time", "max_blockage"]
    click(tab, "Histogram", axes, ["F0"])
    click(tab, second, axes, ["F0"])

    tab.tab_controller.update_tab_actions(None, True)

    assert kept(tab).plot_type == "Histogram"
    assert on_figure(tab) == {(0, "F0")}
    assert drawn(tab) > 0
    assert history(tab) == ["reset", "overlay_plot"]


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", ["Histogram", "Heatmap", "Scatterplot"])
def test_undo_of_the_only_plot_clears_the_figure(tab: Triad, plot_type: str) -> None:
    click(tab, plot_type, ["max_deviation", "start_time", "max_blockage"], ["F0"])

    tab.tab_controller.update_tab_actions(None, True)

    assert on_figure(tab) == set()
    assert drawn(tab) == 0


# ------------------------------------------------------------------ what Export Plot Data holds

#: Columns each dataset adds to the export, per plot type that caches one. The event
#: overlays are not cached (too much data), and Capture Rate has nothing to fit in the
#: synthetic data, so it is drawn in no test here.
EXPORTED_COLUMNS = {
    "Histogram": 2,
    "Normalized Histogram": 2,
    "Kernel Density Plot": 2,
    "Categorical Histogram": 2,
    "Scatterplot": 2,
    "3D Scatterplot": 3,
    "Heatmap": 3,
    "Raw All Points Histogram": 2,
    "Normalized Raw All Points Histogram": 2,
    "Filtered All Points Histogram": 2,
    "Normalized Filtered All Points Histogram": 2,
}


@pytest.mark.timeout(120)
@pytest.mark.parametrize("plot_type", list(EXPORTED_COLUMNS))
def test_the_export_holds_every_dataset_on_the_figure(
    tab: Triad, plot_type: str
) -> None:
    """
    The export is what Export Plot Data writes: one set of columns per dataset drawn,
    two filters where the plot type overlays them, so a dataset added later is not lost
    from it.
    """
    axes = ["max_deviation", "start_time", "max_blockage"]
    if plot_type == "Categorical Histogram":
        axes = ["event_id", "start_time", "max_blockage"]
    names = ["F0"] if plot_type == "Heatmap" else ["F0", "few"]

    assert overlay(tab, plot_type, filters=names, axes=axes) is True

    model = tab.tab_controller.model
    assert on_figure(tab) == {(0, name) for name in names}
    assert len(model.cache_data) == EXPORTED_COLUMNS[plot_type] * len(names)
    assert len(model.cache_labels) == len(model.cache_data)
    assert all(len(column) > 0 for column in model.cache_data)


@pytest.mark.timeout(120)
def test_an_exported_histogram_counts_each_filters_own_rows(tab: Triad) -> None:
    """Each filter's exported counts add up to the rows that filter selected."""
    overlay(tab, "Histogram", filters=["F0", "few"])

    counts = tab.tab_controller.model.cache_data[1::2]
    rows = [len(values) for values in kept(tab).values]
    assert [int(np.sum(c)) for c in counts] == rows
    assert rows[0] > rows[1] == 5
