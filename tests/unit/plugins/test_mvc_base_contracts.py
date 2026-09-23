"""
The analysis-tab bases' abstract surface, pinned exactly.

``test_plugin_compliance.py`` *reads* ``__abstractmethods__`` to check that each
concrete subclass implements what its base declares. It never asserts anything
about the set itself, so removing a method from it - making it concrete, or
deleting it - simply means one fewer thing to check, and every test still passes.

That matters because **2.0.0 takes a deliberate list of ABC breaks**, and a list
of intended breaks is only meaningful if an unintended one fails. These contracts
have changed on purpose:

* ``MetaView._set_control_area`` became concrete (landed 2026-09-06),
  which relaxed a contract every subclass satisfied. Its replacement hook
  ``_build_controls`` is deliberately **not** abstract - it returns an empty panel
  by default, so a tab that lays out its own control area can override
  ``_set_control_area`` instead and stay instantiable. So the set below is one
  smaller and nothing joined it. No break, but still a contract change.
* ``MetaView.handle_parameter_change`` became abstract (landed 2026-09-22),
  which widens the set by one. ``_set_control_area`` connects the controls panel's
  ``actionTriggered`` signal to it during construction, so a tab that did not define
  it raised ``AttributeError`` out of ``__init__``; the requirement existed and was
  simply not declared. All five shipped tabs already satisfied it. A break, and
  called out as one in ``changelog.md``.
* Deleting the ``_factors`` overrides in RawData and EventAnalysis is safe -
  ``_factors`` is concrete on the base - but the same reasoning does not extend to
  ``notify_plugin_state_changed``, which is abstract; deleting those overrides
  would make both classes uninstantiable.

So the rule here is not "these sets must never change". It is that changing one
must be a deliberate edit to this file, reviewed alongside the change, rather than
something that happens quietly. It was added after a review found that nothing
pinned it.
"""

from typing import Set

import pytest

from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaModel import MetaModel
from poriscope.utils.MetaView import MetaView

pytestmark = pytest.mark.characterization

#: The abstract surface of each analysis-tab base.
#: Changing one of these is a contract change: update the entry in the same commit
#: as the code, and say in the message why the change is intended.
CONTRACTS = {
    MetaView: {
        "_init",
        "_reset_actions",
        "handle_parameter_change",
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
    Deleting the ``_factors`` overrides in the subclasses is therefore safe.

    Its sibling claim about ``notify_plugin_state_changed`` does not hold, and is
    asserted in ``tests/unit/views/test_plugin_state_notifications.py``.
    """
    assert "_factors" not in MetaView.__abstractmethods__
    assert "_factors" in MetaView.__dict__


def test_metamodel_declares_almost_nothing() -> None:
    """
    One abstract method, which four of the five tab Models implement as ``pass``.

    This is why the compliance test cannot notice anything the refactor does to the
    Model layer, and it is the reason moving logic into the Models needed
    characterization tests rather than relying on compliance. Pinned so that if the
    Model layer ever grows a real contract, the fact is recorded rather than
    absorbed.
    """
    assert len(MetaModel.__abstractmethods__) == 1
