"""
What the autodoc generators cover, and what Step 3f would move outside it.

Nothing in ``tests/`` mentioned ``automethod`` before the Step 2 exit review, so the
published API documentation had no gate at all. Two refactor steps change it, and
measuring rather than assuming corrected the plan on both.

**Step 3a's risk was smaller than recorded, and it has now landed.** The plan said
the generators "skip classes with no docstring - none of the five has one - so ~50
``automethod`` lines would vanish". The five controls classes genuinely have no
class docstring and were documented anyway; the *plugins* generator writes a
docstring when there is one and documents the class either way. The gate that
actually bites is the other generator's: ``metaclasses_generate_autodoc.py`` scans
``poriscope/utils/`` as a directory, so ``MetaControls.py`` needed no registration
step - but it ``continue``s past a class with no docstring and emits no page at
all. So the promoted methods moved to a new page rather than disappearing, and
what holds that is ``MetaControls``' own class docstring. Both halves are asserted
below: that the page exists, and that the promoted directives are on it and on no
per-tab page.

**Step 3f landed 2026-09-06, and the outcome was decided rather than discovered.** The
generators scan exactly two roots, ``poriscope/utils`` and ``poriscope/plugins``.
**``poriscope/views/`` is scanned by neither.** 3f moved ``walkthrough.py`` and
``walkthrough_mixin.py`` from ``plugins/analysistabs/utils/`` into ``views/widgets/`` to
fix a layering inversion, taking them out of a documented tree and into an undocumented
one, which deleted the four pages those modules owned - 26 ``automethod`` directives.

Three of the four were let go deliberately: ``IntroDialog``, ``Overlay`` and
``StepDialog`` are internal UI machinery named in no prose documentation anywhere, and a
plugin author never instantiates them. ``WalkthroughMixin`` was not, because a live
tutorial tells authors to inherit it, so it has a hand-written page carrying a real
``.. _walkthrough_mixin:`` label. The tests below now hold that shape: the three have no
page, the fourth does, and it is not under ``autodoc/``.

Pages are keyed by **class**, not by module, which is why 14 modules under the
scanned roots legitimately have no page: they hold decorators, metaclasses and
helpers rather than documented classes. "Every module has a page" is therefore the
wrong invariant, and is not what this asserts.
"""

import ast
import re
from pathlib import Path
from typing import Set

import pytest

pytestmark = pytest.mark.characterization

REPO_ROOT = Path(__file__).resolve().parents[3]
AUTODOC = REPO_ROOT / "docs" / "source" / "autodoc"

#: The roots the two generators scan, read from their own module constants below.
EXPECTED_ROOTS = {"poriscope/utils", "poriscope/plugins"}

#: Dotted path Step 3a's promoted methods are documented under, now that they live
#: on the shared base rather than on five copies.
BASE_CLASS_PATH = "poriscope.utils.MetaControls.MetaControls"

#: The three dialog classes whose pages Step 3f deliberately gave up.
WALKTHROUGH_DIALOG_CLASSES = {"introdialog", "overlay", "stepdialog"}

#: The hand-written replacement for ``WalkthroughMixin``'s generated page, and the
#: tutorial that links to it. Both are hand-maintained, so neither is under ``autodoc/``.
HANDWRITTEN_MIXIN_PAGE = Path(
    "docs/source/utils/user_manuals/plugins_manual/plugin_development"
    "/frontend_plugin/next_steps/walkthrough_mixin.rst"
)
WALKTHROUGH_TUTORIAL = HANDWRITTEN_MIXIN_PAGE.with_name("adding_walkthrough.rst")


def generator_roots() -> Set[str]:
    """
    Read ``FOLDER_ORIGIN`` out of each generator without importing it.

    Parsed rather than imported because importing runs module-level path setup and
    would couple this test to the generators' side effects.

    :return: the repository-relative roots the generators scan
    :rtype: Set[str]
    """
    roots: Set[str] = set()
    for script in sorted(
        (REPO_ROOT / "scripts" / "autodoc").glob("*_generate_autodoc.py")
    ):
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "FOLDER_ORIGIN" not in names:
                continue
            # ast.unparse keeps source order; ast.walk does not, and a BinOp
            # chain like PROJECT_ROOT / "poriscope" / "utils" walks right to left.
            parts = re.findall(r"['\"]([^'\"]+)['\"]", ast.unparse(node.value))
            roots.add("/".join(parts))
    return roots


needs_autodoc = pytest.mark.skipif(
    not AUTODOC.is_dir(),
    reason=(
        "docs/source/autodoc is generated output and is gitignored; regenerate it "
        "with `python scripts/generate_all_autodoc_rst.py`"
    ),
)


# ===========================================================================
# Always runs - reads the generators' own configuration
# ===========================================================================


def test_the_generators_scan_exactly_two_roots() -> None:
    """
    Recorded so that adding or losing a root is a deliberate edit.

    Step 3f needs a third root, or a different destination, if the walkthrough
    modules are to keep their pages.
    """
    assert generator_roots() == EXPECTED_ROOTS


def test_the_app_shell_is_covered_by_no_generator() -> None:
    """
    ``poriscope/views/`` is documented by nothing, which is the Step 3f problem.

    Not a defect in itself - the shell is not public API the way plugins are - but
    it is the reason moving a documented module there deletes its pages.
    """
    assert not any(root.startswith("poriscope/views") for root in generator_roots())


