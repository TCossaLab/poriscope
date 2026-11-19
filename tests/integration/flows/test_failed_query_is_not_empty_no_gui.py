"""
A database query that fails is reported as a failure, never as a subset with no rows.

Each test drives one tab site against a real ``SQLiteDBLoader`` and a query the
database cannot run, and asserts on the status panel: the site's own "could not"
message, carrying the database's reason, and not its "nothing matched" one. Two
failures are used. A condition that overflows an integer passes SQLite's query plan
check and fails only while it runs, so it reaches the load after the query was built.
A file that is not a database fails every query, including the ones a tab builds for
itself from event ids.
"""

from pathlib import Path
from typing import Any, List

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import (
    Triad,
    build_clustering_tab,
    build_triad,
    hdbscan_config,
)

LOADER = "loader"
#: Passes ``EXPLAIN QUERY PLAN``; SQLite raises "integer overflow" only when it runs.
OVERFLOWS = "abs(-9223372036854775808) > 0"


def listen(triad: Triad) -> List[str]:
    """Collect every line the tab puts on the status panel."""
    said: List[str] = []
    triad.tab_view.add_text_to_display.connect(lambda text, source: said.append(text))
    triad.tab_controller.add_text_to_display.connect(
        lambda text, source: said.append(text)
    )
    return said


def spoil(db_path: str) -> None:
    """Replace the database with a file SQLite cannot read."""
    Path(db_path).write_bytes(b"this is not a database\n" * 64)


@pytest.fixture
def metadata_tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """A Metadata tab with a real loader over a copy of the synthetic database."""
    triad = build_triad("MetadataController", tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    triad.db_path = sample_metadata_db  # type: ignore[attr-defined]
    triad.said = listen(triad)  # type: ignore[attr-defined]
    yield triad
    triad.close()


@pytest.fixture
def clustering_tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """A Clustering tab with a real loader over a copy of the synthetic database."""
    triad = build_clustering_tab(tmp_path, sample_metadata_db, LOADER)
    triad.said = listen(triad)  # type: ignore[attr-defined]
    yield triad
    triad.close()


def test_clustering_says_the_load_failed(clustering_tab: Triad) -> None:
    config = hdbscan_config()
    config["filter"] = OVERFLOWS

    ran = clustering_tab.tab_controller.load_metadata_for_clustering(config, LOADER)

    said = clustering_tab.said  # type: ignore[attr-defined]
    assert ran is False
    assert any("integer overflow" in line for line in said), said
    assert "No data matches the given query" not in said


def test_a_metadata_overlay_says_the_load_failed_and_stops(metadata_tab: Triad) -> None:
    """One failed dataset stops the plot, as every other failure to load one does."""
    drawn = metadata_tab.tab_controller.overlay_plot(
        loader=LOADER,
        plot_type="Histogram",
        axes=["max_deviation", "start_time", "max_blockage"],
        logs=[False, False, False],
        bins=[20],
        sizes=False,
        filters={"broken": f"duration >= 0 AND {OVERFLOWS}", "fine": "duration >= 0"},
        scope={"exp_a": ["0"]},
    )

    said = metadata_tab.said  # type: ignore[attr-defined]
    assert drawn is False
    assert any("integer overflow" in line for line in said), said
    assert not any("No data matching the subset" in line for line in said), said
    assert not metadata_tab.tab_controller.model.overlay.datasets


def test_a_raw_filter_that_fails_while_running_says_why(metadata_tab: Triad) -> None:
    run = metadata_tab.tab_controller._run_raw_filter(
        LOADER,
        f"SELECT event_id, duration FROM events WHERE {OVERFLOWS}",
        None,
        "broken_raw",
    )

    said = metadata_tab.said  # type: ignore[attr-defined]
    assert run is None
    assert any("broken_raw" in line and "integer overflow" in line for line in said)
    assert not any("see the log" in line for line in said), said


def test_the_event_id_cache_says_why_its_query_failed(metadata_tab: Triad) -> None:
    view = metadata_tab.tab_view
    view.event_id_rows = None

    metadata_tab.tab_controller.load_event_id_cache(
        LOADER, OVERFLOWS, {"exp_a": [0]}, "broken"
    )

    said = metadata_tab.said  # type: ignore[attr-defined]
    assert view.event_id_rows is None
    assert any("integer overflow" in line for line in said), said
    assert not any("see the log" in line for line in said), said


def test_plotting_events_from_an_unreadable_database_says_it_could_not_look(
    metadata_tab: Triad,
) -> None:
    spoil(metadata_tab.db_path)  # type: ignore[attr-defined]

    drawn = metadata_tab.tab_controller.plot_events(
        loader=LOADER,
        event_ids=[0, 1],
        experiment=None,
        channel=None,
        subset_name="F0",
        sql_filter="duration >= 0",
        raw=False,
    )

    said = metadata_tab.said  # type: ignore[attr-defined]
    assert drawn is False
    assert any("Could not look up these events" in line for line in said), said
    assert not any("No data available" in line for line in said), said


def test_an_experiment_lookup_that_fails_is_not_a_missing_experiment(
    metadata_tab: Triad,
) -> None:
    spoil(metadata_tab.db_path)  # type: ignore[attr-defined]

    drawn = metadata_tab.tab_controller.plot_events(
        loader=LOADER,
        event_ids=[0, 1],
        experiment="exp_a",
        channel="0",
        subset_name="F0",
        sql_filter="duration >= 0",
        raw=False,
    )

    said = metadata_tab.said  # type: ignore[attr-defined]
    assert drawn is False
    assert any("Could not look up experiment exp_a" in line for line in said), said
    assert not any("has no experiment named" in line for line in said), said
