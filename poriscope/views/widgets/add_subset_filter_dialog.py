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

from PySide6.QtWidgets import QDialogButtonBox

from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.views.widgets.base_widgets.base_subset_filter_dialog import (
    BaseSubsetFilterDialog,
)


class AddSubsetFilterDialog(BaseSubsetFilterDialog, WalkthroughMixin):
    def __init__(self, parent, existing_names):
        super().__init__(parent, "Create Subset Filter", existing_names)

    def get_current_view(self):
        return "AddSubsetFilterDialog"

    def get_walkthrough_steps(self):
        return [
            (
                "Add Filter",
                "Enter a name for your new subset filter.",
                "AddSubsetFilterDialog",
                lambda: [self.name_input],
            ),
            (
                "Add Filter",
                "Define your filter criteria here. For details on the SQL filter format refer to the documentation: User Guide/MetaData Tab - Step 3",
                "AddSubsetFilterDialog",
                lambda: [self.filter_input],
            ),
            (
                "Add Filter",
                "Click OK to confirm and save the subset.",
                "AddSubsetFilterDialog",
                lambda: [self.button_box.button(QDialogButtonBox.Ok)],
            ),
        ]
