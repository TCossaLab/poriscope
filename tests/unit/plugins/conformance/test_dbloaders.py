"""
Behavioural conformance for every discovered ``MetaDatabaseLoader``.

Database loaders back the Metadata, Clustering and Protein tabs: they answer what
experiments and channels a database holds, what columns exist, and what a filter
query means. Those answers populate the UI, so a loader that reports the wrong
channels sends the whole tab looking at the wrong data.

``SQLiteDBLoader`` has a unit suite and is driven by the metadata and clustering
flows. ``SQLitePeakDBLoader`` had no coverage at all - it subclasses
``SQLiteDBLoader`` and overrides only ``get_plot_features``, so everything checked
here is inherited behaviour, which is exactly the kind of thing a subclass can break
by accident.
"""

from typing import List, Type

import pandas as pd
import pytest

from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader
from tests.unit.plugins.conformance._recipes import (
    METADATA_CHANNELS,
    METADATA_EVENT_COUNTS,
    METADATA_EXPERIMENT,
    build_db_loader,
    discover_concrete,
)

DB_LOADERS: List[Type[MetaDatabaseLoader]] = discover_concrete(MetaDatabaseLoader)


@pytest.fixture(params=DB_LOADERS, ids=[cls.__name__ for cls in DB_LOADERS])
def db_loader(request, metadata_db_path):
    """
    Build the database loader under test over the shared metadata database.

    :param request: Pytest request, carrying the parametrised loader class.
    :type request: pytest.FixtureRequest
    :param metadata_db_path: Path to the shared synthetic metadata database.
    :type metadata_db_path: str
    :return: A configured database loader.
    :rtype: MetaDatabaseLoader
    """
    instance = build_db_loader(request.param, metadata_db_path)
    yield instance
    instance.close_resources()


@pytest.mark.conformance
def test_reports_experiments_and_channels(db_loader: MetaDatabaseLoader) -> None:
    """
    A loader reports the experiment and both its channels.

    The metadata tab builds its experiment and channel selectors from these, and a
    single-channel answer is indistinguishable from a stub - which is why the fixture
    plants two channels with *different* event counts.

    :param db_loader: The configured database loader under test.
    :type db_loader: MetaDatabaseLoader
    """
    names = db_loader.get_experiment_names()
    assert (
        names is not None and METADATA_EXPERIMENT in names
    ), f"expected experiment {METADATA_EXPERIMENT!r}, got {names}"

    channels = db_loader.get_channels_by_experiment(METADATA_EXPERIMENT)
    assert channels is not None
    assert sorted(channels) == sorted(
        METADATA_CHANNELS
    ), f"expected channels {sorted(METADATA_CHANNELS)}, got {sorted(channels)}"

    combined = db_loader.get_experiments_and_channels()
    assert (
        METADATA_EXPERIMENT in combined
    ), "get_experiments_and_channels disagrees with get_experiment_names"

    for channel, expected in zip(METADATA_CHANNELS, METADATA_EVENT_COUNTS):
        count = db_loader.get_event_counts_by_experiment_and_channel(
            METADATA_EXPERIMENT, channel
        )
        assert (
            count == expected
        ), f"channel {channel} reports {count} events, fixture planted {expected}"
        assert (
            db_loader.get_samplerate_by_experiment_and_channel(
                METADATA_EXPERIMENT, channel
            )
            is not None
        ), f"no sample rate for channel {channel}"


@pytest.mark.conformance
def test_describes_its_own_schema(db_loader: MetaDatabaseLoader) -> None:
    """
    A loader can enumerate its tables and each table's columns, with types and units.

    The metadata tab's column pickers and axis labels come from here, so a column
    the loader lists but cannot type is a hole in the UI rather than a crash.

    :param db_loader: The configured database loader under test.
    :type db_loader: MetaDatabaseLoader
    """
    tables = db_loader.get_table_names()
    assert tables, "no tables reported"
    assert {"events", "channels", "experiments"}.issubset(
        set(tables)
    ), f"expected the core tables among {sorted(tables)}"

    columns = db_loader.get_column_names_by_table("events")
    assert columns, "events table reported no columns"

    errors = []
    for column in columns:
        if db_loader.get_column_type(column) is None:
            errors.append(f"{column!r} has no type")
        if db_loader.get_table_by_column(column) is None:
            errors.append(f"{column!r} maps to no table")
    assert not errors, "\n  ".join([""] + errors)


@pytest.mark.conformance
def test_validates_queries_and_loads_metadata(db_loader: MetaDatabaseLoader) -> None:
    """
    A loader accepts a well-formed query, rejects a malformed one, and returns rows.

    ``validate_filter_query`` gates what the user is allowed to run, so it has to
    discriminate: accepting everything makes it useless, rejecting everything makes
    the filter UI unusable. Note it wraps the input in ``EXPLAIN QUERY PLAN``, so it
    expects a complete statement rather than a bare ``WHERE`` fragment.

    :param db_loader: The configured database loader under test.
    :type db_loader: MetaDatabaseLoader
    """
    ok, message = db_loader.validate_filter_query("SELECT * FROM events")
    assert ok, f"a valid query was rejected: {message}"

    bad_ok, bad_message = db_loader.validate_filter_query("SELECT * FROM no_such_table")
    assert not bad_ok, "a query against a nonexistent table was accepted"
    assert bad_message, "rejection came with no explanation"

    frame = db_loader.query_database_directly("SELECT * FROM events LIMIT 5")
    assert isinstance(frame, pd.DataFrame), f"got {type(frame).__name__}"
    assert not frame.empty, "no rows returned from a populated events table"


@pytest.mark.conformance
def test_reports_an_llm_prompt(db_loader: MetaDatabaseLoader) -> None:
    """
    ``get_llm_prompt`` returns a string or None, never something unusable.

    It is abstract on the base and its value is passed straight into a prompt, so a
    subclass returning a dict or a list would fail far from here.

    :param db_loader: The configured database loader under test.
    :type db_loader: MetaDatabaseLoader
    """
    prompt = db_loader.get_llm_prompt()
    assert prompt is None or isinstance(
        prompt, str
    ), f"get_llm_prompt returned {type(prompt).__name__}"


@pytest.mark.conformance
def test_reset_and_close_are_safe(db_loader: MetaDatabaseLoader) -> None:
    """
    A loader survives reset and repeated close, and still queries afterwards.

    :param db_loader: The configured database loader under test.
    :type db_loader: MetaDatabaseLoader
    """
    db_loader.reset_channel()
    assert db_loader.get_experiment_names(), "reset_channel left the loader unusable"
    db_loader.close_resources()
    db_loader.close_resources()


@pytest.mark.conformance
def test_at_least_one_db_loader_was_discovered() -> None:
    """Guard against the discovery walk silently finding nothing."""
    assert DB_LOADERS, "no concrete MetaDatabaseLoader subclasses were discovered"
