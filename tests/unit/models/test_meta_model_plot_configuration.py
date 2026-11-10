"""
A tab's saved plot configuration: the file names its format and version, and is checked whole on reading.

``MetaModel.save_plot_configuration`` writes it and ``read_plot_configuration`` reads it back;
a file from an earlier version, another format, another tab, or not a plot configuration at
all is refused with the reason, before anything is replayed.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, override

import pytest

from poriscope.constants import __VERSION__
from poriscope.utils.MetaModel import (
    PLOT_CONFIGURATION_FORMAT,
    PLOT_CONFIGURATION_FORMAT_VERSION,
    MetaModel,
    PlotConfigurationRefused,
)

TAB = "MetadataController"

ENTRIES: List[Dict[str, Any]] = [
    {"action": "reset", "args": [], "kwargs": {"axis_type": "2d"}},
    {"action": "overlay_plot", "args": [], "kwargs": {"loader": "DB1", "bins": 20}},
]


class _ConcreteModel(MetaModel):
    """A minimal concrete MetaModel, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model() -> _ConcreteModel:
    return _ConcreteModel()


def _written(path: Path, content: Any) -> str:
    path.write_text(json.dumps(content), encoding="utf-8")
    return str(path)


def _file(**changes: Any) -> Dict[str, Any]:
    content: Dict[str, Any] = {
        "format": PLOT_CONFIGURATION_FORMAT,
        "format_version": PLOT_CONFIGURATION_FORMAT_VERSION,
        "poriscope_version": "2.1.0",
        "tab": TAB,
        "actions": ENTRIES,
    }
    content.update(changes)
    return content


def test_a_saved_configuration_reads_back_as_its_entries(
    model: _ConcreteModel, tmp_path: Path
) -> None:
    path = str(tmp_path / "plots.json")

    model.save_plot_configuration(path, TAB, ENTRIES)

    assert model.read_plot_configuration(path, TAB) == ENTRIES


def test_the_file_names_its_format_version_writer_and_tab_first(
    model: _ConcreteModel, tmp_path: Path
) -> None:
    path = tmp_path / "plots.json"

    model.save_plot_configuration(str(path), TAB, ENTRIES)

    content = json.loads(path.read_text())
    assert list(content) == [
        "format",
        "format_version",
        "poriscope_version",
        "tab",
        "actions",
    ]
    assert content["format"] == "poriscope.plot_configuration"
    assert content["format_version"] == 1
    assert content["poriscope_version"] == __VERSION__
    assert content["tab"] == TAB
    assert content["actions"] == ENTRIES


def test_a_failed_save_leaves_the_earlier_file(
    model: _ConcreteModel, tmp_path: Path
) -> None:
    path = str(tmp_path / "plots.json")
    model.save_plot_configuration(path, TAB, ENTRIES)
    before = Path(path).read_text()

    with pytest.raises(TypeError):
        model.save_plot_configuration(
            path, TAB, [{"action": "x", "args": [], "kwargs": {"bad": object()}}]
        )

    assert Path(path).read_text() == before


def test_unknown_keys_are_ignored(model: _ConcreteModel, tmp_path: Path) -> None:
    path = _written(tmp_path / "plots.json", _file(note="added later"))

    assert model.read_plot_configuration(path, TAB) == ENTRIES


#: An overlay and its reset as Poriscope 2.0.2's Save Plot Configuration saved them.
SAVED_BY_2_0 = {
    "0": {"function": "_reset_actions", "args": [], "kwargs": {}},
    "1": {
        "function": "_overlay_plot",
        "args": [{"db_loader": "DB1", "plot_type": "Histogram"}],
        "kwargs": {},
    },
}

#: As develop saved it after actions got declared names, before values were saved by name.
SAVED_BEFORE_NAMED_VALUES = {
    "0": {"action": "reset", "args": [], "kwargs": {"axis_type": "2d"}},
    "1": {"action": "overlay_plot", "args": [{"db_loader": "DB1"}], "kwargs": {}},
}

#: As develop saved it once values were named, before the file named its format.
SAVED_WITHOUT_A_FORMAT = {
    "0": {"action": "reset", "args": [], "kwargs": {"axis_type": "2d"}},
    "1": {"action": "overlay_plot", "args": [], "kwargs": {"loader": "DB1"}},
}

EARLIER_OR_FOREIGN = (
    "it was saved by an earlier version of Poriscope, or is not a plot configuration"
)


@pytest.mark.parametrize(
    "content",
    [
        SAVED_BY_2_0,
        SAVED_BEFORE_NAMED_VALUES,
        SAVED_WITHOUT_A_FORMAT,
        [ENTRIES],
        "text",
        _file(format="poriscope.something_else"),
        {"format_version": 2, "plugins": [], "tabs": {}, "last_tab": ""},
    ],
    ids=[
        "2.0",
        "before-named-values",
        "no-format",
        "a-list",
        "a-string",
        "another-format",
        "a-session",
    ],
)
def test_an_earlier_or_foreign_file_is_refused(
    model: _ConcreteModel, tmp_path: Path, content: Any
) -> None:
    path = _written(tmp_path / "old.json", content)

    with pytest.raises(PlotConfigurationRefused) as refused:
        model.read_plot_configuration(path, TAB)

    assert refused.value.reason == EARLIER_OR_FOREIGN
    assert refused.value.earlier


def test_another_format_version_is_refused_naming_the_writer(
    model: _ConcreteModel, tmp_path: Path
) -> None:
    path = _written(
        tmp_path / "later.json",
        _file(format_version=2, poriscope_version="2.3.0"),
    )

    with pytest.raises(PlotConfigurationRefused) as refused:
        model.read_plot_configuration(path, TAB)

    assert refused.value.reason == (
        "it was saved by Poriscope 2.3.0 in a plot configuration format this version "
        "does not read (format 2)"
    )


def test_another_tabs_configuration_is_refused(
    model: _ConcreteModel, tmp_path: Path
) -> None:
    path = _written(tmp_path / "protein.json", _file(tab="ProteinController"))

    with pytest.raises(PlotConfigurationRefused) as refused:
        model.read_plot_configuration(path, TAB)

    assert refused.value.reason == "it holds the plot configuration of ProteinController"
    assert not refused.value.earlier


@pytest.mark.parametrize("actions", [{"0": ENTRIES[0]}, [ENTRIES[0], "text"]])
def test_actions_that_are_not_a_list_of_entries_are_refused(
    model: _ConcreteModel, tmp_path: Path, actions: Any
) -> None:
    path = _written(tmp_path / "broken.json", _file(actions=actions))

    with pytest.raises(PlotConfigurationRefused) as refused:
        model.read_plot_configuration(path, TAB)

    assert refused.value.reason == "it does not hold a plot configuration"


def test_a_file_that_is_not_json_raises_value_error(
    model: _ConcreteModel, tmp_path: Path
) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError):
        model.read_plot_configuration(str(path), TAB)


def test_a_missing_file_raises_os_error(model: _ConcreteModel, tmp_path: Path) -> None:
    with pytest.raises(OSError):
        model.read_plot_configuration(str(tmp_path / "missing.json"), TAB)
