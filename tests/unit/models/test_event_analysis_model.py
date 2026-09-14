"""
Unit-test suite for EventAnalysisModel.

``EventAnalysisModel`` was the last ``def _init(self): pass`` Model in the repository
- the shape section 01 of the refactor plan opens on. Step 4's first closeout branch
gave it its first real method, ``event_time_bases``. The closeout's RawData branch then
found the second caller and promoted it to ``MetaModel.time_bases``, generalised with a
scale and an offset, since four of the five tabs plot event traces the same way - so the
behaviour is pinned in ``test_meta_model_time_bases.py`` and what remains here is this
subclass's own construction.
"""

import pytest

from poriscope.plugins.analysistabs.EventAnalysisModel import EventAnalysisModel
from poriscope.utils.MetaModel import MetaModel


@pytest.fixture
def model():
    """
    An EventAnalysisModel to compute with.

    :return: a constructed EventAnalysisModel
    :rtype: EventAnalysisModel
    """
    return EventAnalysisModel()


class TestConstruction:
    def test_instantiates_without_error(self, model):
        assert model is not None

    def test_is_instance_of_meta_model(self, model):
        assert isinstance(model, MetaModel)

    def test_init_returns_none(self, model):
        assert model._init() is None