def test_the_walkthrough_modules_live_in_the_app_shell() -> None:
    """
    Step 3f moved them into ``poriscope/views/widgets/``, which no generator scans.

    Asserted from the destination rather than the origin so that moving them back -
    which would restore the layering inversion rule 4 of the MVC boundary exists to
    catch - fails here too.
    """
    for name in ("walkthrough.py", "walkthrough_mixin.py"):
        moved = REPO_ROOT / "poriscope" / "views" / "widgets" / name
        origin = REPO_ROOT / "poriscope" / "plugins" / "analysistabs" / "utils" / name

        assert moved.is_file(), f"{name} is not in views/widgets/; see Step 3f"
        assert not origin.is_file(), f"{name} is back under plugins/; see Step 3f"


# ===========================================================================
# Runs when the generated tree is present
# ===========================================================================


@needs_autodoc
def test_the_three_dialog_classes_have_no_generated_page() -> None:
    """
    Given up deliberately by Step 3f, so their absence must not read as a regression.

    If one reappears, either a generator grew a third root or the modules moved back -
    both worth knowing about.
    """
    pages = {p.stem.lower() for p in AUTODOC.rglob("*.rst")}

    assert not (WALKTHROUGH_DIALOG_CLASSES & pages), sorted(
        WALKTHROUGH_DIALOG_CLASSES & pages
    )


def test_the_mixin_keeps_a_hand_written_page_with_a_real_label() -> None:
    """
    The one page 3f replaced rather than dropped.

    ``adding_walkthrough.rst`` tells plugin authors to inherit ``WalkthroughMixin``, and
    linked to it through two **backslash-escaped** pseudo-references that Sphinx rendered
    as literal text - and whose labels existed nowhere in ``docs/``, so they could never
    have resolved even unescaped. 3f wrote the label and repaired both links.
    """
    page = REPO_ROOT / HANDWRITTEN_MIXIN_PAGE
    assert page.is_file(), f"{HANDWRITTEN_MIXIN_PAGE} is missing"

    text = page.read_text(encoding="utf-8")
    assert ".. _walkthrough_mixin:" in text
    assert "poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin" in text

    tutorial = (REPO_ROOT / WALKTHROUGH_TUTORIAL).read_text(encoding="utf-8")
    assert ":ref:`walkthrough_mixin`" in tutorial
    assert r"\:ref:" not in tutorial, "an escaped pseudo-link is back"


#: Every base Step 3 creates to hold promoted analysis-tab code. Each is listed here
#: as it lands, because losing one's page is invisible to everything else.
STEP_3_BASES = (
    "metacontrols",
    "metaeventtabcontroller",
    "metaeventtabcontrols",
    "metaeventtabview",
    "metasubsettabcontroller",
    "metasubsettabcontrols",
    "metasubsettabview",
)


@needs_autodoc
@pytest.mark.parametrize("module", STEP_3_BASES)
def test_every_step_3_base_has_a_page_at_all(module: str) -> None:
    """
    The one thing nothing else in this file would notice.

    ``metaclasses_generate_autodoc.py`` skips any class in ``poriscope/utils/``
    with no docstring - a bare ``continue``, printed to stdout and nowhere else.
    So a Step 3 base that lost its class docstring would publish **no page**,
    silently, with ``sphinx-build -W`` green and every other test here passing,
    taking every directive that step promoted with it. Pages are keyed off the
    *module* name lowercased, not the class name.

    :param module: the lowercased module name whose page must exist
    :type module: str
    """
    page = AUTODOC / "metaclasses" / f"{module}.rst"

    assert page.is_file(), f"{module} lost its page; check its class docstring"
    assert "automethod" in page.read_text(encoding="utf-8")


@needs_autodoc
def test_the_controls_classes_are_documented_despite_having_no_docstring() -> None:
    """
    The plan's stated reason for Step 3a's autodoc risk, checked and found wrong.

    All five classes lack a docstring and all five are documented anyway. Asserted
    so the corrected understanding is held rather than drifting back.
    """
    utils = REPO_ROOT / "poriscope" / "plugins" / "analysistabs" / "utils"
    for source in sorted(utils.glob("*ontrols*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        assert classes, source.name
        assert ast.get_docstring(classes[0]) is None, source.name

        page = (
            AUTODOC
            / "plugins"
            / "analysistabs"
            / "utils"
            / f"{source.stem.lower()}.rst"
        )
        assert page.is_file(), f"{source.name} lost its page"
        assert "automethod" in page.read_text(encoding="utf-8")


@needs_autodoc
def test_the_methods_step_3a_promoted_are_documented_on_metacontrols() -> None:
    """
    The directives 3a moved, now on ``MetaControls``' page rather than on five.

    Before 3a this asserted the same three names appeared **five times** across the
    per-tab pages, one per class. They now appear once each, on the base's page, and
    on none of the five - which is the whole point of the promotion. The failure
    this still guards against is unchanged: if they appear on neither, roughly sixty
    directives have silently left the published documentation, and both a
    ``sphinx-build -W`` and the rest of this file stay green while it happens.
    """
    promoted = ("create_info_button", "create_delete_button", "create_add_button")
    base_page = (AUTODOC / "metaclasses" / "metacontrols.rst").read_text(
        encoding="utf-8"
    )
    utils_pages = (AUTODOC / "plugins" / "analysistabs" / "utils").glob("*ontrols*.rst")
    per_tab = "\n".join(p.read_text(encoding="utf-8") for p in utils_pages)

    for method in promoted:
        assert f".. automethod:: {BASE_CLASS_PATH}.{method}" in base_page, method
        assert method not in per_tab, f"{method} still has a per-tab copy"
