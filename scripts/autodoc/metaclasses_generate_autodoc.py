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

import ast
import os
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Resolve base paths
SCRIPT_DIR = Path(__file__).resolve().parent

# Folder where plugin source code lives
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # up from scripts/autodoc

#: Where the Meta* base classes live; read to find the published private contract.
UTILS_DIR = PROJECT_ROOT / "poriscope" / "utils"
FOLDER_ORIGIN = PROJECT_ROOT / "poriscope" / "utils"

# Where generated .rst documentation should be written

OUTPUT_DIR = PROJECT_ROOT / "docs" / "source" / "autodoc" / "metaclasses"

# This directory is generated output, gitignored, and owned entirely by this
# script - every file in it is rewritten on every run. Clearing it first is what
# prunes the .rst for a module that no longer exists: writing is unconditional,
# so a stale file would otherwise survive forever, dropped from the index below
# but still on disk and still autodoc-ing a module that is gone, which fails
# sphinx-build -W. CI never saw this because it builds from a clean checkout.
shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_RST = OUTPUT_DIR / "metaclasses_index.rst"
BASE_PACKAGE = "poriscope.utils"
toc_entries = []

# External base class mapping
EXTERNAL_BASES = {
    "ABC": "abc.ABC",
    "ABCMeta": "abc.ABCMeta",
    "QObject": "PySide6.QtCore.QObject",
    "QWidget": "PySide6.QtWidgets.QWidget",
}


def abstract_private_names() -> Set[str]:
    """
    Collect every private method name that some base class declares abstract.

    A leading underscore means "internal" almost everywhere, but not on the ``Meta*``
    bases: there it marks the methods a *subclass author* has to write, which is the
    published contract rather than an implementation detail. ``_apply_filter``,
    ``_map_data`` and ``_locate_sublevel_transitions`` are the plugin author's whole job.

    So the rule is by name rather than by decorator. The base declares
    ``@abstractmethod`` and a concrete plugin's override does not, but the override is
    the substance of that plugin's page - dropping it would gut exactly the page someone
    reads to learn how a shipped plugin works. Matching on the name keeps both ends.

    ``__init__`` is included for the same reason: it is public API however it is
    spelled, and its parameter documentation is published nowhere else.

    :return: the private method names that count as published contract
    :rtype: Set[str]
    """
    names: Set[str] = set()
    for source in UTILS_DIR.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for class_node in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for item in class_node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                if not item.name.startswith("_"):
                    continue
                if any(
                    isinstance(decorator, ast.Name) and decorator.id == "abstractmethod"
                    for decorator in item.decorator_list
                ):
                    names.add(item.name)
    # The constructor is public API however it is spelled. Its signature already
    # appears on the class line, but the ``:param:`` fields documenting what each
    # argument means live in its docstring and are published nowhere else.
    names.add("__init__")
    return names


def classify_method(method_node: ast.FunctionDef) -> Tuple[str, str]:
    is_private = method_node.name.startswith("_")
    is_abstract = any(
        isinstance(decorator, ast.Name) and decorator.id == "abstractmethod"
        for decorator in method_node.decorator_list
    )
    return (
        "private" if is_private else "public",
        "abstract" if is_abstract else "concrete",
    )


def is_property(method_node: ast.FunctionDef) -> bool:
    """
    Report whether a ``def`` is really a property.

    ``.. automethod::`` on a property makes Sphinx warn that the object "is not a
    callable object", and both docs workflows build with ``-W``, so one property
    documented as a method turns the docs job red. ``MetaSubsetTabView``'s
    ``_subset_controls`` did exactly that from the moment Step 3b added it.

    Only the bare ``@property`` form is recognised, which is every property under
    ``poriscope/utils/`` today; a setter is written ``@<name>.setter`` and is
    deliberately not documented separately.

    :param method_node: the function definition to classify
    :type method_node: ast.FunctionDef
    :return: True if the definition carries a ``@property`` decorator
    :rtype: bool
    """
    return any(
        isinstance(decorator, ast.Name) and decorator.id == "property"
        for decorator in method_node.decorator_list
    )


def parse_base_classes(base_nodes):
    bases = []
    for base in base_nodes:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            parts: List[str] = []
            while isinstance(base, ast.Attribute):
                parts.insert(0, base.attr)
                base = base.value
            if isinstance(base, ast.Name):
                parts.insert(0, base.id)
            bases.append(".".join(parts))
        elif hasattr(ast, "unparse"):
            bases.append(ast.unparse(base))
    return bases


