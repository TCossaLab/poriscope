"""
The Clustering controls' whole-value setters, which write-back uses to show a recorded value.

Each writes its fields with their signals held off, fires no ``actionTriggered`` (a handler reacting to a
value that was just written would undo it, and a loader change asks for its columns) and reports whether
the values were options.
"""

from typing import Any

import pytest

from poriscope.plugins.analysistabs.utils.clusteringcontrols import ClusteringControls


@pytest.fixture
def controls(qapp: Any) -> Any:
    panel = ClusteringControls()
    panel.update_loaders(["db1", "db2"])
    panel.update_clusters([-1, 0, 1])
    panel.actions = []  # type: ignore[attr-defined]
    panel.actionTriggered.connect(lambda *args: panel.actions.append(args))
    yield panel
    panel.deleteLater()
    qapp.processEvents()


def test_set_db_loader_shows_the_loader_and_fires_nothing(controls: Any) -> None:
    assert controls.set_db_loader("db2") is True

    assert controls.db_loader_comboBox.currentText() == "db2"
    assert controls.actions == []


def test_a_loader_that_is_not_an_option_leaves_the_box_as_it_was(
    controls: Any,
) -> None:
    before = controls.db_loader_comboBox.currentText()

    assert controls.set_db_loader("a loader that is gone") is False

    assert controls.db_loader_comboBox.currentText() == before
    assert controls.actions == []


def test_set_merge_labels_shows_both_labels_and_fires_nothing(controls: Any) -> None:
    assert controls.set_merge_labels(1, -1) is True

    assert controls.label_x_comboBox.currentText() == "1"
    assert controls.label_y_comboBox.currentText() == "-1"
    assert controls.actions == []


def test_a_label_that_is_not_an_option_is_reported_and_the_other_still_shown(
    controls: Any,
) -> None:
    before = controls.label_x_comboBox.currentText()

    assert controls.set_merge_labels(7, 0) is False

    assert controls.label_x_comboBox.currentText() == before
    assert controls.label_y_comboBox.currentText() == "0"
    assert controls.actions == []


def test_merge_enables_once_the_written_values_allow_it(controls: Any) -> None:
    """The setters validate at the end, so the buttons follow without an emitted action."""
    controls.update_loaders([])
    assert controls.merge_button.isEnabled() is False

    controls.update_loaders(["db1"])
    controls.actions.clear()  # the refresh above announces the loader, as it always has
    controls.set_db_loader("db1")
    controls.set_merge_labels(0, 1)

    assert controls.merge_button.isEnabled() is True
    assert controls.actions == []


def test_writing_the_labels_revalidates_merge(controls: Any) -> None:
    """With no label selected Merge is off; writing both turns it on without a further call."""
    controls.label_x_comboBox.setCurrentIndex(-1)
    controls.label_y_comboBox.setCurrentIndex(-1)
    assert controls.merge_button.isEnabled() is False
    controls.actions.clear()

    controls.set_merge_labels(0, 1)

    assert controls.merge_button.isEnabled() is True
    assert controls.actions == []
