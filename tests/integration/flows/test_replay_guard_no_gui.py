"""
A replayed action reproduces what the user's own action produced, whatever the panel holds now.

For each tab and each declared action: run the action as the user does, in tab A, and capture what
it produced. Then build a second tab B that is not the one the user acted in (the Load Session
case), change everything B's widgets and stored inputs hold, replay A's recorded history into it
and capture again. The captures must be equal. Four things are compared:

* the calls that reached the data plugins (``MetaModel.call``), with their arguments;
* the plot cache the export reads;
* what each figure holds;
* the tab's bookkeeping: what it believes is plotted and the fits it holds.

Replay runs under the tripwire (``poriscope.utils.ReplayGuard``), so an action that reached a
helper that reads a controls panel fails here as an error, not as a quiet difference.

Every declared action must be covered: a test lists the actions each tab declares and fails for
one no scenario records, so an action added without a fixture cannot land.
"""

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import (
    Triad,
    build_clustering_tab,
    build_event_analysis_tab,
    build_rawdata_tab,
    build_triad,
    hdbscan_config,
)

LOADER = "loader"
READER = "reader"
FINDER = "finder"
EVENTS = "events"
FITTER = "fitter"
FILTERS = {
    "F0": "duration >= 0",
    "F1": "duration >= 1",
    "F2": "duration >= 2",
    "F3": "duration >= 3",
}
TABS = [
    "RawDataController",
    "EventAnalysisController",
    "ClusteringController",
    "MetadataController",
    "ProteinController",
]

#: What a tab believes about its own plot, which a replay must rebuild.
BOOKKEEPING = (
    "plotted_datasets",
    "allowed_plot_type",
    "allowed_columns",
    "allowed_logs",
    "allowed_bins",
    "allowed_sizes",
    "ensemble_fit_params",
    "ensemble_fit_bins",
    "ensemble_fit_sizes",
)


# ---------------------------------------------------------------- capturing