# Loop through all Python files
for filename in os.listdir(FOLDER_ORIGIN):
    if not filename.endswith(".py") or filename.startswith("__"):
        continue

    filepath = os.path.join(FOLDER_ORIGIN, filename)
    module_name = filename[:-3]
    full_module_path = f"{BASE_PACKAGE}.{module_name}"

    # Parse the file's abstract syntax tree (AST)
    with open(filepath, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=filename)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            docstring = ast.get_docstring(node)
            if not docstring:
                print(f"Skipped {class_name} in {filename} (no docstring)")
                continue

            full_class_path = f"{full_module_path}.{class_name}"
            label = class_name
            title = class_name
            underline = "=" * len(title)
            rst_filename = f"{module_name.lower()}.rst"
            rst_path = os.path.join(OUTPUT_DIR, rst_filename)
            toc_entries.append(rst_filename[:-4])

            # Group methods

            methods: Dict[Tuple[str, str], List[str]] = {
                ("public", "abstract"): [],
                ("public", "concrete"): [],
                ("private", "abstract"): [],
                ("private", "concrete"): [],
            }
            properties: Set[str] = set()
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    visibility, abstractness = classify_method(item)
                    methods[(visibility, abstractness)].append(item.name)
                    if is_property(item):
                        properties.add(item.name)

            # Base class references
            base_classes = parse_base_classes(node.bases)
            base_refs = []
            for base in base_classes:
                if base in EXTERNAL_BASES:
                    base_refs.append(f":class:`~{EXTERNAL_BASES[base]}`")
                else:
                    ref_path = OUTPUT_DIR / f"{base.lower()}.rst"
                    if ref_path.exists():
                        base_refs.append(f":ref:`{base}`")
                    else:
                        base_refs.append(f":class:`~{BASE_PACKAGE}.{base}`")
            base_str = f"Bases: {', '.join(base_refs)}" if base_refs else ""

            # Init signature
            init_args = "()"
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    args = item.args.args[1:]  # skip 'self'
                    defaults = [None] * (
                        len(args) - len(item.args.defaults)
                    ) + item.args.defaults
                    arg_list = []
                    for arg, default in zip(args, defaults):
                        arg_str = arg.arg
                        if arg.annotation:
                            try:
                                annotation = ast.unparse(arg.annotation)
                                arg_str += f": {annotation}"
                            except Exception:
                                pass
                        if default is not None:
                            try:
                                default_val = ast.unparse(default)
                                arg_str += f" = {default_val}"
                            except Exception:
                                arg_str += " = ..."
                        arg_list.append(arg_str)
                    init_args = f"({', '.join(arg_list)})"
                    break

            # Write .rst file
            with open(rst_path, "w", encoding="utf-8") as f:
                f.write(f".. _{label}:\n\n{title}\n{underline}\n\n")
                f.write(f"**class {class_name}{init_args}**\n\n")
                if base_str:
                    f.write(f"{base_str}\n\n")
                f.write(f"{docstring}\n\n")

                for visibility in ["public", "private"]:
                    vis_title = (
                        "Public Methods"
                        if visibility == "public"
                        else "Private Methods"
                    )
                    f.write(f"{vis_title}\n{'-' * len(vis_title)}\n\n")
                    for abstractness in ["abstract", "concrete"]:
                        # A private concrete method is an internal helper, and
                        # publishing it buried the contract that matters. Private
                        # *abstract* methods stay: on these bases the underscore
                        # marks a subclass author's obligation, not a detail.
                        if (visibility, abstractness) == ("private", "concrete"):
                            continue
                        sub_title = (
                            "Abstract Methods"
                            if abstractness == "abstract"
                            else "Concrete Methods"
                        )
                        f.write(f"{sub_title}\n{'~' * len(sub_title)}\n\n")
                        if abstractness == "abstract":
                            f.write(
                                "These methods must be implemented by subclasses.\n\n"
                            )
                        key = (visibility, abstractness)
                        for method_name in sorted(methods[key]):
                            directive = (
                                "autoproperty"
                                if method_name in properties
                                else "automethod"
                            )
                            f.write(
                                f".. {directive}:: {full_class_path}.{method_name}\n"
                            )
                        if not methods[key]:
                            f.write("(none)\n")
                        f.write("\n")

# Write master index
with open(INDEX_RST, "w", encoding="utf-8") as f:
    f.write(
        """.. _metaclasses_index:

Abstract Base Classes
=======================

.. toctree::
   :maxdepth: 1

"""
    )
    for entry in sorted(toc_entries):
        f.write(f"   {entry}\n")

print("Generated individual .rst files and master TOC.")
