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


RAW = "SELECT id, experiment_id, channel_id FROM events WHERE duration > 100"
SCOPE = {"exp1": [2]}
FRAME = pd.DataFrame({"id": [4, 9, 4], "experiment_id": [7] * 3, "channel_id": [2] * 3})


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterLoadsItsOwnEvents:
    """
    A raw filter's events are the ones its ``id`` column names within the selection.
    """

    @staticmethod
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
            "query_database_directly": FRAME,
            "construct_event_data_query": ("SELECT generated", ""),
            "load_event_data": iter([]),
            **overrides,
        }

    def test_the_ids_it_returns_within_the_selection_are_loaded(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The query is wrapped in the selection, and the events it names are loaded by id
        with no further scope.
        """
        generator = iter([])
        controller = _controller(cls, mocker, self.answers(load_event_data=generator))

        fetched = controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        _, (executed,), check = controller.model.calls_to("query_database_directly")
        assert check[0].startswith("SELECT id, experiment_id, channel_id FROM events")
        assert RAW in executed
        assert executed.endswith("WHERE (experiment_id = 7 AND channel_id IN (2))")
        assert controller.model.calls_to("load_event_data") == [("e.id IN (4,9)", None)]
        assert fetched == (executed, generator)

    def test_a_query_without_the_scope_columns_says_what_to_add(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The selection cannot be applied to it, so it is not run over everything.
        """
        controller = _controller(
            cls,
            mocker,
            self.answers(query_database_directly=pd.DataFrame({"id": [1]})),
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "experiment_id and channel_id" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_a_query_without_an_id_column_says_how_to_fix_it(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        Nothing to load, so nothing is guessed: the message names the column and shows
        the shape of the fix.
        """
        controller = _controller(
            cls,
            mocker,
            self.answers(
                query_database_directly=FRAME.drop(columns=["id"]),
            ),
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "mine_raw" in _said(controller)
        assert "SELECT id" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_an_id_returned_twice_is_refused_naming_the_fix(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A join's ``SELECT *`` returns both tables' ``id``; wrapped, SQLite renames the
        second ``id:1`` and the first would be read silently, so nothing is loaded.
        """
        doubled = FRAME.assign(**{"id:1": [1, 2, 3]})
        controller = _controller(
            cls, mocker, self.answers(query_database_directly=doubled)
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "id more than once" in _said(controller)
        assert "AS id" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_a_duplicated_scope_column_is_not_in_the_way(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        ``experiment_id`` in both tables holds the same value, and only ``id`` is read.
        """
        generator = iter([])
        doubled = FRAME.assign(**{"experiment_id:1": [7] * 3})
        controller = _controller(
            cls,
            mocker,
            self.answers(query_database_directly=doubled, load_event_data=generator),
        )

        fetched = controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        assert fetched is not None

    def test_an_id_that_is_not_the_events_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The query claims these ids are events of experiment 7 channel 2, and the events
        table says otherwise - the ``id`` is another table's, and would load the wrong
        events without a word.
        """
        controller = _controller(cls, mocker, self.answers())
        events_table = pd.DataFrame(
            {"id": [4, 9], "experiment_id": [7, 7], "channel_id": [1, 1]}
        )
        answers = iter([FRAME, FRAME, events_table])
        controller.model.call = lambda *a: (
            next(answers) if a[2] == "query_database_directly" else 7
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "column does not hold the events' id values" in _said(controller)
        assert "e.id AS id" in _said(controller)

    def test_an_id_with_no_event_at_all_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A sublevel's id can be larger than any event's.
        """
        controller = _controller(cls, mocker, self.answers())
        answers = iter([FRAME, FRAME, FRAME.iloc[0:0]])
        controller.model.call = lambda *a: (
            next(answers) if a[2] == "query_database_directly" else 7
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "column does not hold the events' id values" in _said(controller)

    def test_a_query_that_returns_no_events_says_so(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        An empty result is not an ``IN ()`` clause that loads everything or errors.
        """
        controller = _controller(
            cls,
            mocker,
            self.answers(query_database_directly=FRAME.iloc[0:0]),
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
        controller = _controller(
            cls, mocker, self.answers(query_database_directly=None)
        )

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
        controller = _controller(cls, mocker, self.answers(load_event_data=generator))

        fetched = controller._fetch_event_subset(
            "ldr", "duration < 300", SCOPE, "short events"
        )

        assert controller.model.calls_to("query_database_directly") == []
        assert controller.model.calls_to("load_event_data") == [
            ("duration < 300", SCOPE)
        ]
        assert fetched == ("SELECT generated", generator)


EVENT_FRAME = pd.DataFrame(
    {"experiment_id": [7] * 4, "channel_id": [2] * 4, "event_id": [10, 10, 11, 12]}
)


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterFillsTheEventNavigation:
    """
    Plot Events and the arrows read a list of ``event_id`` values; a raw query supplies it.
    """

    @staticmethod
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
            "query_database_directly": EVENT_FRAME,
            "load_metadata": pd.DataFrame({"event_id": [1, 2]}),
            **overrides,
        }

    def test_the_event_ids_it_returns_within_the_selection_are_the_list(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        One entry per event, though a join repeats each once per sublevel, and the
        builder is never asked.
        """
        controller = _controller(cls, mocker, self.answers())

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        (rows,), _ = controller.view.set_event_id_rows.call_args
        assert rows["event_id"].tolist() == [10, 11, 12]
        assert controller.model.calls_to("load_metadata") == []
        _, (final,), _ = controller.model.calls_to("query_database_directly")
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
            self.answers(
                query_database_directly=EVENT_FRAME.drop(columns=["event_id"])
            ),
        )

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        assert "event_id" in _said(controller)
        assert "SELECT experiment_id, channel_id, event_id" in _said(controller)
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_event_id_returned_twice_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        A join's ``SELECT *`` returns the sublevel's ``event_id`` beside the event's.
        """
        controller = _controller(
            cls,
            mocker,
            self.answers(
                query_database_directly=EVENT_FRAME.assign(**{"event_id:1": [1] * 4})
            ),
        )

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        assert "event_id more than once" in _said(controller)
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_event_id_that_is_not_the_events_is_refused(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The numbers exist, but the events table has no such event in that channel.
        """
        controller = _controller(cls, mocker, self.answers())
        answers = iter([EVENT_FRAME, EVENT_FRAME, EVENT_FRAME.iloc[0:1]])
        controller.model.call = lambda *a: (
            next(answers) if a[2] == "query_database_directly" else 7
        )

        controller.load_event_id_cache("ldr", RAW, SCOPE, "mine_raw")

        assert "event_id column does not hold the events' event_id values" in _said(
            controller
        )
        controller.view.set_event_id_rows.assert_not_called()

    def test_an_assisted_filter_still_asks_the_builder(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The suffix is the marker; an ordinary filter never touches the raw route.
        """
        controller = _controller(cls, mocker, self.answers())

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
