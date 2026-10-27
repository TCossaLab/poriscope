"""
The EventAnalysis controls' whole-value setters, which write-back uses to show a recorded value.

Each writes one field, fires no ``actionTriggered`` (a handler reacting to a value that was just
written would undo it) and reports whether the value was one of the field's options. ``set_filter``
and ``set_channels`` are shared with RawData, so they live on the event-tab base and are tested here
on this panel too.
"""

from typing import Any, List

import pytest

from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)
from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls
from poriscope.utils.MetaEventTabControls import MetaEventTabControls


@pytest.fixture
def controls(qapp: Any) -> Any:
    panel = EventAnalysisControls()
    panel.update_loaders(["l1", "l2"])
    panel.update_eventfitters(["ef1", "ef2"])
    panel.update_filters(["f1", "f2"])
    panel.channel_comboBox.addItems(["0", "1", "2"])
    panel.actions = []  # type: ignore[attr-defined]
    panel.actionTriggered.connect(lambda *args: panel.actions.append(args))
    yield panel
    panel.deleteLater()
    qapp.processEvents()


def test_set_loader_shows_the_loader_and_fires_nothing(controls: Any) -> None:
    assert controls.set_loader("l2") is True

    assert controls.loaders_comboBox.currentText() == "l2"
    assert controls.actions == []


def test_set_eventfitter_shows_the_fitter_and_fires_nothing(controls: Any) -> None:
    assert controls.set_eventfitter("ef2") is True

    assert controls.eventfitters_comboBox.currentText() == "ef2"
    assert controls.actions == []


def test_set_filter_shows_the_filter_and_an_empty_key_means_no_filter(
    controls: Any,
) -> None:
    assert controls.set_filter("f2") is True
    assert controls.filters_comboBox.currentText() == "f2"

    assert controls.set_filter("") is True
    assert controls.filters_comboBox.currentText() == "No Filter"
    assert controls.actions == []


@pytest.mark.parametrize(
    "setter, combo",
    [
        ("set_loader", "loaders_comboBox"),
        ("set_eventfitter", "eventfitters_comboBox"),
        ("set_filter", "filters_comboBox"),
    ],
)
def test_a_value_that_is_not_an_option_leaves_the_control_as_it_was(
    controls: Any, setter: str, combo: str
) -> None:
    box = getattr(controls, combo)
    before = box.currentText()

    assert getattr(controls, setter)("not an option") is False

    assert box.currentText() == before
    assert controls.actions == []


def test_set_channels_selects_exactly_those_and_reports_the_missing(
    controls: Any,
) -> None:
    missing = controls.set_channels([0, 2, 7])

    assert controls.channel_comboBox.getSelectedItems() == ["0", "2"]
    assert missing == ["7"]
    assert controls.actions == []


def test_set_raw_shows_the_checkbox_state_and_fires_nothing(controls: Any) -> None:
    toggled: List[int] = []
    controls.raw_checkbox.stateChanged.connect(toggled.append)

    controls.set_raw(True)
    assert controls.raw_checkbox.isChecked() is True

    controls.set_raw(False)
    assert controls.raw_checkbox.isChecked() is False
    assert controls.actions == []
    assert toggled == [], "the checkbox's own signal was left on"


def test_the_buttons_follow_what_was_written(controls: Any) -> None:
    """The setters validate at the end, so Fit Events enables without an emitted action."""
    controls.set_channels([])
    controls.set_loader("l1")
    controls.set_eventfitter("ef1")
    assert controls.fit_events_pushButton.isEnabled() is False

    controls.set_channels([1])

    assert controls.fit_events_pushButton.isEnabled() is True
    assert controls.actions == []


def test_set_filter_and_set_channels_are_shared_with_raw_data() -> None:
    """One copy on the event-tab base, so a second tab's write-back does not add a duplicate."""
    for name in ("set_filter", "set_channels"):
        assert name in MetaEventTabControls.__dict__
        assert name not in RawDataControls.__dict__
        assert name not in EventAnalysisControls.__dict__
