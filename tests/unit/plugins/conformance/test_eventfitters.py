"""
Behavioural conformance for every discovered ``MetaEventFitter``.

``tests/unit/plugins/test_plugin_compliance.py`` checks that a fitter declares the
right interface, ``test_plugin_settings_schema.py`` checks that its settings schema
is internally self-consistent, and ``test_settings_defaults.py`` checks that its
shipped defaults survive its own validators; none of the three runs the plugin. The
per-fitter unit tests under
``tests/unit/plugins/eventfitters/`` do run the algorithms, but build instances via
``object.__new__`` and attach ``MagicMock()`` loaders, so they cannot see a broken
``__init__``/``apply_settings``/``_finalize_initialization`` lifecycle, and they pass
whether or not a real ``MetaEventLoader`` returns what the fitter assumes.

This module drives each fitter the way the app does - real settings, a real loader
over a real database - and asserts it behaves like a well-formed member of the
family. Parametrised over discovered classes rather than a hand-written list, so a
new fitter is covered the moment the file is added, matching how
``MainModel.populate_available_plugins`` actually finds plugins.
"""

from typing import List, Type

import numpy as np
import pytest

from poriscope.utils.MetaEventFitter import MetaEventFitter
from tests.unit.plugins.conformance._recipes import (
    EVENT_AMPLITUDE_PA,
    EVENTS_CHANNEL,
    EVENTS_COUNT,
    FITTER_FIXTURE_SHAPES,
    FITTER_FIXTURES,
    INJECTED_EVENT_COLUMNS,
    INJECTED_SUBLEVEL_COLUMNS,
    NOISE_STD_PA,
    PEAKED_EVENTS_DIP_PA,
    STAIRCASE_LEVEL_AMPLITUDES_PA,
    build_event_fitter,
    build_event_loader,
    discover_concrete,
    fitters_using,
)

EVENT_FITTERS: List[Type[MetaEventFitter]] = discover_concrete(MetaEventFitter)
STAIRCASE_FITTERS: List[Type[MetaEventFitter]] = [
    cls for cls in EVENT_FITTERS if cls.__name__ in fitters_using("staircase")
]
PEAKED_FITTERS: List[Type[MetaEventFitter]] = [
    cls for cls in EVENT_FITTERS if cls.__name__ in fitters_using("dip")
]


@pytest.fixture
def fitter(
    request,
    events_db_path,
    peaked_events_db_path,
    peakfinder_events_db_path,
) -> MetaEventFitter:
    """
    Build the fitter under test, attached to a fresh loader, and close it after.

    ``FITTER_FIXTURES`` in ``_recipes.py`` says which recording each fitter is
    driven against: "dip" for a peak-based fitter needing a resolvable extremum
    inside the blockage, "deep_dip" for ``PeakFinder``, which needs one deeper
    and narrower still. A fitter mapped to "staircase" is driven against the
    shared flat database here - its planted levels are only meaningful to
    ``staircase_fitter``, which reads the count.

    :param request: Pytest request, carrying the parametrised fitter class.
    :type request: pytest.FixtureRequest
    :param events_db_path: Path to the shared synthetic events database.
    :type events_db_path: str
    :param peaked_events_db_path: Path to the events database with a
        resolvable intra-event dip.
    :type peaked_events_db_path: str
    :param peakfinder_events_db_path: Path to the events database with a dip
        deep and narrow enough for ``PeakFinder`` specifically.
    :type peakfinder_events_db_path: str
    :return: A configured fitter, ready to fit.
    :rtype: MetaEventFitter
    """
    fitter_cls = request.param
    by_shape = {
        "dip": peaked_events_db_path,
        "staircase": events_db_path,
        "deep_dip": peakfinder_events_db_path,
    }
    shape = FITTER_FIXTURES.get(fitter_cls.__name__)
    if shape is not None and shape not in by_shape:
        raise KeyError(
            f"{fitter_cls.__name__} is mapped to fixture shape {shape!r}, which "
            f"has no database here; known shapes are {sorted(by_shape)}"
        )
    db_path = by_shape[shape] if shape is not None else events_db_path
    loader = build_event_loader(db_path)
    instance = build_event_fitter(fitter_cls, loader)
    yield instance
    instance.close_resources()
    loader.close_resources()


