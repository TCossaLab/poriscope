"""
Assert every shipped data plugin declares a self-consistent settings schema.

This is the plugin-wide half of the settings-schema check.
``tests/unit/utils/test_settings_schema.py`` tests the validator's rules against
hand-built schemas; this runs those rules over the real thing.

It is deliberately a separate file from ``test_plugin_compliance.py`` rather than an
addition to it, even though the two share a discovery step: that file belongs to another
developer, and keeping out of it is the point.
"""

from typing import Any, Dict, List, Type

import pytest

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.plugin_schemas import discover_plugin_classes, get_declared_schema
from poriscope.utils.settings_schema import validate_settings_schema

PLUGIN_CLASSES = sorted(discover_plugin_classes().items())


@pytest.mark.compliance
def test_plugins_were_discovered() -> None:
    """
    Guard against the sweep below silently passing because it found nothing to check.
    """
    assert PLUGIN_CLASSES, "no concrete data plugins were discovered"


@pytest.mark.compliance
@pytest.mark.parametrize(
    "plugin_cls",
    [cls for _name, cls in PLUGIN_CLASSES],
    ids=[n for n, _ in PLUGIN_CLASSES],
)
def test_declared_schema_is_retrievable(plugin_cls: Type[BaseDataPlugin]) -> None:
    """
    A plugin must be able to describe its settings before it has been configured.

    The GUI calls ``get_empty_settings()`` on a throwaway instance to build the settings
    dialog, so a plugin whose schema depends on state only a full ``__init__`` provides
    cannot be added through the UI at all.
    """
    schema = get_declared_schema(plugin_cls)
    assert isinstance(schema, dict)


@pytest.mark.compliance
@pytest.mark.parametrize(
    "plugin_cls",
    [cls for _name, cls in PLUGIN_CLASSES],
    ids=[n for n, _ in PLUGIN_CLASSES],
)
def test_declared_schema_is_self_consistent(plugin_cls: Type[BaseDataPlugin]) -> None:
    """
    Every declared parameter must be internally coherent.

    A contradiction here — a default whose Python type contradicts its declared ``Type``,
    a ``Min`` above its ``Max``, an ``Options`` list the default is not in — reaches the
    user as a ``TypeError`` or ``ValueError`` raised from inside ``BaseDataPlugin`` when
    they try to instantiate the plugin, with nothing pointing at the schema as the cause.
    """
    schema: Dict[str, Dict[str, Any]] = get_declared_schema(plugin_cls)
    problems: List[str] = validate_settings_schema(schema)
    assert not problems, "\n".join(
        [f"{plugin_cls.__name__} declares an inconsistent settings schema:"] + problems
    )
