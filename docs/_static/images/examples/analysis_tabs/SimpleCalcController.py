import logging

from plugins.analysistabs.SimpleCalcModel import SimpleCalcModel
from plugins.analysistabs.SimpleCalcView import SimpleCalcView
from utils.LogDecorator import log
from utils.MetaController import MetaController


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
