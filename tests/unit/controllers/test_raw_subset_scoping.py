"""
Characterization tests for the scope clause a raw SQL subset gets appended to it.

Was ``tests/unit/views/test_view_authored_sql.py``. Step 4a moved this string surgery
out of ``ProteinView._build_load_event_data_args`` and into
``ProteinController._scope_raw_subset_query``, so the module moved with it - the SQL is
not authored in a View any more, which was the premise of the old name.

``_scope_raw_subset_query`` takes a user's raw SQL filter and appends a scope clause to
it by string surgery, choosing between ``AND`` and ``WHERE`` on a bare
``"WHERE" in query.upper()`` test. That test is wrong for any filter whose only
``WHERE`` sits inside a subquery or a string literal - exactly the case
``MetaDatabaseLoader._split_on_opaque_spans`` exists to handle, and which this path does
not use. The mis-fire is pinned below as current behaviour and queued in
``future_fixes.md``; **this file records what the code does, it does not endorse it**.

Two of the old tests pinned behaviour this step deliberately changed. A scope lookup
that failed used to leave the filter unscoped, which silently widened a raw query to
the whole database; it stops the plot now. Those two are rewritten rather than moved,
and named for what they assert.

Step 4b moves this into ``MetaDatabaseLoader``, which is what these tests exist to make
safe.
"""

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ProteinController import ProteinController
from tests.unit.controllers._recording_model import RecordingModel

pytestmark = pytest.mark.characterization


@pytest.fixture
def controller(mocker: MockerFixture) -> ProteinController:
    """
    A ``ProteinController`` whose loader answers the two id lookups.

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :return: the controller under test
    :rtype: ProteinController
    """
    ctrl = ProteinController.__new__(ProteinController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.model = RecordingModel(
        {"get_experiment_id_by_name": 7, "get_channel_db_id": 3}
    )
    return ctrl


def scope(controller: ProteinController, sql_filter: str, exp="exp1"):
    """
    Scope a raw filter with the arguments a plot request supplies.

    :param controller: the controller under test
    :type controller: ProteinController
    :param sql_filter: the user's filter text
    :type sql_filter: str
    :param exp: the experiment name, or None
    :type exp: Any
    :return: the scoped query, or None if the scope could not be resolved
    :rtype: Optional[str]
    """
    return controller._scope_raw_subset_query("loader", sql_filter, exp, 2)


def panel_text(controller: ProteinController) -> str:
    """
    Everything the controller put on the status panel, joined.

    :param controller: the controller under test
    :type controller: ProteinController
    :return: the concatenated message text
    :rtype: str
    """
    return "\n".join(
        call.args[0] for call in controller.add_text_to_display.emit.call_args_list
    )


class TestOnlyRawSubsetsTakeThisPath:
    """A managed subset never reaches the string surgery at all."""

    def test_a_named_subset_is_handed_to_the_query_builder(
        self, controller: ProteinController
    ) -> None:
        """
        The loader does the scoping itself for a managed subset, so the filter goes
        to ``construct_event_data_query`` with its scope alongside it.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {
                "construct_event_data_query": ("SELECT * FROM data", ""),
                "load_event_data": iter([]),
            }
        )

        controller.load_event_distribution_data(
            "loader", "duration > 5", "mine", "exp1", 2, {"exp1": [2]}
        )

        assert controller.model.calls_to("construct_event_data_query") == [
            ("duration > 5", {"exp1": [2]})
        ]
        assert controller.model.calls_to("load_event_data") == [
            ("duration > 5", {"exp1": [2]})
        ]
        assert controller.model.calls_to("get_experiment_id_by_name") == []

    def test_a_raw_subset_runs_its_own_scoped_query_instead(
        self, controller: ProteinController
    ) -> None:
        """
        The filter is already a complete SELECT, so it is scoped and run as it
        stands - ``construct_event_data_query`` is never asked, and the scope travels
        in the SQL rather than as a separate argument.

        Also the fix for what the tab *shows*: the View used to display the
        constructed query while loading through the scoped raw one.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {
                "get_experiment_id_by_name": 7,
                "get_channel_db_id": 3,
                "load_event_data": iter([]),
            }
        )

        controller.load_event_distribution_data(
            "loader",
            "SELECT * FROM events",
            "mine_raw",
            "exp1",
            2,
            {"exp1": [2]},
        )

        expected = (
            "SELECT * FROM events WHERE experiment_id = 7 AND channel_db_id = 3"
        )
        assert controller.model.calls_to("construct_event_data_query") == []
        assert controller.model.calls_to("load_event_data") == [(expected, None)]
        controller.view.set_event_query.assert_called_once_with(expected)


