"""
Direct tests for the five helpers behind ``construct_metadata_query``.

A repository-wide grep for these names in ``tests/`` returned **zero hits**. They
are exercised only through ``construct_metadata_query``, which means their edge
cases are reachable only by constructing a whole query that happens to hit them -
and several of those edge cases exist precisely because a 2026-09-03 bug let
condition qualification rewrite text inside SQL string literals.

Step 4b moves the Views' hand-built SQL into the builder these helpers serve, so
they are about to take input shapes they have never seen. Each is tested here on
its own terms.

The one that matters most is ``_split_on_opaque_spans``, whose docstring states an
exact-reconstruction invariant - ``"".join(result)`` reproduces the input - that
nothing asserted. Everything else in the qualification path is built on it holding.
"""

from typing import Dict

import pytest

from tests.unit.utils.test_meta_database_loader import ConcreteDatabaseLoader

pytestmark = pytest.mark.characterization


@pytest.fixture
def loader() -> ConcreteDatabaseLoader:
    """
    The shared stub loader.

    :return: a concrete loader over the stub schema
    :rtype: ConcreteDatabaseLoader
    """
    settings = {"Input File": {"Type": str, "Value": "/path/to/db.db"}}
    return ConcreteDatabaseLoader(settings=settings)


# ===========================================================================
# _end_of_subquery
# ===========================================================================


