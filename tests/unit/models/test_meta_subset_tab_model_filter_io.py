"""
``MetaSubsetTabModel.load_filters``/``save_filters`` - the subset filter file, read and
written.

A subset filter is a WHERE clause somebody wrote, and a filter file is a plain JSON
object of filter name to filter text. The widget that owns the filters picks the path
with a file dialog; the file itself is opened here, so a failure has somewhere to be
reported from and the round trip has somewhere to be tested.
"""

import json
from typing import override

import pytest

from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel


class _ConcreteModel(MetaSubsetTabModel):
    """A minimal concrete subset-tab Model, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model():
    """
    A concrete subset-tab Model to read and write filters with.

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

    def test_a_session_file_is_refused(self, model, tmp_path):
        """
        A saved session is a JSON object too, so the container check alone passed it.
        Measured before this guard existed: an entry whose value is falsy builds a
        query with no WHERE clause, validates cleanly and commits as
        ``<name>_assisted`` with no body, while a non-empty one raises out of the
        query builder into a modal - half the file as filters nobody wrote, half as
        dialogs.
        """
        path = tmp_path / "filters.json"
        path.write_text(
            json.dumps(
                {
                    "WaveletFilter_0": {"Wavelet": {"Type": "str", "Value": "db4"}},
                    "MetadataController": {},
                }
            )
        )

        with pytest.raises(ValueError, match="WaveletFilter_0"):
            model.load_filters(str(path))

    def test_a_null_filter_body_is_refused(self, model, tmp_path):
        """The shape that used to commit a filter with a name and nothing in it."""
        path = tmp_path / "filters.json"
        path.write_text(json.dumps({"long": "dwell > 5", "empty": None}))

        with pytest.raises(ValueError, match="empty"):
            model.load_filters(str(path))

    def test_an_empty_filter_body_is_kept(self, model, tmp_path):
        """
        The add-filter dialog requires a name and not a body, so a file this
        application wrote can hold an empty string. Refusing it here would reject
        the application's own output.
        """
        path = tmp_path / "filters.json"
        path.write_text(json.dumps({"everything": ""}))

        assert model.load_filters(str(path)) == {"everything": ""}

    def test_a_file_that_is_not_json_raises(self, model, tmp_path):
        path = tmp_path / "filters.json"
        path.write_text("dwell > 5")

        with pytest.raises(ValueError):
            model.load_filters(str(path))

    def test_a_missing_file_raises(self, model, tmp_path):
        with pytest.raises(OSError):
            model.load_filters(str(tmp_path / "nothing_here.json"))
