"""
How raw SQL subset filters meet the event-data plots and the event navigation.

A raw filter is a complete ``SELECT``, which cannot be spliced where
``load_event_data`` expects a WHERE-clause body. It scopes itself instead: the
experiment and channel the selection names are bound into ``:experiment_id`` and
``:channel_id`` in its text, and the events its ``event_id`` column names are loaded
with the key of the pair it ran for. The navigation (Plot Events, the arrows) takes its
list of ``event_id`` values from the same query instead of from the query builder. What
these tests pin is those routes, the warnings for a query that does not scope itself,
and the failures.

The projection comparison at the bottom used to assert that the two tabs' event-plot
chains authored *different* queries. They do not any more: the chain is one body on
``MetaSubsetTabModel``, and the test now pins that.
"""

import inspect
from typing import Any

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.utils.MetaSubsetTabController import (
    bind_scope,
    code_spans,
    relabelled_keys,
    scope_placeholders,
    selected_pairs,
    with_event_id,
    writing_keyword,
)
from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel
from tests.unit.controllers._recording_model import RecordingModel

pytestmark = pytest.mark.characterization


class SequencedModel(RecordingModel):
    """
    A recording Model that answers ``query_database_directly`` from a list, in order.

    A raw filter asks it twice - the query itself, then the events table - and the two
    answers differ; the last one is repeated if the code asks again.
    """

    def __init__(self, answers: dict, replies: list) -> None:
        """
        :param answers: plugin method name to canned answer
        :type answers: dict
        :param replies: the answers to ``query_database_directly``, in the order asked
        :type replies: list
        """
        super().__init__(answers)
        self.replies = list(replies)

    def call(self, metaclass: str, key: str, method: str, *args: object) -> object:
        """
        Record one plugin call and answer it.

        :param metaclass: the plugin family
        :type metaclass: str
        :param key: the plugin instance's key
        :type key: str
        :param method: the method being called on it
        :type method: str
        :param args: the positional arguments
        :type args: object
        :return: the canned answer
        :rtype: object
        """
        if method != "query_database_directly":
            return super().call(metaclass, key, method, *args)
        self.calls.append((metaclass, key, method, args))
        answer = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _controller(
    cls: type, mocker: MockerFixture, answers: dict, replies: Any = None
) -> Any:
    """
    A bare Controller of the given class with a recording Model and a mocked View.

    :param cls: MetadataController or ProteinController
    :type cls: type
    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :param answers: plugin method name to canned answer
    :type answers: dict
    :param replies: answers to ``query_database_directly`` in order, or None to use ``answers``
    :type replies: Any
    :return: the controller under test
    :rtype: Any
    """
    controller = cls.__new__(cls)
    controller.view = mocker.Mock()
    controller.logger = mocker.Mock()
    controller.add_text_to_display = mocker.Mock()
    controller.model = (
        RecordingModel(answers) if replies is None else SequencedModel(answers, replies)
    )
    return controller


def _said(controller: Any) -> str:
    """
    Everything the controller put on the status panel, joined.

    :param controller: the controller under test
    :type controller: Any
    :return: the concatenated message text
    :rtype: str
    """
    return "\n".join(
        call.args[0] for call in controller.add_text_to_display.emit.call_args_list
    )


SCOPED = (
    "SELECT event_id FROM events WHERE duration > 100 "
    "AND experiment_id = :experiment_id AND channel_id = :channel_id"
)
UNSCOPED = "SELECT experiment_id, channel_id, event_id FROM events WHERE duration > 100"
SCOPE = {"exp1": [2]}
#: A join repeats each event once per sublevel, so the same event arrives several times.
EVENTS = pd.DataFrame({"event_id": [10, 10, 11, 12]})
#: What the events table says about those events, for the check that they exist.
IN_DATABASE = pd.DataFrame(
    {"experiment_id": [7] * 3, "channel_id": [2] * 3, "event_id": [10, 11, 12]}
)
#: A query that returns the whole key, for one that does not scope itself.
WHOLE_KEY = pd.DataFrame(
    {"experiment_id": [7] * 4, "channel_id": [2] * 4, "event_id": [10, 10, 11, 12]}
)


