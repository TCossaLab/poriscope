"""
Characterization tests for the SQL the Views write themselves.

Step 4b moves this into ``MetaDatabaseLoader``. Folding it into
``construct_metadata_query`` will change the generated text even where it preserves
behaviour, so what these Views emit today is pinned first.

``ProteinView._build_load_event_data_args`` is the one worth the most attention. It
takes a user's raw SQL filter and appends a scope clause to it by string surgery,
choosing between ``AND`` and ``WHERE`` on a bare ``"WHERE" in query.upper()`` test.
That test is wrong for any filter whose only ``WHERE`` sits inside a subquery or a
string literal - exactly the case ``MetaDatabaseLoader._split_on_opaque_spans``
exists to handle, and which this path does not use. The mis-fire is pinned below as
current behaviour and queued in ``future_fixes.md``; **this file records what the
code does, it does not endorse it**.

``MetadataView._handle_plot_events`` builds a near-twin query
(``SELECT id FROM events WHERE ...`` against ``ProteinView``'s
``SELECT id, event_id FROM events WHERE ...``) but does so inline, 120 lines into a
244-line orchestrator, so pinning its text means driving the whole method. Its twin
in ``ProteinView._resolve_event_db_ids`` *is* pinned, in
``test_protein_view_characterization.py``. The gap is recorded in
``future_fixes.md``: extract that query before Step 4b moves it.
"""

import pytest

from poriscope.plugins.analysistabs.ProteinView import ProteinView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization


@pytest.fixture
def view() -> ProteinView:
    """
    A ProteinView built without Qt, with its bus answering the two id lookups.

    The stub sets the attributes the real dispatcher would, rather than doing
    nothing - a silent stub would make every assertion here vacuous.

    :return: the view
    :rtype: ProteinView
    """
    instance = ProteinView.__new__(ProteinView)
    shadow_signals(instance, ProteinView)

    def deliver(metaclass, key, method, args, return_fn, extra):
        if return_fn == "set_experiment_id":
            instance.experiment_id = 7
        elif return_fn == "set_channel_db_id":
            instance.channel_db_id = 3

    instance.global_signal.emit.side_effect = deliver
    return instance


def build(view: ProteinView, sql_filter: str, subset: str = "mine_raw", exp="exp1"):
    """
    Call the builder with the arguments a plot request supplies.

    :param view: the view under test
    :type view: ProteinView
    :param sql_filter: the user's filter text
    :type sql_filter: str
    :param subset: the subset name, whose ``_raw`` suffix selects the scoping path
    :type subset: str
    :param exp: the experiment name, or None
    :type exp: Any
    :return: the (filter_or_query, exp_and_ch_or_None) tuple
    :rtype: tuple
    """
    return view._build_load_event_data_args(
        sql_filter, subset, exp, "2", {"exp1": [2]}, "loader"
    )


class TestNonRawSubsetsArePassedThrough:
    """Only a ``_raw`` subset takes the string-surgery path."""

    def test_a_named_subset_is_returned_untouched_with_its_scope(
        self, view: ProteinView
    ) -> None:
        """The loader does the scoping itself for a managed subset."""
        result = build(view, "duration > 5", subset="mine")

        assert result == ("duration > 5", {"exp1": [2]})

    def test_a_named_subset_makes_no_bus_calls(self, view: ProteinView) -> None:
        """No id lookups are needed when the loader will scope it."""
        build(view, "duration > 5", subset="mine")

        view.global_signal.emit.assert_not_called()


