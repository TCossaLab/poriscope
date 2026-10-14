"""A page switch refused by an active milestone must leave no tab behind."""

from unittest.mock import MagicMock

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView


def test_blocked_sidebar_click_does_not_instantiate_tab(qtbot, tmp_path):
    app_config = {
        "Parent Folder": str(tmp_path),
        "User Plugin Folder": str(tmp_path),
        "Log Level": 20,
    }
    model = MainModel(app_config)
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)
    qtbot.addWidget(view)

    view._milestone_dialog = MagicMock()
    view._expected_next_view = "EventAnalysisView"

    view.on_raw_data_view_click()

    assert "RawDataController" not in controller.analysis_tabs
    assert "RawDataView" not in view.pages
