"""
An assisted filter stays inside the experiment and channel selection, however it is written.

The builder joins the user's condition to the selection with ``AND``. Without brackets an
``OR`` in the condition took the selection with only its last term, so a filter such as
``duration > 0 OR max_blockage > 0`` drew every channel for each ticked one; and a ``--``
comment at the end swallowed the selection written after it on the same line. Run against a
real loader over a database whose channels hold different numbers of events, so a leak shows
as a count that is too large.
"""

from pathlib import Path
from typing import Any, Generator

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.synthetic_data.synthetic_metadata_db import generate_metadata_database

CHANNEL_0 = 5
CHANNEL_1 = 7


@pytest.fixture
def loader(tmp_path: Path) -> Generator[SQLiteDBLoader, None, None]:
    """
    A real loader over a database with 5 events on channel 0 and 7 on channel 1.

    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the configured loader
    :rtype: Generator[SQLiteDBLoader, None, None]
    """
    database = generate_metadata_database(
        tmp_path / "scope.sqlite3",
        experiments=[
            {
                "name": "exp_a",
                "channels": [
                    {"channel_id": 0, "num_events": CHANNEL_0, "seed": 1},
                    {"channel_id": 1, "num_events": CHANNEL_1, "seed": 2},
                ],
            }
        ],
    )
    instance = SQLiteDBLoader()
    settings = instance.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(database.db_path)
    instance.apply_settings(settings)
    yield instance


CONDITIONS = [
    "duration > 0",
    "duration > 0 OR max_blockage > 0",
    "duration > 0 --",
    "duration < 0 OR duration >= 0",
    "(duration > 0 AND max_blockage > 0) OR duration < 0",
    "e.id IN (SELECT event_db_id FROM sublevels)",
    "duration > 0 OR e.id IN (SELECT event_db_id FROM sublevels)",
]


def count_events(loader: SQLiteDBLoader, condition: str, scope: Any) -> int:
    """
    Count the events ``load_event_data`` yields for a condition and a selection.

    :param loader: the loader under test
    :type loader: SQLiteDBLoader
    :param condition: the assisted filter text
    :type condition: str
    :param scope: the experiment and channel selection
    :type scope: Any
    :return: how many events came back
    :rtype: int
    """
    generator = loader.load_event_data(condition, scope)
    return 0 if generator is None else sum(1 for _ in generator)


@pytest.mark.timeout(120)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_the_metadata_query_stays_inside_the_selected_channel(
    loader: SQLiteDBLoader, condition: str
) -> None:
    """
    Only channel 0's rows, whatever the condition's ``OR`` or comment does.
    """
    rows = loader.load_metadata(["duration"], condition, {"exp_a": [0]})

    assert rows is not None
    assert len(rows) == CHANNEL_0


@pytest.mark.timeout(120)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_the_event_data_query_stays_inside_the_selected_channel(
    loader: SQLiteDBLoader, condition: str
) -> None:
    """
    The events loaded for a plot are the selected channel's only.
    """
    assert count_events(loader, condition, {"exp_a": [0]}) == CHANNEL_0


@pytest.mark.timeout(120)
def test_two_selected_channels_are_still_their_union(loader: SQLiteDBLoader) -> None:
    """
    The brackets narrow the condition, not the selection.
    """
    rows = loader.load_metadata(
        ["duration"], "duration > 0 OR max_blockage > 0", {"exp_a": [0, 1]}
    )

    assert rows is not None
    assert len(rows) == CHANNEL_0 + CHANNEL_1


@pytest.mark.timeout(120)
def test_a_condition_that_matches_nothing_still_matches_nothing(
    loader: SQLiteDBLoader,
) -> None:
    """
    The brackets do not widen a condition either.
    """
    rows = loader.load_metadata(["duration"], "duration < 0", {"exp_a": [0]})

    assert rows is not None
    assert len(rows) == 0


UNBALANCED = ["1=1) OR (1=1", "duration > 0)", "(duration > 0", ") OR (duration > 0"]


@pytest.mark.timeout(120)
@pytest.mark.parametrize("condition", UNBALANCED)
def test_a_condition_whose_brackets_do_not_balance_is_refused(
    loader: SQLiteDBLoader, condition: str
) -> None:
    """
    ``1=1) OR (1=1`` closes the brackets the condition is put in and opens another, so
    its ``OR`` took the selection with only its last term. It is refused instead.
    """
    query, debug, _ = loader.construct_metadata_query(
        ["duration"], condition, {"exp_a": [0]}
    )

    assert query == ""
    assert "brackets" in debug
    assert loader.load_metadata(["duration"], condition, {"exp_a": [0]}) is None
    assert count_events(loader, condition, {"exp_a": [0]}) == 0


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "condition",
    [
        "duration > 0 AND ')' = ')'",
        "duration > 0 AND '(' = '('",
        "duration > 0 -- )",
        "duration > 0 /* ( */",
        'duration > 0 AND ")" = ")"',
    ],
)
def test_brackets_inside_strings_and_comments_do_not_count(
    loader: SQLiteDBLoader, condition: str
) -> None:
    """
    They are text, not brackets, so the condition is accepted and stays in its channel.
    """
    rows = loader.load_metadata(["duration"], condition, {"exp_a": [0]})

    assert rows is not None
    assert len(rows) == CHANNEL_0
