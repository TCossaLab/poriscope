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
# Alejandra Carolina González González

from typing import Any, Dict, List, Set

#: Keys :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.get_empty_settings`'s
#: docstring documents as part of a parameter entry.
DOCUMENTED_KEYS: Set[str] = {"Type", "Value", "Options", "Min", "Max"}

#: Consumed as real data by at least one plugin (``SQLiteEventWriter`` and
#: ``SQLiteDBWriter`` both read ``base_settings["Voltage"]["Units"]`` when writing
#: channel metadata) but declared in neither the ``get_empty_settings()`` docstring
#: contract nor :py:class:`~poriscope.utils.BaseDataPlugin.Setting`. Tolerated here
#: rather than rejected, since the fix belongs to that contract, not to the plugins
#: already relying on it - see ``DECISIONS.md``.
UNDOCUMENTED_KEYS: Set[str] = {"Units"}

#: ``Options`` on these two reserved parameters holds a Qt file-dialog filter glob
#: (e.g. ``['Chimera Logfiles (*.log)']``), not a set of permitted values.
#: :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._validate_param_ranges`
#: exempts exactly these two keys from its ``Options`` membership check; this mirrors
#: that exemption so a file parameter's glob isn't flagged as mistyped ``Options``.
FILE_PARAM_KEYS: Set[str] = {"Input File", "Output File"}


def validate_settings_schema(schema: Dict[str, Any]) -> List[str]:
    """
    Check a ``get_empty_settings()`` schema for internal self-consistency.

    This is a static check: it never instantiates a plugin or supplies a value, and
    it looks only at the schema's own shape. It cannot tell you whether a plugin's
    *default* values would actually pass that plugin's validators - that requires a
    live instance and its own ``_validate_param_types``/``_validate_param_ranges``,
    which is deliberately not reimplemented here so this check cannot drift from the
    rules it would be duplicating. ``tests/unit/plugins/test_settings_schema.py``
    covers that half directly against each plugin.

    Per parameter, checks that:

    1. Both ``Type`` and ``Value`` are present. The
       :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.get_empty_settings`
       docstring calls both required, and
       :py:class:`~poriscope.utils.BaseDataPlugin.Setting` declares both
       non-optional. A missing ``Value`` is not merely undocumented: the base
       validator subscripts ``val["Value"]`` unguarded, so an unfilled parameter
       raises ``KeyError: 'Value'`` instead of a message naming the parameter.
    2. ``Type`` is actually a class, since both the validators and the settings
       dialog call it.
    3. No unrecognised keys are present, so a typo'd key (e.g. ``"Minimum"``)
       cannot silently disable a range check.
    4. ``Min`` does not exceed ``Max``, when both are given.
    5. Every entry in ``Options`` is an instance of the declared ``Type``. A file
       parameter (``Input File``/``Output File``) is exempt, since its ``Options``
       holds a dialog filter glob rather than a set of permitted values.

    :param schema: A settings schema, as returned by a plugin's
        ``get_empty_settings()``.
    :type schema: Dict[str, Any]
    :return: Human-readable problem descriptions, one per violation found. An empty
        list means the schema is self-consistent.
    :rtype: List[str]
    """
    errors: List[str] = []
    allowed = DOCUMENTED_KEYS | UNDOCUMENTED_KEYS

    for param, entry in schema.items():
        if not isinstance(entry, dict):
            errors.append(f"{param!r}: entry is {type(entry).__name__}, not a dict")
            continue

        for required in ("Type", "Value"):
            if required not in entry:
                errors.append(
                    f"{param!r}: missing required key {required!r} "
                    f"(has {sorted(entry)})"
                )

        if "Type" in entry and not isinstance(entry["Type"], type):
            errors.append(f"{param!r}: Type is {entry['Type']!r}, which is not a class")

        unknown = set(entry) - allowed
        if unknown:
            errors.append(f"{param!r}: unrecognised keys {sorted(unknown)}")

        minimum, maximum = entry.get("Min"), entry.get("Max")
        if minimum is not None and maximum is not None and minimum > maximum:
            errors.append(f"{param!r}: Min={minimum!r} exceeds Max={maximum!r}")

        # An option the declared Type cannot hold can never be selected, so the
        # parameter is unsatisfiable. File parameters need no explicit exemption
        # here: their Options hold Qt dialog filter globs, which are strings under
        # a str Type, so they pass this check on their own terms.
        declared = entry.get("Type")
        options = entry.get("Options")
        if options is not None and isinstance(declared, type):
            mistyped = [
                opt
                for opt in options
                if declared in (int, float, bool, str) and not isinstance(opt, declared)
            ]
            if mistyped:
                errors.append(
                    f"{param!r}: Options {mistyped!r} are not {declared.__name__}"
                )

    return errors
