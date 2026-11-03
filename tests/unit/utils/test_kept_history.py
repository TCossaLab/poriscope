"""
Tests for ``poriscope.utils.kept_history.build_kept_history``.

Each case is a tab's live history in and the history a restore replays out. The
declarations below are the tabs' own, read from their Controllers, so a change to a
tab's declaration shows up here as a changed kept history.
"""

from copy import deepcopy
from typing import Any, Dict, List, Mapping

import pytest

from poriscope.plugins.analysistabs.ClusteringController import ClusteringController
from poriscope.plugins.analysistabs.EventAnalysisController import (
    EventAnalysisController,
)
from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.RawDataController import RawDataController
from poriscope.utils.kept_history import build_kept_history
from poriscope.utils.LogDecorator import RESET_ACTION, ActionDeclaration
from poriscope.utils.MetaController import declarations_of

RAW = declarations_of(RawDataController)
FIT = declarations_of(EventAnalysisController)
CLUSTER = declarations_of(ClusteringController)
METADATA = declarations_of(MetadataController)
PROTEIN = declarations_of(ProteinController)


def _entry(action: str, **kwargs: Any) -> Dict[str, Any]:
    return {"action": action, "args": [], "kwargs": kwargs}


def find(finder: str, channel: int, start: float = 0.0) -> Dict[str, Any]:
    return _entry(
        "find_events",
        eventfinder=finder,
        channel=channel,
        ranges=[[start, 10.0]],
        data_filter="",
        time_limits={},
    )


def trace(start: float = 0.0) -> Dict[str, Any]:
    return _entry(
        "update_trace",
        reader="Reader",
        channels=[1],
        start=start,
        length=1.0,
        data_filter="",
        baseline=False,
    )


def plot_found(finder: str, channel: int) -> Dict[str, Any]:
    return _entry(
        "plot_events", eventfinder=finder, channel=channel, events=[0], data_filter=""
    )


def fit(fitter: str, channel: int) -> Dict[str, Any]:
    return _entry("fit_events", eventfitter=fitter, channel=channel, data_filter="")


def plot_fitted(fitter: str, channel: int) -> Dict[str, Any]:
    return _entry(
        "plot_events",
        loader="Loader",
        eventfitter=fitter,
        channel=channel,
        events=[0],
        data_filter="",
        raw=False,
    )


def reset(**kwargs: Any) -> Dict[str, Any]:
    return _entry(RESET_ACTION, axis_type="2d", **kwargs)


def overlay(column: str) -> Dict[str, Any]:
    return _entry("overlay_plot", loader="Loader", axes=[column])


def metadata_events() -> Dict[str, Any]:
    return _entry("plot_events", loader="Loader", event_ids=[0])


def run(label: str) -> Dict[str, Any]:
    return _entry("cluster_run", config={"label": label}, loader="Loader")


def merge(keep: int, other: int) -> Dict[str, Any]:
    return _entry("merge_clusters", keep=keep, merge=other)


def distribution(mode: str, bins: int) -> Dict[str, Any]:
    return _entry(f"update_{mode}_distribution", loader="Loader", bins=[bins])


def protein_events(action: str = "plot_events") -> Dict[str, Any]:
    return _entry(action, loader="Loader", event_ids=[0])


def _kept(
    entries: List[Dict[str, Any]], declarations: Mapping[str, ActionDeclaration]
) -> List[Dict[str, Any]]:
    return build_kept_history(entries, declarations)


