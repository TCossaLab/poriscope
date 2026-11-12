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
# Michelle Stephen

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.MetaControls import MetaControls
from poriscope.utils.ReplayGuard import forbid_while_replaying
from poriscope.views.widgets.multiselect import MultiSelectComboBox
from poriscope.views.widgets.validators.numeric_validation import NumericLineEdit


@inherit_docstrings
class ConditioningControls(MetaControls):
    """
    The Conditioning tab's controls: the experiment, the channels, the 1/f fit range, the
    noise thresholds and the noise axis minimum, and the Plot and Export buttons.

    Built and placed by ``MetaView._set_control_area``, which also connects the
    four signals every controls panel carries.
    """

    logger = logging.getLogger(__name__)

    #: What the experiment combobox shows while no experiment exists yet.
    placeholder_texts: Tuple[str, ...] = ("No Experiment",)

    #: Each numeric field: its parameter name, label and default, all in the units the
    #: label names. The defaults are the conditioning app's.
    NUMERIC_FIELDS: Tuple[Tuple[str, str, float], ...] = (
        ("fit_start", "FIT START (Hz)", 1.0),
        ("fit_end", "FIT END (Hz)", 30.0),
        ("good_noise", "GOOD NOISE (pA²/Hz)", 10.0),
        ("decent_noise", "DECENT NOISE (pA²/Hz)", 100.0),
        ("psd_axis_min", "NOISE AXIS MIN (pA²/Hz)", 1e-4),
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Build the panel, wire it up, and settle the state of its widgets.

        :param parent: Widget that owns this panel.
        :type parent: Optional[QWidget]
        """
        super().__init__(parent)
        self.setupUi()
        self.connect_signals()
        self.validate_inputs()

    def setupUi(self) -> None:
        """
        Lay out this panel's widgets.
        """
        main_layout = QVBoxLayout(self)
        self.groupBox = QGroupBox(self)
        grid = QGridLayout(self.groupBox)

        loader_header = QHBoxLayout()
        loader_label = self.createLabel(self.groupBox, 12, "EXPERIMENT")
        self.loader_comboBox = self.create_comboBox(self.groupBox)
        self.loader_comboBox.addItem(self.placeholder_texts[0])
        self.loader_add_button = self.create_add_button(
            self.groupBox,
            self.loader_comboBox,
            "Add experiment",
            "MetaConditioningLoader",
        )
        self.loader_info_button = self.create_info_button(
            self.groupBox,
            self.loader_comboBox,
            "Edit selected experiment",
            "MetaConditioningLoader",
        )
        self.loader_delete_button = self.create_delete_button(
            self.groupBox,
            self.loader_comboBox,
            "Delete experiment",
            "MetaConditioningLoader",
        )
        loader_header.addWidget(loader_label)
        loader_header.addWidget(self.loader_add_button)
        loader_header.addWidget(self.loader_info_button)
        loader_header.addWidget(self.loader_delete_button)
        loader_header.addStretch(1)
        grid.addLayout(loader_header, 0, 0)
        grid.addWidget(self.loader_comboBox, 1, 0)

        grid.addWidget(self.createLabel(self.groupBox, 12, "CHANNEL"), 2, 0)
        self.channel_comboBox = MultiSelectComboBox(self.groupBox)
        grid.addWidget(self.channel_comboBox, 3, 0)

        self.numeric: Dict[str, NumericLineEdit] = {}
        for column, (name, label, default) in enumerate(self.NUMERIC_FIELDS, start=1):
            row = 0 if column <= 3 else 2
            col = column if column <= 3 else column - 3
            grid.addWidget(self.createLabel(self.groupBox, 12, label), row, col)
            field = NumericLineEdit(self.groupBox)
            field.setRange(0.0, None, float)
            field.setText(f"{default:g}")
            grid.addWidget(field, row + 1, col)
            self.numeric[name] = field

        self.bands_checkBox = QCheckBox("Noise bands", self.groupBox)
        self.bands_checkBox.setChecked(True)
        grid.addWidget(self.bands_checkBox, 3, 3)

        self.plot_button = self.createButton(self.groupBox, "Plot", bold=True)
        self.export_button = self.createButton(
            self.groupBox, "Export Plot Data", bold=True
        )
        grid.addWidget(self.plot_button, 4, 0)
        grid.addWidget(self.export_button, 4, 1)
        main_layout.addWidget(self.groupBox)

    def connect_signals(self) -> None:
        """
        Connect this panel's widgets to the handlers that turn them into requests.
        """
        self.loader_comboBox.currentIndexChanged.connect(self._on_loader_changed)
        self.channel_comboBox.selectionChanged.connect(self.validate_inputs)
        for field in self.numeric.values():
            field.textChanged.connect(self.validate_inputs)
        self.plot_button.clicked.connect(lambda: self._emit("plot"))
        self.export_button.clicked.connect(lambda: self._emit("export_plot_data"))

    def validate_inputs(self) -> None:
        """
        Enable Plot only with an experiment, a channel and every number valid.
        """
        ready = (
            not self.is_placeholder_item(self.loader_comboBox)
            and bool(self.channel_comboBox.getSelectedItems())
            and all(field.isValid() for field in self.numeric.values())
        )
        self.plot_button.setEnabled(ready)

    def collect_parameters(self) -> Dict[str, Any]:
        """
        Read this panel's widgets into the arguments a plot needs.

        :return: The values the requested action needs.
        :rtype: Dict[str, Any]
        """
        forbid_while_replaying("collect_parameters")
        parameters: Dict[str, Any] = {
            "loader": self.loader_comboBox.currentText(),
            "channels": [int(c) for c in self.channel_comboBox.getSelectedItems()],
            "show_bands": self.bands_checkBox.isChecked(),
        }
        for name, field in self.numeric.items():
            parameters[name] = float(field.text()) if field.isValid() else None
        return parameters

    def update_loaders(self, loaders: Sequence[str]) -> None:
        """
        Offer these experiments, keeping the current one if it is still among them.

        :param loaders: the experiments' plugin keys
        :type loaders: Sequence[str]
        """
        current = self.loader_comboBox.currentText()
        options = list(loaders) or [self.placeholder_texts[0]]
        self.loader_comboBox.blockSignals(True)
        self.loader_comboBox.clear()
        self.loader_comboBox.addItems(options)
        if current in options:
            self.loader_comboBox.setCurrentText(current)
        self.loader_comboBox.blockSignals(False)
        # The blocked signals include the currentIndexChanged these buttons re-check on.
        self.toggle_info_button(self.loader_info_button, self.loader_comboBox)
        self.toggle_info_button(self.loader_delete_button, self.loader_comboBox)
        self._on_loader_changed()

    def update_channels(self, channels: Sequence[int]) -> None:
        """
        Offer these channels, keeping the ones still selected, or selecting all when none are.

        :param channels: the experiment's channels
        :type channels: Sequence[int]
        """
        offered = [str(channel) for channel in channels]
        kept = [c for c in self.channel_comboBox.getSelectedItems() if c in offered]
        self.channel_comboBox.blockSignals(True)
        self.channel_comboBox.listWidget.clear()
        self.channel_comboBox.addItems(offered)
        self.channel_comboBox.blockSignals(False)
        self.channel_comboBox.setSelectedItems(kept or offered)
        self.validate_inputs()

    def set_loader(self, loader: str) -> bool:
        """
        Show an experiment without emitting, if it is one of the options.

        :param loader: the experiment's plugin key
        :type loader: str
        :return: True if it is shown
        :rtype: bool
        """
        shown = self.set_combo_text(self.loader_comboBox, loader)
        self.validate_inputs()
        return shown

    def set_values(self, values: Dict[str, Any]) -> List[int]:
        """
        Show recorded channels, numbers and band setting without emitting.

        :param values: the recorded values, by parameter name
        :type values: Dict[str, Any]
        :return: the channels that are not options here
        :rtype: List[int]
        """
        missing = self.channel_comboBox.setSelectedItems(
            [str(channel) for channel in values["channels"]]
        )
        for name, field in self.numeric.items():
            field.blockSignals(True)
            field.setText(f"{values[name]:g}")
            field.blockSignals(False)
        self.bands_checkBox.setChecked(bool(values["show_bands"]))
        self.validate_inputs()
        return [int(channel) for channel in missing]

    def _on_loader_changed(self) -> None:
        """
        Ask for the chosen experiment's channels, or clear them when none is chosen.
        """
        if self.is_placeholder_item(self.loader_comboBox):
            self.update_channels([])
            return
        # Only the experiment travels: this also runs when the app's plugins change,
        # which can happen during a replay, when the panel must not be read.
        self.actionTriggered.emit(
            self.__class__.__name__,
            "loader_changed",
            ({"loader": self.loader_comboBox.currentText()},),
        )

    def _emit(self, action: str) -> None:
        """
        Send a request to the View, carrying what the panel shows now.

        :param action: the action name the View dispatches on
        :type action: str
        """
        self.actionTriggered.emit(
            self.__class__.__name__, action, (self.collect_parameters(),)
        )