def answers(**overrides: Any) -> dict:
    """
    The loader's answers for a raw filter, with any of them replaced.

    :param overrides: answers to replace, by plugin method name
    :type overrides: Any
    :return: the canned answers
    :rtype: dict
    """
    return {
        "get_experiment_id_by_name": 7,
        "query_database_directly": EVENTS,
        "construct_event_data_query": ("SELECT generated", ""),
        "load_event_data": iter([]),
        "load_metadata": pd.DataFrame({"event_id": [1, 2]}),
        **overrides,
    }


def _event_controller(
    cls: type, mocker: MockerFixture, *replies: Any, **extra: Any
) -> Any:
    """
    A Controller whose raw filter returns ``replies`` in turn, the events table last.

    :param cls: MetadataController or ProteinController
    :type cls: type
    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :param replies: the answers to ``query_database_directly`` in order
    :type replies: Any
    :param extra: plugin answers to replace
    :type extra: Any
    :return: the controller under test
    :rtype: Any
    """
    return _controller(cls, mocker, answers(**extra), list(replies))


# ------------------------------------------------------------------ the text helpers


def test_a_placeholder_is_found_only_in_code() -> None:
    """
    The same text in a string or a comment is not a placeholder, and the name has to end
    where the word does.
    """
    sql = (
        "SELECT a FROM t WHERE experiment_id = :experiment_id -- :channel_id\n"
        "AND note = ':channel_id' AND x = :channel_idx"
    )

    assert scope_placeholders(sql) == {"experiment_id"}


@pytest.mark.parametrize(
    ("sql", "found"),
    [
        ("SELECT 1", set()),
        ("WHERE experiment_id = :EXPERIMENT_ID", {"experiment_id"}),
        (
            "WHERE channel_id = :channel_id AND experiment_id = :experiment_id",
            {"channel_id", "experiment_id"},
        ),
        ('SELECT "a :channel_id" FROM t', set()),
        ("SELECT [a :channel_id] FROM t", set()),
        ("SELECT /* :channel_id */ 1", set()),
    ],
)
def test_the_placeholders_a_query_uses(sql: str, found: set) -> None:
    """
    Which of the two a query uses, whatever its case or quoting.
    """
    assert scope_placeholders(sql) == found


def test_binding_puts_whole_numbers_into_code_only() -> None:
    """
    Strings and comments are left as written.
    """
    sql = "SELECT 1 WHERE a = :experiment_id AND b = :channel_id AND c = ':channel_id'"

    assert bind_scope(sql, 3, 7) == (
        "SELECT 1 WHERE a = 3 AND b = 7 AND c = ':channel_id'"
    )


def test_selected_pairs_lists_a_channel_each() -> None:
    """
    One entry per channel; a whole experiment has no channel, and None names nothing.
    """
    assert selected_pairs({"a": [1, 3], "b": None, None: [None]}) == [
        ("a", 1),
        ("a", 3),
        ("b", None),
    ]
    assert selected_pairs(None) == []
    assert selected_pairs({None: [None]}) == []


def test_the_code_spans_leave_out_strings_and_comments() -> None:
    """
    The stretches that are SQL, in order.
    """
    sql = "SELECT 'a' /* b */ FROM t -- c\nWHERE x"
    assert [sql[a:b] for a, b in code_spans(sql)] == [
        "SELECT ",
        " ",
        " FROM t ",
        "WHERE x",
    ]


@pytest.mark.parametrize(
    ("sql", "found"),
    [
        ("SELECT a FROM t", None),
        ("WITH x AS (SELECT 1) DELETE FROM events", "delete"),
        ("WITH x AS (SELECT 1) UPDATE events SET a = 1", "update"),
        ("WITH x AS (SELECT 1) INSERT INTO t SELECT 1", "insert"),
        ("WITH x AS (SELECT 1) REPLACE INTO t SELECT 1", "replace into"),
        ("SELECT a FROM t; DROP TABLE t", "drop"),
        ("SELECT 'delete' AS a, \"update\" FROM t", None),
        ("SELECT a FROM t -- DELETE FROM t", None),
        ("SELECT /* update */ a FROM t", None),
        ("SELECT updated_at, created, replace(a, 'x', 'y') FROM t", None),
        ("SELECT a FROM t WHERE note = 'drop table'", None),
    ],
)
def test_a_keyword_that_would_write_is_found_in_code_only(sql: str, found: str) -> None:
    """
    Whole words outside strings, quoted names and comments.
    """
    assert writing_keyword(sql) == found


