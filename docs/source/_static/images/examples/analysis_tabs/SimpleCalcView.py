from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from utils.MetaView import MetaView


class SimpleCalcView(MetaView):
    # Signals emitted from this view
    calculate_operation = Signal(float, str, float)
    request_plot = Signal()
    request_reset = Signal()

    def _init(self):
        self.result_labels = []
        self.result_list = []
        self.limit_warning_label = None

    def _set_control_area(self, layout):
        self.main_layout = QVBoxLayout()
        layout.addLayout(self.main_layout)

        # Input row
        input_layout = QHBoxLayout()
        self.left_input = QLineEdit()
        self.left_input.setPlaceholderText("Value")
        self.operator_box = QComboBox()
        self.operator_box.addItems(["+", "-"])
        self.right_input = QLineEdit()
        self.right_input.setPlaceholderText("Value")
        self.calculate_button = QPushButton("Add Calculation")
        self.calculate_button.clicked.connect(self._on_add_calculation)

        input_layout.addWidget(self.left_input)
        input_layout.addWidget(self.operator_box)
        input_layout.addWidget(self.right_input)
        input_layout.addWidget(self.calculate_button)
        self.main_layout.addLayout(input_layout)

        # Results row
        results_container = QHBoxLayout()
        results_container.setContentsMargins(0, 0, 0, 0)

        self.result_display_container = QHBoxLayout()
        self.result_display_container.setContentsMargins(0, 0, 0, 0)
        self.result_display_container.setSpacing(5)

        results_container.addWidget(QLabel("Results:"))
        results_container.addLayout(self.result_display_container)

        # Limit warning label
        self.limit_warning_label = QLabel("")
        self.limit_warning_label.setStyleSheet("color: red; font-style: italic;")
        results_container.addWidget(self.limit_warning_label)

        self.main_layout.addLayout(results_container)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.request_plot.emit)
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._on_reset)
        btn_layout.addWidget(self.plot_button)
        btn_layout.addWidget(self.reset_button)
        self.main_layout.addLayout(btn_layout)

    def _on_add_calculation(self):
        try:
            left = float(self.left_input.text())
            right = float(self.right_input.text())
            operator = self.operator_box.currentText()
            self.calculate_operation.emit(left, operator, right)
        except ValueError:
            return

    def add_result(self, result):
        if self.limit_warning_label is None:
            raise AttributeError("Unable to find limit_warning_label attribute")
        if len(self.result_labels) >= 5:
            self.limit_warning_label.setText(
                "You have reached the limit! Reset to start again..."
            )
            return

        label = QLabel(f"[ {result} ]")
        self.result_labels.append(label)
        self.result_display_container.addWidget(label)

        if len(self.result_labels) == 5:
            self.limit_warning_label.setText(
                "You have reached the limit! Reset to start..."
            )

    def _on_reset(self):
        self._reset_actions()
        self.request_reset.emit()

    def _reset_actions(self):
        # Clear inputs
        self.left_input.clear()
        self.right_input.clear()
        self.operator_box.setCurrentIndex(0)

        # Clear result display
        for label in self.result_labels:
            self.result_display_container.removeWidget(label)
            label.deleteLater()
        self.result_labels = []
        self.result_list = []

        # Clear plot
        try:
            self.figure.clear()
            self.canvas.draw()
        except AttributeError:
            pass

        # Clear warning
        if self.limit_warning_label is None:
            raise AttributeError("Unable to find limit_warning_label attribute")
        self.limit_warning_label.setText("")

    def update_plot_data(self, results):
        self.result_list = results

    def update_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(self.result_list, marker="o")
        ax.set_title("Results Over Time")
        ax.set_xlabel("Step")
        ax.set_ylabel("Result")
        self.canvas.draw()

    def update_available_plugins(self, _):
        pass
