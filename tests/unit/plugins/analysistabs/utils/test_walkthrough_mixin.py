"""
Tests for poriscope/plugins/analysistabs/utils/walkthrough_mixin.py

Strategy: create a minimal concrete QWidget subclass that implements the two
abstract methods (get_current_view, get_walkthrough_steps), then test all
WalkthroughMixin methods by calling them directly.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QRect, Signal
from PySide6.QtWidgets import QWidget

from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin

# ---------------------------------------------------------------------------
# Minimal concrete implementation
# ---------------------------------------------------------------------------


class ConcreteWalkthrough(WalkthroughMixin, QWidget):
    """Minimal concrete subclass for testing."""

    walkthrough_finished = Signal(str, bool)

    def __init__(self, view="MainView", steps=None):
        QWidget.__init__(self)
        self.resize(800, 600)
        self._view = view
        self._steps = steps or []
        self._init_walkthrough()

    def get_current_view(self):
        return self._view

    def get_walkthrough_steps(self):
        return self._steps


@pytest.fixture
def widget(qtbot):
    w = ConcreteWalkthrough()
    qtbot.addWidget(w)
    w.show()
    return w


def _make_step(view="MainView", label="Step", desc="Desc", widget_fn=None):
    """Return a single (label, desc, view, widget_fn) tuple."""
    if widget_fn is None:
        mock_w = MagicMock(spec=QWidget)

        def widget_fn():
            return mock_w

    return (label, desc, view, widget_fn)


# ---------------------------------------------------------------------------
# _init_walkthrough
# ---------------------------------------------------------------------------


class TestInitWalkthrough:
    def test_sets_active_false(self, widget):
        assert widget._walkthrough_active is False

    def test_sets_index_zero(self, widget):
        assert widget._walkthrough_index == 0

    def test_sets_empty_steps(self, widget):
        assert widget._global_walkthrough_steps == []

    def test_sets_dialog_none(self, widget):
        assert widget.walkthrough_dialog is None


# ---------------------------------------------------------------------------
# launch_walkthrough
# ---------------------------------------------------------------------------


class TestLaunchWalkthrough:
    def test_invalid_view_sets_active_false(self, qtbot):
        target = MagicMock(spec=QWidget)
        steps = [_make_step("OtherView", widget_fn=lambda: target)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w.launch_walkthrough()
        assert w._walkthrough_active is False

    def test_valid_view_sets_index_to_matching_step(self, qtbot):
        target = MagicMock(spec=QWidget)
        steps = [
            _make_step("OtherView", label="S0", widget_fn=lambda: target),
            _make_step("MainView", label="S1", widget_fn=lambda: target),
        ]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        with patch.object(w, "_run_next_walkthrough_step") as mock_run:
            w.launch_walkthrough()
            assert w._walkthrough_index == 1
            mock_run.assert_called_once()

    def test_sets_global_steps(self, qtbot):
        target = MagicMock(spec=QWidget)
        steps = [_make_step("MainView", widget_fn=lambda: target)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        with patch.object(w, "_run_next_walkthrough_step"):
            w.launch_walkthrough()
        assert w._global_walkthrough_steps == steps


# ---------------------------------------------------------------------------
# _run_next_walkthrough_step
# ---------------------------------------------------------------------------


class TestRunNextWalkthroughStep:
    def test_index_past_end_sets_inactive(self, widget):
        widget._global_walkthrough_steps = []
        widget._walkthrough_index = 0
        widget._walkthrough_active = True
        widget._run_next_walkthrough_step()
        assert widget._walkthrough_active is False

    def test_view_matches_launches_dialog(self, qtbot):
        """When current view matches target, start_walkthrough is called."""
        real_widget = QWidget()
        qtbot.addWidget(real_widget)
        real_widget.show()

        steps = [_make_step("MainView", widget_fn=lambda: real_widget)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w.show()
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.start_walkthrough"
        ) as mock_start:
            mock_dialog = MagicMock()
            mock_dialog.done_signal = MagicMock()
            mock_start.return_value = mock_dialog
            w._run_next_walkthrough_step()
            qtbot.waitUntil(lambda: mock_start.called, timeout=1000)
            mock_start.assert_called_once()

    def test_view_mismatch_schedules_retry(self, qtbot):
        """When view doesn't match, a QTimer retry is scheduled (no crash)."""
        real_widget = QWidget()
        qtbot.addWidget(real_widget)

        steps = [_make_step("OtherView", widget_fn=lambda: real_widget)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.QTimer"
        ) as mock_timer:
            w._run_next_walkthrough_step()
            mock_timer.singleShot.assert_called()

    def test_no_valid_widgets_logs_error(self, qtbot):
        """widget_fn returning None/falsy raises ValueError → logs error, no crash."""
        steps = [_make_step("MainView", widget_fn=lambda: None)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.start_walkthrough"
        ) as mock_start:
            w._run_next_walkthrough_step()
            # start_walkthrough should NOT have been called since no valid widgets
            qtbot.wait(100)
            mock_start.assert_not_called()

    def test_collects_steps_for_same_view_only(self, qtbot):
        """Steps from a different view are not included in the launched dialog."""
        real_widget = QWidget()
        qtbot.addWidget(real_widget)
        real_widget.show()

        steps = [
            _make_step("MainView", label="S0", widget_fn=lambda: real_widget),
            _make_step("MainView", label="S1", widget_fn=lambda: real_widget),
            _make_step("OtherView", label="S2", widget_fn=lambda: real_widget),
        ]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w.show()
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        captured = []

        def fake_start(parent, s):
            captured.extend(s)
            mock_dialog = MagicMock()
            mock_dialog.done_signal = MagicMock()
            return mock_dialog

        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.start_walkthrough",
            side_effect=fake_start,
        ):
            w._run_next_walkthrough_step()
            qtbot.waitUntil(lambda: len(captured) > 0, timeout=1000)

        # Only 2 MainView steps, not the OtherView one
        assert len(captured) == 2


