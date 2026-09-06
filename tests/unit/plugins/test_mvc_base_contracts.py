"""
The analysis-tab bases' abstract surface, pinned exactly.

``test_plugin_compliance.py`` *reads* ``__abstractmethods__`` to check that each
concrete subclass implements what its base declares. It never asserts anything
about the set itself, so removing a method from it - making it concrete, or
deleting it - simply means one fewer thing to check, and every test still passes.

That matters because **Decision C lists the ABC breaks 2.0.0 intends to take**, and
a list of intended breaks is only meaningful if an unintended one fails. Two steps
change these contracts on purpose:

* **3a-bis** proposes making ``MetaView._set_control_area`` concrete, which relaxes
  a contract every subclass satisfies today. No break, but a contract change
  Decision C does not list.
* **3c** proposes deleting ``_factors`` overrides in RawData and EventAnalysis.
  That one is safe - ``_factors`` is concrete on the base - but the same bullet
  wrongly named ``notify_plugin_state_changed``, which is abstract, and acting on
  it would make both classes uninstantiable.

So the rule here is not "these sets must never change". It is that changing one
must be a deliberate edit to this file, reviewed alongside the change, rather than
something that happens quietly. The Step 2 exit review added it after finding that
nothing pinned it.
"""

from typing import Set

import pytest

from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaModel import MetaModel
from poriscope.utils.MetaView import MetaView

pytestmark = pytest.mark.characterization

#: The abstract surface of each analysis-tab base, as of the Step 2 exit review.
#: Changing one of these is a contract change: update the entry in the same commit
#: as the code, and say in the message which refactor step authorises it.
CONTRACTS = {
    MetaView: {
        "_init",
        "_reset_actions",
        "_set_control_area",
        "notify_plugin_state_changed",
        "update_available_plugins",
    },
    MetaModel: {"_init"},
    MetaController: {"_init", "_setup_connections"},
}


@pytest.mark.parametrize(
    ("base", "expected"), CONTRACTS.items(), ids=lambda v: getattr(v, "__name__", "")
)
def test_the_abstract_surface_is_exactly_as_recorded(
    base: type, expected: Set[str]
) -> None:
    """
    Neither wider nor narrower than recorded.

    A *wider* set breaks every existing subclass loudly, so it would be noticed
    anyway. A *narrower* one is the dangerous direction: nothing fails, and the
    plugin-compliance test simply has one fewer method to check.
    """
    assert set(base.__abstractmethods__) == expected


def test_factors_is_concrete_on_metaview() -> None:
    """
    The half of Step 3c's claim that holds, so the deletion it proposes is safe.

    Its sibling claim about ``notify_plugin_state_changed`` does not hold, and is
    asserted in ``tests/unit/views/test_plugin_state_notifications.py``.
    """
    assert "_factors" not in MetaView.__abstractmethods__
    assert "_factors" in MetaView.__dict__


def test_metamodel_declares_almost_nothing() -> None:
    """
    One abstract method, which four of the five tab Models implement as ``pass``.

    This is why the compliance test cannot notice anything the refactor does to the
    Model layer, and it is the reason Steps 3d and 4a-4e needed characterization
    tests rather than relying on compliance. Pinned so that if the Model layer ever
    grows a real contract, the fact is recorded rather than absorbed.
    """
    assert len(MetaModel.__abstractmethods__) == 1
