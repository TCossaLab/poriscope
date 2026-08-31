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

from typing import Dict, Optional

from PySide6.QtWidgets import QWidget

from poriscope.views.widgets.base_widgets.base_subset_filter_dialog import (
    BaseSubsetFilterDialog,
)


class EditSubsetFilterDialog(BaseSubsetFilterDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        original_name: str,
        existing_filters: Dict[str, str],
    ) -> None:
        super().__init__(
            parent,
            title=f"Edit Filter: {original_name}",
            existing_names=existing_filters.keys(),
            default_name=original_name,
            default_filter=existing_filters.get(original_name, ""),
        )
        self.new_name: Optional[str] = None
        self.new_filter: Optional[str] = None

    def accept(self) -> None:
        self.new_name = self.name
        self.new_filter = self.filter_text
        super().accept()
