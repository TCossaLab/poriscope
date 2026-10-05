"""
Check that a plugin's shipped default values survive its own real validators.

``tests/unit/plugins/test_plugin_settings_schema.py`` checks that every plugin's
declared schema is internally self-consistent, via
:py:func:`poriscope.utils.settings_schema.validate_settings_schema` - a static check
against hand-built rules. This module checks something that static check cannot: that
the *same plugin's own* ``_validate_param_types``/``_validate_param_ranges`` actually
accept the defaults it ships. The two are complementary rather than redundant - a
schema can be internally self-consistent by the static rules and still be rejected by
a live instance if those rules and the plugin's own validator ever disagree, and only
driving the real instance would catch that.

Why this needed catching at all:

- ``test_plugin_compliance.py`` never calls the plugin.
- The per-plugin unit tests build instances via ``object.__new__`` and inject
  settings directly, so they never see ``get_empty_settings()``'s own output.
- ``tests/integration/flows/`` and ``tests/e2e/`` hand-write correct values over
  the defaults (``fset["Cutoff"]["Value"] = 200_000.0``), so a wrong default is
  overwritten before it reaches a validator.
- In the GUI, ``DictDialog.on_ok`` coerces every value through
  ``self.params[key]["Type"](...)``, which masks a mismatched default entirely.

That last point is why these checks matter despite the app working: the defaults
are only reachable un-coerced by a programmatic caller - a script, a headless
flow, or the settings-filling layer a behavioural conformance suite needs.
"""

from typing import Any, Dict, List, Set, Type

import pytest

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.plugin_schemas import discover_plugin_classes, get_declared_schema
from poriscope.utils.settings_schema import FILE_DIALOG_PARAMS

# Parameters whose value is a live plugin instance rather than a scalar. They are
# keyed by the name of the Meta* family they accept, and BaseDataPlugin's direct
# subclasses are exactly that set of families, so deriving it here keeps this in
# step with any new family without a list to maintain.
#
# These are excluded from the checks below: such a parameter's declared Type is str
# (it describes the pre-resolution dropdown key, not the resolved value), while the
# family validators - e.g. MetaEventFinder._validate_param_types - require an object
# inheriting the Meta* base. No standalone schema can satisfy both, so there is
# nothing self-consistent to assert.
PLUGIN_DEPENDENCY_KEYS: Set[str] = {
    cls.__name__ for cls in BaseDataPlugin.__subclasses__()
}

PLUGIN_CLASSES = sorted(discover_plugin_classes().items())

plugin_cases = pytest.mark.parametrize(
    "plugin_cls",
    [cls for _name, cls in PLUGIN_CLASSES],
    ids=[name for name, _cls in PLUGIN_CLASSES],
)


@pytest.mark.compliance
@plugin_cases
def test_settings_defaults_pass_own_validators(
    plugin_cls: Type[BaseDataPlugin],
) -> None:
    """
    Any default a plugin ships must satisfy that plugin's own validators.

    Only parameters carrying a usable default are checked. Three encodings mean
    "the caller must supply this", and all three are skipped here: the ``Value``
    key omitted, ``Value`` explicitly None, and - for plugin-dependency
    parameters - ``Value`` as an empty string.

    The real validators are invoked rather than reimplemented, so this stays
    correct if the rules in ``_validate_param_types`` /
    ``_validate_param_ranges`` change.

    :param plugin_cls: The plugin class under test.
    :type plugin_cls: Type[BaseDataPlugin]
    """
    plugin = plugin_cls()
    settings: Dict[str, Any] = get_declared_schema(plugin_cls)

    defaults = {
        param: entry
        for param, entry in settings.items()
        if isinstance(entry, dict)
        and param not in PLUGIN_DEPENDENCY_KEYS
        and entry.get("Value") is not None
    }
    if not defaults:
        pytest.skip(f"{plugin_cls.__name__} ships no default values to check")

    errors: List[str] = []

    try:
        plugin._validate_param_types(defaults)
    except TypeError as exc:
        offenders = [
            f"{param!r}: Type={entry['Type'].__name__} "
            f"but default Value={entry['Value']!r} "
            f"({type(entry['Value']).__name__})"
            for param, entry in defaults.items()
            if isinstance(entry.get("Type"), type)
            and entry["Type"] in (int, float, bool, str)
            and not isinstance(entry["Value"], entry["Type"])
        ]
        errors.append(f"_validate_param_types rejected its own defaults: {exc}")
        errors.extend(offenders)

    try:
        plugin._validate_param_ranges(defaults)
    except ValueError as exc:
        errors.append(f"_validate_param_ranges rejected its own defaults: {exc}")

    for param, entry in defaults.items():
        options = entry.get("Options")
        if (
            options is not None
            and param not in FILE_DIALOG_PARAMS
            and entry["Value"] not in options
        ):
            errors.append(
                f"{param!r}: default Value={entry['Value']!r} "
                f"is not among Options={options!r}"
            )

    assert not errors, f"{plugin_cls.__name__} defaults:\n  " + "\n  ".join(errors)
