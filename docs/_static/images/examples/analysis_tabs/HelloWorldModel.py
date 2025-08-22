import logging

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


class HelloWorldModel(MetaModel):

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    def _init(self):
        # No setup needed yet
        pass