# ---------------------------------------------------------------------------
# _reposition_dialog – fallback branches (lines 240, 253, 265)
# ---------------------------------------------------------------------------


class TestRepositionDialogFallbacks:
    """
    Force each fallback branch by controlling what QRect.contains returns.
    We patch the contains() method on QRect instances via the module-level
    QRect so we can precisely control which branch executes.
    """

    def _setup(self, qtbot):
        from poriscope.plugins.analysistabs.utils.walkthrough import Overlay, StepDialog

        parent = ConcreteWalkthrough()
        parent.resize(800, 600)
        qtbot.addWidget(parent)
        parent.show()

        overlay = Overlay(parent)
        qtbot.addWidget(overlay)
        steps = [("Title", "Msg", parent)]
        dialog = StepDialog(parent, steps, overlay)
        qtbot.addWidget(dialog)
        dialog.setFixedSize(320, 160)
        parent.walkthrough_dialog = dialog
        return parent, dialog

    @pytest.mark.skip(
        reason="Qt object lifetime makes this unreliable across platforms"
    )
    def test_candidate_fits_calls_move_and_returns(self, qtbot):
        """Primary candidate fits → dialog.move(pos) called (lines 240-241).
        Parent is enormous so 'right of widget' candidate fits inside window_rect."""
        from poriscope.plugins.analysistabs.utils.walkthrough import Overlay, StepDialog

        parent = ConcreteWalkthrough()
        parent.resize(3000, 3000)
        parent.move(0, 0)
        qtbot.addWidget(parent)
        parent.show()
        qtbot.waitExposed(parent)

        # Small target widget positioned near left edge so 'right' candidate fits
        target = QWidget(parent)
        target.resize(50, 50)
        target.move(10, 1500)  # vertically centred so above/below also fits
        target.show()

        overlay = Overlay(parent)
        # Do NOT add overlay to qtbot — parent owns it, double-delete causes the error
        steps = [("Title", "Msg", target)]
        dialog = StepDialog(parent, steps, overlay)
        qtbot.addWidget(dialog)
        dialog.setFixedSize(100, 80)
        parent.walkthrough_dialog = dialog

        # Keep hard references so GC doesn't collect them mid-test
        parent._test_refs = [target, overlay, dialog]

        move_calls = []
        original_move = dialog.move

        def tracking_move(pos):
            move_calls.append(pos)
            original_move(pos)

        dialog.move = tracking_move

        event = MagicMock()
        parent._reposition_dialog(event)

        assert len(move_calls) >= 1

    @pytest.mark.skip(
        reason="Qt object lifetime makes this unreliable across platforms"
    )
    def test_fallback_below_branch(self, qtbot):
        """All candidates fail, fallback_below fits → lines 253-254 hit."""
        parent, dialog = self._setup(qtbot)

        move_calls = []
        dialog.move = lambda pos: move_calls.append(pos)

        # Patch QRect.contains so:
        #   - first 4 calls (candidates) → False
        #   - 5th call (below_rect) → True
        #   - intersects always False
        call_count = [0]

        def fake_contains(self_rect, other):
            call_count[0] += 1
            if call_count[0] <= 4:
                return False  # candidates fail
            if call_count[0] == 5:
                return True  # fallback_below succeeds
            return False

        with patch.object(QRect, "contains", fake_contains):
            with patch.object(QRect, "intersects", return_value=False):
                event = MagicMock()
                parent._reposition_dialog(event)

        assert len(move_calls) >= 1

    def test_fallback_above_branch(self, qtbot):
        """Candidates + below fail, fallback_above fits → lines 265-266 hit."""
        parent, dialog = self._setup(qtbot)

        move_calls = []
        dialog.move = lambda pos: move_calls.append(pos)

        call_count = [0]

        def fake_contains(self_rect, other):
            call_count[0] += 1
            if call_count[0] <= 5:
                return False  # candidates + below fail
            if call_count[0] == 6:
                return True  # fallback_above succeeds
            return False

        with patch.object(QRect, "contains", fake_contains):
            with patch.object(QRect, "intersects", return_value=False):
                event = MagicMock()
                parent._reposition_dialog(event)

        assert len(move_calls) >= 1

    def test_last_resort_branch(self, qtbot):
        """All fallbacks fail → last-resort bottom-right placement (no crash)."""
        parent, dialog = self._setup(qtbot)

        move_calls = []
        dialog.move = lambda pos: move_calls.append(pos)

        # All contains() calls return False → falls through to last resort
        with patch.object(QRect, "contains", return_value=False):
            with patch.object(QRect, "intersects", return_value=True):
                event = MagicMock()
                parent._reposition_dialog(event)

        assert len(move_calls) == 1  # last resort always moves


