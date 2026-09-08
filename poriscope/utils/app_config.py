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
# Alejandra Carolina González González

import logging
from pathlib import Path
from typing import Any, Dict, Union


def default_app_config(user_plugin_folder: Union[str, Path]) -> Dict[str, Any]:
    """
    Build a fresh copy of the application's default configuration.

    This is the single definition of what "default" means for the three keys
    stored in ``config/config.json``. It is used both when bootstrapping a new
    install and when the user resets settings, so the two cannot drift apart.

    It is a function rather than a module-level constant for two reasons: two of
    the three values are resolved at runtime, and a shared dict would be mutable
    in place by any caller that edited the config it was handed.

    Values are stored as ``str`` rather than ``Path`` because they round-trip
    through JSON, and a ``Path`` left in the dict fails the
    ``isinstance(value, str)`` check in ``BaseDataPlugin._validate_param_types``
    when it is used to pre-populate a plugin's Folder setting.

    :param user_plugin_folder: Location the app scans for user-supplied plugins.
    :type user_plugin_folder: Union[str, Path]

    :return: A new dict of default configuration values.
    :rtype: Dict[str, Any]
    """
    return {
        "Parent Folder": str(Path.home()),
        "User Plugin Folder": str(user_plugin_folder),
        "Log Level": logging.WARNING,
    }
