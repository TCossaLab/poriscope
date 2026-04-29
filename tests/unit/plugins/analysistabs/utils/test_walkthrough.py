"""
Tests for poriscope/plugins/analysistabs/utils/walkthrough.py

Covers:
- Overlay: __init__, highlight (single/list), eventFilter (Resize/Move/other), paintEvent
- StepDialog: __init__, update_step, next_step, prev_step, force_close,
              reposition, _reposition_now (no widget), _reposition_and_show
- start_walkthrough: happy path, overlay failure, dialog failure
- IntroDialog: emit_start, paintEvent
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDialog, QWidget

from poriscope.plugins.analysistabs.utils.walkthrough import (
    IntroDialog,
    Overlay,
    StepDialog,
    start_walkthrough,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parent_widget(qtbot):
    w = QWidget()
    w.resize(800, 600)
    qtbot.addWidget(w)
    w.show()
    return w


@pytest.fixture
def overlay(parent_widget, qtbot):
    ov = Overlay(parent_widget)
    qtbot.addWidget(ov)
    return ov


def _make_steps(parent_widget, n=3):
    """Make n dummy steps, each pointing at the parent widget."""
    return [(f"Title {i}", f"Message {i}", parent_widget) for i in range(n)]


@pytest.fixture
def step_dialog(parent_widget, overlay, qtbot):
    steps = _make_steps(parent_widget, 3)
    d = StepDialog(parent_widget, steps, overlay)
    qtbot.addWidget(d)
    return d


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------


class TestOverlay:
    def test_init_geometry_matches_parent(self, overlay, parent_widget):
        assert overlay.geometry() == parent_widget.rect()

    def test_highlight_single_widget(self, overlay, parent_widget):
        overlay.highlight(parent_widget)
        assert overlay.target_widgets == [parent_widget]

    def test_highlight_list_of_widgets(self, overlay, parent_widget, qtbot):
        w2 = QWidget()
        qtbot.addWidget(w2)
        overlay.highlight([parent_widget, w2])
        assert len(overlay.target_widgets) == 2

    def test_highlight_tuple(self, overlay, parent_widget, qtbot):
        w2 = QWidget()
        qtbot.addWidget(w2)
        overlay.highlight((parent_widget, w2))
        assert len(overlay.target_widgets) == 2

    def test_eventfilter_resize_updates_geometry(self, overlay, parent_widget):
        parent_widget.resize(400, 300)
        # geometry should track parent
        assert overlay.geometry() == parent_widget.rect()

    def test_eventfilter_other_event_ignored(self, overlay, parent_widget):
        """Non-resize/move events don't crash."""
        event = QEvent(QEvent.Paint)
        result = overlay.eventFilter(parent_widget, event)
        assert result is False  # passed to super

    def test_eventfilter_move_event(self, overlay, parent_widget):
        event = QEvent(QEvent.Move)
        overlay.eventFilter(parent_widget, event)
        assert overlay.geometry() == parent_widget.rect()

    def test_paint_event_no_crash_empty_targets(self, overlay):
        overlay.target_widgets = []
        overlay.update()  # triggers paintEvent internally — should not crash

    def test_paint_event_no_crash_with_targets(self, overlay, parent_widget):
        overlay.highlight(parent_widget)
        overlay.update()  # should not crash


# ---------------------------------------------------------------------------
# StepDialog – initialization
# ---------------------------------------------------------------------------


class TestStepDialogInit:
    def test_starts_at_step_zero(self, step_dialog):
        assert step_dialog.current == 0

    def test_title_set_correctly(self, step_dialog):
        assert step_dialog.title.text() == "Title 0"

    def test_message_set_correctly(self, step_dialog):
        assert step_dialog.message.text() == "Message 0"

    def test_step_label_shows_1_of_n(self, step_dialog):
        assert step_dialog.step_label.text() == "1/3"

    def test_back_btn_hidden_on_first_step(self, step_dialog):
        assert not step_dialog.back_btn.isVisible()

    def test_next_btn_text_is_next_not_done(self, step_dialog):
        assert step_dialog.next_btn.text() == "Next"

    def test_next_btn_text_is_done_on_last_step(self, parent_widget, overlay, qtbot):
        steps = _make_steps(parent_widget, 1)
        d = StepDialog(parent_widget, steps, overlay)
        qtbot.addWidget(d)
        assert d.next_btn.text() == "Done"


# ---------------------------------------------------------------------------
# StepDialog – navigation
# ---------------------------------------------------------------------------


