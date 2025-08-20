# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Alejandra Carolina González González


import logging

from PySide6.QtCore import QPoint, QRect, QTimer, Signal

from poriscope.plugins.analysistabs.utils.walkthrough import (
    IntroDialog,
    start_walkthrough,
)


class WalkthroughMixin:
    """
    Mixin class to provide walkthrough functionality.

    Subclasses must implement `get_current_view()` and `get_walkthrough_steps()`.

    Signals:
        walkthrough_finished (str, bool): Emitted when the walkthrough ends.
            Parameters:
                - current_view (str): The name of the current view.
                - was_completed (bool): True if walkthrough finished successfully, False if exited early.
    """

    walkthrough_finished = Signal(str, bool)
    logger = logging.getLogger(__name__)

    def _init_walkthrough(self):
        """
        Initializes walkthrough state and internal tracking variables.
        """
        self._walkthrough_active = False
        self._walkthrough_index = 0
        self._global_walkthrough_steps = []
        self.walkthrough_dialog = None

    def launch_walkthrough(self):
        """
        Starts the walkthrough process from the appropriate view.
        Skips to the relevant section depending on the current view.
        """
        self.logger.debug("Walkthrough launched")
        self._walkthrough_active = True
        self._walkthrough_index = 0

        current_view = self.get_current_view()
        self._global_walkthrough_steps = self.get_walkthrough_steps()

        # Ensure we are on a valid view for the walkthrough
        if current_view not in [step[2] for step in self._global_walkthrough_steps]:
            self.logger.error(f"Walkthrough cannot start from '{current_view}'")
            self._walkthrough_active = False
            return

        # Find starting point in the steps list
        for i, step in enumerate(self._global_walkthrough_steps):
            if step[2] == current_view:
                self._walkthrough_index = i
                break

        self._run_next_walkthrough_step()

    def _run_next_walkthrough_step(self):
        """
        Executes the next step in the walkthrough, waiting for the correct view.
        """
        if self._walkthrough_index >= len(self._global_walkthrough_steps):
            self.logger.info("Walkthrough completed.")
            self._walkthrough_active = False
            return

        label, desc, target_view, widget_func = self._global_walkthrough_steps[
            self._walkthrough_index
        ]

        def wait_for_view():
            """
            Recursively waits until the user is on the correct view before launching the step.
            """
            self.logger.debug(
                f"Current view during wait: {self.get_current_view()}, target: {target_view}"
            )
            if self.get_current_view() == target_view:
                try:
                    steps = []
                    for i in range(
                        self._walkthrough_index, len(self._global_walkthrough_steps)
                    ):
                        lbl, dsc, vw, func = self._global_walkthrough_steps[i]
                        if vw != target_view:
                            break
                        widget = func()
                        if widget:
                            steps.append((lbl, dsc, widget))

                    if not steps:
                        raise ValueError("No valid widgets found for this view.")

                    self.walkthrough_dialog = start_walkthrough(self, steps)

                    def check_next_view():
                        if self.get_current_view() != target_view:
                            self.logger.info(
                                "Auto-advancing walkthrough on view change."
                            )
                            self._handle_walkthrough_done(len(steps), is_pseudo=True)
                        else:
                            QTimer.singleShot(500, check_next_view)

                    check_next_view()

                    self.walkthrough_dialog.done_signal.connect(
                        lambda: self._handle_walkthrough_done(len(steps))
                    )
                    self.walkthrough_dialog.moveEvent = self._reposition_dialog

                except Exception as e:
                    self.logger.error(f"Error in walkthrough step '{label}': {e}")
            else:
                QTimer.singleShot(200, wait_for_view)

        wait_for_view()

    def _advance_walkthrough_index(self):
        """
        Increments the walkthrough index and moves to the next step, if available.
        """
        self._walkthrough_index += 1
        if self._walkthrough_index < len(self._global_walkthrough_steps):
            self._run_next_walkthrough_step()
        else:
            self._walkthrough_active = False
            self.logger.info("Walkthrough finished.")

    def _handle_walkthrough_done(self, steps_completed, *, is_pseudo=False):
        """
        Handles cleanup and transition after a walkthrough step or sequence.

        :param steps_completed: Number of steps completed in the walkthrough.
        :type steps_completed: int
        :param is_pseudo: True if the step was completed implicitly (e.g. view change).
        :type is_pseudo: bool
        """
        self._walkthrough_index += steps_completed

        if self.walkthrough_dialog:
            self.walkthrough_dialog.overlay.hide()
            self.walkthrough_dialog.overlay.deleteLater()
            if hasattr(self.walkthrough_dialog, "reposition_timer"):
                self.walkthrough_dialog.reposition_timer.stop()

            was_completed = getattr(self.walkthrough_dialog, "_was_completed", False)
            self.walkthrough_dialog.close()
            self.walkthrough_dialog = None

            if was_completed:
                self.logger.info("Walkthrough completed manually.")
                self.walkthrough_finished.emit(self.get_current_view(), True)
            else:
                self.logger.info("Walkthrough closed early.")
                self.walkthrough_finished.emit(self.get_current_view(), False)

        self._walkthrough_active = False

        if is_pseudo:
            current_view = self.get_current_view()
            while self._walkthrough_index < len(self._global_walkthrough_steps):
                next_view = self._global_walkthrough_steps[self._walkthrough_index][2]
                if current_view == next_view:
                    self._run_next_walkthrough_step()
                    return
                self._walkthrough_index += 1

            self.logger.info("Walkthrough pseudo-ended, no next step found.")

    def _reposition_dialog(self, event):
        """
        Reposition the walkthrough dialog near the highlighted widget,
        avoiding overlap and staying within the main window.
        """
        if not self.walkthrough_dialog:
            return

        label, desc, widgets = self.walkthrough_dialog.steps[
            self.walkthrough_dialog.current
        ]
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]

        dialog = self.walkthrough_dialog
        dialog_size = dialog.size()
        margin = 20

        window_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        widget = widgets[0]
        widget_rect = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())

        # Candidate positions in order of preference
        candidates = [
            QPoint(widget_rect.right() + margin, widget_rect.top()),  # right
            QPoint(
                widget_rect.left() - dialog_size.width() - margin, widget_rect.top()
            ),  # left
            QPoint(
                widget_rect.left(), widget_rect.top() - dialog_size.height() - margin
            ),  # above
            QPoint(widget_rect.left(), widget_rect.bottom() + margin),  # below
        ]

        for pos in candidates:
            dialog_rect = QRect(pos, dialog_size)
            if window_rect.contains(dialog_rect) and not dialog_rect.intersects(
                widget_rect
            ):
                dialog.move(pos)
                return

        # Fallback: try to place below or above, clipped if needed
        fallback_below = QPoint(
            max(
                window_rect.left(),
                min(widget_rect.left(), window_rect.right() - dialog_size.width()),
            ),
            widget_rect.bottom() + margin,
        )
        below_rect = QRect(fallback_below, dialog_size)
        if window_rect.contains(below_rect) and not below_rect.intersects(widget_rect):
            dialog.move(fallback_below)
            return

        fallback_above = QPoint(
            max(
                window_rect.left(),
                min(widget_rect.left(), window_rect.right() - dialog_size.width()),
            ),
            widget_rect.top() - dialog_size.height() - margin,
        )
        above_rect = QRect(fallback_above, dialog_size)
        if window_rect.contains(above_rect) and not above_rect.intersects(widget_rect):
            dialog.move(fallback_above)
            return

        # Last resort: bottom right corner of parent, clamped
        safe_x = window_rect.right() - dialog_size.width() - 10
        safe_y = window_rect.bottom() - dialog_size.height() - 10
        dialog.move(
            QPoint(max(window_rect.left(), safe_x), max(window_rect.top(), safe_y))
        )

    def show_walkthrough_intro(self, current_view):
        """
        Displays the initial tutorial intro dialog.

        :param current_view: Identifier of the current view.
        :type current_view: str
        """
        if self._walkthrough_active:
            self.logger.info("Walkthrough is already active, skipping intro.")
            return

        self.logger.info(f"Starting walkthrough intro for {current_view}.")
        intro = IntroDialog(self, current_step=current_view)
        intro.start_walkthrough.connect(self.launch_walkthrough)
        intro.exec()

    def get_current_view(self):
        """
        Abstract method to get the name of the current view.

        :return: Current view name.
        :rtype: str
        """
        raise NotImplementedError(
            "get_current_view must be implemented in the subclass"
        )

    def get_walkthrough_steps(self):
        """
        Abstract method to retrieve the walkthrough steps for the current view.

        :return: List of walkthrough steps.
        :rtype: list[tuple[str, str, str, Callable[[], QWidget]]]
        """
        raise NotImplementedError(
            "get_walkthrough_steps must be implemented in the subclass"
        )

    def _force_close_walkthrough_dialog(self):
        """
        Forcefully closes the walkthrough dialog and emits a termination signal.
        """
        if hasattr(self, "walkthrough_dialog") and self.walkthrough_dialog:
            try:
                self.walkthrough_dialog.done(0)
                self.walkthrough_dialog.deleteLater()
                self.logger.info("Walkthrough dialog force-closed.")
                self.walkthrough_finished.emit(
                    self.get_current_view(), False
                )  # ← this line is new
            except Exception as e:
                self.logger.warning(f"Failed to force-close walkthrough dialog: {e}")
            finally:
                self.walkthrough_dialog = None
                self._walkthrough_active = False
