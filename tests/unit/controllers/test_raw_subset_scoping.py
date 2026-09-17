"""
Raw SQL subset filters are refused before a plot is attempted.

This module used to pin ``ProteinController._scope_raw_subset_query`` - the string
surgery that appended an experiment and channel scope to a user's raw ``SELECT`` - and
before that, the same code as ``ProteinView._build_load_event_data_args``. All of it is
gone, because measurement showed **the route it served could never produce a plot**:

    >>> loader.load_event_data("SELECT * FROM events WHERE duration > 0", None)

``load_event_data`` passes its ``conditions`` argument to
``construct_event_data_query``, which splices it in after ``WHERE``. A complete
``SELECT`` therefore produced ``WHERE SELECT * FROM events WHERE ...``, SQLite rejected
it as ``near "SELECT": syntax error``, the builder reported that by returning an empty
query, and the generator yielded nothing - silently. Measured against a real
``SQLiteDBLoader`` over a synthetic database: the same filter as an ordinary
WHERE-clause body yields every event, and as a raw ``SELECT`` yields none.

So there was nothing to convert and nothing to fix in place. What replaces it is a
refusal at the plot entry points, which is what these tests pin, plus the assertion
that the dead branch has not come back.

The projection comparison at the bottom used to assert that the two tabs' event-plot
chains authored *different* queries. They do not any more: the chain is one body on
``MetaSubsetTabModel``, and the test now pins that.
"""

import inspect

import pytest
from pytest_mock import MockerFixture

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
    The guard that replaced the branch, shared by both subset tabs.
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
        assert "cannot be used for plotting" in said(view)

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

    Derived rather than listed: every method that reads the selected filters and can
    begin a plot must consult it, so a new plot path cannot quietly skip it. The
    nested helpers those methods call are covered by their callers.
    """

    ENTRY_POINTS = {
        "poriscope.plugins.analysistabs.MetadataView": [
            "_overlay_plot",
            "_handle_plot_events",
        ],
        "poriscope.plugins.analysistabs.ProteinView": [
            "_handle_plot_events",
            "_handle_plot_histogram",
            "_update_distribution_individual",
            "_update_distribution_ensemble",
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


def test_the_dead_raw_branch_has_not_come_back() -> None:
    """
    The branch was removed because it could not work, not because it was untidy.

    Re-adding an ``endswith("_raw")`` route in the distribution chain would restore a
    path that hands a complete SELECT where a WHERE-clause body is expected - so this
    names the measurement rather than the style rule.

    :return: None
    :rtype: None
    """
    source = inspect.getsource(ProteinController.load_event_distribution_data)

    assert "_raw" not in source.split('"""')[2], (
        "load_event_distribution_data has regained a raw-filter branch; "
        "load_event_data takes a WHERE-clause body, so a complete SELECT cannot work"
    )
    assert not hasattr(ProteinController, "_scope_raw_subset_query")


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

    controller.load_event_distribution_data("ldr", "duration < 300", {"exp1": [2]})

    assert controller.model.calls_to("load_event_data") == [
        ("duration < 300", {"exp1": [2]})
    ]
    controller.view.set_event_query.assert_called_once_with("SELECT * FROM data")
    controller.view.set_event_data_generator.assert_called_once_with(generator)