class TestStepDialogNavigation:
    def test_next_step_advances_current(self, step_dialog):
        step_dialog.next_step()
        assert step_dialog.current == 1

    def test_next_step_updates_title(self, step_dialog):
        step_dialog.next_step()
        assert step_dialog.title.text() == "Title 1"

    def test_next_step_shows_back_btn(self, step_dialog):
        step_dialog.next_step()
        assert step_dialog.back_btn.isVisible()

    def test_prev_step_goes_back(self, step_dialog):
        step_dialog.next_step()
        step_dialog.prev_step()
        assert step_dialog.current == 0

    def test_prev_step_hides_back_btn(self, step_dialog):
        step_dialog.next_step()
        step_dialog.prev_step()
        assert not step_dialog.back_btn.isVisible()

    def test_prev_step_at_zero_stays_at_zero(self, step_dialog):
        step_dialog.prev_step()
        assert step_dialog.current == 0

    def test_next_step_on_last_emits_done_signal(self, step_dialog, qtbot):
        step_dialog.current = 2  # last step (3 steps total, 0-indexed)
        with qtbot.waitSignal(step_dialog.done_signal, timeout=1000):
            step_dialog.next_step()

    def test_next_step_on_last_sets_was_completed(self, step_dialog):
        step_dialog.current = 2
        step_dialog.next_step()
        assert step_dialog._was_completed is True

    def test_step_label_updates_on_next(self, step_dialog):
        step_dialog.next_step()
        assert step_dialog.step_label.text() == "2/3"

    def test_next_btn_becomes_done_on_last(self, step_dialog):
        step_dialog.next_step()
        step_dialog.next_step()
        assert step_dialog.next_btn.text() == "Done"


# ---------------------------------------------------------------------------
# StepDialog – force_close
# ---------------------------------------------------------------------------


class TestStepDialogForceClose:
    def test_force_close_emits_done_signal(self, step_dialog, qtbot):
        with qtbot.waitSignal(step_dialog.done_signal, timeout=1000):
            step_dialog.force_close()

    def test_force_close_stops_timer(self, step_dialog):
        step_dialog.force_close()
        assert not step_dialog.reposition_timer.isActive()


# ---------------------------------------------------------------------------
# StepDialog – reposition
# ---------------------------------------------------------------------------


class TestStepDialogReposition:
    def test_reposition_no_crash_with_no_target(self, step_dialog):
        step_dialog.target_widget = None
        step_dialog.reposition()  # should not crash

    def test_reposition_now_no_widget_returns_early(self, step_dialog):
        step_dialog.target_widget = None
        step_dialog._reposition_now()  # should not crash

    def test_reposition_now_moves_dialog(self, step_dialog, parent_widget):
        step_dialog.target_widget = parent_widget
        step_dialog._reposition_now()
        # dialog should have moved somewhere (not crashed)
        assert step_dialog._last_pos is not None

    def test_reposition_and_show_no_crash(self, step_dialog, parent_widget):
        step_dialog.target_widget = parent_widget
        step_dialog._reposition_and_show()


# ---------------------------------------------------------------------------
# IntroDialog
# ---------------------------------------------------------------------------


class TestIntroDialog:
    @pytest.fixture
    def mock_parent(self, qtbot):
        parent = QWidget()
        parent.resize(800, 600)
        parent.get_intro_text = MagicMock(return_value="Welcome text for testing.")
        qtbot.addWidget(parent)
        parent.show()
        return parent

    def test_emit_start_emits_signal(self, mock_parent, qtbot):
        dialog = IntroDialog(mock_parent, "MainView")
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.start_walkthrough, timeout=1000):
            dialog.emit_start()

    def test_emit_start_closes_dialog(self, mock_parent, qtbot):
        dialog = IntroDialog(mock_parent, "MainView")
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.emit_start()
        assert not dialog.isVisible()

    def test_paint_event_no_crash(self, mock_parent, qtbot):
        dialog = IntroDialog(mock_parent, "MainView")
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.update()  # triggers paintEvent


# ---------------------------------------------------------------------------
# start_walkthrough
# ---------------------------------------------------------------------------


class TestStartWalkthrough:
    def test_returns_step_dialog(self, parent_widget, qtbot):
        steps = _make_steps(parent_widget, 2)
        result = start_walkthrough(parent_widget, steps)
        if result is not None:
            qtbot.addWidget(result)
        assert result is not None

    def test_returns_dialog_instance(self, parent_widget, qtbot):
        steps = _make_steps(parent_widget, 2)
        result = start_walkthrough(parent_widget, steps)
        if result is not None:
            qtbot.addWidget(result)
        assert isinstance(result, QDialog)

    def test_overlay_failure_falls_back_gracefully(self, parent_widget, qtbot):
        """If Overlay raises, start_walkthrough still returns a dialog."""
        steps = _make_steps(parent_widget, 1)
        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough.Overlay",
            side_effect=RuntimeError("overlay boom"),
        ):
            result = start_walkthrough(parent_widget, steps)
            if result is not None:
                qtbot.addWidget(result)
            assert result is not None

    def test_dialog_failure_returns_fallback(self, parent_widget, qtbot):
        """If StepDialog raises, start_walkthrough returns a fallback QDialog."""
        steps = _make_steps(parent_widget, 1)
        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough.StepDialog",
            side_effect=RuntimeError("dialog boom"),
        ):
            result = start_walkthrough(parent_widget, steps)
            if result is not None:
                qtbot.addWidget(result)
            assert isinstance(result, QDialog)
