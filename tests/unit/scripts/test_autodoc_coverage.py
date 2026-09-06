"""
What the autodoc generators cover, and what Step 3f would move outside it.

Nothing in ``tests/`` mentioned ``automethod`` before the Step 2 exit review, so the
published API documentation had no gate at all. Two refactor steps change it, and
measuring rather than assuming corrected the plan on both.

**Step 3a's risk is smaller than recorded.** The plan says the generators "skip
classes with no docstring - none of the five has one - so ~50 ``automethod`` lines
would vanish". The five controls classes genuinely have no class docstring, and are
documented anyway: they carry **143 ``automethod`` directives between them**. The
generator writes a docstring when there is one and documents the class either way.
And ``metaclasses_generate_autodoc.py`` scans ``poriscope/utils/`` as a directory,
so a new ``MetaControls.py`` dropped there is picked up with no registration step.
The methods move to a new page rather than disappearing.

**Step 3f's risk is real and is the one to hold.** The generators scan exactly two
roots, ``poriscope/utils`` and ``poriscope/plugins``. **``poriscope/views/`` is
scanned by neither**, and has no autodoc anywhere. 3f moves ``walkthrough.py`` and
``walkthrough_mixin.py`` from ``plugins/analysistabs/utils/`` into
``views/widgets/`` - out of a documented tree and into an undocumented one - which
would silently delete the four pages those modules own.

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

#: The classes the two walkthrough modules own. Step 3f moves both modules.
WALKTHROUGH_CLASSES = {"introdialog", "overlay", "stepdialog", "walkthroughmixin"}


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


def test_the_walkthrough_modules_are_currently_inside_a_scanned_root() -> None:
    """
    They live under ``poriscope/plugins`` today, which is why they have pages.

    When 3f moves them this fails, which is the intended prompt: either extend the
    generators to the destination or accept losing four pages, deliberately.
    """
    for name in ("walkthrough.py", "walkthrough_mixin.py"):
        path = REPO_ROOT / "poriscope" / "plugins" / "analysistabs" / "utils" / name
        assert path.is_file(), f"{name} has moved; see Step 3f"


# ===========================================================================
# Runs when the generated tree is present
# ===========================================================================


@needs_autodoc
def test_the_walkthrough_classes_each_have_a_page() -> None:
    """
    Four pages, keyed by class name rather than by module.

    These are what 3f puts at risk, so they are named individually rather than
    counted.
    """
    pages = {p.stem.lower() for p in AUTODOC.rglob("*.rst")}

    assert WALKTHROUGH_CLASSES <= pages, sorted(WALKTHROUGH_CLASSES - pages)


@needs_autodoc
def test_metacontrols_has_a_page_at_all() -> None:
    """
    The one thing nothing else in this file would notice.

    ``metaclasses_generate_autodoc.py`` skips any class in ``poriscope/utils/``
    with no docstring - a bare ``continue``, printed to stdout and nowhere else.
    So a ``MetaControls`` that lost its class docstring would publish **no page**,
    silently, with ``sphinx-build -W`` green and every other test here passing,
    taking every directive Step 3a promoted with it. The page is keyed off the
    *module* name lowercased, not the class name.
    """
    page = AUTODOC / "metaclasses" / "metacontrols.rst"

    assert page.is_file(), "MetaControls lost its page; check its class docstring"
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
def test_the_controls_family_documents_the_methods_step_3a_promotes() -> None:
    """
    The directives 3a moves, present on the per-tab pages today.

    After 3a they should appear on ``MetaControls``' page instead. If they appear
    on neither, ~50 directives have silently left the published documentation,
    which is the outcome the plan warns about even though its stated mechanism was
    wrong.
    """
    promoted = ("create_info_button", "create_delete_button", "create_add_button")
    utils_pages = (AUTODOC / "plugins" / "analysistabs" / "utils").glob("*ontrols*.rst")
    text = "\n".join(p.read_text(encoding="utf-8") for p in utils_pages)

    for method in promoted:
        assert text.count(method) >= 5, method
