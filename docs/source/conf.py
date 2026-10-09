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

import logging
import os
import sys
from typing import Dict, List, Optional

from docutils import nodes
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.ext.intersphinx import missing_reference

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
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "sklearn": ("https://scikit-learn.org/stable/", None),
}

# An inventory lists a library's public names in full. Our docstrings name types by
# their import aliases (``np.ndarray``, ``npt.NDArray``, ``pd.DataFrame``) or bare
# (``QWidget``, ``Axes``), and autodoc writes some real types under the private module
# that defines them (``pandas.core.frame.DataFrame``), so none of these is found as
# written. _resolve_third_party retries each under its public name.
_PREFIX_ALIASES: Dict[str, str] = {
    "np.": "numpy.",
    "npt.": "numpy.typing.",
    "pd.": "pandas.",
}
_NAME_ALIASES: Dict[str, str] = {
    "NDArray": "numpy.typing.NDArray",
    "Axes": "matplotlib.axes.Axes",
    "Axes3D": "mpl_toolkits.mplot3d.axes3d.Axes3D",
    "GaussianMixture": "sklearn.mixture.GaussianMixture",
    "Path": "pathlib.Path",
    "datetime": "datetime.datetime",
    "QComboBox": "PySide6.QtWidgets.QComboBox",
    "QLabel": "PySide6.QtWidgets.QLabel",
    "QPushButton": "PySide6.QtWidgets.QPushButton",
    "QToolButton": "PySide6.QtWidgets.QToolButton",
    "QWidget": "PySide6.QtWidgets.QWidget",
    "pandas.core.frame.DataFrame": "pandas.DataFrame",
    "matplotlib.axes._axes.Axes": "matplotlib.axes.Axes",
    "sklearn.mixture._gaussian_mixture.GaussianMixture": "sklearn.mixture.GaussianMixture",
}

# Names no inventory can link: our own type alias and TypeVar, a numpy-internal TypeVar
# autodoc reaches through numpy's annotations, and the PySide6 package, which Qt for
# Python's inventory does not list as a module. They only matter once nitpicky is on.
nitpick_ignore = [
    ("py:class", "Numeric"),
    ("py:class", "F"),
    ("py:class", "poriscope.utils.LogDecorator.F"),
    ("py:class", "poriscope.utils.SerializeDecorator.F"),
    ("py:class", "numpy._typing._array_like._ScalarType_co"),
    ("py:mod", "PySide6"),
]

# The docs are built with -W (see .github/workflows/docs-check.yml and the
# post-merge hook), so an unreachable inventory would fail the build on a transient
# network problem rather than on anything a contributor did. Cap the wait, and let a
# failed fetch degrade to unlinked type names: setup() downgrades that one warning to
# an info line. suppress_warnings cannot do it - Sphinx 8 emits it with no type.
intersphinx_timeout = 10

templates_path = ["_templates"]
exclude_patterns: List[str] = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_context = {
    "release_date": release_date,
}


def _public_name(target: str) -> str:
    """
    Return the name an inventory lists for a type our docs write another way.

    :param target: the reference target as written
    :type target: str
    :return: the full public name, or the target unchanged
    :rtype: str
    """
    if target in _NAME_ALIASES:
        return _NAME_ALIASES[target]
    for alias, full in _PREFIX_ALIASES.items():
        if target.startswith(alias):
            return full + target[len(alias) :]
    return target


def _resolve_third_party(
    app: Sphinx, env: BuildEnvironment, node: pending_xref, contnode: nodes.TextElement
) -> Optional[nodes.reference]:
    """
    Link a Python reference intersphinx missed, under its public name and any object type.

    Intersphinx has already tried the reference exactly as written. This retries it by
    its public name, then as any object type, since numpy lists its scalar types
    (``numpy.float64``) as attributes and ``numpy.typing.NDArray`` as data, while our
    docstrings name them as classes.

    :param app: the Sphinx application
    :type app: Sphinx
    :param env: the build environment
    :type env: BuildEnvironment
    :param node: the unresolved reference
    :type node: pending_xref
    :param contnode: the reference's rendered text
    :type contnode: nodes.TextElement
    :return: the resolved reference, or None to leave it unresolved
    :rtype: Optional[nodes.reference]
    """
    if node.get("refdomain") != "py":
        return None
    target = node["reftarget"]
    public = _public_name(target)
    for reftype in (node["reftype"], "obj"):
        if public == target and reftype == node["reftype"]:
            continue
        retry = node.deepcopy()
        retry["reftarget"] = public
        retry["reftype"] = reftype
        resolved = missing_reference(app, env, retry, contnode)
        if resolved is not None:
            return resolved
    return None


class _UnreachableInventoryIsInfo(logging.Filter):
    """Report an inventory that could not be downloaded as information, not a warning."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Downgrade the unreachable-inventory warning; pass every other record unchanged.

        :param record: a record from Sphinx's intersphinx logger
        :type record: logging.LogRecord
        :return: True, so the record is still logged
        :rtype: bool
        """
        if record.levelno == logging.WARNING and record.getMessage().startswith(
            "failed to reach any of the inventories"
        ):
            record.levelno = logging.INFO
            record.levelname = "INFO"
        return True


def setup(app: Sphinx) -> None:
    """
    Register the third-party reference resolver, and keep an unreachable inventory from failing a -W build.

    :param app: the Sphinx application
    :type app: Sphinx
    """
    app.connect("missing-reference", _resolve_third_party)
    logging.getLogger("sphinx.sphinx.ext.intersphinx").addFilter(
        _UnreachableInventoryIsInfo()
    )
