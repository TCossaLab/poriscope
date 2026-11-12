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
# Kyle Briggs

from typing import Any

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QMessageBox


class MessageBoxValidationGuard(QObject):
    """
    The one application-wide watcher behind ``BaseLineEdit``'s two class flags.

    While a ``QMessageBox`` is shown it sets ``suspend_validation``, so a line edit that
    loses focus to the box does not validate against it, and once the application is
    about to quit it sets ``app_closing``. It is parented to the application and lives
    as long as it does. ``install`` returns the existing guard, so however many line
    edits exist, each Qt event passes through one filter.
    """

    def __init__(self, app: QApplication, target: Any) -> None:
        """
        Watch ``app`` for message boxes and its quit, on behalf of ``target``.

        :param app: the application to watch
        :type app: QApplication
        :param target: the class whose ``suspend_validation`` and ``app_closing`` it sets
        :type target: Any
        """
        super().__init__(app)
        self._target = target
        app.installEventFilter(self)
        app.aboutToQuit.connect(self.on_app_about_to_quit)

    @classmethod
    def install(cls, app: QApplication, target: Any) -> "MessageBoxValidationGuard":
        """
        Return the application's guard, creating it on the first call.

        :param app: the application to watch
        :type app: QApplication
        :param target: the class whose flags the guard sets
        :type target: Any
        :return: the application's one guard
        :rtype: MessageBoxValidationGuard
        """
        existing = app.findChild(cls)
        if existing is not None:
            return existing
        return cls(app, target)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Suspend validation while a message box is shown, and resume it when it hides.

        :param obj: the object the event is for
        :type obj: QObject
        :param event: the event
        :type event: QEvent
        :return: False, so every event still reaches its receiver
        :rtype: bool
        """
        if isinstance(obj, QMessageBox):
            if event.type() == QEvent.Type.Show:
                self._target.suspend_validation = True
            elif event.type() == QEvent.Type.Hide:
                self._target.suspend_validation = False
        return False

    def on_app_about_to_quit(self) -> None:
        """Mark the application as closing, so no line edit validates on its way out."""
        self._target.app_closing = True
