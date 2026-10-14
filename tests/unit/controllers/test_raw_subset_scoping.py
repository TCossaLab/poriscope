"""
How raw SQL subset filters meet the event-data plots and the event navigation.

A raw filter is a complete ``SELECT``, which cannot be spliced where
``load_event_data`` expects a WHERE-clause body - measured against a real
``SQLiteDBLoader``, the same filter as an ordinary body yields every event and as a raw
``SELECT`` yields none, silently. So the plots that load traces run the raw query
restricted to the experiment and channel selection, and load the events its ``id`` column
names; the navigation (Plot Events, the arrows) takes its list of ``event_id`` values
from the query instead of from the query builder. What these tests pin is those two
routes and their failures.

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
from poriscope.utils.MetaSubsetTabController import relabelled_keys
from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel
from tests.unit.controllers._recording_model import RecordingModel

pytestmark = pytest.mark.characterization


def _controller(cls: type, mocker: MockerFixture, answers: dict) -> Any:
    """
    A bare Controller of the given class with a recording Model and a mocked View.

    :param cls: MetadataController or ProteinController
    :type cls: type
    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :param answers: plugin method name to canned answer
    :type answers: dict
    :return: the controller under test
    :rtype: Any
    """
    controller = cls.__new__(cls)
    controller.view = mocker.Mock()
    controller.logger = mocker.Mock()
    controller.add_text_to_display = mocker.Mock()
    controller.model = RecordingModel(answers)
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


RAW = "SELECT experiment_id, channel_id, event_id FROM events WHERE duration > 100"
SCOPE = {"exp1": [2]}
#: A join repeats each event once per sublevel, so the same key arrives several times.
KEYS = pd.DataFrame(
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
        "query_database_directly": KEYS,
        "construct_event_data_query": ("SELECT generated", ""),
        "load_event_data": iter([]),
        "load_metadata": pd.DataFrame({"event_id": [1, 2]}),
        **overrides,
    }


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterLoadsItsOwnEvents:
    """
    A raw filter's events are the ones its event key names within the selection.
    """

    def test_the_events_it_names_within_the_selection_are_loaded(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The query is wrapped in the selection, and the events are found from their key
        with no further scope, each listed once.
        """
        generator = iter([])
        controller = _controller(cls, mocker, answers(load_event_data=generator))

        fetched = controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        _, (executed,), *_ = controller.model.calls_to("query_database_directly")
        assert RAW in executed
        assert executed.endswith("WHERE (experiment_id = 7 AND channel_id IN (2))")
        assert controller.model.calls_to("load_event_data") == [
            (
                "(e.experiment_id = 7 AND e.channel_id = 2 AND e.event_id IN (10,11,12))",
                None,
            )
        ]
        assert fetched == (executed, generator)

    def test_one_condition_per_experiment_and_channel_is_built(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Event ids repeat from channel to channel, so each channel's own are listed.
        """
        two_channels = pd.DataFrame(
            {
                "experiment_id": [7, 7],
                "channel_id": [2, 3],
                "event_id": [10, 10],
            }
        )
        controller = _controller(
            cls, mocker, answers(query_database_directly=two_channels)
        )

        controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        ((conditions, _),) = controller.model.calls_to("load_event_data")
        assert conditions.count("e.event_id IN") == 2
        assert " OR " in conditions

    def test_a_query_without_the_event_key_says_what_to_add(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing identifies an event, so nothing is guessed: the message names what is
        missing and shows the shape of the fix.
        """
        controller = _controller(
            cls,
            mocker,
            answers(query_database_directly=KEYS.drop(columns=["event_id"])),
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "event_id" in _said(controller)
        assert "SELECT experiment_id, channel_id, event_id" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_an_id_column_is_not_what_names_an_event(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        ``id`` means a different row in each table, so a query that returns only it is
        told to return the event key instead.
        """
        controller = _controller(
            cls,
            mocker,
            answers(
                query_database_directly=KEYS.drop(columns=["event_id"]).assign(
                    id=[1, 2, 3, 4]
                )
            ),
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "event_id" in _said(controller)

    def test_an_event_key_returned_twice_is_not_in_the_way(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A join returns the sublevel's key beside the event's, and the two are equal -
        a sublevel's key is its parent event's - so the first is used.
        """
        generator = iter([])
        doubled = KEYS.assign(**{"event_id:1": [10, 10, 11, 12]})
        controller = _controller(
            cls,
            mocker,
            answers(query_database_directly=doubled, load_event_data=generator),
        )

        fetched = controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        assert fetched is not None

    def test_column_names_are_matched_without_regard_to_case(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        SQLite matches ``Event_ID`` to ``event_id``, so a query a viewer accepts is not
        refused for its capitals.
        """
        shouting = KEYS.rename(columns={"event_id": "EVENT_ID"})
        controller = _controller(cls, mocker, answers())
        replies = iter([shouting, shouting, shouting, KEYS])
        controller.model.call = lambda *a: (
            next(replies)
            if a[2] == "query_database_directly"
            else {
                "get_experiment_id_by_name": 7,
                "construct_event_data_query": ("SELECT generated", ""),
            }.get(a[2], iter([]))
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is not None

    def test_keys_that_name_no_event_are_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A column that is not an event's - a level number labelled ``event_id`` - names
        events the database does not have, and would load the wrong ones or none.
        """
        controller = _controller(cls, mocker, answers())
        replies = iter([KEYS, KEYS, KEYS, KEYS.iloc[0:1]])
        controller.model.call = lambda *a: (
            next(replies) if a[2] == "query_database_directly" else 7
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "are not an event in the database" in _said(controller)

    def test_a_query_that_returns_no_events_says_so(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        An empty result is not an ``IN ()`` clause that loads everything or errors.
        """
        controller = _controller(
            cls, mocker, answers(query_database_directly=KEYS.iloc[0:0])
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "no events" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_a_query_that_failed_validation_reports_it(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        ``query_database_directly`` answers None for a query it could not run.
        """
        controller = _controller(cls, mocker, answers(query_database_directly=None))

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
        controller = _controller(cls, mocker, answers(load_event_data=generator))

        fetched = controller._fetch_event_subset(
            "ldr", "duration < 300", SCOPE, "short events"
        )

        assert controller.model.calls_to("query_database_directly") == []
        assert controller.model.calls_to("load_event_data") == [
            ("duration < 300", SCOPE)
        ]
        assert fetched == ("SELECT generated", generator)


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


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterKeyWarnings:
    """
    What a raw filter's event key can get wrong without the database noticing.
    """

    def test_a_relabelled_key_is_warned_about_and_still_plots(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing can check that a renamed column was meant, so it is a warning, not a
        refusal - and the events it names still load.
        """
        generator = iter([])
        controller = _controller(cls, mocker, answers(load_event_data=generator))
        sql = "SELECT experiment_id, channel_id, level_id AS event_id FROM sublevels"

        fetched = controller._fetch_event_subset("ldr", sql, SCOPE, "mine_raw")

        assert fetched is not None
        assert "labels 'level_id' as event_id" in _said(controller)

    def test_a_key_that_is_not_relabelled_says_nothing(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        No warning for the ordinary query.
        """
        controller = _controller(cls, mocker, answers())

        controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        assert "labels" not in _said(controller)

    def test_rows_with_a_null_key_are_counted_on_the_panel(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A NULL event_id names no event, so the row is left out - and the panel says so
        instead of dropping it silently.
        """
        with_nulls = KEYS.copy()
        with_nulls["event_id"] = [10.0, None, 11.0, None]
        controller = _controller(cls, mocker, answers())
        # probe, run, NULL count, then the events table's own answer for the key check
        replies = iter([with_nulls, with_nulls, with_nulls, KEYS])
        controller.model.call = lambda *a: (
            next(replies)
            if a[2] == "query_database_directly"
            else {
                "get_experiment_id_by_name": 7,
                "construct_event_data_query": ("SELECT generated", ""),
            }.get(a[2], iter([]))
        )

        controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        assert "2 row(s)" in _said(controller)
        assert "left out" in _said(controller)

    def test_no_null_key_means_no_message(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The count is only worth a line when it is above zero.
        """
        controller = _controller(cls, mocker, answers())

        controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        assert "left out" not in _said(controller)


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterFillsTheEventNavigation:
    """
    Plot Events and the arrows read a list of ``event_id`` values; a raw query supplies it.
    """

    def test_the_event_ids_it_names_within_the_selection_are_the_list(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        One entry per event, though a join repeats each once per sublevel, and the
        builder is never asked.
        """
        controller = _controller(cls, mocker, answers())

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        (rows,), _ = controller.view.set_event_id_rows.call_args
        assert rows["event_id"].tolist() == [10, 11, 12]
        assert controller.model.calls_to("load_metadata") == []
        _, (final,), *_ = controller.model.calls_to("query_database_directly")
        assert final.endswith("WHERE (experiment_id = 7 AND channel_id IN (2))")

    def test_a_query_without_event_id_says_what_to_add(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing to navigate, so the View's answer stays unset and the panel says why.
        """
        controller = _controller(
            cls,
            mocker,
            answers(query_database_directly=KEYS.drop(columns=["event_id"])),
        )

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        assert "event_id" in _said(controller)
        assert "SELECT experiment_id, channel_id, event_id" in _said(controller)
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_event_id_returned_twice_is_not_in_the_way(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A join's ``SELECT *`` returns the sublevel's ``event_id`` beside the event's, and
        they are equal.
        """
        controller = _controller(
            cls,
            mocker,
            answers(
                query_database_directly=KEYS.assign(**{"event_id:1": [10, 10, 11, 12]})
            ),
        )

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        controller.view.set_event_id_rows.assert_called_once()

    def test_an_event_id_that_is_not_an_event_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The numbers exist, but the events table has no such event in that channel.
        """
        controller = _controller(cls, mocker, answers())
        replies = iter([KEYS, KEYS, KEYS, KEYS.iloc[0:1]])
        controller.model.call = lambda *a: (
            next(replies) if a[2] == "query_database_directly" else 7
        )

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        assert "are not an event in the database" in _said(controller)
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_assisted_filter_still_asks_the_builder(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The suffix is the marker; an ordinary filter never touches the raw route.
        """
        controller = _controller(cls, mocker, answers())

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