@pytest.fixture(
    params=STAIRCASE_FITTERS, ids=[cls.__name__ for cls in STAIRCASE_FITTERS]
)
def staircase_fitter(request, staircase_events_db_path) -> MetaEventFitter:
    """
    Build a step-detection fitter over the staircase database, and close it after.

    A dedicated fixture rather than reusing ``fitter``: it is parametrised
    directly over ``STAIRCASE_FITTERS``, not routed through
    ``pytest_generate_tests`` (which parametrises ``fitter`` over every
    discovered fitter class), so this only ever runs for the CUSUM family.

    :param request: Pytest request, carrying the parametrised fitter class.
    :type request: pytest.FixtureRequest
    :param staircase_events_db_path: Path to the events database with a known
        number of discrete levels inside every blockage.
    :type staircase_events_db_path: str
    :return: A configured fitter, ready to fit.
    :rtype: MetaEventFitter
    """
    loader = build_event_loader(staircase_events_db_path)
    instance = build_event_fitter(request.param, loader)
    yield instance
    instance.close_resources()
    loader.close_resources()


def pytest_generate_tests(metafunc):
    """
    Parametrise the ``fitter`` fixture over every discovered fitter class.

    Every discovered fitter is driven; there is no exemption list. A fitter the
    current fixtures cannot exercise fails rather than being marked, on the grounds
    that the generator can plant any shape a fitter looks for - see
    ``quality_control.rst`` for how to add one.

    :param metafunc: Pytest's per-function collection hook argument.
    :type metafunc: pytest.Metafunc
    """
    if "fitter" not in metafunc.fixturenames:
        return
    metafunc.parametrize(
        "fitter",
        EVENT_FITTERS,
        ids=[cls.__name__ for cls in EVENT_FITTERS],
        indirect=True,
    )


@pytest.mark.conformance
def test_fits_every_planted_event(fitter: MetaEventFitter) -> None:
    """
    A fitter reaches every planted event and reports fitting as complete.

    Asserting the full count, rather than merely "did not raise", is what stops a
    fitter passing by silently rejecting everything - the failure mode the
    ``step_size_1000_too_few_levels`` case in ``tests/e2e/event_analysis`` shows
    is reachable with plausible settings.

    :param fitter: The configured fitter under test.
    :type fitter: MetaEventFitter
    """
    channels = fitter.get_channels()
    assert (
        EVENTS_CHANNEL in channels
    ), f"expected channel {EVENTS_CHANNEL}, got {channels}"

    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass

    assert (
        fitter.get_eventfitting_status(EVENTS_CHANNEL) is True
    ), f"fitting did not complete:\n{fitter.report_channel_status()}"
    assert fitter.get_num_events(EVENTS_CHANNEL) == EVENTS_COUNT, (
        f"fitted {fitter.get_num_events(EVENTS_CHANNEL)} of {EVENTS_COUNT} planted events:"
        f"\n{fitter.report_channel_status()}"
    )


