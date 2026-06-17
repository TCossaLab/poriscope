"""
Full unit-test suite for EventSegmentationSettingsWidget.

The widget is a pure Qt UI form generated from a .ui file — no database,
no file I/O, no modals. Every test simply instantiates the widget and
exercises its attributes and retranslateUi output.

Run with:
    pytest test_event_segmentation_settings_widget.py -v
    pytest test_event_segmentation_settings_widget.py --cov=poriscope --cov-report=html
"""

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QLineEdit,
    QPushButton,
)

from poriscope.views.widgets.event_segmentation_settings_widget import (
    EventSegmentationSettingsWidget,
)

# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def widget(qt_app):
    w = EventSegmentationSettingsWidget()
    qt_app.processEvents()
    return w


# ===========================================================================
# Instantiation
# ===========================================================================

class TestInstantiation:
    def test_creates_without_error(self, widget):
        assert widget is not None

    def test_is_qdialog(self, widget):
        assert isinstance(widget, QDialog)

    def test_object_name(self, widget):
        assert widget.objectName() == "Dialog"

    def test_initial_size(self, widget):
        assert widget.width() == 486
        assert widget.height() == 469


# ===========================================================================
# Labels — presence and text (retranslateUi)
# ===========================================================================

class TestLabels:
    def test_title_label_text(self, widget):
        assert "Event Segmentation Settings" in widget.label.text()

    def test_label_2_minimum_baseline(self, widget):
        assert "Minimum Baseline" in widget.label_2.text()

    def test_label_3_maximum_baseline(self, widget):
        assert "Maximum Baseline" in widget.label_3.text()

    def test_label_4_manual_baseline_override(self, widget):
        assert "Manual Baseline Override" in widget.label_4.text()

    def test_label_5_manual_baseline_mean(self, widget):
        assert "Manual Baseline Mean" in widget.label_5.text()

    def test_label_6_manual_baseline_stdev(self, widget):
        assert "Manual Baseline Stdev" in widget.label_6.text()

    def test_label_7_detection_threshold(self, widget):
        assert "Detection Threshold" in widget.label_7.text()

    def test_label_8_detection_hysteresis(self, widget):
        assert "Detection Hysteresis" in widget.label_8.text()

    def test_label_9_fixed_event_length(self, widget):
        assert "Fixed Event Length" in widget.label_9.text()

    def test_label_10_event_direction(self, widget):
        assert "Event Direction" in widget.label_10.text()

    def test_label_11_use_data_filter(self, widget):
        assert "Use Data Filter" in widget.label_11.text()

    def test_label_12_data_filter_cutoff(self, widget):
        assert "Data Filter Cutoff" in widget.label_12.text()

    def test_label_13_data_filter_order(self, widget):
        assert "Data Filter Order" in widget.label_13.text()

    def test_label_14_pa_unit(self, widget):
        assert widget.label_14.text() == "pA"

    def test_label_15_pa_unit(self, widget):
        assert widget.label_15.text() == "pA"

    def test_label_16_pa_unit(self, widget):
        assert widget.label_16.text() == "pA"

    def test_label_17_pa_unit(self, widget):
        assert widget.label_17.text() == "pA"

    def test_label_18_rms_noise(self, widget):
        assert "RMS Noise" in widget.label_18.text()

    def test_label_19_rms_noise(self, widget):
        assert "RMS Noise" in widget.label_19.text()

    def test_label_20_us_unit(self, widget):
        assert widget.label_20.text() == "us"

    def test_label_21_hz_unit(self, widget):
        assert widget.label_21.text() == "Hz"

    def test_label_22_empty(self, widget):
        assert widget.label_22.text() == ""

    def test_label_4_bold_font(self, widget):
        assert widget.label_4.font().bold()


# ===========================================================================
# Line edits — presence and initial state
# ===========================================================================

