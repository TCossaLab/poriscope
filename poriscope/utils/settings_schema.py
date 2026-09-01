# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs

from typing import Any, Dict, List

#: Keys a settings-schema entry is allowed to carry.
#:
#: ``Type``, ``Value``, ``Options``, ``Min`` and ``Max`` are the five documented by
#: :meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.get_empty_settings`.
#: ``Units`` is not in that docstring but is used by most shipped plugins to label
#: the GUI field, so it is legitimate rather than a typo.
ALLOWED_KEYS = frozenset({"Type", "Value", "Options", "Min", "Max", "Units"})

#: Parameter names whose ``Options`` list holds file-dialog filters
#: (``"ABF2 Files (*.abf)"``) rather than permissible values, so a ``Value`` is not
#: expected to appear in it. ``BaseDataPlugin._validate_param_ranges`` carves out the
#: first two for the same reason; ``Folder`` is included here because
#: :class:`~poriscope.utils.MetaReader.MetaReader` documents all three as reserved and
#: ``DataPluginController`` special-cases it when pre-populating the settings dialog.
FILE_DIALOG_PARAMS = frozenset({"Input File", "Output File", "Folder"})

#: Types for which ``Value`` and ``Options`` entries can be checked against ``Type``.
#: These are the same four ``_validate_param_types`` checks at runtime; anything else
#: (a ``Meta*`` class, say) is left alone.
PRIMITIVE_TYPES = (int, float, bool, str)


