"""
Behavioural conformance for every discovered ``MetaEventFitter``.

``tests/unit/plugins/test_plugin_compliance.py`` checks that a fitter declares the
right interface and ``test_settings_schema.py`` checks that its settings schema
describes itself; neither runs the plugin. The per-fitter unit tests under
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
    EVENTS_CHANNEL,
    EVENTS_COUNT,
    FITTERS_SKIPPED,
    FITTERS_USING_PEAKED_EVENTS,
    INJECTED_EVENT_COLUMNS,
    INJECTED_SUBLEVEL_COLUMNS,
    build_event_fitter,
    build_event_loader,
    discover_concrete,
)

EVENT_FITTERS: List[Type[MetaEventFitter]] = discover_concrete(MetaEventFitter)


@pytest.fixture
def fitter(request, events_db_path, peaked_events_db_path) -> MetaEventFitter:
    """
    Build the fitter under test, attached to a fresh loader, and close it after.

    Fitters in ``FITTERS_USING_PEAKED_EVENTS`` (peak-based fitters, which need a
    resolvable local extremum inside the blockage) are attached to
    ``peaked_events_db_path`` instead of the shared flat ``events_db_path`` -
    see that fixture and ``_recipes.py``'s ``PEAKED_EVENTS_DIP_PA``.

    :param request: Pytest request, carrying the parametrised fitter class.
    :type request: pytest.FixtureRequest
    :param events_db_path: Path to the shared synthetic events database.
    :type events_db_path: str
    :param peaked_events_db_path: Path to the events database with a
        resolvable intra-event dip.
    :type peaked_events_db_path: str
    :return: A configured fitter, ready to fit.
    :rtype: MetaEventFitter
    """
    fitter_cls = request.param
    db_path = (
        peaked_events_db_path
        if fitter_cls.__name__ in FITTERS_USING_PEAKED_EVENTS
        else events_db_path
    )
    loader = build_event_loader(db_path)
    instance = build_event_fitter(fitter_cls, loader)
    yield instance
    instance.close_resources()
    loader.close_resources()


def pytest_generate_tests(metafunc):
    """
    Parametrise the ``fitter`` fixture over every discovered fitter class.

    Classes in ``FITTERS_SKIPPED`` are parametrised as skips rather than
    dropped, so they stay visible in the report, each with the specific reason
    recorded for it rather than a generic one.

    :param metafunc: Pytest's per-function collection hook argument.
    :type metafunc: pytest.Metafunc
    """
    if "fitter" not in metafunc.fixturenames:
        return
    params = []
    for cls in EVENT_FITTERS:
        marks = []
        if cls.__name__ in FITTERS_SKIPPED:
            marks.append(pytest.mark.skip(reason=FITTERS_SKIPPED[cls.__name__]))
        params.append(pytest.param(cls, marks=marks, id=cls.__name__))
    metafunc.parametrize("fitter", params, indirect=True)


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