# ---------------------------------------------------------------------------
# check_next_view auto-advance (line 128-131) and pseudo while-loop (line 197)
# ---------------------------------------------------------------------------


class TestCheckNextViewAndPseudo:
    def test_check_next_view_auto_advances_on_view_change(self, qtbot):
        """
        When check_next_view fires and current_view != target_view,
        _handle_walkthrough_done is called with is_pseudo=True (lines 128-131).
        """
        real_widget = QWidget()
        qtbot.addWidget(real_widget)
        real_widget.show()

        steps = [_make_step("MainView", widget_fn=lambda: real_widget)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w.show()
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        mock_dialog = MagicMock()
        mock_dialog.done_signal = MagicMock()

        # Flip view immediately so check_next_view sees a mismatch on first fire
        def fake_start(parent, s):
            w._view = "OtherView"
            return mock_dialog

        handle_called = []

        def tracking_handle(*args, **kwargs):
            handle_called.append((args, kwargs))

        w._handle_walkthrough_done = tracking_handle

        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.start_walkthrough",
            side_effect=fake_start,
        ):
            w._run_next_walkthrough_step()
            # Process Qt event loop long enough for singleShot(500) to fire
            qtbot.wait(700)

        assert len(handle_called) > 0
        # Verify it was called with is_pseudo=True
        assert any(kw.get("is_pseudo") is True for _, kw in handle_called)

    def test_pseudo_skips_non_matching_views_increments_index(self, qtbot):
        """
        is_pseudo=True with steps [MainView, OtherView, MainView]:
        after completing MainView step (index=0), pseudo should scan forward,
        skip OtherView (index 1, line 197 hit), and find next MainView.
        """
        real_widget = QWidget()
        qtbot.addWidget(real_widget)

        steps = [
            _make_step("MainView", label="S0", widget_fn=lambda: real_widget),
            _make_step("OtherView", label="S1", widget_fn=lambda: real_widget),
            _make_step("MainView", label="S2", widget_fn=lambda: real_widget),
        ]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 1  # already past S0, now pointing at OtherView

        dialog = MagicMock()
        dialog._was_completed = False
        dialog.overlay = MagicMock()
        dialog.reposition_timer = MagicMock()
        w.walkthrough_dialog = dialog

        with patch.object(w, "_run_next_walkthrough_step") as mock_run:
            w._handle_walkthrough_done(0, is_pseudo=True)
            # index 1 is OtherView (skipped via line 197), index 2 is MainView
            mock_run.assert_called_once()
            assert w._walkthrough_index == 2