def validate_settings_schema(schema: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Check a plugin's settings schema for internal self-consistency.

    This is a static check of the schema a plugin *declares* — the dict returned by its
    ``get_empty_settings()`` — rather than of any particular settings dict a user
    supplies. ``BaseDataPlugin._validate_param_types`` and ``_validate_param_ranges``
    already do the latter, per instantiation. Nothing checked the schema itself, so a
    contradiction baked into a plugin (a ``Min`` above its ``Max``, an ``Options`` list
    whose entries do not match the declared ``Type``) only surfaced when a user tried to
    instantiate that plugin and got a ``TypeError`` from inside the base class.

    A missing ``Value`` key is **not** reported. The docstring on ``get_empty_settings``
    says ``Value`` is required, but the base implementations themselves omit it — a
    reader's schema is literally ``{"Input File": {"Type": str}}`` — and
    ``_validate_param_ranges`` reads it with ``.get("Value")``, treating absent as unset.
    Reporting it would flag roughly a third of every entry shipped today.

    :param schema: a settings schema as returned by ``get_empty_settings()``, keyed by
        parameter name, each entry carrying ``Type`` plus optionally ``Value``,
        ``Options``, ``Min``, ``Max`` and ``Units``
    :type schema: Dict[str, Dict[str, Any]]
    :return: one human-readable message per problem found, empty if the schema is clean
    :rtype: List[str]
    """
    problems: List[str] = []
    for name, entry in schema.items():
        if not isinstance(entry, dict):
            problems.append(f"{name}: entry must be a dict, got {type(entry).__name__}")
            continue
        problems.extend(_validate_entry(name, entry))
    return problems


def _validate_entry(name: str, entry: Dict[str, Any]) -> List[str]:
    """
    Check one parameter's entry in a settings schema.

    :param name: the parameter name this entry is keyed by, used in the messages
    :type name: str
    :param entry: the entry itself, already known to be a dict
    :type entry: Dict[str, Any]
    :return: one human-readable message per problem found with this entry
    :rtype: List[str]
    """
    problems: List[str] = []

    for key in sorted(set(entry) - ALLOWED_KEYS):
        problems.append(
            f"{name}: unknown key {key!r}; expected one of {sorted(ALLOWED_KEYS)}"
        )

    if "Type" not in entry:
        problems.append(f"{name}: missing required key 'Type'")
        return problems

    declared = entry["Type"]
    if not isinstance(declared, type):
        problems.append(
            f"{name}: 'Type' must be a type, got {declared!r} "
            f"({type(declared).__name__})"
        )
        return problems

    value = entry.get("Value")
    problems.extend(_validate_value_type(name, declared, value))
    problems.extend(_validate_bounds(name, entry, value))
    problems.extend(_validate_options(name, declared, entry, value))
    return problems


def _validate_value_type(name: str, declared: type, value: Any) -> List[str]:
    """
    Check that a default ``Value`` matches the ``Type`` its entry declares.

    ``_validate_param_types`` uses a bare ``isinstance`` at runtime, so this is strict in
    the same way: an ``int`` default under a ``float`` declaration really does raise
    there, because ``isinstance(500, float)`` is False. ``bool`` is rejected for an
    ``int`` declaration despite ``isinstance(True, int)`` being True, since a checkbox and
    a number field are not interchangeable in the settings dialog.

    :param name: the parameter name, used in the messages
    :type name: str
    :param declared: the type the entry declares under ``Type``
    :type declared: type
    :param value: the entry's ``Value``, or None if absent or explicitly unset
    :type value: Any
    :return: one human-readable message per problem found, empty if clean
    :rtype: List[str]
    """
    if value is None or declared not in PRIMITIVE_TYPES:
        return []
    if declared is not bool and isinstance(value, bool):
        return [
            f"{name}: 'Value' is a bool ({value!r}) but 'Type' is {declared.__name__}"
        ]
    if not isinstance(value, declared):
        return [
            f"{name}: 'Value' {value!r} is a {type(value).__name__}, "
            f"but 'Type' is {declared.__name__}"
        ]
    return []


def _validate_bounds(name: str, entry: Dict[str, Any], value: Any) -> List[str]:
    """
    Check that ``Min`` and ``Max`` are ordered and that any default lies between them.

    Comparisons are wrapped because ``Min``/``Max`` are typed ``Any`` and a schema can
    pair bounds with a value they cannot be compared to. A ``TypeError`` from the
    comparison is itself a finding, and is a far better one than the
    ``'<' not supported between instances of 'NoneType' and 'float'`` a user gets today.

    :param name: the parameter name, used in the messages
    :type name: str
    :param entry: the parameter's entry
    :type entry: Dict[str, Any]
    :param value: the entry's ``Value``, or None if absent or explicitly unset
    :type value: Any
    :return: one human-readable message per problem found, empty if clean
    :rtype: List[str]
    """
    problems: List[str] = []
    minimum = entry.get("Min")
    maximum = entry.get("Max")

    for bound, label, ordering in (
        (minimum, "Min", "below"),
        (maximum, "Max", "above"),
    ):
        if bound is None or value is None:
            continue
        try:
            out_of_range = value < bound if label == "Min" else value > bound
        except TypeError as exc:
            problems.append(
                f"{name}: 'Value' {value!r} cannot be compared to '{label}' "
                f"{bound!r} ({exc})"
            )
            continue
        if out_of_range:
            problems.append(
                f"{name}: default 'Value' {value!r} is {ordering} its own "
                f"'{label}' of {bound!r}"
            )

    if minimum is not None and maximum is not None:
        try:
            inverted = minimum > maximum
        except TypeError as exc:
            problems.append(
                f"{name}: 'Min' {minimum!r} cannot be compared to 'Max' "
                f"{maximum!r} ({exc})"
            )
        else:
            if inverted:
                problems.append(
                    f"{name}: 'Min' {minimum!r} is greater than 'Max' {maximum!r}"
                )

    return problems


def _validate_options(
    name: str, declared: type, entry: Dict[str, Any], value: Any
) -> List[str]:
    """
    Check an ``Options`` list against the entry's ``Type`` and default ``Value``.

    The ``Value in Options`` check is skipped for the reserved file-dialog parameter
    names, whose ``Options`` are file filters rather than permissible values;
    ``_validate_param_ranges`` skips two of the three for the same reason.

    :param name: the parameter name, used in the messages and to spot a reserved name
    :type name: str
    :param declared: the type the entry declares under ``Type``
    :type declared: type
    :param entry: the parameter's entry
    :type entry: Dict[str, Any]
    :param value: the entry's ``Value``, or None if absent or explicitly unset
    :type value: Any
    :return: one human-readable message per problem found, empty if clean
    :rtype: List[str]
    """
    if "Options" not in entry or entry["Options"] is None:
        return []

    options = entry["Options"]
    if not isinstance(options, list):
        return [f"{name}: 'Options' must be a list, got {type(options).__name__}"]
    if not options:
        return [f"{name}: 'Options' is an empty list; omit it or set it to None"]

    problems: List[str] = []
    if declared in PRIMITIVE_TYPES:
        for option in options:
            if declared is not bool and isinstance(option, bool):
                problems.append(
                    f"{name}: option {option!r} is a bool but 'Type' is "
                    f"{declared.__name__}"
                )
            elif not isinstance(option, declared):
                problems.append(
                    f"{name}: option {option!r} is a {type(option).__name__}, "
                    f"but 'Type' is {declared.__name__}"
                )

    if value is not None and name not in FILE_DIALOG_PARAMS and value not in options:
        problems.append(f"{name}: default 'Value' {value!r} is not one of {options}")

    return problems
