"""
``MetaModel.load_filters`` and ``save_filters`` - the subset filter file, read and written.

A subset filter is a WHERE clause somebody wrote, and a filter file is a plain JSON
object of filter name to filter text. The widget that owns the filters picks the path
with a file dialog; the file itself is opened here, so a failure has somewhere to be
reported from and the round trip has somewhere to be tested.
"""

import json
from typing import override

import pytest

from poriscope.utils.MetaModel import MetaModel


class _ConcreteModel(MetaModel):
    """A minimal concrete MetaModel, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model():
    """
    A concrete MetaModel to read and write filters with.

    :return: the model under test
    :rtype: _ConcreteModel
    """
    return _ConcreteModel()


class TestSaveFilters:
    """What lands on disk."""

    def test_the_file_is_the_filters(self, model, tmp_path):
        path = tmp_path / "filters.json"

        model.save_filters(str(path), {"long": "dwell > 5", "big": "amp > 100"})

        assert json.loads(path.read_text()) == {
            "long": "dwell > 5",
            "big": "amp > 100",
        }

    def test_the_file_is_readable_by_a_person(self, model, tmp_path):
        """
        Indented on purpose: a filter is a clause somebody wrote, and the file is
        meant to be hand-editable. One line of JSON would still load.
        """
        path = tmp_path / "filters.json"

        model.save_filters(str(path), {"long": "dwell > 5", "big": "amp > 100"})

        assert path.read_text().count("\n") > 1

    def test_no_filters_still_writes_a_file(self, model, tmp_path):
        """An empty file is a valid answer - it is what loads back as no filters."""
        path = tmp_path / "filters.json"

        model.save_filters(str(path), {})

        assert json.loads(path.read_text()) == {}

    def test_a_path_that_cannot_be_written_raises(self, model, tmp_path):
        """The caller reports it; the model does not swallow it."""
        with pytest.raises(OSError):
            model.save_filters(str(tmp_path / "no_such_dir" / "f.json"), {"a": "b"})


class TestLoadFilters:
    """What comes back off disk, and what is refused."""

    def test_a_file_this_model_wrote_comes_back_unchanged(self, model, tmp_path):
        path = tmp_path / "filters.json"
        filters = {"long": "dwell > 5", "raw_one_raw": "SELECT 1"}
        model.save_filters(str(path), filters)

        assert model.load_filters(str(path)) == filters

    def test_a_json_list_is_refused(self, model, tmp_path):
        """
        Anything but an object is refused rather than half accepted: a list would
        iterate into filter names one character at a time, and the caller would be
        left holding filters nobody wrote.
        """
        path = tmp_path / "filters.json"
        path.write_text(json.dumps(["dwell > 5"]))

        with pytest.raises(ValueError, match="list"):
            model.load_filters(str(path))

    def test_a_json_scalar_is_refused(self, model, tmp_path):
        path = tmp_path / "filters.json"
        path.write_text(json.dumps("dwell > 5"))

        with pytest.raises(ValueError, match="str"):
            model.load_filters(str(path))

    def test_a_file_that_is_not_json_raises(self, model, tmp_path):
        path = tmp_path / "filters.json"
        path.write_text("dwell > 5")

        with pytest.raises(ValueError):
            model.load_filters(str(path))

    def test_a_missing_file_raises(self, model, tmp_path):
        with pytest.raises(OSError):
            model.load_filters(str(tmp_path / "nothing_here.json"))
