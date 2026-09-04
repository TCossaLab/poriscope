from PySide6.QtWidgets import QLabel

from utils.MetaView import MetaView


class HelloWorldView(MetaView):
    def _init(self):
        pass

    def _set_control_area(self, layout):
        # This is where you'd add controls (e.g. buttons, dropdowns)
        label = QLabel("Hello, world!")
        layout.addWidget(label)
        pass

    def _reset_actions(self):
        # Reset custom state if needed
        pass

    def update_available_plugins(self, available_plugins):
        # Update logic when new plugins are available
        pass
