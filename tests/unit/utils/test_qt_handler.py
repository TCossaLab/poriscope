"""
Tests for ``QtHandler``, the log handler that surfaces records as modal dialogs.

The dialog code had no tests at all before this file. That mattered: a plugin
name collision logs at ``ERROR`` during startup, and the parentless
``QMessageBox`` it raised arrived behind a main window that had not finished
painting - an invisible modal dialog holding the input grab, which is
indistinguishable from a hung application. Nothing asserted where the dialog
went, so nothing could have caught it.

``QMessageBox`` is patched in the handler's own namespace throughout, so these
run without putting a real modal dialog on screen and blocking the suite.
"""

import logging
from unittest.mock import MagicMock

import pytest

from poriscope.utils.QtHandler import MAX_PENDING_RECORDS, QtHandler


def make_record(level: int, message: str = "something happened") -> logging.LogRecord:
    """
    Build a log record at a given level.

    :param level: The record's level.
    :type level: int
    :param message: The record's message.
    :type message: str
    :return: A record the handler can format and show.
    :rtype: logging.LogRecord
    """
    return logging.LogRecord(
        name="test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


@pytest.fixture
def handler() -> QtHandler:
    """
    A handler with a plain formatter, so the shown text is the message itself.

    :return: The handler under test.
    :rtype: QtHandler
    """
    h = QtHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    return h


class TestWhereTheDialogGoes:
    """The fix: a dialog belongs above the window the user is looking at."""

    def test_the_dialog_is_parented_to_the_active_window(self, handler, mocker):
        """
        A parentless QMessageBox can land behind the main window on Windows, and a
        modal dialog nobody can see reads as a freeze rather than an error.

        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        box_cls = mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        active = MagicMock(name="active window")
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=active
        )

        handler.show_message_box(make_record(logging.ERROR))

        assert box_cls.call_args[0][-1] is active

    def test_the_dialog_is_raised_and_activated(self, handler, mocker):
        """
        Belt and braces for startup, where ``activeWindow()`` is None because
        nothing has been shown yet and there is no parent to stack above.

        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        box_cls = mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=None
        )

        handler.show_message_box(make_record(logging.ERROR))

        box = box_cls.return_value
        box.raise_.assert_called_once()
        box.activateWindow.assert_called_once()
        box.exec.assert_called_once()


class TestWhichDialog:
    """Severity picks the icon and the title, and the floor is WARNING."""

    def test_an_error_is_critical(self, handler, mocker):
        """
        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        box_cls = mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=None
        )

        handler.show_message_box(make_record(logging.ERROR, "it broke"))

        icon, title, text = box_cls.call_args[0][:3]
        assert icon is box_cls.Icon.Critical
        assert title == "Error"
        assert text == "it broke"

    def test_a_warning_is_a_warning(self, handler, mocker):
        """
        Reachable only if the handler's level is lowered, which
        ``update_logging_level`` deliberately never does.

        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        box_cls = mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=None
        )

        handler.show_message_box(make_record(logging.WARNING))

        icon, title, _ = box_cls.call_args[0][:3]
        assert icon is box_cls.Icon.Warning
        assert title == "Warning"

    def test_anything_below_warning_shows_nothing(self, handler, mocker):
        """Log severity is not a statement about how the user should be interrupted."""
        box_cls = mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=None
        )

        handler.show_message_box(make_record(logging.INFO))

        box_cls.assert_not_called()


class TestQueueingIsUnchanged:
    """The behaviour the fix had to leave alone."""

    def test_a_record_arriving_while_a_dialog_is_open_is_queued(self, handler, mocker):
        """
        A modal dialog runs its own event loop, during which more records arrive.
        They used to be dropped outright.

        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        box_cls = mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=None
        )
        handler._dialog_open = True

        handler.show_message_box(make_record(logging.ERROR, "second problem"))

        box_cls.assert_not_called()
        assert len(handler._pending) == 1

    def test_a_repeat_of_what_is_on_screen_is_dropped(self, handler, mocker):
        """One dialog per distinct failure, not one per loop iteration."""
        mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        handler._dialog_open = True
        handler._current_text = "the same thing"

        handler.show_message_box(make_record(logging.ERROR, "the same thing"))

        assert not handler._pending

    def test_a_burst_beyond_the_cap_is_collapsed(self, handler, mocker):
        """
        A failing per-event code path can log hundreds of records in a second, and
        one modal dialog each would wedge the application.

        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        mocker.patch("poriscope.utils.QtHandler.QMessageBox")
        handler._dialog_open = True

        for i in range(MAX_PENDING_RECORDS + 5):
            handler.show_message_box(make_record(logging.ERROR, f"problem {i}"))

        assert len(handler._pending) == MAX_PENDING_RECORDS
        assert handler._suppressed == 5

    def test_the_dialog_flag_is_cleared_even_if_showing_raises(self, handler, mocker):
        """
        Without the ``finally``, one failed dialog would silently suppress every
        later one for the rest of the session.

        :param handler: The handler under test.
        :param mocker: Pytest-mock fixture.
        """
        mocker.patch(
            "poriscope.utils.QtHandler.QApplication.activeWindow", return_value=None
        )
        mocker.patch(
            "poriscope.utils.QtHandler.QMessageBox", side_effect=RuntimeError("no gui")
        )

        with pytest.raises(RuntimeError):
            handler.show_message_box(make_record(logging.ERROR))

        assert handler._dialog_open is False
