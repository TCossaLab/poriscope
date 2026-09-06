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
# Kyle Briggs

import logging
from abc import abstractmethod
from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QListWidgetItem

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaControls import MetaControls
from poriscope.utils.QWidgetABCMeta import QWidgetABCMeta
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit
from poriscope.views.widgets.multiselect import MultiSelectComboBox


class MetaEventTabControls(MetaControls, metaclass=QWidgetABCMeta):
    """
    Shared base for the control panels of the two event-oriented analysis tabs.

    ``RawDataControls`` and ``EventAnalysisControls`` build the same three widgets
    above their tab's plot: a multi-select channel combobox, a filter combobox, and an
    event-index field. The two carried three methods verbatim between them; this base
    holds that shared half so there is one copy to fix.

    It extends ``MetaControls`` rather than replacing it - the widget factories, the
    icon buttons and the placeholder guard all still come from there. It also declares
    ``QWidgetABCMeta`` as its metaclass, which is what makes ``@abstractmethod`` below
    actually fire: ``MetaControls`` is a plain ``QWidget``, so its own metaclass is
    Shiboken's ``ObjectType``, which computes no ``__abstractmethods__`` and would let
    an unimplemented hook through silently. ``MetaView`` uses the same metaclass for
    the same reason.

    What a subclass inherits, on top of everything ``MetaControls`` gives it:

    - ``update_channels``, the largest single duplicate in the analysis-tab layer,
      which repopulates the channel combobox from a plugin's channel list while
      preserving whatever the user had selected.
    - ``update_filters``, which keeps the filter combobox in step with the filters
      instantiated elsewhere in the app.
    - ``set_event_index_input``, which writes an event index into the field and
      revalidates.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, as ``MetaControls``
      already requires, and its own ``placeholder_texts`` - the two tabs name
      different plugin families, so unlike the subset tabs they do not share it.
    - **A ``setupUi`` that builds** ``channel_comboBox``, ``filters_comboBox`` and
      ``event_index_lineEdit``. They are declared below but not created here, because
      each tab lays its panel out differently.
    - **``validate_inputs``**, declared abstract below: each tab validates a different
      set of fields.

    :ivar logger: the module logger the shared methods below log under
    """

    logger = logging.getLogger(__name__)

    #: Built by each subclass's ``setupUi``, which lays its panel out differently.
    #: Declared here so the shared methods below have a contract to read.
    channel_comboBox: MultiSelectComboBox
    event_index_lineEdit: IntegerRangeLineEdit
    filters_comboBox: QComboBox

    @abstractmethod
    def validate_inputs(self) -> None:
        """
        Re-validate the panel's input fields and enable or disable its actions.

        Abstract because each tab validates a different set of fields.
        """

    def update_channels(self, channels: Sequence[int]) -> None:
        """
        Updates the channels displayed in the MultiSelectComboBox widget and restores previous selections.

        :param channels: Channel indices to display.
        :type channels: Sequence[int]
        """
        self.logger.info(f"Updating channels to {channels}")

        # Get current selections from the MultiSelectComboBox BEFORE clearing
        current_selections = set(self.channel_comboBox.getSelectedItems())
        self.logger.debug(
            f"Current selections before restoration: {current_selections}"
        )

        new_channels = [str(i) for i in channels]

        # Check if this is a first load (no items exist yet) to default to Select All
        is_first_load = self.channel_comboBox.listWidget.count() == 0

        # Block signals during the entire rebuild to avoid emitting incorrect states
        self.channel_comboBox.listWidget.itemChanged.disconnect(
            self.channel_comboBox.handleItemChanged
        )

        # Clear and rebuild items, preserving checked state from previous selections.
        # On first load, default all channels to checked (Select All behavior).
        self.channel_comboBox.listWidget.clear()
        for text in new_channels:
            item = QListWidgetItem(text, self.channel_comboBox.listWidget)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # On first load select all by default, otherwise restore previous selection
            state = (
                Qt.Checked
                if (is_first_load or text in current_selections)
                else Qt.Unchecked
            )
            item.setCheckState(state)

        self.logger.debug(f"Added channels: {new_channels}")

        self.channel_comboBox.listWidget.itemChanged.connect(
            self.channel_comboBox.handleItemChanged
        )

        # Update display text and Select All button without emitting selectionChanged
        self.channel_comboBox.refreshDisplayText()
        self.channel_comboBox.updateSelectAllButton()

        # Log the final state of selections
        restored_selections = self.channel_comboBox.getSelectedItems()
        self.logger.debug(f"Selected items after restoration: {restored_selections}")

    def update_filters(self, filters: list[str]) -> None:
        self.logger.info(f"Updating filters: {filters}")

        # Store current selection
        current_selection = self.filters_comboBox.currentText()

        self.filters_comboBox.clear()
        display_filters = filters if filters != [] else ["No Filter"]
        self.filters_comboBox.addItems(display_filters)

        # Restore selection if it still exists
        if current_selection in display_filters:
            self.filters_comboBox.setCurrentText(current_selection)
        else:
            self.filters_comboBox.setCurrentIndex(0)

    @log(logger=logger)
    def set_event_index_input(self, value: str) -> None:
        self.event_index_lineEdit.blockSignals(True)
        self.event_index_lineEdit.set_range(value)
        self.event_index_lineEdit.blockSignals(False)
        self.validate_inputs()
