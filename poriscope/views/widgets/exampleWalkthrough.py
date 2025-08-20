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

# main.py

from PySide6.QtWidgets import QApplication, QComboBox, QMainWindow, QPushButton
from walkthrough import start_walkthrough


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demo View with Walkthrough")
        self.setFixedSize(800, 600)

        self.btn1 = QPushButton("Step 1: Event", self)
        self.btn1.setGeometry(50, 80, 160, 40)

        self.dropdown = QComboBox(self)
        self.dropdown.setGeometry(250, 200, 160, 40)
        self.dropdown.addItems(["Option 1", "Option 2", "Option 3"])

        self.btn3 = QPushButton("Step 3: Start", self)
        self.btn3.setGeometry(50, 300, 160, 40)

        self.launch_btn = QPushButton("Launch Walkthrough", self)
        self.launch_btn.setGeometry(50, 400, 200, 40)
        self.launch_btn.clicked.connect(self.run_walkthrough)

    def run_walkthrough(self):
        steps = [
            ("Step 1", "Click this button to select an event.", self.btn1),
            ("Step 2", "Pick an option from the dropdown.", self.dropdown),
            ("Step 3", "Click to start the analysis.", self.btn3),
        ]
        start_walkthrough(self, steps)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