@pytest.mark.conformance
def test_produced_columns_are_declared(fitter: MetaEventFitter) -> None:
    """
    Every metadata column a fitter produces is declared with a type and a unit.

    This is the fitter's half of its contract with ``SQLiteDBWriter``, which reads
    ``get_event_metadata_types()``/``get_sublevel_metadata_types()`` to build its
    schema: a column that is computed but never declared has no type downstream.
    A ``MagicMock`` loader cannot surface this, because the produced column set
    only exists once real events have been fitted.

    :param fitter: The configured fitter under test.
    :type fitter: MetaEventFitter
    """
    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass

    checks = (
        (
            "event",
            fitter.get_metadata_columns(EVENTS_CHANNEL),
            INJECTED_EVENT_COLUMNS,
            fitter.get_event_metadata_types(),
            fitter.get_event_metadata_units(),
        ),
        (
            "sublevel",
            fitter.get_sublevel_columns(EVENTS_CHANNEL),
            INJECTED_SUBLEVEL_COLUMNS,
            fitter.get_sublevel_metadata_types(),
            fitter.get_sublevel_metadata_units(),
        ),
    )

    errors = []
    for label, produced, injected, types, units in checks:
        assert produced, f"{label} metadata has no columns at all"
        owned = [column for column in produced if column not in injected]
        assert owned, f"{label} metadata is entirely base-injected columns"
        for column in owned:
            if column not in types:
                errors.append(f"{label} column {column!r} has no declared type")
            if column not in units:
                errors.append(f"{label} column {column!r} has no declared unit")
        for column, declared in types.items():
            if not isinstance(declared, type):
                errors.append(
                    f"{label} column {column!r} declares {declared!r}, not a type"
                )
        for column, unit in units.items():
            if unit is not None and not isinstance(unit, str):
                errors.append(f"{label} column {column!r} unit is {unit!r}")

    assert not errors, "\n  ".join([""] + errors)


@pytest.mark.conformance
def test_single_event_metadata_round_trips(fitter: MetaEventFitter) -> None:
    """
    ``get_single_event_metadata`` returns usable data for a fitted event.

    This is what the Event Analysis tab calls to draw one event, so its shape is
    a real contract rather than an internal detail.

    :param fitter: The configured fitter under test.
    :type fitter: MetaEventFitter
    """
    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass

    event_meta, sublevel_meta, filtered, raw, _fitted = (
        fitter.get_single_event_metadata(EVENTS_CHANNEL, 0)
    )

    assert event_meta, "event metadata dict is empty"
    assert sublevel_meta, "sublevel metadata dict is empty"
    assert set(event_meta) == set(fitter.get_metadata_columns(EVENTS_CHANNEL))

    for label, array in (("filtered", filtered), ("raw", raw)):
        assert isinstance(array, np.ndarray), f"{label} data is {type(array).__name__}"
        assert array.dtype == np.float64, f"{label} data is {array.dtype}, not float64"
        assert array.size > 0, f"{label} data is empty"
    assert (
        filtered.shape == raw.shape
    ), f"filtered {filtered.shape} and raw {raw.shape} differ in shape"


@pytest.mark.conformance
def test_reset_and_close_are_safe(fitter: MetaEventFitter) -> None:
    """
    A fitter can be reset after fitting and closed twice without raising.

    ``close_resources`` runs on app exit and on plugin deletion, and
    ``reset_channel`` runs whenever a channel is re-analysed, so both are
    reachable more than once against the same instance.

    :param fitter: The configured fitter under test.
    :type fitter: MetaEventFitter
    """
    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass
    assert fitter.get_eventfitting_status(EVENTS_CHANNEL) is True

    fitter.reset_channel(EVENTS_CHANNEL)
    assert (
        fitter.get_eventfitting_status(EVENTS_CHANNEL) is False
    ), "reset_channel left fitting marked complete"

    fitter.close_resources()
    fitter.close_resources()


@pytest.mark.conformance
def test_sublevel_count_matches_the_planted_staircase(
    staircase_fitter: MetaEventFitter,
) -> None:
    """
    A step-detection fitter counts exactly the planted number of levels.

    ``num_sublevels`` includes the baseline segments before and after the
    blockage, not just the levels inside it - confirmed directly against a
    flat single-level blockage, which reports 3 (baseline, the one level,
    baseline) - so a staircase of ``len(STAIRCASE_LEVEL_AMPLITUDES_PA)``
    discrete levels should report exactly that many plus 2.

    :param staircase_fitter: The configured fitter under test.
    :type staircase_fitter: MetaEventFitter
    """
    for _progress in staircase_fitter.fit_events(EVENTS_CHANNEL):
        pass

    expected = len(STAIRCASE_LEVEL_AMPLITUDES_PA) + 2
    wrong = {
        index: meta["num_sublevels"]
        for index, meta in staircase_fitter.event_metadata[EVENTS_CHANNEL].items()
        if meta["num_sublevels"] != expected
    }
    assert not wrong, (
        f"expected num_sublevels=={expected} for every event, got {wrong}:"
        f"\n{staircase_fitter.report_channel_status()}"
    )


