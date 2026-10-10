"""
How raw SQL subset filters meet the event-data plots.

A raw filter is a complete ``SELECT``, which cannot be spliced where
``load_event_data`` expects a WHERE-clause body - measured against a real
``SQLiteDBLoader``, the same filter as an ordinary body yields every event and as a raw
``SELECT`` yields none, silently. So the plots that load traces run the raw query as
written, unscoped, and load the events its ``id`` column names; what these tests pin is
that route, its failures, and the one place a raw filter is still refused: the plots
that step through individual events by ``event_id``, which only means something within
one experiment and channel.

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
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel
from tests.unit.controllers._recording_model import RecordingModel
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization


@pytest.fixture
def view(qapp: object) -> ProteinView:
    """
    A subset-tab View with its signals shadowed, for the refusal guard.

    :param qapp: the QApplication the view fixture needs
    :type qapp: object
    :return: the view under test
    :rtype: ProteinView
    """
    instance = ProteinView.__new__(ProteinView)
    shadow_signals(instance, ProteinView)
    return instance


def said(view: ProteinView) -> str:
    """
    Everything the view put on the status panel, joined.

    :param view: the view under test
    :type view: ProteinView
    :return: the concatenated message text
    :rtype: str
    """
    return "\n".join(
        call.args[0] for call in view.add_text_to_display.emit.call_args_list
    )


class TestRawFiltersAreRefused:
    """
    The guard on the event-by-event plots, shared by both subset tabs.
    """

    def test_an_assisted_filter_is_allowed_through(self, view: ProteinView) -> None:
        """
        The ordinary case must not pay for the guard, and must say nothing.

        :param view: the view under test
        :type view: ProteinView
        """
        assert view._refuse_raw_filters({"short events": "duration < 300"}) is False
        view.add_text_to_display.emit.assert_not_called()

    def test_no_filter_at_all_is_allowed_through(self, view: ProteinView) -> None:
        """
        Plotting the whole dataset is not a filter, raw or otherwise.

        :param view: the view under test
        :type view: ProteinView
        """
        assert view._refuse_raw_filters({}) is False

    def test_a_raw_filter_is_refused_and_named(self, view: ProteinView) -> None:
        """
        Named, because the user has to know which one to deselect - the combobox can
        hold several and only some of them are raw.

        :param view: the view under test
        :type view: ProteinView
        """
        assert view._refuse_raw_filters({"mine_raw": "SELECT * FROM events"}) is True
        assert "mine_raw" in said(view)
        assert "step through individual events" in said(view)

    def test_one_raw_filter_among_several_refuses_the_plot(
        self, view: ProteinView
    ) -> None:
        """
        Refusing only the raw one and plotting the rest would silently plot something
        other than what was selected, which is the fault class this whole step exists
        to remove.

        :param view: the view under test
        :type view: ProteinView
        """
        selected = {"short events": "duration < 300", "mine_raw": "SELECT 1"}

        assert view._refuse_raw_filters(selected) is True
        assert "mine_raw" in said(view)

    def test_a_name_merely_containing_raw_is_not_refused(
        self, view: ProteinView
    ) -> None:
        """
        The marker is the suffix the filter dialog appends, not the word. A filter
        called "raw current" is an ordinary assisted filter.

        :param view: the view under test
        :type view: ProteinView
        """
        assert view._refuse_raw_filters({"raw current": "x > 1"}) is False
        assert view._refuse_raw_filters({"my_raw_events": "x > 1"}) is False


class TestEveryPlotEntryPointAsks:
    """
    The guard is only worth anything where a plot actually starts.

    Every method that looks events up by ``event_id`` must consult it. The overlay,
    all-points and distribution plots are not here: they run a raw filter, through
    ``_fetch_event_subset``.
    """

    ENTRY_POINTS = {
        "poriscope.plugins.analysistabs.MetadataView": ["_handle_plot_events"],
        "poriscope.plugins.analysistabs.ProteinView": [
            "_handle_plot_events",
            "_handle_plot_histogram",
        ],
    }

    @pytest.mark.parametrize(
        ("module_name", "method_name"),
        [
            (module, method)
            for module, methods in ENTRY_POINTS.items()
            for method in methods
        ],
    )
    def test_the_entry_point_consults_the_guard(
        self, module_name: str, method_name: str
    ) -> None:
        """
        :param module_name: the tab View module the entry point lives in
        :type module_name: str
        :param method_name: the entry point
        :type method_name: str
        """
        import importlib

        module = importlib.import_module(module_name)
        view_cls = getattr(module, module_name.rsplit(".", 1)[-1])
        source = inspect.getsource(getattr(view_cls, method_name))

        assert "_refuse_raw_filters" in source, (
            f"{module_name}.{method_name} starts a plot from the selected filters "
            "without asking whether any of them is raw"
        )


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


RAW = "SELECT id, duration FROM events WHERE duration > 100"
SCOPE = {"exp1": [2]}


@pytest.mark.parametrize("cls", [MetadataController, ProteinController])
class TestRawFilterLoadsItsOwnEvents:
    """
    A raw filter's events are the ones its ``id`` column names, whatever the scope.
    """

    def test_the_ids_it_returns_are_loaded_unscoped(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        The query runs as written, and the events are loaded by id with no scope.
        """
        generator = iter([])
        controller = _controller(
            cls,
            mocker,
            {
                "query_database_directly": pd.DataFrame(
                    {"id": [4, 9, 4], "duration": [1.0, 2.0, 1.0]}
                ),
                "construct_event_data_query": ("SELECT generated", ""),
                "load_event_data": generator,
            },
        )

        fetched = controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw")

        assert controller.model.calls_to("query_database_directly") == [(RAW,)]
        assert controller.model.calls_to("load_event_data") == [("e.id IN (4,9)", None)]
        assert fetched == (RAW, generator)

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
            {"query_database_directly": pd.DataFrame({"duration": [1.0]})},
        )

        assert controller._fetch_event_subset("ldr", RAW, SCOPE, "mine_raw") is None

        assert "mine_raw" in _said(controller)
        assert "SELECT id" in _said(controller)
        assert controller.model.calls_to("load_event_data") == []

    def test_a_query_that_returns_no_events_says_so(
        self, cls: type, mocker: MockerFixture
    ) -> None:
        """
        An empty result is not an ``IN ()`` clause that loads everything or errors.
        """
        controller = _controller(
            cls,
            mocker,
            {"query_database_directly": pd.DataFrame({"id": []})},
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
        controller = _controller(cls, mocker, {"query_database_directly": None})

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
        controller = _controller(
            cls,
            mocker,
            {
                "construct_event_data_query": ("SELECT generated", ""),
                "load_event_data": generator,
            },
        )

        fetched = controller._fetch_event_subset(
            "ldr", "duration < 300", SCOPE, "short events"
        )

        assert controller.model.calls_to("query_database_directly") == []
        assert controller.model.calls_to("load_event_data") == [
            ("duration < 300", SCOPE)
        ]
        assert fetched == ("SELECT generated", generator)


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
