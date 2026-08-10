"""
Unit-test suite for ProteinModel.

ProteinModel is a minimal MetaModel subclass with a no-op _init(). There is
essentially no ProteinModel-specific logic to test — these tests confirm the
class constructs correctly, inherits from MetaModel as expected, and that
_init() is a genuine no-op that doesn't set any unexpected state or raise.

Run with:
    pytest test_protein_model.py -v
    pytest test_protein_model.py --cov=poriscope --cov-report=html
"""

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.utils.MetaModel import MetaModel

# ===========================================================================
# Construction / inheritance
# ===========================================================================


class TestConstruction:
    def test_instantiates_without_error(self):
        model = ProteinModel()
        assert model is not None

    def test_is_instance_of_meta_model(self):
        model = ProteinModel()
        assert isinstance(model, MetaModel)

    def test_is_instance_of_protein_model(self):
        model = ProteinModel()
        assert isinstance(model, ProteinModel)


# ===========================================================================
# _init — should be a genuine no-op
# ===========================================================================


class TestInit:
    def test_init_does_not_raise(self):
        # Constructing the model already calls _init() internally via
        # MetaModel.__init__; this just makes the intent explicit.
        model = ProteinModel()
        model._init()  # calling again directly should also be safe/idempotent

    def test_init_does_not_set_any_new_instance_attributes(self):
        model = ProteinModel()
        before = set(vars(model).keys())
        model._init()
        after = set(vars(model).keys())
        assert before == after

    def test_init_returns_none(self):
        model = ProteinModel()
        assert model._init() is None

    def test_has_logger_attribute(self):
        # logger is a class-level attribute set via logging.getLogger(__name__)
        assert ProteinModel.logger is not None

    def test_logger_name_matches_module(self):
        assert ProteinModel.logger.name == "poriscope.plugins.analysistabs.ProteinModel"