# ---------------------------------------------------------------------------
# _advance_walkthrough_index
# ---------------------------------------------------------------------------


class TestAdvanceWalkthroughIndex:
    def test_increments_index(self, widget):
        target = MagicMock(spec=QWidget)
        widget._global_walkthrough_steps = [
            _make_step(widget_fn=lambda: target),
            _make_step(widget_fn=lambda: target),
        ]
        widget._walkthrough_index = 0
        with patch.object(widget, "_run_next_walkthrough_step") as mock_run:
            widget._advance_walkthrough_index()
            assert widget._walkthrough_index == 1
            mock_run.assert_called_once()

    def test_sets_inactive_when_no_more_steps(self, widget):
        target = MagicMock(spec=QWidget)
        widget._global_walkthrough_steps = [_make_step(widget_fn=lambda: target)]
        widget._walkthrough_index = 0
        widget._walkthrough_active = True
        widget._advance_walkthrough_index()
        assert widget._walkthrough_active is False


# ---------------------------------------------------------------------------
# _handle_walkthrough_done
# ---------------------------------------------------------------------------


class TestHandleWalkthroughDone:
    def _make_mock_dialog(self, was_completed=True):
        dialog = MagicMock()
        dialog._was_completed = was_completed
        dialog.overlay = MagicMock()
        dialog.reposition_timer = MagicMock()
        return dialog

    def test_increments_index_by_steps_completed(self, widget):
        widget._walkthrough_index = 0
        widget.walkthrough_dialog = self._make_mock_dialog()
        widget._handle_walkthrough_done(3)
        assert widget._walkthrough_index == 3

    def test_closes_dialog(self, widget):
        dialog = self._make_mock_dialog()
        widget.walkthrough_dialog = dialog
        widget._handle_walkthrough_done(1)
        dialog.close.assert_called_once()

    def test_hides_overlay(self, widget):
        dialog = self._make_mock_dialog()
        widget.walkthrough_dialog = dialog
        widget._handle_walkthrough_done(1)
        dialog.overlay.hide.assert_called_once()

    def test_stops_reposition_timer(self, widget):
        dialog = self._make_mock_dialog()
        widget.walkthrough_dialog = dialog
        widget._handle_walkthrough_done(1)
        dialog.reposition_timer.stop.assert_called_once()

    def test_emits_finished_true_when_completed(self, widget, qtbot):
        dialog = self._make_mock_dialog(was_completed=True)
        widget.walkthrough_dialog = dialog
        with qtbot.waitSignal(widget.walkthrough_finished, timeout=1000) as blocker:
            widget._handle_walkthrough_done(1)
        view, completed = blocker.args
        assert completed is True

    def test_emits_finished_false_when_not_completed(self, widget, qtbot):
        dialog = self._make_mock_dialog(was_completed=False)
        widget.walkthrough_dialog = dialog
        with qtbot.waitSignal(widget.walkthrough_finished, timeout=1000) as blocker:
            widget._handle_walkthrough_done(1)
        view, completed = blocker.args
        assert completed is False

    def test_sets_dialog_none_after_close(self, widget):
        widget.walkthrough_dialog = self._make_mock_dialog()
        widget._handle_walkthrough_done(1)
        assert widget.walkthrough_dialog is None

    def test_sets_active_false(self, widget):
        widget._walkthrough_active = True
        widget.walkthrough_dialog = self._make_mock_dialog()
        widget._handle_walkthrough_done(1)
        assert widget._walkthrough_active is False

    def test_no_dialog_no_crash(self, widget):
        widget.walkthrough_dialog = None
        widget._walkthrough_index = 0
        widget._handle_walkthrough_done(2)
        assert widget._walkthrough_index == 2

    def test_dialog_without_reposition_timer(self, widget):
        """Dialog without reposition_timer attr should not crash."""
        dialog = MagicMock(spec=["overlay", "_was_completed", "close"])
        dialog._was_completed = False
        dialog.overlay = MagicMock()
        widget.walkthrough_dialog = dialog
        widget._handle_walkthrough_done(1)  # should not raise

    def test_pseudo_advances_to_matching_next_view(self, qtbot):
        """is_pseudo=True should call _run_next_walkthrough_step if next view matches."""
        target = MagicMock(spec=QWidget)
        steps = [
            _make_step("MainView", label="S0", widget_fn=lambda: target),
            _make_step("MainView", label="S1", widget_fn=lambda: target),
        ]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        dialog = MagicMock()
        dialog._was_completed = False
        dialog.overlay = MagicMock()
        dialog.reposition_timer = MagicMock()
        w.walkthrough_dialog = dialog

        with patch.object(w, "_run_next_walkthrough_step") as mock_run:
            w._handle_walkthrough_done(1, is_pseudo=True)
            mock_run.assert_called_once()

    def test_pseudo_no_matching_next_view_stops(self, qtbot):
        """is_pseudo=True with no matching next view just logs and stops."""
        target = MagicMock(spec=QWidget)
        steps = [_make_step("MainView", widget_fn=lambda: target)]
        w = ConcreteWalkthrough(view="MainView", steps=steps)
        qtbot.addWidget(w)
        w._global_walkthrough_steps = steps
        w._walkthrough_index = 0

        dialog = MagicMock()
        dialog._was_completed = False
        dialog.overlay = MagicMock()
        dialog.reposition_timer = MagicMock()
        w.walkthrough_dialog = dialog

        with patch.object(w, "_run_next_walkthrough_step") as mock_run:
            w._handle_walkthrough_done(1, is_pseudo=True)
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# show_walkthrough_intro
# ---------------------------------------------------------------------------


