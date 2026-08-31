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

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


from poriscope.constants import __VERSION__, VERSION_DATE

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = "Poriscope"
copyright = "2024, Kyle Briggs, Carolina González G."
author = "Kyle Briggs, Carolina González G."
release = __VERSION__
release_date = VERSION_DATE.strftime("%B %d, %Y")

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinx.ext.autodoc", "sphinx_tabs.tabs", "sphinx.ext.intersphinx"]

# PySide6 is deliberately NOT mocked here, and must not be added back.
#
# This file imports ``poriscope.constants`` above, which runs ``poriscope/__init__.py``
# and pulls in the real PySide6 long before autodoc can install its mock finder. Since
# ``sys.modules`` is consulted ahead of any meta-path finder, ``autodoc_mock_imports``
# was already inert on any machine where PySide6 imports cleanly - the docs have always
# been built against the real library.
#
# Where it was *not* inert it was actively harmful. On a box missing libEGL, PySide6.QtGui
# fails to import partway through ``poriscope.exposed``, leaving QtCore real and QtGui
# mocked; shiboken's import hook then calls ``inspect.getsource()`` on a Sphinx mock, whose
# ``__wrapped__`` chain never terminates, and every documented member raises
# "ValueError: wrapper loop when unwrapping PySide6.QtGui".
#
# Mocking PySide6 *completely* is not the alternative: only 44 of the 100 modules under
# ``poriscope/`` import under a total mock, because the ``functools.wraps`` and ``re``
# calls in ``utils/DocstringDecorator.py`` and ``utils/LogDecorator.py`` run against mock
# objects. Against the real library 99 of 100 import.
#
# The consequence is that a docs build needs PySide6 importable. Both docs workflows
# install libegl1/libgl1 for exactly this reason - see the "Install Qt native libs" step
# in .github/workflows/docs-check.yml and build_and_deploy_docs.yml.

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),  # for abc.ABC, abc.ABCMeta
    # qtforpython/ 301-redirects to qtforpython-6/; naming the real location
    # avoids a redirect notice on every build.
    "qt": (
        "https://doc.qt.io/qtforpython-6/",
        None,
    ),  # for PySide6.QtCore.QObject, etc.
}

# The docs are built with -W (see .github/workflows/docs-check.yml), so an
# unreachable inventory would otherwise fail CI on a transient network problem
# rather than on anything a contributor did. Cap the wait and let a failed
# fetch degrade to unresolved references instead of an error.
intersphinx_timeout = 10
suppress_warnings = ["intersphinx.external"]

templates_path = ["_templates"]
exclude_patterns: List[str] = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_context = {
    "release_date": release_date,
}
