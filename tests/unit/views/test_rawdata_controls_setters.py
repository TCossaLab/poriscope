"""
The RawData controls' whole-value setters, which write-back uses to show a recorded value.

Each writes one field, fires no ``actionTriggered`` (a handler reacting to a value that was just
written would undo it) and reports whether the value was one of the field's options.
"""

from typing import Any, List

import pytest

from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls


@pytest.fixture
def controls(qapp: Any) -> Any:
    panel = RawDataControls()
    panel.update_readers(["r1", "r2"])
    panel.update_filters(["f1", "f2"])
    panel.update_eventfinders(["e1", "e2"])
    panel.channel_comboBox.addItems(["0", "1", "2"])
    panel.actions = []  # type: ignore[attr-defined]
    panel.actionTriggered.connect(lambda *args: panel.actions.append(args))
    yield panel
    panel.deleteLater()
    qapp.processEvents()


def test_set_reader_shows_the_reader_and_fires_nothing(controls: Any) -> None:
    assert controls.set_reader("r2") is True

    assert controls.readers_comboBox.currentText() == "r2"
    assert controls.actions == []


def test_set_filter_shows_the_filter_and_an_empty_key_means_no_filter(
    controls: Any,
) -> None:
    assert controls.set_filter("f2") is True
    assert controls.filters_comboBox.currentText() == "f2"

    assert controls.set_filter("") is True
    assert controls.filters_comboBox.currentText() == "No Filter"
    assert controls.actions == []


def test_set_eventfinder_shows_the_finder_and_fires_nothing(controls: Any) -> None:
    assert controls.set_eventfinder("e2") is True

    assert controls.eventfinders_comboBox.currentText() == "e2"
    assert controls.actions == []


@pytest.mark.parametrize(
    "setter, combo",
    [
        ("set_reader", "readers_comboBox"),
        ("set_filter", "filters_comboBox"),
        ("set_eventfinder", "eventfinders_comboBox"),
    ],
)
def test_a_value_that_is_not_an_option_leaves_the_field_as_it_was(
    controls: Any, setter: str, combo: str
) -> None:
    before = getattr(controls, combo).currentText()

    assert getattr(controls, setter)("not an option") is False

    assert getattr(controls, combo).currentText() == before


def test_set_channels_selects_exactly_these_channels(controls: Any) -> None:
    missing: List[str] = controls.set_channels([1, 2])

    assert missing == []
    assert controls.channel_comboBox.getSelectedItems() == ["1", "2"]
    assert controls.actions == []


def test_set_channels_reports_a_channel_the_list_does_not_have(controls: Any) -> None:
    missing = controls.set_channels([0, 9])

    assert missing == ["9"]
    assert controls.channel_comboBox.getSelectedItems() == ["0"]
