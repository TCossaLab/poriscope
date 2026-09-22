"""
Tests for ``scripts/check_version_consistency.py``, the release version gate.

``CITATION.cff``'s version is a hand-maintained copy of ``poriscope/constants.py``'s, and
``release.yml`` validated only that the file parsed as CFF. **Zenodo builds its record from
``CITATION.cff``**, so a stale version there publishes the release under the old number and
nothing fails - the release succeeds, the DOI resolves, and the metadata is wrong.

The checked-in files are asserted to agree as well as the parsing being exercised against
fakes, because the whole point is a gate over the *real* files: a test that only ever reads
a temporary fixture would pass happily while the repository it guards had drifted.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import importlib.util
import types
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "check_version_consistency.py")

pytestmark = pytest.mark.characterization


def load_script() -> types.ModuleType:
    """
    Import the checker by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("check_version_consistency", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> types.ModuleType:
    """
    Provide the checker module.

    :return: the imported module
    :rtype: types.ModuleType
    """
    return load_script()


class TestTheRepositoryItself:
    """The gate is only worth anything if it is run against the real files."""

    def test_the_checked_in_files_agree(self, script: types.ModuleType) -> None:
        """If this fails, the repository is in the state the gate exists to catch."""
        assert script.disagreements(None) == []

    def test_the_two_files_are_read_not_guessed(self, script: types.ModuleType) -> None:
        """Both parsers return something version-shaped from the real files."""
        code_version, code_date = script.read_constants()
        cff_version, cff_date = script.read_citation()
        assert code_version.count(".") == 2, code_version
        assert cff_version == code_version
        assert code_date == cff_date
        assert len(code_date) == len("YYYY-MM-DD")


class TestTheTagComparison:
    """The tag is the third source, and the one a release actually publishes under."""

    def test_a_matching_tag_passes(self, script: types.ModuleType) -> None:
        version, _ = script.read_constants()
        assert script.disagreements(f"v{version}") == []

    def test_a_tag_without_its_prefix_still_matches(
        self, script: types.ModuleType
    ) -> None:
        """Release tags carry a ``v``, but the check should not depend on it."""
        version, _ = script.read_constants()
        assert script.disagreements(version) == []

    def test_a_mismatched_tag_is_reported_against_both_files(
        self, script: types.ModuleType
    ) -> None:
        """
        Two messages, not one.

        Cutting a release from the wrong tag is wrong against `constants.py` *and* against
        `CITATION.cff`, and saying so twice is what tells the reader both need changing.
        """
        problems = script.disagreements("v99.99.99")
        assert len(problems) == 2
        assert all("v99.99.99" in problem for problem in problems)


class TestReporting:
    """A gate nobody can act on is a gate that gets bypassed."""

    def test_it_exits_zero_and_says_what_it_checked(
        self, script: types.ModuleType, capsys: Any
    ) -> None:
        assert script.main([]) == 0
        out = capsys.readouterr().out
        version, _ = script.read_constants()
        assert version in out

    def test_a_failure_names_zenodo_as_the_consequence(
        self, script: types.ModuleType, capsys: Any
    ) -> None:
        """
        The reason matters more than the rule here.

        Someone hitting this at release time needs to know why a mismatched CFF is worth
        stopping for, because the release would otherwise succeed and look fine.
        """
        assert script.main(["--tag", "v99.99.99"]) == 1
        err = capsys.readouterr().err
        assert "Zenodo" in err
        assert "v99.99.99" in err

    def test_every_disagreement_is_reported_at_once(
        self, script: types.ModuleType, capsys: Any
    ) -> None:
        """Reporting one at a time turns a single fix into several CI rounds."""
        script.main(["--tag", "v99.99.99"])
        err = capsys.readouterr().err
        assert err.count("does not match") == 2