# ------------------------------------------------------------------ scoping and warnings


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterScopesItself:
    """
    The selection is bound into the query, and a query that does not use it is said so.
    """

    def test_both_placeholders_are_bound_and_nothing_is_said(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The query that runs is the user's own with the numbers in.
        """
        controller = _event_controller(cls, mocker, EVENTS)

        run = controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw")

        assert run is not None and run.scoped
        assert run.executed.endswith("experiment_id = 7 AND channel_id = 2")
        assert controller.model.calls_to("query_database_directly") == [(run.executed,)]
        assert _said(controller) == ""

    def test_a_query_that_uses_neither_is_warned_about_and_still_runs(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        It ignores the selection, so the same rows would be drawn for every channel.
        """
        controller = _event_controller(cls, mocker, WHOLE_KEY)

        run = controller._run_raw_filter("ldr", UNSCOPED, SCOPE, "mine_raw")

        assert run is not None and not run.scoped
        assert "does not use :experiment_id or :channel_id" in _said(controller)
        assert "ignores the Scope selection" in _said(controller)

    @pytest.mark.parametrize(
        ("only", "missing"),
        [("experiment_id", "channel_id"), ("channel_id", "experiment_id")],
    )
    def test_a_query_that_uses_only_one_is_warned_about(
        self, cls: type, mocker: MockerFixture, only: str, missing: str
    ) -> None:
        """
        Half a selection draws the same rows for every channel or experiment.
        """
        controller = _event_controller(cls, mocker, EVENTS)
        sql = f"SELECT event_id FROM events WHERE {only} = :{only}"

        run = controller._run_raw_filter("ldr", sql, SCOPE, "mine_raw")

        assert run is not None and not run.scoped
        assert f"uses :{only} but not :{missing}" in _said(controller)
        assert f"Add {missing} = :{missing}" in _said(controller)
        if missing == "channel_id":
            assert "every channel of that experiment, not only the one selected" in (
                _said(controller)
            )
        else:
            assert "that channel number from every other experiment" in _said(
                controller
            )

    def test_with_no_selection_a_query_that_needs_one_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        There is nothing to bind, and running it over everything would not be what the
        placeholders ask for.
        """
        controller = _event_controller(cls, mocker, EVENTS)

        for scope in (None, {}, {None: [None]}):
            assert controller._run_raw_filter("ldr", SCOPED, scope, "mine_raw") is None

        assert "no experiment and channel is selected" in _said(controller)
        assert controller.model.calls_to("query_database_directly") == []

    def test_with_no_selection_a_query_without_placeholders_just_runs(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing was selected, so ignoring the selection is not a fault.
        """
        controller = _event_controller(cls, mocker, WHOLE_KEY)

        run = controller._run_raw_filter("ldr", UNSCOPED, None, "mine_raw")

        assert run is not None
        assert _said(controller) == ""

    @pytest.mark.parametrize("scope", [{"exp1": [1, 2]}, {"exp1": None}])
    def test_placeholders_need_one_channel_at_a_time(
        self, cls: type, mocker: MockerFixture, scope: dict
    ) -> None:
        """
        Several channels, or a whole experiment, are not one value to bind.
        """
        controller = _event_controller(cls, mocker, EVENTS)

        assert controller._run_raw_filter("ldr", SCOPED, scope, "mine_raw") is None

        assert "one experiment and one channel at a time" in _said(controller)

    def test_an_unknown_experiment_is_reported(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The selection names an experiment the database does not have.
        """
        controller = _event_controller(
            cls, mocker, EVENTS, get_experiment_id_by_name=None
        )

        assert controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw") is None

        assert "exp1" in _said(controller)

    def test_the_same_warning_is_shown_once_not_once_per_channel(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A plot asks once per ticked channel with the same query.
        """
        controller = _event_controller(cls, mocker, WHOLE_KEY)

        for channel in (1, 2, 3):
            controller._run_raw_filter("ldr", UNSCOPED, {"exp1": [channel]}, "mine_raw")

        assert _said(controller).count("ignores the Scope selection") == 1
        assert "runs on the whole database" in _said(controller)
        assert "not with its own rows" in _said(controller)

    def test_a_query_that_is_fixed_and_then_broken_again_is_warned_about_again(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A clean run forgets the last warning, so the same mistake made again is not
        silenced by the one before the fix.
        """
        controller = _event_controller(cls, mocker, WHOLE_KEY)

        controller._run_raw_filter("ldr", UNSCOPED, SCOPE, "mine_raw")
        controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw")
        controller._run_raw_filter("ldr", UNSCOPED, SCOPE, "mine_raw")

        assert _said(controller).count("ignores the Scope selection") == 2

    def test_rows_from_other_channels_are_warned_about(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A placeholder in a subquery and not on the main table leaks other channels'
        rows, which then draw under the selected one's name.
        """
        leaking = pd.DataFrame(
            {"experiment_id": [7, 7, 7], "channel_id": [2, 3, 3], "event_id": [1, 2, 3]}
        )
        controller = _event_controller(cls, mocker, leaking)

        controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw")

        assert "2 of 3 rows" in _said(controller)
        assert (
            "other experiments or channels than the one selected (exp1 Ch 2)"
            in _said(controller)
        )

    def test_the_warning_names_both_usual_causes_and_the_bracketed_fix(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A reader who never wrote a subquery still learns that an unbracketed ``OR`` does it.
        """
        leaking = pd.DataFrame(
            {"experiment_id": [7, 7, 7], "channel_id": [2, 3, 3], "event_id": [1, 2, 3]}
        )
        controller = _event_controller(cls, mocker, leaking)

        controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw")

        said = _said(controller)
        assert "only in a subquery" in said
        assert "OR is not in brackets" in said
        assert "WHERE (a OR b) AND experiment_id = :experiment_id" in said

    def test_rows_that_all_belong_to_the_selection_say_nothing(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        No warning for the query that scoped itself.
        """
        controller = _event_controller(cls, mocker, WHOLE_KEY)

        controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw")

        assert "other experiments" not in _said(controller)

    def test_a_result_without_those_columns_cannot_be_checked_and_says_nothing(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The check needs the columns; it does not demand them.
        """
        controller = _event_controller(cls, mocker, EVENTS)

        controller._run_raw_filter("ldr", SCOPED, SCOPE, "mine_raw")

        assert _said(controller) == ""


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
@pytest.mark.parametrize(
    ("sql", "runs"),
    [
        ("SELECT event_id FROM events", True),
        ("  select event_id FROM events", True),
        ("-- a note\nSELECT event_id FROM events", True),
        ("/* a note */ WITH x AS (SELECT 1) SELECT * FROM x", True),
        ("DELETE FROM events WHERE id > 2", False),
        ("UPDATE events SET duration = 1", False),
        ("DROP TABLE events", False),
        ("-- SELECT\nDELETE FROM events", False),
        ("WITH x AS (SELECT 1) DELETE FROM events", False),
        ("WITH x AS (SELECT 1) UPDATE events SET duration = 1", False),
        ("WITH x AS (SELECT 1) INSERT INTO events SELECT * FROM events", False),
        ("SELECT updated_at, replace(a, 'x', 'y') FROM t -- drop table", True),
    ],
)
def test_only_a_select_is_run(
    cls: type, mocker: MockerFixture, sql: str, runs: bool
) -> None:
    """
    The loader's validator accepts any statement, so Poriscope checks it itself.
    """
    controller = _event_controller(cls, mocker, EVENTS)

    out = controller._run_raw_filter("ldr", sql, None, "mine_raw")

    assert (out is not None) == runs
    assert ("so it was not run" in _said(controller)) == (not runs)
    if not runs:
        assert controller.model.calls_to("query_database_directly") == []


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT experiment_id, channel_id, level_id AS event_id FROM sublevels", 1),
        ("SELECT experiment_id, channel_id, e.event_id AS event_id FROM events e", 0),
        ("SELECT experiment_id, channel_id, event_id FROM events", 0),
        ("select experiment_id, channel_id, (event_id + 1) as EVENT_ID from t", 1),
        ("SELECT f(a, b) AS event_id, experiment_id, channel_id FROM t", 1),
        (
            "SELECT CASE WHEN x > 1 THEN experiment_id END AS experiment_id, "
            "channel_id, event_id FROM events",
            1,
        ),
        (
            "SELECT experiment_id, channel_id, event_id FROM "
            "(SELECT experiment_id, channel_id, level_id AS event_id FROM sublevels)",
            1,
        ),
        ("SELECT duration AS d, experiment_id, channel_id, event_id FROM events", 0),
    ],
)
def test_a_key_column_made_by_renaming_another_is_found(
    sql: str, expected: int
) -> None:
    """
    ``level_id AS event_id`` is found, wherever it sits; the key itself, qualified or
    not, and renames of other columns are not.
    """
    assert len(relabelled_keys(sql)) == expected


# ------------------------------------------------------------------ event plots


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterLoadsItsOwnEvents:
    """
    A raw filter's events are the ones its event key names, for the selected channel.
    """

    def test_the_events_it_names_are_loaded_with_the_pair_it_ran_for(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Only event_id is returned: the query scoped itself, so the pair is known, and
        each event is listed once.
        """
        generator = iter([])
        controller = _event_controller(
            cls, mocker, EVENTS, IN_DATABASE, load_event_data=generator
        )

        fetched = controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw")

        assert controller.model.calls_to("load_event_data") == [
            (
                "(e.experiment_id = 7 AND e.channel_id = 2 AND e.event_id IN (10,11,12))",
                None,
            )
        ]
        assert fetched is not None and fetched[1] is generator
        assert fetched[0].endswith("experiment_id = 7 AND channel_id = 2")

    def test_what_was_selected_is_stated_on_the_panel(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A key that names other events than the user meant is then visible.
        """
        controller = _event_controller(cls, mocker, EVENTS, IN_DATABASE)

        controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw")

        assert "mine_raw: 3 events on exp1 Ch 2, event_id 10-12" in _said(controller)

    def test_a_query_that_returns_the_whole_key_needs_no_placeholders(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        It still ignores the selection, which is warned about, but its events are named.
        """
        controller = _event_controller(cls, mocker, WHOLE_KEY, IN_DATABASE)

        fetched = controller._fetch_event_subset("ldr", UNSCOPED, SCOPE, "mine_raw")

        assert fetched is not None
        assert "ignores the Scope selection" in _said(controller)

    def test_one_condition_per_experiment_and_channel_is_built(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Event ids repeat from channel to channel, so each channel's own are listed.
        """
        two_channels = pd.DataFrame(
            {"experiment_id": [7, 7], "channel_id": [2, 3], "event_id": [10, 10]}
        )
        controller = _event_controller(cls, mocker, two_channels, two_channels)

        controller._fetch_event_subset("ldr", UNSCOPED, SCOPE, "mine_raw")

        ((conditions, _),) = controller.model.calls_to("load_event_data")
        assert conditions.count("e.event_id IN") == 2
        assert " OR " in conditions

    def test_a_query_without_event_id_says_what_to_add(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing identifies an event, so nothing is guessed.
        """
        controller = _event_controller(
            cls, mocker, pd.DataFrame({"duration": [1.0, 2.0]})
        )
        without = SCOPED.replace("SELECT event_id", "SELECT duration", 1)

        assert controller._fetch_event_subset("ldr", without, SCOPE, "mine_raw") is None

        assert "does not return event_id" in _said(controller)
        assert "WHERE duration > 100 AND experiment_id = :experiment_id" in _said(
            controller
        )
        assert controller.model.calls_to("load_event_data") == []

    def test_an_id_column_is_not_what_names_an_event(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        ``id`` means a different row in each table, so a query that returns only it is
        told to return event_id instead.
        """
        controller = _event_controller(cls, mocker, pd.DataFrame({"id": [1, 2, 3]}))

        assert controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is None

        assert "does not return event_id" in _said(controller)

    def test_a_query_that_neither_scopes_itself_nor_returns_the_pair_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        event_id alone repeats from channel to channel, so its events cannot be placed.
        """
        controller = _event_controller(cls, mocker, EVENTS)
        sql = "SELECT event_id FROM events WHERE duration > 100"

        assert controller._fetch_event_subset("ldr", sql, SCOPE, "mine_raw") is None

        assert "cannot be placed" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_an_event_id_returned_twice_is_not_in_the_way(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A join returns the sublevel's key beside the event's, and the two are equal - a
        sublevel's key is its parent event's - so the first is used.
        """
        doubled = EVENTS.assign(**{"event_id:1": [10, 10, 11, 12]})
        controller = _event_controller(cls, mocker, doubled, IN_DATABASE)

        assert (
            controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is not None
        )

    def test_column_names_are_matched_without_regard_to_case(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        SQLite matches ``Event_ID`` to ``event_id``, so a query a viewer accepts is not
        refused for its capitals.
        """
        shouting = EVENTS.rename(columns={"event_id": "EVENT_ID"})
        controller = _event_controller(cls, mocker, shouting, IN_DATABASE)

        assert (
            controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is not None
        )

    def test_keys_that_name_no_event_are_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A column that is not an event's - a level number labelled ``event_id`` - names
        events the database does not have, and would load the wrong ones or none.
        """
        controller = _event_controller(cls, mocker, EVENTS, IN_DATABASE.iloc[0:1])

        assert controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is None

        assert "are not an event in the database" in _said(controller)

    def test_a_query_that_returns_no_events_says_so(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        An empty result is not an ``IN ()`` clause that loads everything or errors.
        """
        controller = _event_controller(cls, mocker, EVENTS.iloc[0:0])

        assert controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is None

        assert "no events" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_a_query_that_failed_validation_reports_it(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        ``query_database_directly`` answers None for a query it could not run.
        """
        controller = _event_controller(cls, mocker, None)

        assert (
            controller._fetch_event_subset("ldr", "SELECT", SCOPE, "mine_raw") is None
        )

        assert "mine_raw" in _said(controller)

    def test_an_assisted_filter_still_takes_the_scoped_path(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The suffix is the marker; an ordinary filter never touches the raw route.
        """
        generator = iter([])
        controller = _event_controller(cls, mocker, EVENTS, load_event_data=generator)

        fetched = controller._fetch_event_subset(
            "ldr", "duration < 300", SCOPE, "short events"
        )

        assert controller.model.calls_to("query_database_directly") == []
        assert controller.model.calls_to("load_event_data") == [
            ("duration < 300", SCOPE)
        ]
        assert fetched == ("SELECT generated", generator)

    @pytest.mark.parametrize(
        "bad",
        [[10.5, 11.0, 12.0, 13.0], ["a", "b", "c", "d"]],
        ids=["fraction", "text"],
    )
    def test_a_key_that_is_not_a_whole_number_is_refused(
        self, cls: type, mocker: MockerFixture, bad: list
    ) -> None:
        """
        An event number is a whole number. 10.5 would be cut to 10 and name another
        event, so it names none and the plot is refused.
        """
        controller = _event_controller(cls, mocker, pd.DataFrame({"event_id": bad}))

        assert controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is None

        assert "not a whole number" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_whole_numbers_held_as_floats_are_accepted(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A column with a NULL elsewhere arrives as floats; 10.0 is still event 10.
        """
        floats = pd.DataFrame({"event_id": [10.0, 10.0, 11.0, 12.0]})
        controller = _event_controller(cls, mocker, floats, IN_DATABASE)

        assert (
            controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw") is not None
        )

    def test_rows_with_a_null_key_are_counted_on_the_panel(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A NULL event_id names no event, so the row is left out - and the panel says so
        instead of dropping it silently.
        """
        nulls = pd.DataFrame({"event_id": [10.0, None, 11.0, None]})
        controller = _event_controller(cls, mocker, nulls, IN_DATABASE)

        controller._fetch_event_subset("ldr", SCOPED, SCOPE, "mine_raw")

        assert "2 row(s)" in _said(controller)
        assert "left out" in _said(controller)

    def test_a_relabelled_key_is_warned_about_and_still_plots(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing can check that a renamed column was meant, so it is a warning, not a
        refusal - and the events it names still load.
        """
        controller = _event_controller(cls, mocker, EVENTS, IN_DATABASE)
        sql = SCOPED.replace("SELECT event_id", "SELECT level_id AS event_id")

        assert controller._fetch_event_subset("ldr", sql, SCOPE, "mine_raw") is not None

        assert "labels 'level_id' as event_id" in _said(controller)


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterFillsTheEventNavigation:
    """
    Plot Events and the arrows read a list of ``event_id`` values; a raw query supplies it.
    """

    def test_the_event_ids_it_names_are_the_list(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        One entry per event, though a join repeats each once per sublevel, and the
        builder is never asked.
        """
        controller = _event_controller(cls, mocker, EVENTS, IN_DATABASE)

        controller.load_event_id_cache("ldr", SCOPED, SCOPE, "mine_raw")

        (rows,), _ = controller.view.set_event_id_rows.call_args
        assert rows["event_id"].tolist() == [10, 11, 12]
        assert controller.model.calls_to("load_metadata") == []

    def test_a_query_that_ignored_the_selection_is_cut_to_the_selected_pair(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The arrows step through the selected channel's events, whatever the query held.
        """
        several = pd.DataFrame(
            {
                "experiment_id": [7, 7, 7],
                "channel_id": [2, 3, 2],
                "event_id": [10, 20, 11],
            }
        )
        controller = _event_controller(cls, mocker, several, several)

        controller.load_event_id_cache("ldr", UNSCOPED, SCOPE, "mine_raw")

        (rows,), _ = controller.view.set_event_id_rows.call_args
        assert rows["event_id"].tolist() == [10, 11]

    def test_a_query_without_event_id_says_what_to_add(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing to navigate, so the View's answer stays unset and the panel says why.
        """
        controller = _event_controller(cls, mocker, pd.DataFrame({"duration": [1.0]}))

        controller.load_event_id_cache("ldr", SCOPED, SCOPE, "mine_raw")

        assert "does not return event_id" in _said(controller)
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_event_id_returned_twice_is_not_in_the_way(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A join's ``SELECT *`` returns the sublevel's ``event_id`` beside the event's, and
        they are equal.
        """
        doubled = EVENTS.assign(**{"event_id:1": [10, 10, 11, 12]})
        controller = _event_controller(cls, mocker, doubled, IN_DATABASE)

        controller.load_event_id_cache("ldr", SCOPED, SCOPE, "mine_raw")

        controller.view.set_event_id_rows.assert_called_once()

    def test_an_event_id_that_is_not_an_event_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The numbers exist, but the events table has no such event in that channel.
        """
        controller = _event_controller(cls, mocker, EVENTS, IN_DATABASE.iloc[0:1])

        controller.load_event_id_cache("ldr", SCOPED, SCOPE, "mine_raw")

        assert "are not an event in the database" in _said(controller)
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_assisted_filter_still_asks_the_builder(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The suffix is the marker; an ordinary filter never touches the raw route.
        """
        controller = _event_controller(cls, mocker, EVENTS)

        controller.load_event_id_cache("ldr", "duration > 1", SCOPE, "short events")

        assert controller.model.calls_to("query_database_directly") == []
        assert len(controller.model.calls_to("load_metadata")) == 1
        controller.view.set_event_id_rows.assert_called_once()


def test_the_two_tabs_share_one_projection() -> None:
    """
    The near-twin event-plot queries are one body now, and it projects ``id`` alone.

    The protein copy used to project ``id, event_id``, recorded in three places as
    being needed because its caller re-sorts the rows into the order it asked for
    them in. It is not: ``ProteinView._fetch_event_data`` sorts on the ``event_id``
    the loader reports with each event, against the indices it requested, so nothing
    ever read the extra column. Narrowing the projection and running the whole suite
    failed only assertions on the query text itself.

    That difference was the open question blocking the promotion, so this test
    inverts rather than disappearing: what is worth pinning now is that neither tab
    has grown a copy back.

    :return: None
    :rtype: None
    """
    shared = inspect.getsource(MetaSubsetTabModel.resolve_event_ids)

    assert "SELECT id FROM events WHERE" in shared
    assert "id, event_id" not in shared
    assert "resolve_event_ids" not in ProteinModel.__dict__
    assert "resolve_event_ids" not in MetadataModel.__dict__


def test_the_distribution_chain_still_loads_an_assisted_subset(
    mocker: MockerFixture,
) -> None:
    """
    Removing the branch must not have taken the ordinary path with it.

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :return: None
    :rtype: None
    """
    controller = ProteinController.__new__(ProteinController)  # type: ignore[type-abstract]
    controller.view = mocker.Mock()
    controller.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    controller.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    generator = iter([])
    controller.model = RecordingModel(
        {
            "construct_event_data_query": ("SELECT * FROM data", ""),
            "load_event_data": generator,
        }
    )

    controller.load_event_distribution_data(
        "ldr", "duration < 300", {"exp1": [2]}, "short events"
    )

    assert controller.model.calls_to("load_event_data") == [
        ("duration < 300", {"exp1": [2]})
    ]
    controller.view.set_event_query.assert_called_once_with("SELECT * FROM data")
    controller.view.set_event_data_generator.assert_called_once_with(generator)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT duration FROM events WHERE channel_id = :channel_id",
            "SELECT event_id, duration FROM events WHERE channel_id = :channel_id",
        ),
        (
            "  select duration, max_blockage from events;",
            "SELECT event_id, duration, max_blockage from events",
        ),
        (
            "SELECT 'group' AS label, duration FROM events -- union of nothing",
            "SELECT event_id, 'group' AS label, duration FROM events -- union of nothing",
        ),
    ],
)
def test_a_one_row_per_event_query_gets_event_id_suggested_first(
    sql: str, expected: str
) -> None:
    """
    The suggestion keeps the user's text and placeholders as written, and words that sit
    inside a string or a comment do not count as ``GROUP`` or ``UNION``.
    """
    assert with_event_id(sql) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT DISTINCT duration FROM events",
        "SELECT AVG(duration) FROM events GROUP BY channel_id",
        "SELECT duration FROM events UNION SELECT duration FROM events",
        "WITH x AS (SELECT 1) SELECT duration FROM events",
        "SELECT e.duration FROM events e JOIN sublevels s ON s.event_db_id = e.id",
        "SELECT * FROM events",
        "DELETE FROM events",
    ],
)
def test_no_event_id_is_suggested_where_it_would_change_the_rows(sql: str) -> None:
    """
    The shapes that are not one row per event are never offered a rewrite.
    """
    assert with_event_id(sql) is None


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
def test_the_missing_event_id_message_shows_the_users_query_with_it_added(
    cls: type, mocker: MockerFixture
) -> None:
    """
    A plain filter is told exactly what to type, and a ``DISTINCT`` one is not.
    """
    plain = "SELECT duration FROM events WHERE experiment_id = :experiment_id AND channel_id = :channel_id"
    controller = _event_controller(cls, mocker, pd.DataFrame({"duration": [1.0]}))

    assert controller._fetch_event_subset("ldr", plain, SCOPE, "mine_raw") is None
    assert f"Try: SELECT event_id, {plain[len('SELECT '):]}" in _said(controller)

    distinct = plain.replace("SELECT ", "SELECT DISTINCT ")
    controller = _event_controller(cls, mocker, pd.DataFrame({"duration": [1.0]}))

    assert controller._fetch_event_subset("ldr", distinct, SCOPE, "mine_raw") is None
    assert "Try:" not in _said(controller)
    assert "DISTINCT, GROUP BY" in _said(controller)