class TestRawSubsetScoping:
    """The ``_raw`` path appends an experiment and channel scope by hand."""

    def test_a_filter_without_where_gains_one(self, view: ProteinView) -> None:
        """The common case, and the reason the branch exists."""
        query, scope = build(view, "duration > 5")

        assert query == "duration > 5 WHERE experiment_id = 7 AND channel_db_id = 3"
        assert scope is None

    def test_a_filter_with_where_gains_an_and(self, view: ProteinView) -> None:
        """The other branch of the same choice."""
        query, _ = build(view, "SELECT * FROM events WHERE duration > 5")

        assert query == (
            "SELECT * FROM events WHERE duration > 5 "
            "AND experiment_id = 7 AND channel_db_id = 3"
        )

    def test_a_trailing_semicolon_is_stripped_before_appending(
        self, view: ProteinView
    ) -> None:
        """Otherwise the scope would land after the statement terminator."""
        query, _ = build(view, "duration > 5;")

        assert query == "duration > 5 WHERE experiment_id = 7 AND channel_db_id = 3"

    def test_surrounding_whitespace_is_stripped(self, view: ProteinView) -> None:
        """Users paste filters with stray newlines."""
        query, _ = build(view, "  duration > 5  \n")

        assert query.startswith("duration > 5 WHERE")

    def test_no_experiment_means_no_scope_is_appended(self, view: ProteinView) -> None:
        """Nothing to scope to, so the filter is returned as the user wrote it."""
        query, scope = build(view, "duration > 5", exp=None)

        assert query == "duration > 5"
        assert scope is None

    def test_the_ids_are_cleared_before_they_are_requested(
        self, view: ProteinView
    ) -> None:
        """
        The stale-read guard.

        A failed dispatch never calls the return function, so without the pre-clear
        the filter would be scoped to the *previous* experiment and channel - which
        silently returns another channel's events rather than failing.
        """
        view.experiment_id = 99
        view.channel_db_id = 99
        view.global_signal.emit.side_effect = lambda *a, **k: None

        query, _ = build(view, "duration > 5")

        assert view.experiment_id is None
        assert view.channel_db_id is None
        assert query == "duration > 5"

    def test_a_partial_lookup_appends_nothing(self, view: ProteinView) -> None:
        """
        Both ids are required; one alone would scope to the wrong rows.

        Pinned because the guard is a three-way ``and``, and dropping either term
        would emit ``channel_db_id = None`` into the SQL.
        """

        def only_experiment(metaclass, key, method, args, return_fn, extra):
            if return_fn == "set_experiment_id":
                view.experiment_id = 7

        view.global_signal.emit.side_effect = only_experiment

        query, _ = build(view, "duration > 5")

        assert query == "duration > 5"


class TestTheNaiveWhereDetection:
    """
    Where the string surgery is wrong, recorded rather than endorsed.

    ``"WHERE" in scoped_query.upper()`` cannot tell a real outer ``WHERE`` from one
    inside a subquery or a string literal. ``MetaDatabaseLoader`` solves exactly this
    with ``_split_on_opaque_spans``; this path does not use it. Queued in
    ``future_fixes.md``.
    """

    def test_a_where_inside_a_subquery_produces_invalid_sql(
        self, view: ProteinView
    ) -> None:
        """
        The filter has no outer WHERE, so the scope needs one - and it gets ``AND``.

        The result cannot execute. Today the user sees a database error they cannot
        act on; after Step 4b this should route through the loader instead.
        """
        query, _ = build(view, "duration > (SELECT AVG(x) FROM t WHERE y = 1)")

        assert query == (
            "duration > (SELECT AVG(x) FROM t WHERE y = 1) "
            "AND experiment_id = 7 AND channel_db_id = 3"
        )
        assert " WHERE experiment_id" not in query

    def test_a_where_inside_a_string_literal_does_the_same(
        self, view: ProteinView
    ) -> None:
        """A value that merely contains the word is enough to mis-fire."""
        query, _ = build(view, "label = 'WHERE'")

        assert query.endswith("AND experiment_id = 7 AND channel_db_id = 3")

    def test_the_detection_is_case_insensitive(self, view: ProteinView) -> None:
        """Lowercase SQL takes the same branch, which is correct here."""
        query, _ = build(view, "select * from events where duration > 5")

        assert query.endswith("AND experiment_id = 7 AND channel_db_id = 3")


def test_the_two_views_build_different_projections(view: ProteinView) -> None:
    """
    The near-twin queries in the two tabs are not interchangeable.

    ``ProteinView._resolve_event_db_ids`` selects ``id, event_id`` while
    ``MetadataView._handle_plot_events`` selects ``id`` alone. Step 4b folds both
    into the loader, and a single shared query would have to serve both - so the
    difference is recorded here rather than discovered during the merge.
    """
    import inspect

    from poriscope.plugins.analysistabs.MetadataView import MetadataView

    protein = inspect.getsource(ProteinView._resolve_event_db_ids)
    metadata = inspect.getsource(MetadataView._handle_plot_events)

    assert "SELECT id, event_id FROM events WHERE" in protein
    assert "SELECT id FROM events WHERE" in metadata