def normalise(value: Any) -> Any:
    """
    Turn anything a tab holds into something two captures can be compared on.

    :param value: an argument, a cached array, a frame, a set, a dict, a number
    :type value: Any
    :return: a plain structure of lists, dicts, strings and numbers
    :rtype: Any
    """
    if isinstance(value, np.ndarray):
        return ["array", list(value.shape), value.tolist()]
    if isinstance(value, pd.DataFrame):
        return [
            "frame",
            {str(k): normalise(v) for k, v in value.to_dict("list").items()},
        ]
    if isinstance(value, dict):
        return {str(k): normalise(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((normalise(v) for v in value), key=repr)
    if isinstance(value, (list, tuple)):
        return [normalise(v) for v in value]
    if callable(value):
        return f"<callable {getattr(value, '__name__', type(value).__name__)}>"
    return value


def figure_summary(figure: Any) -> List[Any]:
    """
    Summarise what a figure holds, axis by axis.

    :param figure: a matplotlib figure
    :type figure: Any
    :return: one entry per axes: counts of what is drawn, and its labels
    :rtype: List[Any]
    """
    return [
        [
            len(ax.lines),
            len(ax.collections),
            len(ax.patches),
            len(ax.texts),
            ax.get_xlabel(),
            ax.get_ylabel(),
            ax.get_title(),
        ]
        for ax in figure.axes
    ]


def figures_of(view: Any) -> Dict[str, Any]:
    """
    The figures a tab draws on, every one of them: Protein keeps one per mode.

    :param view: the tab's View
    :type view: Any
    :return: figure name to figure
    :rtype: Dict[str, Any]
    """
    names = [
        "figure",
        "fig_hist_individual",
        "fig_hist_ensemble",
        "fig_vm_individual",
        "fig_vm_ensemble",
    ]
    return {name: getattr(view, name) for name in names if hasattr(view, name)}


class Spy:
    """Record every call the tab's Model makes to a data plugin, from now on."""

    def __init__(self, triad: Triad) -> None:
        self.calls: List[Any] = []
        model = triad.tab_controller.model
        original = model.call

        def spy(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(normalise((args, kwargs)))
            return original(*args, **kwargs)

        model.call = spy  # type: ignore[method-assign]


def capture(
    triad: Triad,
    spy: Spy,
    extra: Tuple[str, ...] = (),
    click_only_calls: Tuple[str, ...] = (),
    probe: Callable[[Triad], Any] = lambda triad: None,
) -> Dict[str, Any]:
    """
    Capture the four things a replay must reproduce.

    :param triad: the tab
    :type triad: Triad
    :param spy: the recording of the plugin calls made while the action or replay ran
    :type spy: Spy
    :param extra: attributes this tab keeps that the shared list does not name
    :type extra: Tuple[str, ...]
    :param click_only_calls: plugin methods the click path asks before it launches an action,
        which a replay of the recorded method does not repeat
    :type click_only_calls: Tuple[str, ...]
    :param probe: reads state back out of the data plugins after the action or replay
    :type probe: Callable[[Triad], Any]
    :return: the capture
    :rtype: Dict[str, Any]
    """
    view, model = triad.tab_view, triad.tab_controller.model
    return {
        "plugin_calls": [
            call for call in spy.calls if call[0][2] not in click_only_calls
        ],
        "probe": probe(triad),
        "plot_cache": normalise((model.cache_data, model.cache_labels)),
        "figures": {
            name: figure_summary(fig) for name, fig in figures_of(view).items()
        },
        "bookkeeping": {
            name: normalise(getattr(view, name, None)) for name in BOOKKEEPING + extra
        },
        # What the Model keeps of an overlaid figure, where a tab keeps it there.
        "overlay": (
            normalise(vars(model.overlay)) if hasattr(model, "overlay") else None
        ),
    }


# ---------------------------------------------------------------- building tabs


def _with_loader(
    triad: Triad, db: str, controls: str, filters: Dict[str, str]
) -> Triad:
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name, text in filters.items():
        view.subset_filters[name] = text
        combo.addItem(name)
    view.handle_parameter_change(controls, "loader_changed", ({"db_loader": LOADER},))
    return triad


def metadata_tab(tmp_path: Path, db: str) -> Triad:
    return _with_loader(
        build_triad("MetadataController", tmp_path), db, "metadatacontrols", FILTERS
    )


def protein_tab(tmp_path: Path, db: str) -> Triad:
    return _with_loader(
        build_triad("ProteinController", tmp_path), db, "proteincontrols", FILTERS
    )


def clustering_tab(tmp_path: Path, db: str) -> Triad:
    """A Clustering tab with a database loader over the synthetic metadata database."""
    return build_clustering_tab(tmp_path, db, LOADER)


def eventanalysis_tab(tmp_path: Path, events_db: str) -> Triad:
    """An Event Analysis tab with a loader and a fitter over a synthetic events database."""
    return build_event_analysis_tab(tmp_path, events_db, EVENTS, FITTER)


def rawdata_tab(tmp_path: Path, chimera: Dict[str, str]) -> Triad:
    """A RawData tab with a reader over the synthetic recording and a finder on it."""
    return build_rawdata_tab(tmp_path, chimera, READER, FINDER)


def select(triad: Triad, filter_name: str, channel: str) -> None:
    """Select one filter and one channel, as a user would."""
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    combo.selectItem(filter_name, select=True)
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": [channel]}


# ---------------------------------------------------------------- the user's actions


def metadata_act(triad: Triad, qtbot: Any) -> None:
    """Two overlays, a reset, then a plot: the Metadata recorded actions."""
    view = triad.tab_view
    histogram = {
        "db_loader": LOADER,
        "plot_type": "Histogram",
        "x_axis": "duration",
        "y_axis": "duration",
        "z_axis": "duration",
        "x_log": False,
        "y_log": False,
        "z_log": False,
        "bins": [20],
        "sizes": False,
    }
    select(triad, "F0", "0")
    view.handle_parameter_change("metadatacontrols", "update_plot", (dict(histogram),))
    select(triad, "F1", "0")
    view.handle_parameter_change("metadatacontrols", "update_plot", (dict(histogram),))
    view.handle_parameter_change("metadatacontrols", "reset_plot", ({},))
    select(triad, "F2", "0")
    view.handle_parameter_change("metadatacontrols", "update_plot", (dict(histogram),))


def metadata_perturb(triad: Triad) -> None:
    """Change what the panel and the stored inputs hold, everything a click would read."""
    view = triad.tab_view
    select(triad, "F3", "1")
    controls = view.metadatacontrols
    for line_edit, text in (
        (controls.bins_lineEdit, "7"),
        (controls.event_id_lineEdit, "5"),
        (controls.n_events_lineEdit, "3"),
    ):
        line_edit.setText(text)
    for combo in (controls.plot_type_comboBox, controls.x_axis_comboBox):
        combo.setCurrentIndex(combo.count() - 1)
    view.subset_filters["F0"] = "duration >= 999"


def metadata_events_act(triad: Triad, qtbot: Any) -> None:
    """Plot Events on an empty figure, then the forward arrow, as the panel sends them."""
    view = triad.tab_view
    select(triad, "F0", "0")
    view.handle_parameter_change(
        "metadatacontrols",
        "plot_events",
        ({"db_loader": LOADER, "event_id": 0, "n_events": 3, "raw": False},),
    )
    typed = int(view.metadatacontrols.event_id_lineEdit.text())
    view.handle_parameter_change(
        "metadatacontrols",
        "shift_range_forward",
        ({"db_loader": LOADER, "event_id": typed, "n_events": 3, "raw": False},),
    )


def protein_act(triad: Triad, qtbot: Any) -> None:
    """An Ensemble plot, which records its reset and the plot."""
    view = triad.tab_view
    select(triad, "F0", "0")
    view.handle_parameter_change("proteincontrols", "set_mode_ensemble", ({},))
    view.handle_parameter_change(
        "proteincontrols",
        "update_plot",
        (
            {
                "db_loader": LOADER,
                "plot_type": "Filtered Histogram",
                "pore_diameter": 10.0,
                "pore_length": 10.0,
                "n_values": 20,
                "bins": [20],
                "sizes": False,
            },
        ),
    )


def protein_individual_act(triad: Triad, qtbot: Any) -> None:
    """An Individual plot, which records its reset and the plot."""
    view = triad.tab_view
    select(triad, "F0", "0")
    view.handle_parameter_change("proteincontrols", "set_mode_individual", ({},))
    view.handle_parameter_change(
        "proteincontrols",
        "update_plot",
        (
            {
                "db_loader": LOADER,
                "plot_type": "Filtered Histogram",
                "pore_diameter": 10.0,
                "pore_length": 10.0,
                "n_values": 20,
                "bins": [20],
                "sizes": False,
            },
        ),
    )


def individual_fit(triad: Triad) -> Any:
    """The Individual fit the Model keeps, which Commit Individual writes."""
    return normalise(triad.tab_controller.model.individual_fit)


def protein_seed(triad: Triad) -> None:
    """Give the tab an Individual fit that no recorded action made, so a replay can be seen to leave it."""
    triad.tab_controller.model.set_individual_fit(pd.DataFrame({"id": [-1]}))


def protein_perturb(triad: Triad) -> None:
    view = triad.tab_view
    select(triad, "F3", "1")
    controls = view.proteincontrols
    for line_edit, text in (
        (controls.pore_diameter_lineEdit, "99"),
        (controls.pore_length_lineEdit, "98"),
        (controls.bins_lineEdit, "7"),
        (controls.n_values_lineEdit, "5"),
        (controls.event_id_lineEdit, "4"),
    ):
        line_edit.setText(text)
    view.subset_filters["F0"] = "duration >= 999"


def rawdata_act(triad: Triad, qtbot: Any) -> None:
    """Update Trace, Update PSD, Find Events, then Plot Events, as the panel sends them."""
    view = triad.tab_view
    panel = {
        "reader": READER,
        "filter": "No Filter",
        "channel": [str(triad.channel)],  # type: ignore[attr-defined]
        "start_time": 0.0,
        "length": 0.01,
    }
    view.handle_parameter_change(
        "rawdatacontrols", "load_data_and_update_plot", (dict(panel),)
    )
    view.handle_parameter_change(
        "rawdatacontrols", "load_data_and_update_psd", (dict(panel),)
    )
    channel = triad.channel  # type: ignore[attr-defined]
    view.analysis_time_limits[FINDER] = {channel: {"start": 0.0, "end": 0.0}}
    view.handle_parameter_change(
        "rawdatacontrols",
        "find_events",
        ({"eventfinder": FINDER, "filter": "No Filter", "channel": [str(channel)]},),
    )
    settle(triad, qtbot)
    view.handle_parameter_change(
        "rawdatacontrols",
        "plot_events",
        (
            {
                "eventfinder": FINDER,
                "filter": "No Filter",
                "channel": [str(channel)],
                "event_index": [0, 1],
            },
        ),
    )


def rawdata_perturb(triad: Triad) -> None:
    """Change the range the panel holds and the channels it has selected."""
    controls = triad.tab_view.rawdatacontrols
    controls.set_range_inputs(1.0, 0.5)
    controls.channel_comboBox.selectAllToggle(False)
    triad.tab_view.analysis_time_limits[FINDER] = {
        triad.channel: {"start": 0.5, "end": 1.0}  # type: ignore[attr-defined]
    }


def eventanalysis_act(triad: Triad, qtbot: Any) -> None:
    """Fit channel 0, wait for the fitter, then plot three events with their fits, as the panel sends them."""
    view = triad.tab_view
    view.handle_parameter_change(
        "eventAnalysisControls",
        "fit_events",
        (
            {
                "loader": EVENTS,
                "eventfitter": FITTER,
                "filter": "No Filter",
                "channel": ["0"],
            },
        ),
    )
    settle(triad, qtbot)
    view.handle_parameter_change(
        "eventAnalysisControls",
        "plot_events",
        (
            {
                "loader": EVENTS,
                "eventfitter": FITTER,
                "filter": "No Filter",
                "channel": ["0"],
                "event_index": [0, 1, 2],
                "raw": False,
            },
        ),
    )


def eventanalysis_perturb(triad: Triad) -> None:
    """Change the fitter, the raw checkbox, the channel selection and the event index the panel holds."""
    controls = triad.tab_view.eventAnalysisControls
    # One fitter is registered, so another option is added the way a second fitter would appear.
    controls.eventfitters_comboBox.addItem("another fitter")
    controls.set_eventfitter("another fitter")
    controls.set_raw(True)
    controls.set_channels([])
    controls.set_event_index_input("7-9")


def fitted_events(triad: Triad) -> Any:
    """What the fitter holds for channel 0, read back from the plugin."""
    model = triad.tab_controller.model
    return {
        "fitted": model.call("MetaEventFitter", FITTER, "get_eventfitting_status", 0),
        "report": model.call("MetaEventFitter", FITTER, "report_status", 0),
    }


def clustering_act(triad: Triad, qtbot: Any) -> None:
    """Run a clustering as the panel does once the settings dialog is accepted, then merge label 1 into 0."""
    view = triad.tab_view
    view._load_metadata_and_request_clustering(hdbscan_config(), LOADER)
    view.handle_parameter_change(
        "clusteringcontrols",
        "merge_clusters",
        ({"db_loader": LOADER, "label_x": "0", "label_y": "1"},),
    )


def clustering_perturb(triad: Triad) -> None:
    """Change the loader the panel shows and the settings stored for the next dialog."""
    view = triad.tab_view
    view.clusteringcontrols.db_loader_comboBox.addItem("another database")
    view.clusteringcontrols.set_db_loader("another database")
    other = hdbscan_config(("duration",))
    other["method_params"]["HDBSCAN_Cluster_Size_input"] = 50
    view.clustering_config_map = {LOADER: other}


def cluster_labels(triad: Triad) -> Any:
    """How many rows each cluster label holds, read from the result the Model keeps."""
    result = triad.tab_controller.model.result
    if result is None:
        return None
    _clustered, labels, _confidence = result
    counts: Dict[str, int] = {}
    for label in labels:
        counts[str(label)] = counts.get(str(label), 0) + 1
    return counts


def settle(triad: Triad, qtbot: Any) -> None:
    """Wait until no background run of this tab is left."""
    model = triad.tab_controller.model
    qtbot.waitUntil(
        lambda: not any(model.workers.get(key) for key in list(model.workers)),
        timeout=120_000,
    )


def found_events(triad: Triad) -> Any:
    """What the finder holds for the channel, read back from the plugin."""
    channel = triad.channel  # type: ignore[attr-defined]
    model = triad.tab_controller.model
    return {
        "events": model.call(
            "MetaEventFinder", FINDER, "get_num_events_found", channel
        ),
        "finished": model.call(
            "MetaEventFinder", FINDER, "get_eventfinding_status", channel
        ),
    }


def nothing(triad: Triad) -> None:
    return None


@dataclass
class Scenario:
    tab: str
    covers: Tuple[str, ...]
    build: Callable[[Path, Any], Triad]
    act: Callable[[Triad, Any], None]
    perturb: Callable[[Triad], None]
    seed: Callable[[Triad], None] = nothing
    #: the pytest fixture that supplies the data the tab is built over
    needs: str = "sample_metadata_db"
    #: attributes this tab keeps that the shared bookkeeping list does not name
    extra: Tuple[str, ...] = ()
    #: plugin methods the click path asks that a replay of the recorded method does not
    click_only_calls: Tuple[str, ...] = ()
    #: reads state back out of the data plugins, so a background run's outcome is compared
    probe: Callable[[Triad], Any] = lambda triad: None
    #: replay one entry at a time and wait for background runs between them, as the
    #: sequencer will: an entry may need the run before it to have finished
    wait_between: bool = False
    #: the test id, for a tab with more than one scenario
    name: str = ""


SCENARIOS = [
    Scenario(
        tab="MetadataController",
        covers=("reset", "overlay_plot"),
        build=metadata_tab,
        act=metadata_act,
        perturb=metadata_perturb,
    ),
    Scenario(
        tab="MetadataController",
        name="MetadataController-events",
        covers=("reset", "plot_events"),
        build=metadata_tab,
        act=metadata_events_act,
        # The filter, the scope and the Event ID the click would read all change.
        perturb=metadata_perturb,
        # The click path builds the filtered-event cache the Event ID is resolved
        # through; the replay is handed the resolved ids.
        click_only_calls=("load_metadata", "construct_metadata_query"),
    ),
    Scenario(
        tab="ProteinController",
        covers=("reset", "update_ensemble_distribution"),
        build=protein_tab,
        act=protein_act,
        perturb=protein_perturb,
        seed=protein_seed,
        probe=individual_fit,
    ),
    Scenario(
        tab="ProteinController",
        name="ProteinController-individual",
        covers=("reset", "update_individual_distribution"),
        build=protein_tab,
        act=protein_individual_act,
        perturb=protein_perturb,
        probe=individual_fit,
    ),
    Scenario(
        tab="RawDataController",
        covers=("update_trace", "update_psd", "find_events", "plot_events"),
        build=rawdata_tab,
        act=rawdata_act,
        perturb=rawdata_perturb,
        needs="sample_chimera",
        # analysis_time_limits is not compared: writing the recorded Timer limits back is
        # write-back's job, tested on its own, and the replayed Find ran on the recorded
        # ranges although this tab holds different limits, which is the point.
        extra=("plot_samplerate",),
        click_only_calls=("get_eventfinding_status",),
        probe=found_events,
        wait_between=True,
    ),
    Scenario(
        tab="EventAnalysisController",
        covers=("fit_events", "plot_events"),
        build=eventanalysis_tab,
        act=eventanalysis_act,
        perturb=eventanalysis_perturb,
        needs="sample_events_db",
        # The click path asks which loader the fitter was built on and whether the channel is
        # already fitted before it launches; plotting with a fitter asks the same two, so both
        # are left out of the comparison. What the fit and the plot did is compared through
        # the figure and the state read back from the fitter.
        click_only_calls=("get_parents", "get_eventfitting_status"),
        probe=fitted_events,
        wait_between=True,
    ),
    Scenario(
        tab="ClusteringController",
        covers=("reset", "cluster_run", "merge_clusters"),
        build=clustering_tab,
        act=clustering_act,
        perturb=clustering_perturb,
        probe=cluster_labels,
    ),
]


def run_scenario(
    scenario: Scenario, tmp_path: Path, data: Any, qtbot: Any
) -> Tuple[Any, Any, List[Any]]:
    """
    Record in tab A, replay into a perturbed tab B, and return both captures and A's history.

    :param scenario: what to run
    :type scenario: Scenario
    :param tmp_path: scratch directory; each tab gets its own folder
    :type tmp_path: Path
    :param data: what the scenario's builder needs, from the fixture it names
    :type data: Any
    :param qtbot: pytest-qt's fixture, for an action that runs in the background
    :type qtbot: Any
    :return: A's capture, B's capture, and the history recorded in A
    :rtype: Tuple[Any, Any, List[Any]]
    """
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    tab_a = scenario.build(tmp_path / "a", data)
    tab_b = scenario.build(tmp_path / "b", data)
    try:
        scenario.seed(tab_a)
        spy_a = Spy(tab_a)
        scenario.act(tab_a, qtbot)
        settle(tab_a, qtbot)
        captured_a = capture(
            tab_a, spy_a, scenario.extra, scenario.click_only_calls, scenario.probe
        )
        history = copy.deepcopy(list(tab_a.tab_controller.tab_action_history.values()))

        scenario.seed(tab_b)
        scenario.perturb(tab_b)
        spy_b = Spy(tab_b)
        if scenario.wait_between:
            for entry in history:
                tab_b.tab_controller.replay([entry])
                settle(tab_b, qtbot)
        else:
            tab_b.tab_controller.replay(history)
            settle(tab_b, qtbot)
        captured_b = capture(
            tab_b, spy_b, scenario.extra, scenario.click_only_calls, scenario.probe
        )
        return captured_a, captured_b, history
    finally:
        tab_a.close()
        tab_b.close()


# ---------------------------------------------------------------- the tests


@pytest.mark.timeout(240)
@pytest.mark.parametrize(
    "scenario", SCENARIOS, ids=[s.name or s.tab for s in SCENARIOS]
)
def test_a_replay_reproduces_what_the_action_produced(
    qapp, qtbot, request, tmp_path: Path, scenario: Scenario
) -> None:
    data = request.getfixturevalue(scenario.needs)
    captured_a, captured_b, history = run_scenario(scenario, tmp_path, data, qtbot)

    recorded = {entry["action"] for entry in history}
    assert (
        set(scenario.covers) <= recorded
    ), "the scenario did not record the actions it claims to cover"
    assert captured_b["plugin_calls"] == captured_a["plugin_calls"]
    assert captured_b["plot_cache"] == captured_a["plot_cache"]
    assert captured_b["figures"] == captured_a["figures"]
    assert captured_b["bookkeeping"] == captured_a["bookkeeping"]


@pytest.mark.timeout(240)
def test_a_replayed_fit_leaves_the_channel_fitted_in_both_tabs(
    qapp, qtbot, tmp_path: Path, sample_events_db: str
) -> None:
    """The two tabs agreeing is not enough: a fit that never ran would agree with itself."""
    scenario = next(s for s in SCENARIOS if s.tab == "EventAnalysisController")

    captured_a, captured_b, _ = run_scenario(
        scenario, tmp_path, sample_events_db, qtbot
    )

    for captured in (captured_a, captured_b):
        assert captured["probe"]["fitted"] is True
        assert "good fits" in captured["probe"]["report"]


@pytest.mark.timeout(240)
def test_a_replayed_clustering_and_merge_happen_in_both_tabs(
    qapp, qtbot, tmp_path: Path, sample_metadata_db: str
) -> None:
    """The two tabs agreeing is not enough: a run or a merge that did nothing would agree with itself."""
    scenario = next(s for s in SCENARIOS if s.tab == "ClusteringController")

    captured_a, captured_b, _ = run_scenario(
        scenario, tmp_path, sample_metadata_db, qtbot
    )

    for captured in (captured_a, captured_b):
        assert captured["probe"], "no clustering result was produced"
        assert sum(captured["probe"].values()) == 40
        assert "1" not in captured["probe"], "label 1 was not merged into 0"
        assert "0" in captured["probe"]


@pytest.mark.timeout(240)
def test_a_replayed_individual_plot_rebuilds_the_fit_commit_writes(
    qapp, qtbot, tmp_path: Path, sample_metadata_db: str
) -> None:
    """The two tabs agreeing is not enough: a plot that fitted nothing would agree with itself."""
    scenario = next(s for s in SCENARIOS if s.name == "ProteinController-individual")

    captured_a, captured_b, _ = run_scenario(
        scenario, tmp_path, sample_metadata_db, qtbot
    )

    assert captured_a["probe"] is not None
    assert captured_b["probe"] == captured_a["probe"]


@pytest.mark.timeout(240)
def test_a_replayed_ensemble_plot_leaves_the_individual_fit(
    qapp, qtbot, tmp_path: Path, sample_metadata_db: str
) -> None:
    scenario = next(s for s in SCENARIOS if s.tab == "ProteinController" and not s.name)

    captured_a, captured_b, _ = run_scenario(
        scenario, tmp_path, sample_metadata_db, qtbot
    )

    for captured in (captured_a, captured_b):
        assert captured["probe"] == normalise(pd.DataFrame({"id": [-1]}))


@pytest.mark.timeout(240)
@pytest.mark.parametrize("tab", TABS)
def test_every_declared_action_has_a_scenario(qapp, tmp_path: Path, tab: str) -> None:
    """A tab that declares an action nothing records here fails, so a new action cannot land unchecked."""
    triad = build_triad(tab, tmp_path)
    try:
        declared = set(triad.tab_controller.action_registry())
    finally:
        triad.close()
    covered = {name for s in SCENARIOS if s.tab == tab for name in s.covers}

    assert (
        declared <= covered
    ), f"{tab} declares {sorted(declared - covered)} with no scenario"