class TestRawSubsetScoping:
    """The ``_raw`` path appends an experiment and channel scope by hand."""

    def test_a_filter_without_where_gains_one(
        self, controller: ProteinController
    ) -> None:
        """
        The common case, and the reason the branch exists.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(controller, "duration > 5") == (
            "duration > 5 WHERE experiment_id = 7 AND channel_db_id = 3"
        )

    def test_a_filter_with_where_gains_an_and(
        self, controller: ProteinController
    ) -> None:
        """
        The other branch of the same choice.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(controller, "SELECT * FROM events WHERE duration > 5") == (
            "SELECT * FROM events WHERE duration > 5 "
            "AND experiment_id = 7 AND channel_db_id = 3"
        )

    def test_a_trailing_semicolon_is_stripped_before_appending(
        self, controller: ProteinController
    ) -> None:
        """
        Otherwise the scope would land after the statement terminator.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(controller, "duration > 5;") == (
            "duration > 5 WHERE experiment_id = 7 AND channel_db_id = 3"
        )

    def test_surrounding_whitespace_is_stripped(
        self, controller: ProteinController
    ) -> None:
        """
        Users paste filters with stray newlines.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(controller, "  duration > 5  \n").startswith("duration > 5 WHERE")

    def test_no_experiment_means_no_scope_is_appended(
        self, controller: ProteinController
    ) -> None:
        """
        Nothing to scope to, so the filter is returned as the user wrote it, and
        neither lookup is made.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(controller, "duration > 5;", exp=None) == "duration > 5"
        assert controller.model.calls == []


class TestAnUnresolvableScopeStopsThePlot:
    """
    The behaviour this step changed, and why.

    The View appended the scope only when **both** lookups had answered, and returned
    the filter unscoped otherwise - so a lookup the bus had swallowed silently widened
    a raw query from one channel to the whole database. That is the same class of
    fault as the unscoped event-id query, and it is reported now.
    """

    def test_an_experiment_that_does_not_resolve_refuses_the_scope(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"get_experiment_id_by_name": None, "get_channel_db_id": 3}
        )

        assert scope(controller, "duration > 5") is None
        assert "could not place experiment exp1" in panel_text(controller)

    def test_a_partial_lookup_refuses_too(
        self, controller: ProteinController
    ) -> None:
        """
        Both ids are required; one alone would scope to the wrong rows, and the old
        guard being a conjunction is what made a partial answer look like no answer.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"get_experiment_id_by_name": 7, "get_channel_db_id": None}
        )

        assert scope(controller, "duration > 5") is None
        assert "could not place experiment exp1" in panel_text(controller)

    def test_a_lookup_that_raises_is_reported(
        self, controller: ProteinController
    ) -> None:
        """
        The bus swallowed this entirely; ``call()`` raises where it happens.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"get_experiment_id_by_name": RuntimeError("db gone")}
        )

        assert scope(controller, "duration > 5") is None
        assert "Could not scope this raw filter" in panel_text(controller)

    def test_nothing_is_loaded_when_the_scope_is_refused(
        self, controller: ProteinController
    ) -> None:
        """
        The refusal has to stop the whole chain, not just skip the scope.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"get_experiment_id_by_name": None, "get_channel_db_id": 3}
        )

        controller.load_event_distribution_data(
            "loader", "SELECT * FROM events", "mine_raw", "exp1", 2, {"exp1": [2]}
        )

        assert controller.model.calls_to("load_event_data") == []
        controller.view.set_event_query.assert_not_called()
        controller.view.set_event_data_generator.assert_not_called()


class TestTheNaiveWhereDetection:
    """
    Where the string surgery is wrong, recorded rather than endorsed.

    ``"WHERE" in query.upper()`` cannot tell a real outer ``WHERE`` from one inside a
    subquery or a string literal. ``MetaDatabaseLoader`` solves exactly this with
    ``_split_on_opaque_spans``; this path does not use it. Queued in
    ``future_fixes.md``.
    """

    def test_a_where_inside_a_subquery_produces_invalid_sql(
        self, controller: ProteinController
    ) -> None:
        """
        The filter has no outer WHERE, so the scope needs one - and it gets ``AND``.

        The result cannot execute. Today the user sees a database error they cannot
        act on; after Step 4b this should route through the loader instead.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        query = scope(controller, "duration > (SELECT AVG(x) FROM t WHERE y = 1)")

        assert query == (
            "duration > (SELECT AVG(x) FROM t WHERE y = 1) "
            "AND experiment_id = 7 AND channel_db_id = 3"
        )
        assert " WHERE experiment_id" not in query

    def test_a_where_inside_a_string_literal_does_the_same(
        self, controller: ProteinController
    ) -> None:
        """
        A value that merely contains the word is enough to mis-fire.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(controller, "label = 'WHERE'").endswith(
            "AND experiment_id = 7 AND channel_db_id = 3"
        )

    def test_the_detection_is_case_insensitive(
        self, controller: ProteinController
    ) -> None:
        """
        Lowercase SQL takes the same branch, which is correct here.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        assert scope(
            controller, "select * from events where duration > 5"
        ).endswith("AND experiment_id = 7 AND channel_db_id = 3")


def test_the_two_tabs_build_different_projections() -> None:
    """
    The near-twin event-plot queries in the two tabs are not interchangeable.

    Both halves now live in Controllers - Step 4a moved the protein tab out of the
    widget in the same shape the metadata tab went - so this compares the two
    ``load_event_plot_data`` methods. The protein copy selects ``id, event_id``
    because it re-sorts the rows into the order the navigation asked for them in; the
    metadata copy selects ``id`` alone because it does not.

    That difference is the open question for the promotion to
    ``MetaSubsetTabController`` (``DECISIONS.md``, 2026-09-09), so it is asserted here
    rather than left to be rediscovered during the merge. **This test is meant to be
    rewritten by whichever commit promotes them**, not deleted: if one shared method
    ends up serving both, what it selects is exactly what needs pinning.

    :return: None
    :rtype: None
    """
    import inspect

    from poriscope.plugins.analysistabs.MetadataController import MetadataController

    protein = inspect.getsource(ProteinController.load_event_plot_data)
    metadata = inspect.getsource(MetadataController.load_event_plot_data)

    assert "SELECT id, event_id FROM events WHERE" in protein
    assert "SELECT id FROM events WHERE" in metadata
    assert "id, event_id" not in metadata
