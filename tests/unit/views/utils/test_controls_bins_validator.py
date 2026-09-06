"""
Characterization tests for the bins-vs-sizes validator swap in the controls widgets.

``_on_sizes_checkbox_toggled`` is a two-way duplicate between ``metadatacontrols``
and ``proteincontrols`` that Step 3b merges. The refactor-coverage audit reported it
as ``RUNS ONLY``: its body executes when a controls widget is constructed - the
constructor calls it once to set the initial state - but no test named it, so
nothing asserted what it actually does.

What it does is swap the validator on the bins field between integer and float. That
is the difference between the user being able to type ``1.2, 3.5`` and the field
silently refusing the keystroke, so it is worth pinning before the two copies are
merged into one.
"""

from unittest.mock import MagicMock

import pytest

from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls

pytestmark = pytest.mark.characterization

#: Both carriers of the duplicated method. Step 3b merges them.
CONTROLS = (MetadataControls, ProteinControls)


def build(cls: type) -> object:
    """
    Build a controls widget with only what the toggle handler reads.

    ``__new__`` skips the whole widget tree; the handler touches three attributes
    and nothing else.

    :param cls: the controls class
    :type cls: type
    :return: the instance
    :rtype: object
    """
    instance = cls.__new__(cls)
    instance.bins_lineEdit = MagicMock()
    instance.float_validator = MagicMock(name="float_validator")
    instance.int_validator = MagicMock(name="int_validator")
    return instance


@pytest.mark.parametrize("cls", CONTROLS)
class TestSizesCheckboxToggled:
    """Both copies must behave identically, which is why they are parametrized."""

    def test_checking_it_allows_float_bin_sizes(self, cls: type) -> None:
        """
        Sizes mode means the user types bin *widths*, which are fractional.

        Installing the integer validator here would refuse the decimal point
        keystroke outright, with no error message.
        """
        controls = build(cls)

        controls._on_sizes_checkbox_toggled(True)

        controls.bins_lineEdit.setValidator.assert_called_once_with(
            controls.float_validator
        )

    def test_unchecking_it_restores_the_integer_validator(self, cls: type) -> None:
        """Counts mode takes a bin count or a list of edges, all integers."""
        controls = build(cls)

        controls._on_sizes_checkbox_toggled(False)

        controls.bins_lineEdit.setValidator.assert_called_once_with(
            controls.int_validator
        )

    def test_the_placeholder_tells_the_user_which_mode_they_are_in(
        self, cls: type
    ) -> None:
        """
        The placeholder is the only on-screen cue that the accepted format changed.

        Pinned as exact text because it is the whole of the user-facing feedback.
        """
        controls = build(cls)

        controls._on_sizes_checkbox_toggled(True)
        checked = controls.bins_lineEdit.setPlaceholderText.call_args.args[0]

        controls._on_sizes_checkbox_toggled(False)
        unchecked = controls.bins_lineEdit.setPlaceholderText.call_args.args[0]

        assert checked == "e.g. 1.2, 3.5, 4.0"
        assert unchecked == "e.g. 10 or 5,10,15"

    def test_toggling_back_and_forth_leaves_the_integer_validator(
        self, cls: type
    ) -> None:
        """The two branches are symmetric; neither leaks state into the other."""
        controls = build(cls)

        controls._on_sizes_checkbox_toggled(True)
        controls._on_sizes_checkbox_toggled(False)

        assert (
            controls.bins_lineEdit.setValidator.call_args.args[0]
            is controls.int_validator
        )


def test_both_copies_are_byte_identical() -> None:
    """
    The two implementations agree today, which is what makes 3b's merge safe.

    Compared as source rather than by behaviour, because the parametrized tests
    above already cover behaviour and this catches a divergence that keeps the
    same observable effect - the shape that lets a fix land in one copy only.
    """
    import inspect
    import textwrap

    bodies = {
        textwrap.dedent(
            inspect.getsource(cls._on_sizes_checkbox_toggled)
        ).strip()
        for cls in CONTROLS
    }
    assert len(bodies) == 1
