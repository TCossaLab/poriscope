.. _SimpleCalc:

SimpleCalc Full Code Example
============================

.. tabs::

   .. tab:: SimpleCalcModel

      .. code-block:: python

         import logging
         from utils.MetaModel import MetaModel
         from utils.LogDecorator import log

         class SimpleCalcModel(MetaModel):
             """
             Simple calculator model to store and compute values.
             Supports addition (+) and subtraction (-) operations.
             """
             logger = logging.getLogger(__name__)

             @log(logger=logger)
             def _init(self):
                 self.results = []

             @log(logger=logger)
             def compute(self, left, operator, right):
                 if len(self.results) >= 5:
                     return None
                 if operator == "+":
                     result = left + right
                 elif operator == "-":
                     result = left - right
                 else:
                     return None
                 self.results.append(result)
                 return result

             @log(logger=logger)
             def get_results(self):
                 return self.results

             @log(logger=logger)
             def reset(self):
                 self.results = []

   .. tab:: SimpleCalcView

      .. code-block:: python

         from PySide6.QtWidgets import (
             QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton, QLabel
         )
         from PySide6.QtCore import Signal
         from utils.MetaView import MetaView
         from utils.LogDecorator import log

         class SimpleCalcView(MetaView):
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

                 results_container = QHBoxLayout()
                 results_container.setContentsMargins(0, 0, 0, 0)

                 self.result_display_container = QHBoxLayout()
                 self.result_display_container.setContentsMargins(0, 0, 0, 0)
                 self.result_display_container.setSpacing(5)

                 results_container.addWidget(QLabel("Results:"))
                 results_container.addLayout(self.result_display_container)

                 self.limit_warning_label = QLabel("")
                 self.limit_warning_label.setStyleSheet("color: red; font-style: italic;")
                 results_container.addWidget(self.limit_warning_label)

                 self.main_layout.addLayout(results_container)

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
                 if len(self.result_labels) >= 5:
                     self.limit_warning_label.setText("You have reached the limit! Reset to start again...")
                     return

                 label = QLabel(f"[ {result} ]")
                 self.result_labels.append(label)
                 self.result_display_container.addWidget(label)

                 if len(self.result_labels) == 5:
                     self.limit_warning_label.setText("You have reached the limit! Reset to start...")

             def _on_reset(self):
                 self._reset_actions()
                 self.request_reset.emit()

             def _reset_actions(self):
                 self.left_input.clear()
                 self.right_input.clear()
                 self.operator_box.setCurrentIndex(0)

                 for label in self.result_labels:
                     self.result_display_container.removeWidget(label)
                     label.deleteLater()
                 self.result_labels = []
                 self.result_list = []

                 try:
                     self.figure.clear()
                     self.canvas.draw()
                 except AttributeError:
                     pass

                 self.limit_warning_label.setText("")

             def update_plot_data(self, results):
                 self.result_list = results

             def update_plot(self):
                 self.figure.clear()
                 ax = self.figure.add_subplot(111)
                 ax.plot(self.result_list, marker='o')
                 ax.set_title("Results Over Time")
                 ax.set_xlabel("Step")
                 ax.set_ylabel("Result")
                 self.canvas.draw()

             def update_available_plugins(self, _):
                 pass

   .. tab:: SimpleCalcController

      .. code-block:: python

         import logging
         from utils.MetaController import MetaController
         from utils.LogDecorator import log
         from plugins.analysistabs.SimpleCalcView import SimpleCalcView
         from plugins.analysistabs.SimpleCalcModel import SimpleCalcModel

         class SimpleCalcController(MetaController):
             """
             Controller for the SimpleCalc plugin.
             Connects user input from the view to calculation logic in the model.
             """
             logger = logging.getLogger(__name__)

             @log(logger=logger)
             def _init(self):
                 self.view = SimpleCalcView()
                 self.model = SimpleCalcModel()

             @log(logger=logger)
             def _setup_connections(self):
                 self.view.calculate_operation.connect(self.handle_add)
                 self.view.request_plot.connect(self.handle_plot)
                 self.view.request_reset.connect(self.handle_reset)

             @log(logger=logger)
             def handle_add(self, left, operator, right):
                 result = self.model.compute(left, operator, right)
                 if result is not None:
                     self.view.add_result(result)

             @log(logger=logger)
             def handle_plot(self):
                 results = self.model.get_results()
                 self.view.update_plot_data(results)
                 self.view.update_plot()

             @log(logger=logger)
             def handle_reset(self):
                 self.model.reset()


.. admonition:: Pro Tip

   You may have noticed the ``@log(logger=logger)`` tags above some functions.

   This is Poriscope’s way of automatically keeping track of what happens in your plugin — like when a function starts, ends, or runs into a problem.

   It helps with troubleshooting and understanding how everything runs behind the scenes — without needing to write a lot of extra code.

   If you want to log your own messages inside the function (like notes or warnings), you can still do that using lines like ``self.logger.info("Your message here")``.

   For more details, see :ref:`Logging`.


