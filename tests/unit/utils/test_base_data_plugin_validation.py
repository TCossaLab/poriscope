"""
Tests for ``BaseDataPlugin``'s two generic settings validators.

The per-family overrides of ``_validate_param_types`` are covered by
``test_meta_event_finder.py`` and friends; this file covers the base implementations
themselves, and in particular the three defects fixed on 2026-09-01:

* a settings entry with no ``Value`` key raised ``KeyError`` rather than being rejected
  with a message naming the missing parameter,
* ``Value: None`` beside a ``Min`` raised ``TypeError`` from the bound comparison, from a
  method whose contract promises ``ValueError``,
* the ``Options`` carve-out for file-dialog parameters covered ``Input File`` and
  ``Output File`` but not ``Folder``.
"""

from typing import Any, Dict, List, Optional

import pytest

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.settings_schema import FILE_DIALOG_PARAMS


class ConcretePlugin(BaseDataPlugin):
    """Minimal concrete plugin, so the base validators can be driven as they really run."""

    def _init(self) -> None:
        pass

    def _finalize_initialization(self) -> None:
        pass

    def _validate_settings(self, settings: dict) -> None:
        pass

    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        return {}

    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
        return ""

    def close_resources(self, channel: Optional[int] = None) -> None:
        pass

    def reset_channel(self, channel: Optional[int] = None) -> None:
        pass


@pytest.fixture
def plugin() -> ConcretePlugin:
    return ConcretePlugin()


class TestMissingValueIsReportedNotCrashed:
    def test_absent_value_key_does_not_raise_from_the_type_check(self, plugin):
        # get_empty_settings() output legitimately omits Value; subscripting it here
        # used to raise KeyError before the ranges check could report it properly.
        plugin._validate_param_types({"Input File": {"Type": str}})

    def test_absent_value_key_is_rejected_as_a_missing_value(self, plugin):
        with pytest.raises(ValueError, match="Input File requires a value"):
            plugin._validate_param_ranges({"Input File": {"Type": str}})

    def test_explicit_none_value_is_rejected_as_a_missing_value(self, plugin):
        with pytest.raises(ValueError, match="Threshold requires a value"):
            plugin._validate_param_ranges({"Threshold": {"Type": float, "Value": None}})

    def test_none_beside_a_min_reports_the_missing_value_not_a_type_error(self, plugin):
        # Previously "'<' not supported between instances of 'NoneType' and 'float'".
        with pytest.raises(ValueError, match="Threshold requires a value"):
            plugin._validate_param_ranges(
                {"Threshold": {"Type": float, "Value": None, "Min": 0.0}}
            )

    def test_none_is_not_reported_as_a_type_error(self, plugin):
        plugin._validate_param_types({"Threshold": {"Type": float, "Value": None}})

    def test_apply_settings_rejects_an_unset_schema_cleanly(self, plugin):
        # The whole point: get_empty_settings() output can now be handed straight to
        # apply_settings() and get a usable message instead of a KeyError.
        with pytest.raises(ValueError, match="Threshold requires a value"):
            plugin.apply_settings({"Threshold": {"Type": float, "Min": 0.0}})


class TestFileDialogParamsCarveOut:
    @pytest.mark.parametrize("name", sorted(FILE_DIALOG_PARAMS))
    def test_file_filters_are_not_treated_as_permissible_values(self, plugin, name):
        # Options here are file-dialog filters, so the chosen path is never "one of" them.
        plugin._validate_param_ranges(
            {
                name: {
                    "Type": str,
                    "Value": "C:/data/trace.abf",
                    "Options": ["ABF2 Files (*.abf)"],
                }
            }
        )

    def test_folder_is_among_the_carved_out_names(self):
        # The defect this closes: the runtime check omitted Folder while the GUI and the
        # schema validator both treat it as reserved.
        assert "Folder" in FILE_DIALOG_PARAMS

    def test_an_ordinary_parameter_still_checks_its_options(self, plugin):
        with pytest.raises(ValueError, match="must be one of"):
            plugin._validate_param_ranges(
                {"Byte Order": {"Type": str, "Value": "!", "Options": ["<", ">"]}}
            )


class TestUnchangedRejections:
    """The fixes must not widen what is accepted; these all failed before and still do."""

    def test_wrong_type_still_raises_type_error(self, plugin):
        with pytest.raises(TypeError, match="Threshold must have type"):
            plugin._validate_param_types(
                {"Threshold": {"Type": float, "Value": "five"}}
            )

    def test_value_below_min_still_raises(self, plugin):
        with pytest.raises(ValueError, match="must be larger than"):
            plugin._validate_param_ranges(
                {"Threshold": {"Type": float, "Value": -1.0, "Min": 0.0}}
            )

    def test_value_above_max_still_raises(self, plugin):
        with pytest.raises(ValueError, match="must be smaller than"):
            plugin._validate_param_ranges(
                {"Threshold": {"Type": float, "Value": 11.0, "Max": 10.0}}
            )


class TestAcceptedShapes:
    def test_a_fully_specified_parameter_passes_both_checks(self, plugin):
        settings = {"Threshold": {"Type": float, "Value": 5.0, "Min": 0.0, "Max": 10.0}}
        plugin._validate_param_types(settings)
        plugin._validate_param_ranges(settings)

    def test_a_dependency_entry_passes_both_checks(self, plugin):
        # DataPluginController rewrites a plugin dependency to Type None and the live
        # instance as its Value before calling apply_settings.
        settings = {"MetaReader": {"Type": None, "Value": object(), "Options": None}}
        plugin._validate_param_types(settings)
        plugin._validate_param_ranges(settings)

    def test_empty_settings_are_accepted(self, plugin):
        plugin._validate_param_types({})
        plugin._validate_param_ranges({})