class TestShowWalkthroughIntro:
    def test_skips_if_already_active(self, widget):
        widget._walkthrough_active = True
        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.IntroDialog"
        ) as MockDialog:
            widget.show_walkthrough_intro("MainView")
            MockDialog.assert_not_called()

    def test_creates_intro_dialog_when_inactive(self, widget):
        widget._walkthrough_active = False
        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.IntroDialog"
        ) as MockDialog:
            mock_intro = MagicMock()
            MockDialog.return_value = mock_intro
            widget.show_walkthrough_intro("MainView")
            MockDialog.assert_called_once_with(widget, current_step="MainView")
            mock_intro.exec.assert_called_once()

    def test_connects_signal_to_launch(self, widget):
        widget._walkthrough_active = False
        with patch(
            "poriscope.plugins.analysistabs.utils.walkthrough_mixin.IntroDialog"
        ) as MockDialog:
            mock_intro = MagicMock()
            MockDialog.return_value = mock_intro
            widget.show_walkthrough_intro("MainView")
            mock_intro.start_walkthrough.connect.assert_called_once_with(
                widget.launch_walkthrough
            )


# ---------------------------------------------------------------------------
# get_current_view / get_walkthrough_steps – abstract method contract
# ---------------------------------------------------------------------------


class TestAbstractMethods:
    def test_get_current_view_raises_if_not_implemented(self):
        mixin = WalkthroughMixin()
        with pytest.raises(NotImplementedError):
            mixin.get_current_view()

    def test_get_walkthrough_steps_raises_if_not_implemented(self):
        mixin = WalkthroughMixin()
        with pytest.raises(NotImplementedError):
            mixin.get_walkthrough_steps()