class TestEndOfSubquery:
    """A paren-depth scan that knows quotes hide parens."""

    def test_it_returns_the_index_past_the_matching_paren(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """The slice ``fragment[start:end]`` is then the whole parenthesised span."""
        fragment = "a > (SELECT 1) AND b"
        end = loader._end_of_subquery(fragment, 4)

        assert fragment[4:end] == "(SELECT 1)"

    def test_nested_parens_are_balanced(self, loader: ConcreteDatabaseLoader) -> None:
        """An inner group must not be mistaken for the end of the outer one."""
        fragment = "(SELECT max(x) FROM t)"
        assert loader._end_of_subquery(fragment, 0) == len(fragment)

    def test_a_paren_inside_a_literal_is_ignored(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        A close paren inside a quoted string does not close the subquery.

        Without this, ``WHERE x IN (SELECT n FROM t WHERE s = ')')`` would be cut
        short and the remainder rewritten as if it were code.
        """
        fragment = "(SELECT n FROM t WHERE s = ')')"
        assert loader._end_of_subquery(fragment, 0) == len(fragment)

    def test_a_doubled_quote_escape_is_handled(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """``''`` is SQL's escape for a quote; it must not end the literal."""
        fragment = "(SELECT n FROM t WHERE s = 'it''s )' )"
        assert loader._end_of_subquery(fragment, 0) == len(fragment)

    def test_an_unbalanced_paren_consumes_the_rest(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        Malformed input is left whole for the validator rather than rewritten.

        Deliberate: rewriting half of a broken fragment could turn a syntax error
        into a query that parses and means something else.
        """
        fragment = "(SELECT 1 FROM t"
        assert loader._end_of_subquery(fragment, 0) == len(fragment)


# ===========================================================================
# _split_on_opaque_spans
# ===========================================================================


class TestSplitOnOpaqueSpans:
    """Alternating rewritable and pass-through segments."""

    @pytest.mark.parametrize(
        "fragment",
        [
            "",
            "a > 1",
            "name = 'x'",
            "name = 'it''s'",
            "a > (SELECT AVG(b) FROM t)",
            "a = 'x' AND b IN (SELECT c FROM t WHERE d = 'y')",
            "unterminated = 'oops",
            "unbalanced > (SELECT 1",
            "'leading literal' AND x = 1",
        ],
    )
    def test_the_segments_rejoin_to_the_input_exactly(
        self, loader: ConcreteDatabaseLoader, fragment: str
    ) -> None:
        """
        The documented invariant, which nothing asserted before.

        Every rewrite in the qualification path works on the even segments and then
        rejoins; if this ever failed, conditions would be silently corrupted rather
        than raising.
        """
        assert "".join(loader._split_on_opaque_spans(fragment)) == fragment

    def test_a_string_literal_lands_on_an_odd_index(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Odd segments are the ones never rewritten."""
        segments = loader._split_on_opaque_spans("name = 'sublevel_duration'")

        assert segments[1] == "'sublevel_duration'"

    def test_a_subquery_lands_on_an_odd_index(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        A subquery names its own tables, so its columns are not the outer query's.

        Rewriting them would silently correlate the subquery to the outer row.
        """
        segments = loader._split_on_opaque_spans("a > (SELECT b FROM t)")

        assert segments[1] == "(SELECT b FROM t)"

    def test_select_matching_is_case_insensitive(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Users type SQL in whatever case they please."""
        segments = loader._split_on_opaque_spans("a > (select b from t)")

        assert segments[1] == "(select b from t)"

    def test_a_plain_parenthesised_group_is_not_opaque(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        Only ``(SELECT`` is a subquery; ordinary grouping stays rewritable.

        ``(a > 1 OR b > 2)`` must still have its columns qualified.
        """
        segments = loader._split_on_opaque_spans("(a > 1 OR b > 2)")

        assert segments == ["(a > 1 OR b > 2)"]

    def test_an_unterminated_literal_makes_the_remainder_opaque(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Malformed input is passed to the validator, not rewritten."""
        segments = loader._split_on_opaque_spans("name = 'oops AND x = 1")

        assert segments[1] == "'oops AND x = 1"


# ===========================================================================
# _references_column
# ===========================================================================


class TestReferencesColumn:
    """What counts as the outer query referring to a column."""

    def test_a_bare_reference_counts(self, loader: ConcreteDatabaseLoader) -> None:
        """The common case: an unqualified column in a condition."""
        assert loader._references_column("sublevel_duration < 100", "sublevel_duration")

    def test_a_qualified_reference_counts(self, loader: ConcreteDatabaseLoader) -> None:
        """Sought on a word boundary, so an alias prefix does not hide it."""
        assert loader._references_column(
            "s.sublevel_duration < 100", "sublevel_duration"
        )

    def test_a_longer_name_containing_it_does_not_count(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        ``duration`` must not match inside ``sublevel_duration``.

        This is what forces the longest-first ordering in the qualifier, and
        getting it wrong would join a table the query does not need.
        """
        assert not loader._references_column("sublevel_duration < 100", "duration")

    def test_a_reference_inside_a_literal_does_not_count(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        A column name used as a *value* is not a reference to the column.

        Counting it would force a join for a table the query never touches, which
        is what a 2026-09-03 fix addressed.
        """
        assert not loader._references_column(
            "name = 'sublevel_duration'", "sublevel_duration"
        )

    def test_a_reference_inside_a_subquery_does_not_count(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        It resolves against the subquery's own tables, so the outer query joins nothing.

        Keeps this helper in agreement with the qualifier about what the outer
        query refers to.
        """
        assert not loader._references_column(
            "a > (SELECT AVG(sublevel_duration) FROM sublevels)", "sublevel_duration"
        )


# ===========================================================================
# _qualify_conditions
# ===========================================================================


class TestQualifyConditions:
    """Rewriting bare columns to alias-qualified ones."""

    @pytest.fixture
    def joined(self) -> Dict[str, str]:
        """
        Aliases for a query joining events and sublevels.

        :return: the alias map
        :rtype: Dict[str, str]
        """
        return {"events": "e", "sublevels": "s"}

    def test_a_bare_column_is_qualified(
        self, loader: ConcreteDatabaseLoader, joined: Dict[str, str]
    ) -> None:
        """The point of the helper: users write plain SQL and it is made to fit."""
        out = loader._qualify_conditions("sublevel_duration < 100", joined)

        assert out == "s.sublevel_duration < 100"

    def test_an_already_qualified_column_is_left_alone(
        self, loader: ConcreteDatabaseLoader, joined: Dict[str, str]
    ) -> None:
        """
        The lookbehind guard, which stops ``s.s.sublevel_duration``.

        Users who know the aliases qualify their own filters, and a second pass
        must be a no-op.
        """
        out = loader._qualify_conditions("s.sublevel_duration < 100", joined)

        assert out == "s.sublevel_duration < 100"

    def test_a_literal_is_never_rewritten(
        self, loader: ConcreteDatabaseLoader, joined: Dict[str, str]
    ) -> None:
        """A column name appearing as a value stays a value."""
        out = loader._qualify_conditions("name = 'sublevel_duration'", joined)

        assert "'sublevel_duration'" in out
        assert "'s.sublevel_duration'" not in out

    def test_a_subquery_is_passed_through_untouched(
        self, loader: ConcreteDatabaseLoader, joined: Dict[str, str]
    ) -> None:
        """Its columns belong to its own tables."""
        conditions = "dwell_time > (SELECT AVG(sublevel_duration) FROM sublevels)"

        out = loader._qualify_conditions(conditions, joined)

        assert "(SELECT AVG(sublevel_duration) FROM sublevels)" in out
        assert out.startswith("e.dwell_time")

    def test_a_single_table_query_leaves_identity_columns_bare(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        With one table there is nothing to disambiguate, so nothing is added.

        The synthetic identity pass only runs when more than one alias is in play.
        """
        out = loader._qualify_conditions("experiment_id = 2", {"events": "e"})

        assert out == "experiment_id = 2"

    def test_shared_identity_columns_are_anchored_when_tables_are_joined(
        self, loader: ConcreteDatabaseLoader, joined: Dict[str, str]
    ) -> None:
        """
        ``experiment_id`` exists on more than one table, so a bare use is ambiguous.

        It is qualified onto the anchor alias rather than left to SQLite to reject.
        """
        out = loader._qualify_conditions("experiment_id = 2", joined)

        assert out == "e.experiment_id = 2"

    def test_a_longer_column_is_not_clobbered_by_a_shorter_one(
        self, loader: ConcreteDatabaseLoader, joined: Dict[str, str]
    ) -> None:
        """
        Columns are substituted longest-first, so ``sublevel_amplitude`` survives.

        Shortest-first would rewrite the ``amplitude`` inside it and produce
        ``sublevel_e.amplitude``.
        """
        out = loader._qualify_conditions("sublevel_amplitude > 1", joined)

        assert out == "s.sublevel_amplitude > 1"


# ===========================================================================
# _find_ambiguous_id
# ===========================================================================


class TestFindAmbiguousId:
    """Refusing a bare ``id`` when it could mean more than one row."""

    def test_a_single_table_query_permits_a_bare_id(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """With one table there is only one thing ``id`` can mean."""
        assert loader._find_ambiguous_id("id = 4", {"events": "e"}) is None

    def test_a_joined_query_refuses_a_bare_id(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        Two tables, two id columns, so the filter is rejected with guidance.

        Silently picking one would return the wrong rows rather than failing.
        """
        message = loader._find_ambiguous_id("id = 4", {"events": "e", "sublevels": "s"})

        assert message is not None
        assert "e.id" in message and "s.id" in message

    def test_a_qualified_id_is_accepted(self, loader: ConcreteDatabaseLoader) -> None:
        """The user has said which one they mean."""
        assert (
            loader._find_ambiguous_id("e.id = 4", {"events": "e", "sublevels": "s"})
            is None
        )

    def test_an_id_inside_a_literal_is_not_flagged(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """A value that happens to read ``id`` is not a column reference."""
        assert (
            loader._find_ambiguous_id("name = 'id'", {"events": "e", "sublevels": "s"})
            is None
        )

    def test_a_column_ending_in_id_is_not_flagged(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """
        ``experiment_id`` is unambiguous; only a standalone ``id`` is not.

        The pattern requires no word character or dot before the ``id``.
        """
        assert (
            loader._find_ambiguous_id(
                "experiment_id = 2", {"events": "e", "sublevels": "s"}
            )
            is None
        )
