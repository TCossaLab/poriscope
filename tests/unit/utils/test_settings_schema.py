"""
Unit tests for :func:`poriscope.utils.settings_schema.validate_settings_schema`.

Each rule gets a schema that violates only that rule, so a failure names the rule. The
"must not flag" cases at the bottom are the shapes real plugins ship today and which an
over-eager validator would report: a missing ``Value``, file-dialog ``Options``, an
explicit ``Options: None``, and the undocumented-but-legitimate ``Units`` key.
"""

from typing import Any, Dict, List

from poriscope.utils.settings_schema import validate_settings_schema


def _only(problems: List[str]) -> str:
    """Assert exactly one problem was reported and return it."""
    assert len(problems) == 1, f"expected exactly one problem, got {problems}"
    return problems[0]


class TestCleanSchemas:
    def test_empty_schema_is_clean(self):
        assert validate_settings_schema({}) == []

    def test_fully_populated_entry_is_clean(self):
        schema: Dict[str, Dict[str, Any]] = {
            "Threshold": {
                "Type": float,
                "Value": 5.0,
                "Options": None,
                "Min": 0.0,
                "Max": 10.0,
                "Units": "pA",
            }
        }
        assert validate_settings_schema(schema) == []

    def test_categorical_entry_is_clean(self):
        schema = {
            "Byte Order": {"Type": str, "Value": "<", "Options": ["<", ">"]},
        }
        assert validate_settings_schema(schema) == []


class TestEntryShape:
    def test_entry_must_be_a_dict(self):
        problem = _only(validate_settings_schema({"Threshold": 5.0}))  # type: ignore[dict-item]
        assert "must be a dict" in problem

    def test_missing_type_is_reported(self):
        problem = _only(validate_settings_schema({"Threshold": {"Value": 5.0}}))
        assert "missing required key 'Type'" in problem

    def test_type_must_be_a_type(self):
        problem = _only(validate_settings_schema({"Threshold": {"Type": "float"}}))
        assert "'Type' must be a type" in problem

    def test_unknown_key_is_reported(self):
        # The typo this catches: "Mn" silently disables the bound it was meant to set.
        problem = _only(
            validate_settings_schema({"Threshold": {"Type": float, "Mn": 0.0}})
        )
        assert "unknown key 'Mn'" in problem


class TestValueType:
    def test_int_value_under_float_type_is_reported(self):
        # _validate_param_types is strict at runtime: isinstance(500, float) is False.
        problem = _only(
            validate_settings_schema({"Min Height": {"Type": float, "Value": 500}})
        )
        assert "is a int" in problem and "'Type' is float" in problem

    def test_str_value_under_int_type_is_reported(self):
        problem = _only(
            validate_settings_schema({"Header Bytes": {"Type": int, "Value": "0"}})
        )
        assert "'Type' is int" in problem

    def test_bool_value_under_int_type_is_reported(self):
        # isinstance(True, int) is True, so this needs its own guard.
        problem = _only(
            validate_settings_schema({"Header Bytes": {"Type": int, "Value": True}})
        )
        assert "is a bool" in problem

    def test_bool_value_under_bool_type_is_clean(self):
        assert validate_settings_schema({"Invert": {"Type": bool, "Value": True}}) == []

    def test_non_primitive_type_is_not_checked(self):
        schema = {"MetaReader": {"Type": object, "Value": "my reader"}}
        assert validate_settings_schema(schema) == []


class TestBounds:
    def test_min_greater_than_max_is_reported(self):
        problem = _only(
            validate_settings_schema(
                {"Width": {"Type": float, "Min": 10.0, "Max": 1.0}}
            )
        )
        assert "'Min' 10.0 is greater than 'Max' 1.0" in problem

    def test_min_equal_to_max_is_clean(self):
        schema = {"Width": {"Type": float, "Value": 1.0, "Min": 1.0, "Max": 1.0}}
        assert validate_settings_schema(schema) == []

    def test_default_below_its_own_min_is_reported(self):
        problem = _only(
            validate_settings_schema(
                {"Width": {"Type": float, "Value": -1.0, "Min": 0.0}}
            )
        )
        assert "below its own 'Min'" in problem

    def test_default_above_its_own_max_is_reported(self):
        problem = _only(
            validate_settings_schema(
                {"Width": {"Type": float, "Value": 11.0, "Max": 10.0}}
            )
        )
        assert "above its own 'Max'" in problem

    def test_incomparable_bound_is_reported_not_raised(self):
        # The runtime equivalent raises "'<' not supported between instances of
        # 'NoneType' and 'float'" at the user; this reports it instead.
        problem = _only(
            validate_settings_schema(
                {"Width": {"Type": str, "Value": "wide", "Min": 0.0}}
            )
        )
        assert "cannot be compared to 'Min'" in problem


class TestOptions:
    def test_option_of_wrong_type_is_reported(self):
        problem = _only(
            validate_settings_schema(
                {"Data Bytes": {"Type": int, "Value": 8, "Options": [8, "4"]}}
            )
        )
        assert "option '4' is a str" in problem

    def test_value_not_among_options_is_reported(self):
        problem = _only(
            validate_settings_schema(
                {"Byte Order": {"Type": str, "Value": "!", "Options": ["<", ">"]}}
            )
        )
        assert "is not one of" in problem

    def test_empty_options_list_is_reported(self):
        problem = _only(
            validate_settings_schema({"Byte Order": {"Type": str, "Options": []}})
        )
        assert "empty list" in problem

    def test_options_must_be_a_list(self):
        problem = _only(
            validate_settings_schema({"Byte Order": {"Type": str, "Options": "<>"}})
        )
        assert "'Options' must be a list" in problem


class TestShapesThatMustNotBeFlagged:
    """Every case here is a shape a shipped plugin actually declares today."""

    def test_missing_value_is_not_a_problem(self):
        # 27 of 91 shipped entries omit Value entirely, the base classes included.
        assert validate_settings_schema({"Input File": {"Type": str}}) == []

    def test_explicit_none_value_is_not_a_problem(self):
        schema = {
            "Threshold": {"Type": float, "Value": None, "Min": 0.0, "Units": "pA"}
        }
        assert validate_settings_schema(schema) == []

    def test_file_dialog_options_are_not_treated_as_permissible_values(self):
        for name in ("Input File", "Output File", "Folder"):
            schema = {
                name: {
                    "Type": str,
                    "Value": "C:/data/trace.abf",
                    "Options": ["ABF2 Files (*.abf)"],
                }
            }
            assert validate_settings_schema(schema) == [], name

    def test_options_explicitly_none_is_not_a_problem(self):
        # What MetaEventFinder produces when standalone: no readers to offer.
        schema = {"MetaReader": {"Type": str, "Value": "", "Options": None}}
        assert validate_settings_schema(schema) == []

    def test_units_key_is_allowed(self):
        schema = {"Threshold": {"Type": float, "Value": 5.0, "Units": "pA"}}
        assert validate_settings_schema(schema) == []


class TestMultipleProblems:
    def test_problems_from_several_parameters_accumulate(self):
        schema = {
            "Good": {"Type": float, "Value": 1.0},
            "BadType": {"Type": float, "Value": 500},
            "BadBounds": {"Type": float, "Min": 10.0, "Max": 1.0},
        }
        problems = validate_settings_schema(schema)
        assert len(problems) == 2
        assert any(p.startswith("BadType:") for p in problems)
        assert any(p.startswith("BadBounds:") for p in problems)
