"""
Exact-text goldens for ``MetaDatabaseLoader.construct_metadata_query``.

``test_meta_database_loader.py`` covers this method well by behaviour - 110 tests
across the branch shapes - but **not one of them asserts on the generated SQL
text**. Every SQL-shaped assertion there is a substring containment, a negative
containment, or a non-emptiness check. A refactor could reorder the JOIN chain,
reassign the aliases, drop or add a projected column, or reformat the WHERE
assembly, and all 110 would still pass.

That matters because Step 4b moves the Views' hand-built SQL into this method. The
natural way to do it is to widen ``construct_metadata_query`` until it covers those
cases too, and the risk in doing so is not that it breaks - it is that it quietly
starts emitting slightly different SQL for the cases it already served.

So this pins the whole triple - query, debug message and table name - across the
branch shapes, as one ``data_regression`` YAML file, so that every case which moved
shows up in one diff.

**Whitespace is normalised to single spaces before pinning, deliberately.** The
builder assembles its SQL from an indented f-string, so the raw text carries runs of
newlines and alignment spaces that YAML then escapes into an unreadable block
scalar - which defeats the purpose, since the diff is the thing a reviewer reads.
Whitespace is also the one difference that carries no meaning here: what these
goldens exist to catch is a reordered JOIN chain, a reassigned alias, a changed
projection list, a moved ``DISTINCT`` or an altered WHERE assembly, and every one of
those survives normalisation. Reformatting the f-string does not, and should not,
fail this test.

The stub loader is reused from ``test_meta_database_loader.py`` so the schema these
goldens are generated against stays in one place.

**One thing these goldens surfaced, worth knowing before Step 4b.** Verifying that
they are actually sensitive - by renaming the ``sublevels`` alias from ``s`` and
watching the diff - showed the builder emitting
``JOIN sublevels sl ON e.id = s.event_db_id``. The alias map at
``MetaDatabaseLoader.py:1021-1029`` feeds the projection and the WHERE qualification,
but the ``ON`` clause hardcodes ``s.``, so the two are not consistently derived.
Latent today, because nothing changes the aliases; live the moment Step 4b does.
"""

from typing import Dict, List, Optional

import pytest

from tests.unit.utils.test_meta_database_loader import ConcreteDatabaseLoader

pytestmark = pytest.mark.characterization


#: One entry per branch shape the query builder can take. Names are the golden's
#: keys, so they are kept descriptive and stable - renaming one rewrites the file.
CASES: Dict[str, dict] = {
    "events_columns_only": {
        "columns": ["dwell_time", "amplitude"],
    },
    "sublevels_columns_only": {
        "columns": ["sublevel_duration"],
    },
    "events_and_sublevels_columns": {
        "columns": ["dwell_time", "sublevel_duration"],
    },
    "experiments_columns_only": {
        "columns": ["name"],
    },
    "events_with_a_simple_condition": {
        "columns": ["dwell_time"],
        "conditions": "dwell_time > 5",
    },
    "events_plot_filtered_by_a_sublevels_column": {
        "columns": ["dwell_time"],
        "conditions": "sublevel_duration < 100",
    },
    "events_plot_filtered_by_an_experiments_column": {
        "columns": ["dwell_time"],
        "conditions": "name = 'exp1'",
    },
    "sublevels_plot_filtered_by_an_events_column": {
        "columns": ["sublevel_duration"],
        "conditions": "dwell_time > 5",
    },
    "condition_already_qualified": {
        "columns": ["dwell_time", "sublevel_duration"],
        "conditions": "s.sublevel_duration < 100",
    },
    "condition_naming_a_column_inside_a_string_literal": {
        "columns": ["dwell_time"],
        "conditions": "name = 'sublevel_duration'",
    },
    "condition_containing_a_subquery": {
        "columns": ["dwell_time"],
        "conditions": "dwell_time > (SELECT AVG(sublevel_duration) FROM sublevels)",
    },
    "condition_with_an_ambiguous_bare_id": {
        "columns": ["dwell_time", "sublevel_duration"],
        "conditions": "id = 4",
    },
    "a_repeated_column_is_projected_twice": {
        "columns": ["dwell_time", "dwell_time", "amplitude"],
    },
    "scoped_to_one_experiment_and_its_channels": {
        "columns": ["dwell_time"],
        "experiments_and_channels": {"exp1": [0, 1]},
    },
    "scoped_to_one_experiment_all_channels": {
        "columns": ["dwell_time"],
        "experiments_and_channels": {"exp1": None},
    },
    "scoped_to_two_experiments": {
        "columns": ["dwell_time"],
        "experiments_and_channels": {"exp1": [0], "exp2": [0]},
    },
    "scoped_and_filtered_together": {
        "columns": ["dwell_time", "sublevel_duration"],
        "conditions": "sublevel_duration < 100",
        "experiments_and_channels": {"exp1": [0]},
    },
}


