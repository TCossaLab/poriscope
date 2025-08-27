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
from pathlib import Path
from typing import Dict, List

SCRIPT_DIR = (
    Path(__file__).resolve().parent
)  # Always resolve paths relative to the script file
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Folder where plugin source code lives
FOLDER_ORIGIN = PROJECT_ROOT / "poriscope" / "plugins"

# Where generated .rst documentation should be written
OUTPUT_DIR = PROJECT_ROOT / "docs" / "source" / "autodoc" / "plugins"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Optional: generate .rst files for a single category like "filters"
ONLY_CATEGORY = (
    None  # Set to "filters" to restrict to just one, or leave as None for all
)

# Base package used for internal references
BASE_PACKAGE = "poriscope.plugins"

# Exclude specific class members from documentation
CATEGORY_EXCLUDE_MEMBERS = {
    "View": ["PaintDeviceMetric", "RenderFlag"],
    # (add more as needed)
}

# External base class mapping
EXTERNAL_BASES = {
    "ABC": "abc.ABC",
    "ABCMeta": "abc.ABCMeta",
    "QObject": "PySide6.QtCore.QObject",
    "QWidget": "PySide6.QtWidgets.QWidget",
}


def classify_method(method_node):
    return "private" if method_node.name.startswith("_") else "public"


def find_classes_and_nodes(py_file):
    """Return a list of (class_name, class_node) tuples."""
    with open(py_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=py_file.name)
    return [(node.name, node) for node in tree.body if isinstance(node, ast.ClassDef)]


def get_import_path(py_path, class_name):
    """Return the full import path for a class (e.g., plugins.filters.BesselFilter.BesselFilter)."""
    rel_path = py_path.relative_to(FOLDER_ORIGIN).with_suffix("")
    full_path = f"{BASE_PACKAGE}.{'.'.join(rel_path.parts)}.{class_name}"
    return full_path


def get_exclusions(class_name):
    """Return a list of members to exclude based on class name or suffix."""
    exclusions = []
    for key, members in CATEGORY_EXCLUDE_MEMBERS.items():
        if class_name == key or class_name.endswith(key):
            exclusions.extend(members)
    return exclusions


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


def get_init_signature(class_node):
    current_file_path = Path(__file__).resolve()
    return get_init_signature_with_inheritance(
        class_node, current_file_path, PROJECT_ROOT
    )


def format_function_signature(func_node):
    args = func_node.args.args[1:]  # skip 'self'
    defaults = func_node.args.defaults
    default_padding = [None] * (len(args) - len(defaults))
    full_defaults = default_padding + defaults

    arg_list = []
    for arg, default in zip(args, full_defaults):
        arg_str = arg.arg
        if arg.annotation:
            try:
                arg_str += f": {ast.unparse(arg.annotation)}"
            except Exception:
                pass
        if default is not None:
            try:
                arg_str += f" = {ast.unparse(default)}"
            except Exception:
                arg_str += " = ..."
        arg_list.append(arg_str)

    if func_node.args.vararg:
        arg_list.append(f"*{func_node.args.vararg.arg}")
    if func_node.args.kwarg:
        arg_list.append(f"**{func_node.args.kwarg.arg}")

    return f"({', '.join(arg_list)})"


def get_init_signature_with_inheritance(class_node, current_file_path, project_root):
    """Try to get __init__ signature from class or inherited base class"""
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            return format_function_signature(item)

    # If no __init__, try to follow the first base class
    if not class_node.bases:
        return "()"

    first_base = class_node.bases[0]
    if isinstance(first_base, ast.Name):
        base_name = first_base.id
    elif isinstance(first_base, ast.Attribute):
        parts: List[str] = []
        while isinstance(first_base, ast.Attribute):
            parts.insert(0, first_base.attr)
            first_base = first_base.value
        if isinstance(first_base, ast.Name):
            parts.insert(0, first_base.id)
        base_name = parts[-1]
    else:
        return "()"

    # Attempt to locate the base class source file
    possible_file = list(project_root.rglob(f"{base_name}.py"))
    for file_path in possible_file:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(file_path))
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == base_name:
                    return get_init_signature_with_inheritance(
                        node, file_path, project_root
                    )
        except Exception:
            continue

    return "()"


