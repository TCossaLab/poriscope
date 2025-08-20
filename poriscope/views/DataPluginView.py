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
# Alejandra Carolina González González


import logging
from typing import List

from PySide6.QtWidgets import QWidget

from poriscope.utils.LogDecorator import log
from poriscope.views.widgets.dict_dialog_widget import DictDialog


class DataPluginView(QWidget):
    """
    Base controller class that manages exactly data plugins
    """

    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        """
        Initialize the plugin view.

        :param kwargs: Additional keyword arguments.
        """
        super().__init__()

    @log(logger=logger)
    def get_user_settings(
        self,
        user_settings: dict,
        name: str,
        data_server: str,
        editable: bool = True,
        show_delete: bool = False,
        editable_source_plugins: bool = False,
        source_plugins: List[str] = [],
    ) -> tuple[dict, str]:
        """
        Prompt the user to specify a reader plugin to use to open the given file.
        Return the updated user settings and the plugin key.

        :param user_settings: Dictionary of user settings.
        :type user_settings: dict
        :param name: The name of the settings dialog.
        :type name: str
        :param editable: allow editing of the plugin key? Default True
        :type editable: bool
        :param show_delete: allow deleting the plugin? Default False
        :type show_delete: bool
        :return: A tuple containing the updated user settings and the plugin key.
        :rtype: tuple
        """
        dialog = DictDialog(
            user_settings,
            name,
            title="Plugin Settings",
            data_server=data_server,
            editable=editable,
            show_delete=show_delete,
            editable_source_plugins=editable_source_plugins,
            source_plugins=source_plugins,
        )
        dialog.exec()
        return dialog.get_result()
