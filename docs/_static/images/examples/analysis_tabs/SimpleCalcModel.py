import logging

from utils.LogDecorator import log
from utils.MetaModel import MetaModel


class SimpleCalcModel(MetaModel):
    """
    Simple calculator model to store and compute values.
    Supports addition (+) and substraction (-)  operations.
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