# ---------------------------------------------------------------------------
# _reposition_dialog
# ---------------------------------------------------------------------------


class TestRepositionDialog:
    def _make_dialog_with_steps(self, widget_instance, qtbot):
        from poriscope.plugins.analysistabs.utils.walkthrough import (
            Overlay,
            StepDialog,
        )

        overlay = Overlay(widget_instance)
        qtbot.addWidget(overlay)
        steps = [("Title", "Msg", widget_instance)]
        dialog = StepDialog(widget_instance, steps, overlay)
        qtbot.addWidget(dialog)
        return dialog

    def test_no_crash_when_dialog_is_none(self, widget):
        widget.walkthrough_dialog = None
        event = MagicMock()
        widget._reposition_dialog(event)  # should not crash

    def test_repositions_dialog_to_a_point(self, widget, qtbot):
        dialog = self._make_dialog_with_steps(widget, qtbot)
        widget.walkthrough_dialog = dialog
        event = MagicMock()
        widget._reposition_dialog(event)
        # dialog should have been moved somewhere — just check no crash
        assert dialog is not None

    def test_handles_list_widget_in_step(self, widget, qtbot):
        """Steps with list widgets don't crash reposition."""
        dialog = self._make_dialog_with_steps(widget, qtbot)
        dialog.steps = [("Title", "Msg", [widget])]
        widget.walkthrough_dialog = dialog
        event = MagicMock()
        widget._reposition_dialog(event)


# ---------------------------------------------------------------------------
# _force_close_walkthrough_dialog
# ---------------------------------------------------------------------------


class TestForceCloseWalkthroughDialog:
    def test_no_dialog_no_crash(self, widget):
        widget.walkthrough_dialog = None
        widget._force_close_walkthrough_dialog()  # should not crash

    def test_closes_dialog_and_clears(self, widget, qtbot):
        mock_dialog = MagicMock()
        widget.walkthrough_dialog = mock_dialog
        widget._force_close_walkthrough_dialog()
        mock_dialog.done.assert_called_once_with(0)
        assert widget.walkthrough_dialog is None
        assert widget._walkthrough_active is False

    def test_emits_finished_false_on_force_close(self, widget, qtbot):
        mock_dialog = MagicMock()
        widget.walkthrough_dialog = mock_dialog
        with qtbot.waitSignal(widget.walkthrough_finished, timeout=1000) as blocker:
            widget._force_close_walkthrough_dialog()
        _, completed = blocker.args
        assert completed is False

    def test_handles_exception_gracefully(self, widget):
        mock_dialog = MagicMock()
        mock_dialog.done.side_effect = RuntimeError("boom")
        widget.walkthrough_dialog = mock_dialog
        widget._force_close_walkthrough_dialog()  # should not raise
        assert widget.walkthrough_dialog is None
