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

# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Event_Segmentation_Settings.ui'
##
## Created by: Qt User Interface Compiler version 6.7.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, QSize
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class EventSegmentationSettingsWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName("Dialog")
        Dialog.setEnabled(True)
        Dialog.resize(486, 469)
        Dialog.setStyleSheet(";")
        self.label = QLabel(Dialog)
        self.label.setObjectName("label")
        self.label.setGeometry(QRect(100, 30, 311, 51))
        font = QFont()
        font.setPointSize(14)
        font.setBold(False)
        font.setUnderline(False)
        self.label.setFont(font)
        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName("label_2")
        self.label_2.setGeometry(QRect(20, 100, 201, 16))
        font1 = QFont()
        font1.setPointSize(10)
        self.label_2.setFont(font1)
        self.label_3 = QLabel(Dialog)
        self.label_3.setObjectName("label_3")
        self.label_3.setGeometry(QRect(20, 120, 211, 16))
        self.label_3.setFont(font1)
        self.label_4 = QLabel(Dialog)
        self.label_4.setObjectName("label_4")
        self.label_4.setGeometry(QRect(20, 150, 221, 16))
        font2 = QFont()
        font2.setPointSize(10)
        font2.setBold(True)
        font2.setItalic(False)
        font2.setUnderline(False)
        self.label_4.setFont(font2)
        self.label_5 = QLabel(Dialog)
        self.label_5.setObjectName("label_5")
        self.label_5.setGeometry(QRect(20, 170, 201, 16))
        self.label_5.setFont(font1)
        self.label_6 = QLabel(Dialog)
        self.label_6.setObjectName("label_6")
        self.label_6.setGeometry(QRect(20, 190, 211, 16))
        self.label_6.setFont(font1)
        self.label_7 = QLabel(Dialog)
        self.label_7.setObjectName("label_7")
        self.label_7.setGeometry(QRect(20, 220, 201, 16))
        self.label_7.setFont(font1)
        self.label_8 = QLabel(Dialog)
        self.label_8.setObjectName("label_8")
        self.label_8.setGeometry(QRect(20, 240, 211, 16))
        self.label_8.setFont(font1)
        self.label_9 = QLabel(Dialog)
        self.label_9.setObjectName("label_9")
        self.label_9.setGeometry(QRect(20, 260, 211, 21))
        self.label_9.setFont(font1)
        self.label_10 = QLabel(Dialog)
        self.label_10.setObjectName("label_10")
        self.label_10.setGeometry(QRect(20, 280, 221, 21))
        self.label_10.setFont(font1)
        self.label_11 = QLabel(Dialog)
        self.label_11.setObjectName("label_11")
        self.label_11.setGeometry(QRect(20, 320, 151, 16))
        self.label_11.setFont(font1)
        self.label_12 = QLabel(Dialog)
        self.label_12.setObjectName("label_12")
        self.label_12.setGeometry(QRect(20, 340, 211, 21))
        self.label_12.setFont(font1)
        self.lineEdit_3 = QLineEdit(Dialog)
        self.lineEdit_3.setObjectName("lineEdit_3")
        self.lineEdit_3.setGeometry(QRect(250, 100, 120, 20))
        self.lineEdit_4 = QLineEdit(Dialog)
        self.lineEdit_4.setObjectName("lineEdit_4")
        self.lineEdit_4.setGeometry(QRect(250, 120, 120, 20))
        self.lineEdit_5 = QLineEdit(Dialog)
        self.lineEdit_5.setGeometry(QRect(250, 170, 120, 20))
        self.lineEdit_6 = QLineEdit(Dialog)
        self.lineEdit_6.setGeometry(QRect(250, 190, 120, 20))
        self.lineEdit_7 = QLineEdit(Dialog)
        self.lineEdit_7.setObjectName("lineEdit_7")
        self.lineEdit_7.setGeometry(QRect(250, 340, 120, 20))
        self.checkBox = QCheckBox(Dialog)
        self.checkBox.setObjectName("checkBox")
        self.checkBox.setEnabled(True)
        self.checkBox.setGeometry(QRect(300, 150, 21, 20))
        self.checkBox.setStyleSheet("")
        self.checkBox.setIconSize(QSize(10, 10))
        self.checkBox.setChecked(False)
        self.label_14 = QLabel(Dialog)
        self.label_14.setObjectName("label_14")
        self.label_14.setGeometry(QRect(380, 100, 21, 21))
        self.label_14.setFont(font1)
        self.label_18 = QLabel(Dialog)
        self.label_18.setObjectName("label_18")
        self.label_18.setGeometry(QRect(380, 220, 101, 16))
        self.label_18.setFont(font1)
        self.label_20 = QLabel(Dialog)
        self.label_20.setObjectName("label_20")
        self.label_20.setGeometry(QRect(380, 260, 21, 16))
        self.label_20.setFont(font1)
        self.label_21 = QLabel(Dialog)
        self.label_21.setObjectName("label_21")
        self.label_21.setGeometry(QRect(380, 340, 21, 16))
        self.label_21.setFont(font1)
        self.label_19 = QLabel(Dialog)
        self.label_19.setObjectName("label_19")
        self.label_19.setGeometry(QRect(380, 240, 101, 16))
        self.label_19.setFont(font1)
        self.label_13 = QLabel(Dialog)
        self.label_13.setObjectName("label_13")
        self.label_13.setGeometry(QRect(20, 360, 151, 21))
        self.label_13.setFont(font1)
        self.label_15 = QLabel(Dialog)
        self.label_15.setObjectName("label_15")
        self.label_15.setGeometry(QRect(380, 120, 21, 21))
        self.label_15.setFont(font1)
        self.label_16 = QLabel(Dialog)
        self.label_16.setObjectName("label_16")
        self.label_16.setGeometry(QRect(380, 170, 21, 21))
        self.label_16.setFont(font1)
        self.label_17 = QLabel(Dialog)
        self.label_17.setObjectName("label_17")
        self.label_17.setGeometry(QRect(380, 190, 21, 21))
        self.label_17.setFont(font1)
        self.label_22 = QLabel(Dialog)
        self.label_22.setObjectName("label_22")
        self.label_22.setGeometry(QRect(20, 20, 71, 71))
        self.label_22.setPixmap(QPixmap(":/icons/filters.png"))
        self.label_22.setScaledContents(True)
        self.lineEdit_8 = QLineEdit(Dialog)
        self.lineEdit_8.setObjectName("lineEdit_8")
        self.lineEdit_8.setGeometry(QRect(250, 360, 120, 20))
        self.lineEdit_9 = QLineEdit(Dialog)
        self.lineEdit_9.setObjectName("lineEdit_9")
        self.lineEdit_9.setGeometry(QRect(250, 220, 120, 20))
        self.lineEdit_10 = QLineEdit(Dialog)
        self.lineEdit_10.setObjectName("lineEdit_10")
        self.lineEdit_10.setGeometry(QRect(250, 240, 120, 20))
        self.lineEdit_11 = QLineEdit(Dialog)
        self.lineEdit_11.setObjectName("lineEdit_11")
        self.lineEdit_11.setGeometry(QRect(250, 260, 120, 20))
        self.line = QFrame(Dialog)
        self.line.setObjectName("line")
        self.line.setGeometry(QRect(20, 80, 441, 16))
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)
        self.comboBox = QComboBox(Dialog)
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.setObjectName("comboBox")
        self.comboBox.setGeometry(QRect(250, 280, 121, 22))
        self.comboBox.setStyleSheet(
            "QComboBox {\n"
            "    border: 1px solid #555;\n"
            "    border-radius: 5px;\n"
            "    padding: 5px 10px;\n"
            "    background: white;\n"
            "    color: rgb(0, 0, 0); \n"
            "}\n"
            "\n"
            "QComboBox::drop-down {\n"
            "    subcontrol-origin: padding;\n"
            "    subcontrol-position: top right;\n"
            "    width: 15px;\n"
            "    border-left-width: 1px;\n"
            "    border-left-color: darkgray;\n"
            "    border-left-style: solid;\n"
            "    border-top-right-radius: 3px;\n"
            "    border-bottom-right-radius: 3px;\n"
            "}\n"
            "\n"
            "QComboBox::down-arrow {\n"
            "    image: url(:/icons/arrowdown-black.png);\n"
            "    width: 10px;\n"
            "    height: 10px;\n"
            "}\n"
            "\n"
            "\n"
            "\n"
            "\n"
            ""
        )
        self.comboBox_2 = QComboBox(Dialog)
        self.comboBox_2.addItem("")
        self.comboBox_2.addItem("")
        self.comboBox_2.setObjectName("comboBox_2")
        self.comboBox_2.setGeometry(QRect(250, 320, 121, 22))
        self.comboBox_2.setStyleSheet(
            "QComboBox {\n"
            "    border: 1px solid #555;\n"
            "    border-radius: 5px;\n"
            "    padding: 5px 10px;\n"
            "    background: white;\n"
            "    color: rgb(0, 0, 0); \n"
            "}\n"
            "\n"
            "QComboBox::drop-down {\n"
            "    subcontrol-origin: padding;\n"
            "    subcontrol-position: top right;\n"
            "    width: 15px;\n"
            "    border-left-width: 1px;\n"
            "    border-left-color: darkgray;\n"
            "    border-left-style: solid;\n"
            "    border-top-right-radius: 3px;\n"
            "    border-bottom-right-radius: 3px;\n"
            "}\n"
            "\n"
            "QComboBox::down-arrow {\n"
            "    image: url(:/icons/arrowdown-black.png);\n"
            "    width: 10px;\n"
            "    height: 10px;\n"
            "}\n"
            "\n"
            "\n"
            ""
        )
        self.layoutWidget = QWidget(Dialog)
        self.layoutWidget.setObjectName("layoutWidget")
        self.layoutWidget.setGeometry(QRect(80, 410, 311, 30))
        self.horizontalLayout = QHBoxLayout(self.layoutWidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.update_trace_pushButton = QPushButton(self.layoutWidget)
        self.update_trace_pushButton.setObjectName("update_trace_pushButton")
        font3 = QFont()
        font3.setBold(True)
        font3.setStyleStrategy(QFont.PreferDefault)
        self.update_trace_pushButton.setFont(font3)
        self.update_trace_pushButton.setStyleSheet(
            "QPushButton {\n"
            "    background-color: rgb(0, 0, 0);\n"
            "	color: rgb(255, 255, 255);\n"
            "    border-radius: 6px;\n"
            "    border: 1px solid rgb(0, 0, 0); \n"
            "    padding: 5px;\n"
            "}\n"
            "\n"
            "QPushButton:hover{\n"
            "	background-color: rgb(244,244,244);\n"
            "	\n"
            "	color: rgb(0, 0, 0);\n"
            "	\n"
            "}"
        )
        self.update_trace_pushButton.setCheckable(True)

        self.horizontalLayout.addWidget(self.update_trace_pushButton)

        self.update_trace_pushButton_2 = QPushButton(self.layoutWidget)
        self.update_trace_pushButton_2.setObjectName("update_trace_pushButton_2")
        self.update_trace_pushButton_2.setFont(font3)
        self.update_trace_pushButton_2.setStyleSheet(
            "QPushButton {\n"
            "    background-color: rgb(0, 0, 0);\n"
            "	color: rgb(255, 255, 255);\n"
            "    border-radius: 6px;\n"
            "    border: 1px solid rgb(0, 0, 0); \n"
            "    padding: 5px;\n"
            "}\n"
            "\n"
            "QPushButton:hover{\n"
            "	background-color: rgb(244,244,244);\n"
            "	\n"
            "	color: rgb(0, 0, 0);\n"
            "	\n"
            "}"
        )
        self.update_trace_pushButton_2.setCheckable(True)

        self.horizontalLayout.addWidget(self.update_trace_pushButton_2)

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)

    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", "Dialog", None))
        self.label.setText(
            QCoreApplication.translate("Dialog", "Event Segmentation Settings", None)
        )
        self.label_2.setText(
            QCoreApplication.translate("Dialog", "Minimum Baseline", None)
        )
        self.label_3.setText(
            QCoreApplication.translate("Dialog", "Maximum Baseline", None)
        )
        self.label_4.setText(
            QCoreApplication.translate("Dialog", "Manual Baseline Override", None)
        )
        self.label_5.setText(
            QCoreApplication.translate("Dialog", "Manual Baseline Mean", None)
        )
        self.label_6.setText(
            QCoreApplication.translate("Dialog", "Manual Baseline Stdev", None)
        )
        self.label_7.setText(
            QCoreApplication.translate("Dialog", "Detection Threshold", None)
        )
        self.label_8.setText(
            QCoreApplication.translate("Dialog", "Detection Hysteresis", None)
        )
        self.label_9.setText(
            QCoreApplication.translate("Dialog", "Fixed Event Length", None)
        )
        self.label_10.setText(
            QCoreApplication.translate("Dialog", "Event Direction", None)
        )
        self.label_11.setText(
            QCoreApplication.translate("Dialog", "Use Data Filter", None)
        )
        self.label_12.setText(
            QCoreApplication.translate("Dialog", "Data Filter Cutoff Frequency", None)
        )
        self.checkBox.setText("")
        self.label_14.setText(QCoreApplication.translate("Dialog", "pA", None))
        self.label_18.setText(QCoreApplication.translate("Dialog", "x RMS Noise", None))
        self.label_20.setText(QCoreApplication.translate("Dialog", "us", None))
        self.label_21.setText(QCoreApplication.translate("Dialog", "Hz", None))
        self.label_19.setText(QCoreApplication.translate("Dialog", "x RMS Noise", None))
        self.label_13.setText(
            QCoreApplication.translate("Dialog", "Data Filter Order", None)
        )
        self.label_15.setText(QCoreApplication.translate("Dialog", "pA", None))
        self.label_16.setText(QCoreApplication.translate("Dialog", "pA", None))
        self.label_17.setText(QCoreApplication.translate("Dialog", "pA", None))
        self.label_22.setText("")
        self.comboBox.setItemText(
            0, QCoreApplication.translate("Dialog", "Blockage", None)
        )
        self.comboBox.setItemText(
            1, QCoreApplication.translate("Dialog", "Enhancement", None)
        )

        self.comboBox_2.setItemText(
            0, QCoreApplication.translate("Dialog", "None", None)
        )
        self.comboBox_2.setItemText(
            1, QCoreApplication.translate("Dialog", "Bessel", None)
        )

        self.update_trace_pushButton.setText(
            QCoreApplication.translate("Dialog", "Ok and Save", None)
        )
        self.update_trace_pushButton_2.setText(
            QCoreApplication.translate("Dialog", "Cancel", None)
        )

    # retranslateUi


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    widget = EventSegmentationSettingsWidget()
    widget.show()
    sys.exit(app.exec())
