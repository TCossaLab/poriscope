"""
Ownership assertions for Controller methods Step 4a promoted to a shared base.

The behavioural coverage already exists and did not move: ``test_metadata_controller``
has fifteen tests for ``relay_query`` and ``test_protein_controller`` several more, and
after the promotion they all resolve through the MRO to the one copy on
``MetaSubsetTabController``. What none of them can see is whether a *second* copy
survived - a leftover would shadow the base for that one tab and every one of those
tests would still pass, which is the failure this file exists to catch.

Kept separate from ``tests/unit/views/test_duplicated_helpers.py``, which does the same
job for the View-side promotions, because that file lives under ``tests/unit/views`` and
these are Controllers.
"""

import pytest

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController

pytestmark = pytest.mark.characterization

SUBSET_CONTROLLERS = (MetadataController, ProteinController)

#: Promoted in Step 4a. ``relay_query`` was recorded on the base itself as deliberately
#: unshareable, because "the two tabs' copies differ" and each reached into its own
#: View's pending-filter state. The copies differed by a single blank line, and the
#: pending state had already been declared on ``MetaSubsetTabView``, so neither half of
#: the recorded reason held.
PROMOTED = ("relay_query",)


@pytest.mark.parametrize("name", PROMOTED)
def test_the_base_owns_the_only_copy(name: str) -> None:
    """
    Neither Controller may keep its own, or the promotion was partial.

    :param name: the promoted method's name
    :type name: str
    :return: None
    :rtype: None
    """
    assert name in MetaSubsetTabController.__dict__
    for controller_cls in SUBSET_CONTROLLERS:
        assert name not in controller_cls.__dict__, f"{controller_cls.__name__}.{name}"


@pytest.mark.parametrize("name", PROMOTED)
def test_both_tabs_resolve_to_the_same_function(name: str) -> None:
    """
    Stated as identity rather than as absence, so the two halves agree.

    ``__dict__`` absence and MRO identity can in principle disagree - a metaclass or a
    decorator applied at class creation would satisfy one and not the other - and it is
    the identity that the behavioural tests are actually relying on.

    :param name: the promoted method's name
    :type name: str
    :return: None
    :rtype: None
    """
    base = getattr(MetaSubsetTabController, name)
    for controller_cls in SUBSET_CONTROLLERS:
        assert getattr(controller_cls, name) is base, controller_cls.__name__


def test_the_base_no_longer_calls_relay_query_unshareable() -> None:
    """
    The docstring claim went with the method.

    ``MetaSubsetTabController``'s class docstring listed ``relay_query`` under what a
    subclass owes it, with a reason that had stopped being true. A stale contract in a
    published base's docstring is worth a test, because nothing else reads it.

    :return: None
    :rtype: None
    """
    doc = MetaSubsetTabController.__doc__ or ""
    assert "deliberately *not* shared" not in doc
    assert "relay_query" in doc