@pytest.fixture(params=PEAKED_FITTERS, ids=[cls.__name__ for cls in PEAKED_FITTERS])
def peaked_fitter(request, peaked_events_db_path) -> MetaEventFitter:
    """
    Build a peak-based fitter over the peaked database, and close it after.

    A dedicated fixture rather than reusing ``fitter``, for the same reason
    ``staircase_fitter`` is: parametrised directly over ``PEAKED_FITTERS`` so it
    only runs for the family that database exists for.

    :param request: Pytest request, carrying the parametrised fitter class.
    :type request: pytest.FixtureRequest
    :param peaked_events_db_path: Path to the events database carrying a
        resolvable intra-event dip.
    :type peaked_events_db_path: str
    :return: A configured fitter, ready to fit.
    :rtype: MetaEventFitter
    """
    loader = build_event_loader(peaked_events_db_path)
    instance = build_event_fitter(request.param, loader)
    yield instance
    instance.close_resources()
    loader.close_resources()


@pytest.mark.conformance
def test_peak_fitter_resolves_the_planted_dip(peaked_fitter: MetaEventFitter) -> None:
    """
    A peak-based fitter reports a deviation deep enough to include the planted dip.

    Without this the "dip" database earns nothing: measured, ``Basic_PeakFinder``
    fits all 25 events against the plain flat blockage too, and its
    ``num_sublevels`` is noise-driven scatter (6-24) either way, so every other
    check here would pass whichever database it were handed. ``max_deviation`` is
    what separates them - the carrier blockage alone reaches 433-467 pA, the
    carrier plus the dip reaches 554-614 pA, measured over 143 events and six
    seeds.

    The floor sits at ``|amplitude| + |dip| - 3 * noise``, which measured 38 pA
    clear of the flat population's deepest event and 49 pA below the peaked
    population's shallowest.

    :param peaked_fitter: The configured peak-based fitter under test.
    :type peaked_fitter: MetaEventFitter
    """
    for _progress in peaked_fitter.fit_events(EVENTS_CHANNEL):
        pass

    floor = abs(EVENT_AMPLITUDE_PA) + abs(PEAKED_EVENTS_DIP_PA) - 3.0 * NOISE_STD_PA
    shallow = {
        index: meta["max_deviation"]
        for index, meta in peaked_fitter.event_metadata[EVENTS_CHANNEL].items()
        if meta["max_deviation"] <= floor
    }
    assert not shallow, (
        f"expected max_deviation > {floor:.1f} pA for every event, which needs the "
        f"planted dip and not just the carrier blockage; these did not reach it: "
        f"{shallow}"
    )


@pytest.mark.conformance
def test_fitter_fixture_shapes_are_known() -> None:
    """
    Every ``FITTER_FIXTURES`` value names a shape the suite can actually build.

    The shape is a string, so a typo used to route the fitter to the shared flat
    database in silence - it simply fell through to the default - costing exactly
    the coverage the entry was added to buy. Checked here rather than only where
    the fixture is resolved, so a mistyped entry is caught even when that fitter's
    own tests are deselected.
    """
    unknown = {
        name: shape
        for name, shape in FITTER_FIXTURES.items()
        if shape not in FITTER_FIXTURE_SHAPES
    }
    assert not unknown, (
        f"unknown fixture shapes in FITTER_FIXTURES: {unknown}. Known shapes are "
        f"{sorted(FITTER_FIXTURE_SHAPES)}."
    )
