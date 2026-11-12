"""
``MetaSubsetTabController.load_filters`` and ``save_filters`` - the filter file round trip.

The widget picks the path and emits an intent; these two slots do the file work through
the Model and hand the answer back. Both tabs inherit them, so they are driven here
through ``MetadataController``.
"""

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@pytest.fixture
def controller(mocker: MockerFixture) -> MetadataController:
    """
    A controller with its view, model, logger and status signal mocked.

    Built with ``__new__`` so no real Qt objects are created, as the other controller
    tests in this directory do.

    :param mocker: pytest-mock fixture
    :return: the controller under test
    """
    ctrl: MetadataController = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    return ctrl


class TestLoadFilters:
    """Reading a file the user chose, and what happens when it cannot be read."""

    def test_what_the_file_held_reaches_the_view_with_its_loader(
        self, controller: MetadataController
    ) -> None:
        """The loader travels with the answer, because the View validates against it."""
        controller.model.load_filters.return_value = {"long": "dwell > 5"}

        controller.load_filters("/tmp/filters.json", "a_loader")

        controller.model.load_filters.assert_called_once_with("/tmp/filters.json")
        controller.view.set_loaded_filters.assert_called_once_with(
            {"long": "dwell > 5"}, "a_loader"
        )

    def test_an_unreadable_file_reaches_the_status_panel(
        self, controller: MetadataController
    ) -> None:
        """
        A failed read used to reach the log only, so a missing file looked exactly
        like a file holding no filters.
        """
        controller.model.load_filters.side_effect = OSError("no such file")

        controller.load_filters("/tmp/gone.json", "a_loader")

        message = controller.add_text_to_display.emit.call_args.args[0]
        assert "/tmp/gone.json" in message
        assert "no such file" in message

    def test_a_file_that_is_not_filters_leaves_the_tab_alone(
        self, controller: MetadataController
    ) -> None:
        """Nothing is handed back, so the filters already on screen are untouched."""
        controller.model.load_filters.side_effect = ValueError("expected a dictionary")

        controller.load_filters("/tmp/filters.json", "a_loader")

        controller.view.set_loaded_filters.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()


class TestSaveFilters:
    """Writing the filters to a file the user chose."""

    def test_the_filters_are_written_where_the_user_asked(
        self, controller: MetadataController
    ) -> None:
        controller.save_filters("/tmp/filters.json", {"long": "dwell > 5"})

        controller.model.save_filters.assert_called_once_with(
            "/tmp/filters.json", {"long": "dwell > 5"}
        )

    def test_a_failed_write_reaches_the_status_panel(
        self, controller: MetadataController
    ) -> None:
        """
        A full disk or a read-only folder used to be logged and nothing more, which
        is indistinguishable from a save that worked.
        """
        controller.model.save_filters.side_effect = OSError("permission denied")

        controller.save_filters("/tmp/filters.json", {"long": "dwell > 5"})

        message = controller.add_text_to_display.emit.call_args.args[0]
        assert "/tmp/filters.json" in message
        assert "permission denied" in message

    def test_a_save_that_worked_says_nothing_to_the_user(
        self, controller: MetadataController
    ) -> None:
        """There is nothing to draw and nothing went wrong, so the panel stays quiet."""
        controller.save_filters("/tmp/filters.json", {"long": "dwell > 5"})

        controller.add_text_to_display.emit.assert_not_called()


def test_the_view_is_wired_to_both_slots(mocker: MockerFixture) -> None:
    """
    The intents are useless unwired, and nothing else in the suite connects them.

    :param mocker: pytest-mock fixture
    :return: None
    """
    ctrl: MetadataController = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]

    MetaSubsetTabController._setup_connections(ctrl)

    ctrl.view.filters_load_requested.connect.assert_called_once_with(ctrl.load_filters)
    ctrl.view.filters_save_requested.connect.assert_called_once_with(ctrl.save_filters)
