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

"""
What a restored session keeps of a tab's recorded actions.

A tab's live history keeps every entry, because Undo replays from the last reset and needs
what came before it. A restore needs only what the screen and the tab's results depend on
now: the latest run of each result, the latest view of each figure, the drawings added since
its last reset. :py:func:`build_kept_history` works that out from each action's declaration
(:py:class:`~poriscope.utils.LogDecorator.ActionDeclaration`, collected by
:py:func:`~poriscope.utils.MetaController.declarations_of`); it
reads no tab and changes nothing.
"""

import json
from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from poriscope.utils.LogDecorator import ActionDeclaration


def build_kept_history(
    entries: Sequence[Mapping[str, Any]],
    declarations: Mapping[str, ActionDeclaration],
) -> List[Dict[str, Any]]:
    """
    The entries of a tab's history that a restore replays, in recorded order.

    Read newest first, an entry is dropped when something after it makes it irrelevant:

    - a ``result`` by a later result with the same key (the plugin and channel);
    - a ``reset`` by a later reset of its figure;
    - a ``view`` by a later view or reset of its figure, or by a later run of the result
      it was drawn from (its ``depends_on`` values equal that result's key). A dropped view
      still clears its figure, so the view before it is not brought back;
    - an ``additive`` drawing by a later reset or view of its figure.

    An entry this cannot read - no declared action, or values saved by position - is
    kept, so replay can report it.

    :param entries: the tab's recorded entries, oldest first
    :type entries: Sequence[Mapping[str, Any]]
    :param declarations: declared action name -> its declaration, for this tab
    :type declarations: Mapping[str, ActionDeclaration]
    :return: copies of the kept entries, oldest first
    :rtype: List[Dict[str, Any]]
    """
    later_results: Set[Tuple[str, ...]] = set()
    later_resets: Set[str] = set()
    cleared: Set[str] = set()
    kept: List[Mapping[str, Any]] = []
    for entry in reversed(entries):
        declaration, kwargs = _readable(entry, declarations)
        if declaration is None:
            kept.append(entry)
            continue
        if declaration.kind == "result":
            key = _values(kwargs, declaration.key)
            if key not in later_results:
                kept.append(entry)
            later_results.add(key)
            continue
        figure = declaration.figure or str(kwargs[declaration.figure_from])
        if declaration.kind == "reset":
            if figure not in later_resets:
                kept.append(entry)
            later_resets.add(figure)
            cleared.add(figure)
        elif declaration.kind == "view":
            replaced = bool(declaration.depends_on) and (
                _values(kwargs, declaration.depends_on) in later_results
            )
            if figure not in cleared and not replaced:
                kept.append(entry)
            cleared.add(figure)
        elif figure not in cleared:
            kept.append(entry)
    return [dict(deepcopy(entry)) for entry in reversed(kept)]


def _readable(
    entry: Mapping[str, Any], declarations: Mapping[str, ActionDeclaration]
) -> Tuple[Optional[ActionDeclaration], Mapping[str, Any]]:
    """
    An entry's declaration and saved values, or no declaration if they cannot be read.

    :param entry: one recorded entry
    :type entry: Mapping[str, Any]
    :param declarations: declared action name -> its declaration
    :type declarations: Mapping[str, ActionDeclaration]
    :return: the declaration, or None, and the entry's keyword values
    :rtype: Tuple[Optional[ActionDeclaration], Mapping[str, Any]]
    """
    name = entry.get("action") if isinstance(entry, Mapping) else None
    declaration = declarations.get(name) if isinstance(name, str) else None
    kwargs = entry.get("kwargs") if declaration is not None else None
    if declaration is None or not isinstance(kwargs, Mapping) or entry.get("args"):
        return None, {}
    needed = (
        declaration.key
        + declaration.depends_on
        + ((declaration.figure_from,) if declaration.figure_from else ())
    )
    if any(parameter not in kwargs for parameter in needed):
        return None, {}
    return declaration, kwargs


def _values(kwargs: Mapping[str, Any], names: Tuple[str, ...]) -> Tuple[str, ...]:
    """
    The saved values of these parameters, comparable whether read live or from a file.

    :param kwargs: an entry's keyword values
    :type kwargs: Mapping[str, Any]
    :param names: the parameters to read
    :type names: Tuple[str, ...]
    :return: each value as JSON text
    :rtype: Tuple[str, ...]
    """
    return tuple(json.dumps(kwargs[name], sort_keys=True) for name in names)