class TestLineEdits:
    def test_lineEdit_3_exists(self, widget):
        assert isinstance(widget.lineEdit_3, QLineEdit)

    def test_lineEdit_4_exists(self, widget):
        assert isinstance(widget.lineEdit_4, QLineEdit)

    def test_lineEdit_5_exists(self, widget):
        assert isinstance(widget.lineEdit_5, QLineEdit)

    def test_lineEdit_6_exists(self, widget):
        assert isinstance(widget.lineEdit_6, QLineEdit)

    def test_lineEdit_7_exists(self, widget):
        assert isinstance(widget.lineEdit_7, QLineEdit)

    def test_lineEdit_8_exists(self, widget):
        assert isinstance(widget.lineEdit_8, QLineEdit)

    def test_lineEdit_9_exists(self, widget):
        assert isinstance(widget.lineEdit_9, QLineEdit)

    def test_lineEdit_10_exists(self, widget):
        assert isinstance(widget.lineEdit_10, QLineEdit)

    def test_lineEdit_11_exists(self, widget):
        assert isinstance(widget.lineEdit_11, QLineEdit)

    def test_all_line_edits_empty_initially(self, widget):
        for le in [
            widget.lineEdit_3, widget.lineEdit_4, widget.lineEdit_5,
            widget.lineEdit_6, widget.lineEdit_7, widget.lineEdit_8,
            widget.lineEdit_9, widget.lineEdit_10, widget.lineEdit_11,
        ]:
            assert le.text() == ""

    def test_line_edits_accept_text(self, widget):
        widget.lineEdit_3.setText("100.0")
        assert widget.lineEdit_3.text() == "100.0"

    def test_line_edit_7_accepts_value(self, widget):
        widget.lineEdit_7.setText("5.0")
        assert widget.lineEdit_7.text() == "5.0"

    def test_line_edit_geometry_lineEdit_3(self, widget):
        geo = widget.lineEdit_3.geometry()
        assert geo.x() == 250
        assert geo.y() == 100

    def test_line_edit_geometry_lineEdit_4(self, widget):
        geo = widget.lineEdit_4.geometry()
        assert geo.x() == 250
        assert geo.y() == 120


# ===========================================================================
# Checkbox
# ===========================================================================

class TestCheckBox:
    def test_checkbox_exists(self, widget):
        assert isinstance(widget.checkBox, QCheckBox)

    def test_checkbox_unchecked_initially(self, widget):
        assert not widget.checkBox.isChecked()

    def test_checkbox_enabled(self, widget):
        assert widget.checkBox.isEnabled()

    def test_checkbox_text_empty(self, widget):
        assert widget.checkBox.text() == ""

    def test_checkbox_can_be_checked(self, widget):
        widget.checkBox.setChecked(True)
        assert widget.checkBox.isChecked()

    def test_checkbox_can_be_unchecked(self, widget):
        widget.checkBox.setChecked(True)
        widget.checkBox.setChecked(False)
        assert not widget.checkBox.isChecked()


# ===========================================================================
# ComboBoxes
# ===========================================================================

class TestComboBoxes:
    def test_combobox_exists(self, widget):
        assert isinstance(widget.comboBox, QComboBox)

    def test_combobox_2_exists(self, widget):
        assert isinstance(widget.comboBox_2, QComboBox)

    def test_combobox_has_two_items(self, widget):
        assert widget.comboBox.count() == 2

    def test_combobox_2_has_two_items(self, widget):
        assert widget.comboBox_2.count() == 2

    def test_combobox_item_0_blockage(self, widget):
        assert widget.comboBox.itemText(0) == "Blockage"

    def test_combobox_item_1_enhancement(self, widget):
        assert widget.comboBox.itemText(1) == "Enhancement"

    def test_combobox_2_item_0_none(self, widget):
        assert widget.comboBox_2.itemText(0) == "None"

    def test_combobox_2_item_1_bessel(self, widget):
        assert widget.comboBox_2.itemText(1) == "Bessel"

    def test_combobox_default_selection_blockage(self, widget):
        assert widget.comboBox.currentText() == "Blockage"

    def test_combobox_2_default_selection_none(self, widget):
        assert widget.comboBox_2.currentText() == "None"

    def test_combobox_can_switch_to_enhancement(self, widget):
        widget.comboBox.setCurrentIndex(1)
        assert widget.comboBox.currentText() == "Enhancement"

    def test_combobox_2_can_switch_to_bessel(self, widget):
        widget.comboBox_2.setCurrentIndex(1)
        assert widget.comboBox_2.currentText() == "Bessel"

    def test_combobox_switch_back(self, widget):
        widget.comboBox.setCurrentIndex(1)
        widget.comboBox.setCurrentIndex(0)
        assert widget.comboBox.currentText() == "Blockage"