def write_class_rst(category_dir, class_node, import_path, class_name, exclusions=None):
    """Write a single .rst file for a given class."""
    exclusions = exclusions or []
    rst_file = category_dir / f"{class_name.lower()}.rst"
    docstring = ast.get_docstring(class_node) or ""

    # Extract method and property names
    methods: Dict[str, List[str]] = {"public": [], "private": []}
    properties: List[str] = []
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef):
            if any(
                isinstance(d, ast.Name) and d.id == "property"
                for d in item.decorator_list
            ):
                properties.append(item.name)
            else:
                visibility = classify_method(item)
                methods[visibility].append(item.name)

    # Extract __init__ signature
    init_args = get_init_signature(class_node)

    # Extract base classes
    base_classes = parse_base_classes(class_node.bases)
    base_refs = []
    for base in base_classes:
        if base in EXTERNAL_BASES:
            base_refs.append(f":class:`~{EXTERNAL_BASES[base]}`")
        elif (OUTPUT_DIR.parent / "metaclasses" / f"{base.lower()}.rst").exists():
            base_refs.append(f":ref:`{base}`")
        else:
            base_refs.append(f":class:`~{BASE_PACKAGE}.{base}`")

    with open(rst_file, "w", encoding="utf-8") as f:
        # Anchor and title
        f.write(f".. _{class_name}:\n\n")
        f.write(f"{class_name}\n{'=' * len(class_name)}\n\n")

        # Bold class signature
        f.write(f"**class {class_name}{init_args}**\n\n")

        # Base classes
        if base_refs:
            f.write(f"Bases: {', '.join(base_refs)}\n\n")

        # Docstring
        if docstring:
            f.write(f"{docstring}\n\n")

        # Public and Private methods
        for visibility in ["public", "private"]:
            title = "Public Methods" if visibility == "public" else "Private Methods"
            f.write(f"{title}\n{'-' * len(title)}\n\n")
            for method in sorted(methods[visibility]):
                f.write(f".. automethod:: {import_path}.{method}\n")
            if not methods[visibility]:
                f.write("(none)\n")
            f.write("\n")

        # Properties section
        if properties:
            f.write("Properties\n" + "-" * len("Properties") + "\n\n")
            for prop in sorted(properties):
                f.write(f".. autoattribute:: {import_path}.{prop}\n")
            f.write("\n")


def write_category_index(category_name, class_names, has_utils=False):
    """Write a category-level index .rst file with a toctree."""
    path = OUTPUT_DIR / category_name / f"{category_name.lower()}.rst"
    with open(path, "w") as f:
        title = category_name.replace("_", " ").title()
        f.write(
            f"""{title}
{'=' * len(title)}

.. toctree::
   :maxdepth: 1

"""
        )
        for cls in class_names:
            f.write(f"   {cls.lower()}\n")
        # Add utils only if needed
        if has_utils:
            f.write("   utils/utils_index\n")


def write_main_index(category_names):
    path = OUTPUT_DIR / "plugins_index.rst"
    with open(path, "w") as f:
        f.write(
            """.. _plugins_index:

Plugins
=======

.. toctree::
   :maxdepth: 1
   :caption: Contents:

"""
        )
        for category in sorted(set(name.split("/")[0] for name in category_names)):
            f.write(f"   {category}/{category}\n")


def write_utils_index(category_name, utils_classes):
    """Write utils_index.rst for each category that has a utils folder."""
    utils_dir = OUTPUT_DIR / category_name / "utils"
    index_path = utils_dir / "utils_index.rst"
    utils_dir.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w") as f:
        f.write(
            """Utils
=====

.. toctree::
   :maxdepth: 1

"""
        )
        for cls in utils_classes:
            f.write(f"   {cls.lower()}\n")


def main():
    plugin_root = FOLDER_ORIGIN
    all_categories = []

    for category_dir in plugin_root.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith("__"):
            continue

        category_name = category_dir.name
        if ONLY_CATEGORY and category_name != ONLY_CATEGORY:
            continue

        output_dir = OUTPUT_DIR / category_name
        output_dir.mkdir(parents=True, exist_ok=True)

        class_names = []

        for py_file in category_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            for class_name, class_node in find_classes_and_nodes(py_file):
                import_path = get_import_path(py_file, class_name)
                exclusions = get_exclusions(class_name)
                write_class_rst(
                    output_dir, class_node, import_path, class_name, exclusions
                )
                class_names.append(class_name)
        # Process utils/ subfolder if it exists
        utils_dir = category_dir / "utils"
        utils_class_names = []
        if utils_dir.exists():
            # Process top-level .py files in the category
            for py_file in utils_dir.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                for class_name, class_node in find_classes_and_nodes(py_file):
                    import_path = get_import_path(py_file, class_name)
                    exclusions = get_exclusions(class_name)
                    utils_output = OUTPUT_DIR / category_name / "utils"
                    utils_output.mkdir(parents=True, exist_ok=True)
                    write_class_rst(
                        utils_output, class_node, import_path, class_name, exclusions
                    )
                    utils_class_names.append(class_name)
            if utils_class_names:
                write_utils_index(category_name, utils_class_names)
        # Write category-level index if anything was found
        if class_names or utils_class_names:
            write_category_index(
                category_name, class_names, has_utils=bool(utils_class_names)
            )
            all_categories.append(category_name)
    # Write master plugins index
    if ONLY_CATEGORY is None:
        write_main_index(all_categories)

    print("Generated individual .rst files and master TOC.")


if __name__ == "__main__":
    main()
