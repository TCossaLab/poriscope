import logging

from docs.source._static.images.examples.analysis_tabs.HelloWorldModel import (
    HelloWorldModel,
)
from docs.source._static.images.examples.analysis_tabs.HelloWorldView import (
    HelloWorldView,
)

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


class HelloWorldController(MetaController):

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    def _init(self):
        self.view = HelloWorldView()
        self.model = HelloWorldModel()

    @log(logger=logger)
    def _setup_connections(self):
        # This is where you'd connect signals and slots between view and model
        pass
