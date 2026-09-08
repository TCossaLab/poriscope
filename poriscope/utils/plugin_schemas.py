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

"""
Retrieve every data plugin's declared settings schema without instantiating it.

This is kept separate from :mod:`poriscope.utils.settings_schema` on purpose. That
module is a pure function over a schema dict and imports nothing; importing *this* one
walks and executes every file under ``poriscope/plugins/``, which is a side effect no
caller should pay for just to validate a dict it already holds.
"""

import importlib
import inspect
import pkgutil
from typing import Any, Dict, Type

import poriscope.plugins as plugins_pkg
from poriscope.utils.BaseDataPlugin import BaseDataPlugin


def discover_plugin_classes() -> Dict[str, Type[BaseDataPlugin]]:
    """
    Import every module under ``poriscope.plugins`` and collect the concrete plugins.

    A class counts as a plugin when it is named for the module that defines it, subclasses
    :class:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin`, and is not abstract — the
    same rule ``MainModel.populate_available_plugins`` applies at runtime.

    :return: concrete plugin classes keyed by class name, which is also their filename
    :rtype: Dict[str, Type[BaseDataPlugin]]
    """
    discovered: Dict[str, Type[BaseDataPlugin]] = {}
    for _finder, modname, _ispkg in pkgutil.walk_packages(
        plugins_pkg.__path__, prefix=f"{plugins_pkg.__name__}."
    ):
        module = importlib.import_module(modname)
        name = modname.rsplit(".", 1)[-1]
        candidate = getattr(module, name, None)
        if (
            inspect.isclass(candidate)
            and issubclass(candidate, BaseDataPlugin)
            and not inspect.isabstract(candidate)
        ):
            discovered[name] = candidate
    return discovered


def get_declared_schema(plugin_cls: Type[BaseDataPlugin]) -> Dict[str, Dict[str, Any]]:
    """
    Get a plugin's ``get_empty_settings()`` schema without running its constructor.

    ``__init__`` requires a valid settings dict, which is the very thing being checked, so
    the instance is built with ``__new__`` instead. ``_init()`` is then called because
    ``__new__`` alone is not always enough: ``WaveletFilter.get_empty_settings`` reads
    ``self.wavelist``, which only ``_init`` sets. Every plugin shipped today tolerates
    ``_init()`` on a bare instance, but a future one might not, so a failure there is
    allowed through to be reported by the caller rather than masked here.

    ``standalone=True`` is passed because several bases raise ``KeyError`` when no
    dependency plugins exist unless it is set — an event finder refuses to describe itself
    without a reader, for instance.

    :param plugin_cls: the concrete plugin class to interrogate
    :type plugin_cls: Type[BaseDataPlugin]
    :return: the settings schema the plugin declares
    :rtype: Dict[str, Dict[str, Any]]
    """
    instance = plugin_cls.__new__(plugin_cls)
    instance._init()
    return plugin_cls.get_empty_settings(instance, None, True)