@pytest.fixture
def loader() -> ConcreteDatabaseLoader:
    """
    The shared stub loader, so the goldens are generated against one schema.

    :return: a concrete loader over the stub schema
    :rtype: ConcreteDatabaseLoader
    """
    settings = {"Input File": {"Type": str, "Value": "/path/to/db.db"}}
    return ConcreteDatabaseLoader(settings=settings)


def build(loader: ConcreteDatabaseLoader, spec: dict) -> Dict[str, str]:
    """
    Run one case and render its result as plain strings.

    :param loader: the loader under test
    :type loader: ConcreteDatabaseLoader
    :param spec: the case's keyword arguments
    :type spec: dict
    :return: the query, debug message and table name
    :rtype: Dict[str, str]
    """
    columns: List[str] = spec["columns"]
    conditions: Optional[str] = spec.get("conditions")
    scope = spec.get("experiments_and_channels")

    query, debug, table = loader.construct_metadata_query(columns, conditions, scope)
    return {
        "query": " ".join(query.split()),
        "debug": " ".join(debug.split()),
        "table": table,
    }


def test_generated_sql_is_unchanged(
    loader: ConcreteDatabaseLoader, data_regression
) -> None:
    """
    Every branch shape's exact output, in one reviewable file.

    A failure here is not automatically a defect - the query builder is allowed to
    change - but it must be a *reviewed* change. That is the whole point: today
    nothing would show a reviewer that the SQL moved at all.
    """
    generated = {name: build(loader, spec) for name, spec in CASES.items()}

    data_regression.check(generated)


def test_every_case_produced_either_a_query_or_a_refusal(
    loader: ConcreteDatabaseLoader,
) -> None:
    """
    The documented contract: exactly one of query and debug is non-empty.

    Pinned separately from the golden because it is an invariant rather than a
    value, and a golden diff would not make it obvious if it broke.
    """
    for name, spec in CASES.items():
        result = build(loader, spec)
        has_query = bool(result["query"])
        has_debug = bool(result["debug"])
        assert has_query != has_debug, (
            f"{name}: expected exactly one of query and debug to be set, "
            f"got query={result['query']!r} debug={result['debug']!r}"
        )


def test_the_returned_id_column_belongs_to_the_returned_table(
    loader: ConcreteDatabaseLoader,
) -> None:
    """
    Callers write derived columns back against this id, so the pairing is load-bearing.

    Clustering commits its labels using exactly this, which is why a mismatch would
    write cluster ids against the wrong rows rather than failing.
    """
    aliases = {"events": "e", "sublevels": "s", "experiments": "exp"}
    for name, spec in CASES.items():
        result = build(loader, spec)
        if not result["query"]:
            continue
        alias = aliases[result["table"]]
        first = result["query"].split(",")[0]
        assert first.endswith(f"{alias}.id"), f"{name}: {first!r} for {result['table']}"