# ===========================================================================
# Buttons
# ===========================================================================

class TestButtons:
    def test_ok_button_exists(self, widget):
        assert isinstance(widget.update_trace_pushButton, QPushButton)

    def test_cancel_button_exists(self, widget):
        assert isinstance(widget.update_trace_pushButton_2, QPushButton)

    def test_ok_button_text(self, widget):
        assert widget.update_trace_pushButton.text() == "Ok and Save"

    def test_cancel_button_text(self, widget):
        assert widget.update_trace_pushButton_2.text() == "Cancel"

    def test_ok_button_checkable(self, widget):
        assert widget.update_trace_pushButton.isCheckable()

    def test_cancel_button_checkable(self, widget):
        assert widget.update_trace_pushButton_2.isCheckable()

    def test_ok_button_bold_font(self, widget):
        assert widget.update_trace_pushButton.font().bold()

    def test_cancel_button_bold_font(self, widget):
        assert widget.update_trace_pushButton_2.font().bold()

    def test_ok_button_initially_unchecked(self, widget):
        assert not widget.update_trace_pushButton.isChecked()

    def test_cancel_button_initially_unchecked(self, widget):
        assert not widget.update_trace_pushButton_2.isChecked()


# ===========================================================================
# Separator line
# ===========================================================================

class TestSeparatorLine:
    def test_line_exists(self, widget):
        assert isinstance(widget.line, QFrame)

    def test_line_is_horizontal(self, widget):
        assert widget.line.frameShape() == QFrame.Shape.HLine

    def test_line_is_sunken(self, widget):
        assert widget.line.frameShadow() == QFrame.Shadow.Sunken


# ===========================================================================
# retranslateUi — called directly to confirm idempotency
# ===========================================================================

class TestRetranslateUi:
    def test_retranslate_does_not_raise(self, widget):
        widget.retranslateUi(widget)

    def test_retranslate_preserves_title(self, widget):
        widget.retranslateUi(widget)
        assert "Event Segmentation Settings" in widget.label.text()

    def test_retranslate_preserves_combobox_items(self, widget):
        widget.retranslateUi(widget)
        assert widget.comboBox.itemText(0) == "Blockage"
        assert widget.comboBox.itemText(1) == "Enhancement"
        assert widget.comboBox_2.itemText(0) == "None"
        assert widget.comboBox_2.itemText(1) == "Bessel"

    def test_retranslate_preserves_button_text(self, widget):
        widget.retranslateUi(widget)
        assert widget.update_trace_pushButton.text() == "Ok and Save"
        assert widget.update_trace_pushButton_2.text() == "Cancel"


# ===========================================================================
# Layout widget
# ===========================================================================

class TestLayoutWidget:
    def test_layout_widget_exists(self, widget):
        assert hasattr(widget, "layoutWidget")

    def test_horizontal_layout_has_two_buttons(self, widget):
        assert widget.horizontalLayout.count() == 2

    def test_layout_geometry(self, widget):
        geo = widget.layoutWidget.geometry()
        assert geo.x() == 80
        assert geo.width() == 311


# ===========================================================================
# setupUi called again (idempotency check)
# ===========================================================================

class TestSetupUiIdempotency:
    def test_setup_ui_can_be_called_again(self, widget):
        # Calling setupUi again should not crash and text is preserved
        widget.setupUi(widget)
        widget.retranslateUi(widget)
        assert "Event Segmentation Settings" in widget.label.text()