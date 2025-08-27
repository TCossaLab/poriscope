import logging
import re

from PySide6.QtCore import QTimer
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QLineEdit, QPushButton

# Configure logging
logging.basicConfig(level=logging.DEBUG)


class FloatRangeValidator(QValidator):
    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        super().__init__(parent)

    def validate(self, input: str, pos: int):
        input = input.strip()
        self.logger.debug(f"Validating input: '{input}'")

        if input == "":
            self.logger.debug("Intermediate: input is empty")
            return QValidator.Intermediate, input, pos

        if re.search(r"[^\d.,\-]", input):
            self.logger.debug(" Invalid: contains invalid characters")
            return QValidator.Invalid, input, pos

        if re.search(r"[,\-\.]{2,}", input):
            self.logger.debug(" Invalid: repeated punctuation")
            return QValidator.Invalid, input, pos

        if input[0] in "-,.":
            self.logger.debug("Invalid: starts with bad character")
            return QValidator.Invalid, input, pos

        parts = input.split(",")

        for part in parts:
            part = part.strip()
            self.logger.debug(f"Checking part: '{part}'")

            if not part:
                self.logger.debug("Skipped: empty segment")
                continue

            if "-" not in part:
                self.logger.debug("Intermediate: missing '-'")
                return QValidator.Intermediate, input, pos

            split = part.split("-", 1)
            if len(split) != 2:
                self.logger.debug("Invalid: multiple hyphens")
                return QValidator.Invalid, input, pos

            start_str, end_str = split
            start_str = start_str.strip()
            end_str = end_str.strip()
            self.logger.debug(f"Start: '{start_str}', End: '{end_str}'")

            self.logger.debug(f"Start: '{start_str}', End: '{end_str}'")

            if not start_str:
                self.logger.debug(" Intermediate: missing start")
                return QValidator.Intermediate, input, pos

            simulated_end_str = end_str if end_str else "0"
            if re.fullmatch(r"\d+", end_str):
                simulated_end_str += "0"
            self.logger.debug(f"Simulated end: '{simulated_end_str}'")

            try:
                start = float(start_str)
                end = float(simulated_end_str)
                self.logger.debug(f"Parsed: start={start}, end={end}")

                if start == 0.0 and end == 0.0:
                    if len(parts) > 1:
                        self.logger.debug(" Invalid: 0-0 not alone")
                        return QValidator.Invalid, input, pos
                    continue

                if end == 0.0:
                    self.logger.debug("Valid: treated as 'until end'")
                    continue

                if start >= end:
                    self.logger.debug("Intermediate: start >= end (while typing)")
                    return QValidator.Intermediate, input, pos

            except ValueError:
                self.logger.debug(" Intermediate: ValueError during float conversion")
                return QValidator.Intermediate, input, pos

        self.logger.debug("Acceptable: input is valid")
        return QValidator.Acceptable, input, pos


class TimeWidget(QDialog):
    logger = logging.getLogger(__name__)

    def __init__(self, params):
        super().__init__()
        self.setWindowTitle("Event Finding Time Limits")
        self.result = None
        self.params = {}
        self.entrywidgets = {}
        self.ok_button = QPushButton("OK", self)
        self.ok_button.setEnabled(False)
        cancel_button = QPushButton("Cancel", self)
        self._init_ui(params, cancel_button)

    def _init_ui(self, params, cancel_button):
        layout = QGridLayout(self)
        row = 0
        for key, val in params.items():
            self.params[key] = {}

            label = QLabel(f"Channel {key}")
            entry = QLineEdit()
            entry.setValidator(FloatRangeValidator(entry))
            entry.setPlaceholderText("e.g., 0.0-2.5, 3.0-6.0")
            self.entrywidgets[key] = entry

            # Prepopulate with data
            if "ranges" in val:
                formatted = ",".join(
                    f"{start}-{end}" if end is not None else f"{start}-0"
                    for start, end in val["ranges"]
                )
                entry.setText(formatted)
            elif "start" in val and "end" in val:
                entry.setText(f"{val['start']}-{val['end']}")

            entry.textChanged.connect(self._check_validity)
            layout.addWidget(label, row, 0)
            layout.addWidget(entry, row, 1)
            row += 1

        layout.addWidget(self.ok_button, row, 0)
        layout.addWidget(cancel_button, row, 1)

        self.ok_button.clicked.connect(self._on_ok)
        cancel_button.clicked.connect(self._on_cancel)
        QTimer.singleShot(0, self._check_validity)

    def _check_validity(self):
        all_valid = True

        for entry in self.entrywidgets.values():
            text = entry.text().strip()
            validator = entry.validator()

            if not text:
                all_valid = False
                break

            if validator:
                state, _, _ = validator.validate(text, 0)
                if state != QValidator.Acceptable:
                    all_valid = False
                    break

        self.ok_button.setEnabled(all_valid)

    def _on_ok(self):
        for key, entry in self.entrywidgets.items():
            ranges = self._parse_ranges(entry.text())
            self.params[key]["ranges"] = ranges
        self.result = self.params
        self.accept()

    def _on_cancel(self):
        self.result = None
        self.reject()

    def get_result(self):
        return self.result

    def _parse_ranges(self, text: str) -> list[tuple[float, float | None]]:
        result: list[tuple[float, float | None]] = []
        for segment in text.split(","):
            segment = segment.strip()
            if "-" in segment:
                try:
                    start_str, end_str = segment.split("-")
                    start = float(start_str)
                    end = float(end_str)
                    if start == 0.0 and end == 0.0:
                        result.append((0.0, 0.0))
                    elif start > end and end == 0.0:
                        result.append((start, None))
                    else:
                        result.append((start, end))
                except ValueError:
                    continue  # Skip invalid parts; already filtered
        return result