@pytest.mark.parametrize(
    "declarations, live, kept",
    [
        pytest.param(
            RAW,
            [find("A", 1, 0.0), find("A", 2), find("A", 1, 5.0)],
            [find("A", 2), find("A", 1, 5.0)],
            id="a result is replaced per plugin and channel",
        ),
        pytest.param(
            RAW,
            [find("A", 1), find("B", 1)],
            [find("A", 1), find("B", 1)],
            id="every finder keeps its own latest run",
        ),
        pytest.param(
            RAW,
            [trace(0.0), trace(5.0)],
            [trace(5.0)],
            id="a view replaces the view before it on its figure",
        ),
        pytest.param(
            RAW,
            [find("A", 1), trace(), plot_found("A", 1)],
            [find("A", 1), plot_found("A", 1)],
            id="plot events replaces the trace and keeps the run it draws from",
        ),
        pytest.param(
            RAW,
            [find("A", 1, 0.0), plot_found("A", 1), find("A", 1, 5.0)],
            [find("A", 1, 5.0)],
            id="a view drawn from a result that was run again is dropped",
        ),
        pytest.param(
            RAW,
            [find("A", 1), plot_found("A", 1), find("A", 2)],
            [find("A", 1), plot_found("A", 1), find("A", 2)],
            id="a run on another channel does not drop the view",
        ),
        pytest.param(
            RAW,
            [trace(), find("A", 1), plot_found("A", 1), find("A", 1, 5.0)],
            [find("A", 1, 5.0)],
            id="a dropped view still leaves its figure empty",
        ),
        pytest.param(
            FIT,
            [fit("F", 1), plot_fitted("F", 1), fit("F", 1)],
            [fit("F", 1)],
            id="a fitted plot is dropped when its fit is run again",
        ),
        pytest.param(
            FIT,
            [fit("F", 1), plot_fitted("No Event Fitter", 1), fit("F", 1)],
            [plot_fitted("No Event Fitter", 1), fit("F", 1)],
            id="a plot with no fitter draws from no fit",
        ),
        pytest.param(
            METADATA,
            [reset(), overlay("a"), overlay("b"), reset(), overlay("y")],
            [reset(), overlay("y")],
            id="a reset drops everything before it on its figure",
        ),
        pytest.param(
            METADATA,
            [reset(), overlay("a"), overlay("b")],
            [reset(), overlay("a"), overlay("b")],
            id="overlays since the last reset are all kept",
        ),
        pytest.param(
            METADATA,
            [reset(), overlay("a"), overlay("b"), metadata_events()],
            [reset(), metadata_events()],
            id="plot events drops the overlays it replaced",
        ),
        pytest.param(
            CLUSTER,
            [reset(), run("one"), merge(0, 1), merge(0, 2), reset(), run("two")],
            [reset(), run("two")],
            id="a new run's reset ends the old run and its merges",
        ),
        pytest.param(
            CLUSTER,
            [reset(), run("one"), merge(0, 1), merge(0, 2)],
            [reset(), run("one"), merge(0, 1), merge(0, 2)],
            id="a run keeps every merge after it",
        ),
        pytest.param(
            PROTEIN,
            [
                reset(mode="individual"),
                distribution("individual", 10),
                reset(mode="ensemble"),
                distribution("ensemble", 20),
                reset(mode="individual"),
                distribution("individual", 30),
            ],
            [
                reset(mode="ensemble"),
                distribution("ensemble", 20),
                reset(mode="individual"),
                distribution("individual", 30),
            ],
            id="a protein reset clears only its own mode",
        ),
        pytest.param(
            PROTEIN,
            [
                reset(mode="individual"),
                distribution("individual", 10),
                protein_events(),
                protein_events("plot_event_histograms"),
            ],
            [
                reset(mode="individual"),
                distribution("individual", 10),
                protein_events("plot_event_histograms"),
            ],
            id="the event page keeps its newest view and leaves the modes alone",
        ),
    ],
)
def test_a_restore_keeps_what_the_screen_and_results_depend_on(
    declarations: Mapping[str, ActionDeclaration],
    live: List[Dict[str, Any]],
    kept: List[Dict[str, Any]],
) -> None:
    assert _kept(live, declarations) == kept


def test_an_entry_no_declaration_covers_is_kept_for_replay_to_report() -> None:
    live = [
        {"action": "removed_action", "args": [], "kwargs": {}},
        {"args": [], "kwargs": {}},
        {"action": "update_trace", "args": ["Reader", [1]], "kwargs": {}},
        trace(5.0),
    ]

    assert _kept(live, RAW) == live


def test_the_live_history_is_left_as_it_was() -> None:
    live = [trace(0.0), trace(5.0)]
    before = deepcopy(live)

    kept = _kept(live, RAW)
    kept[0]["kwargs"]["start"] = 99.0

    assert live == before


def test_a_history_read_back_from_a_file_is_treated_the_same() -> None:
    """A saved file holds lists where the live history holds tuples."""
    live = [find("A", 1), plot_found("A", 1), find("A", 1, 5.0)]
    saved = [
        {"action": e["action"], "args": list(e["args"]), "kwargs": e["kwargs"]}
        for e in live
    ]

    assert _kept(saved, RAW) == [find("A", 1, 5.0)]
