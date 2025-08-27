import importlib
import inspect
import pkgutil
import typing
from typing import Any, Dict, List, Set, Tuple, Type, get_type_hints

import pytest

import poriscope.plugins as plugins_pkg
from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from poriscope.utils.MetaFilter import MetaFilter
from poriscope.utils.MetaModel import MetaModel
from poriscope.utils.MetaReader import MetaReader
from poriscope.utils.MetaView import MetaView
from poriscope.utils.MetaWriter import MetaWriter

# Recursively import EVERYTHING under poriscope.plugins
# (ensures all plugin subclasses are loaded into memory)
for _finder, modname, _ispkg in pkgutil.walk_packages(
    plugins_pkg.__path__, prefix=f"{plugins_pkg.__name__}."
):
    importlib.import_module(modname)


def get_required_methods(cls: Type) -> List[str]:
    """
    Retrieve all abstract methods that must be implemented by subclasses.

    :param cls: Base class
    :return: List of abstract method names
    """
    return list(getattr(cls, "__abstractmethods__", []))


# Explicit allowlist of framework interface/meta bases that must remain abstract.
# (Keeping this list prevents false positives/negatives that dynamic scans—
# e.g., for names starting with 'Meta' or ABC subclasses—could cause if the
# architecture changes.)

META_CLASSES: Set[Type] = {
    MetaController,
    MetaDatabaseLoader,
    MetaDatabaseWriter,
    MetaEventFinder,
    MetaEventFitter,
    MetaEventLoader,
    MetaFilter,
    MetaModel,
    MetaReader,
    MetaView,
    MetaWriter,
}


# Maps base class names to class objects and required method lists
BASE_CLASS_DATA: Dict[str, Dict[str, Any]] = {
    "BaseDataPlugin": {
        "class": BaseDataPlugin,
        "methods": get_required_methods(BaseDataPlugin),
    },
    "MetaController": {
        "class": MetaController,
        "methods": get_required_methods(MetaController),
    },
    "MetaDatabaseLoader": {
        "class": MetaDatabaseLoader,
        "methods": get_required_methods(MetaDatabaseLoader),
    },
    "MetaDatabaseWriter": {
        "class": MetaDatabaseWriter,
        "methods": get_required_methods(MetaDatabaseWriter),
    },
    "MetaEventFinder": {
        "class": MetaEventFinder,
        "methods": get_required_methods(MetaEventFinder),
    },
    "MetaEventFitter": {
        "class": MetaEventFitter,
        "methods": get_required_methods(MetaEventFitter),
    },
    "MetaEventLoader": {
        "class": MetaEventLoader,
        "methods": get_required_methods(MetaEventLoader),
    },
    "MetaFilter": {
        "class": MetaFilter,
        "methods": get_required_methods(MetaFilter),
    },
    "MetaModel": {
        "class": MetaModel,
        "methods": get_required_methods(MetaModel),
    },
    "MetaReader": {
        "class": MetaReader,
        "methods": get_required_methods(MetaReader),
    },
    "MetaView": {
        "class": MetaView,
        "methods": get_required_methods(MetaView),
    },
    "MetaWriter": {
        "class": MetaWriter,
        "methods": get_required_methods(MetaWriter),
    },
}


def get_all_subclasses(cls: Type) -> Set[Type]:
    """
    Recursively collect all direct and indirect subclasses of a given class.

    :param cls: Base class
    :return: Set of all subclasses
    """
    subclasses: Set[Type] = set(cls.__subclasses__())
    for subcls in cls.__subclasses__():
        subclasses |= get_all_subclasses(subcls)
    return subclasses


_EMPTY = inspect._empty  # sentinel "There’s no default value or no annotation here."


def strip_annotations(sig: inspect.Signature) -> inspect.Signature:
    """
    Return a copy of `sig` with all parameter and return annotations removed.

    :param sig: The original `inspect.Signature` object.
    :return: A new `inspect.Signature` with all annotations removed.
    """
    new_params = []
    for p in sig.parameters.values():
        new_params.append(p.replace(annotation=_EMPTY))
    return sig.replace(parameters=new_params, return_annotation=_EMPTY)


def _is_any(t: Any) -> bool:
    """
    Check whether a given type object is `typing.Any`.

    `typing.Any` is a special type hint that is considered compatible
    with all other types. Our annotation compatibility rules,
    treat `Any` as always passing both parameter (contravariant) and
    return (covariant) checks.

    This function exists so we can explicitly detect `Any` and skip
    strict type compatibility enforcement when it is present on either side of the comparison.

    :param t: Type object or annotation to check.
    :return: True if the type is `typing.Any` (imported in any form), False otherwise.
    """
    return t is Any or t is typing.Any


def _safe_resolved_hints(func: Any) -> Dict[str, Any]:
    """
    Resolve type hints, tolerating runtime/forward-ref issues.
    Returns {} if resolution fails.

    :param func: Function, method, or other callable to inspect.
    :return: A mapping of parameter names (and 'return') to resolved types,
             or an empty dict if resolution fails.
    """
    try:
        # include_extras is 3.11+; ignore if not supported
        return get_type_hints(func, include_extras=True)  # type: ignore[call-arg]
    except TypeError:
        try:
            return get_type_hints(func)
        except Exception:
            return {}
    except Exception:
        return {}


def _is_classlike(t: Any) -> bool:
    """
    Determine whether the given object is a class (type).

    This helper is used during type-compatibility checks to decide
    whether we can safely call `issubclass()` on the value.

    :param t: Object to check.
    :return: True if `t` is a class/type, False otherwise.
    """
    try:
        return isinstance(t, type)
    except Exception:
        # Defensive catch: in rare cases `isinstance` itself can raise
        # if `t` has a problematic `__class__` or metaclass.
        return False


def _param_type_compatible(base_t: Any, sub_t: Any) -> bool:
    """
    Method parameter contravariance:
    Subclass parameter type should be the SAME or a SUPERtype of the base parameter type.
    We treat Any as top (compatible with all).
    If we can't reason about the types, fall back to equality.

    :param base_t: Type annotation from the base method's parameter.
    :param sub_t: Type annotation from the subclass method's parameter.
    :return: True if compatible, False otherwise.
    """
    if base_t is _EMPTY or sub_t is _EMPTY:
        return True  # ignore if missing on either side
    if _is_any(base_t) or _is_any(sub_t):
        return True
    if _is_classlike(base_t) and _is_classlike(sub_t):
        # contravariant: subclass accepts broader -> base must be subclass of sub_t
        try:
            return issubclass(base_t, sub_t)
        except Exception:
            return base_t == sub_t
    # unknown typing constructs -> fallback to string equality
    return base_t == sub_t


def _return_type_compatible(base_t: Any, sub_t: Any) -> bool:
    """
    Method return covariance:
    Subclass return type should be the SAME or a SUBtype of the base return type.
    Treat Any as top/compatible. Fallback to equality when unsure.

    :param base_t: Type annotation from the base method's return.
    :param sub_t: Type annotation from the subclass method's return.
    :return: True if compatible, False otherwise.
    """
    if base_t is _EMPTY or sub_t is _EMPTY:
        return True
    if _is_any(base_t) or _is_any(sub_t):
        return True
    if _is_classlike(base_t) and _is_classlike(sub_t):
        try:
            return issubclass(sub_t, base_t)
        except Exception:
            return base_t == sub_t
    return base_t == sub_t


# Build test cases: (base_class_name, plugin_subclass)
compliance_test_cases: List[Tuple[str, Type]] = []
for base_name, base_info in BASE_CLASS_DATA.items():
    base_cls = base_info["class"]
    for plugin_cls in get_all_subclasses(base_cls):
        compliance_test_cases.append((base_name, plugin_cls))


@pytest.mark.compliance
@pytest.mark.parametrize(
    "base_class_name, plugin_cls",
    compliance_test_cases,
    ids=[f"{base}-{cls.__name__}" for base, cls in compliance_test_cases],
)
def test_plugin_subclass_compliance(base_class_name: str, plugin_cls: Type) -> None:
    """
    Compliance test for plugin subclasses.

    This test validates that every discovered subclass of the given base class meets
    the following requirements:

    1. **Implements all required abstract methods**
       - Names, parameter order, parameter kinds, and default values must match exactly.
       - Type annotations are ignored for structural comparison.

    2. **Optional annotation compatibility**
       - If a subclass **does not** provide type annotations, it passes automatically.
       - If a subclass **does** provide type annotations, they must be compatible with
         the base method:
           * Parameters: contravariant (subclass param type should be the same or broader).
           * Return: covariant (subclass return type should be the same or narrower).
           * `Any` is considered compatible with any type.

    3. **Docstring requirements**
       - The class itself must have a docstring.
       - Every method defined directly in the subclass must have a docstring.

    4. **Abstractness policy**
       - Classes in `META_CLASSES` are framework interfaces and MUST be abstract.
       - All other subclasses are implementations and MUST be concrete.

    :param base_class_name: Name of the base class being tested.
    :param plugin_cls:      Plugin subclass under test.
    """
    base_info = BASE_CLASS_DATA[base_class_name]
    base_cls = base_info["class"]
    required_methods = base_info["methods"]

    signature_mismatches: List[Tuple[str, str, str]] = []
    annotation_mismatches: List[str] = []
    missing_methods: List[str] = []
    missing_docstrings: List[str] = []
    errors: List[str] = []
    unimplemented_abstracts: Set[str] = set()

    # 1) Check each required abstract method
    for method_name in required_methods:
        if not hasattr(plugin_cls, method_name):
            # Method missing entirely
            missing_methods.append(method_name)
            continue

        base_method = getattr(base_cls, method_name, None)
        sub_method = getattr(plugin_cls, method_name, None)
        if base_method and sub_method:
            try:
                # Raw signatures (may include annotations)
                base_sig_raw = inspect.signature(base_method)
                sub_sig_raw = inspect.signature(sub_method)

                # Structural signatures with annotations removed
                base_sig = strip_annotations(base_sig_raw)
                sub_sig = strip_annotations(sub_sig_raw)

                # Compare structure: names, order, kind, defaults
                if base_sig != sub_sig:
                    signature_mismatches.append(
                        (method_name, str(base_sig), str(sub_sig))
                    )

                # 2) If subclass provides annotations, check for compatibility
                base_hints = _safe_resolved_hints(base_method)
                sub_hints = _safe_resolved_hints(sub_method)

                # Parameters: contravariant
                for pname, p in base_sig_raw.parameters.items():
                    if pname not in sub_sig_raw.parameters:
                        # If structural mismatch already found, skip type check
                        continue
                    base_t = base_hints.get(pname, p.annotation)
                    sub_t = sub_hints.get(
                        pname, sub_sig_raw.parameters[pname].annotation
                    )
                    if not _param_type_compatible(base_t, sub_t):
                        annotation_mismatches.append(
                            f"{method_name} param '{pname}' incompatible: "
                            f"base={getattr(base_t, '__name__', base_t)} "
                            f"sub={getattr(sub_t, '__name__', sub_t)}"
                        )

                # Return type: covariant
                base_ret = base_hints.get("return", base_sig_raw.return_annotation)
                sub_ret = sub_hints.get("return", sub_sig_raw.return_annotation)
                if not _return_type_compatible(base_ret, sub_ret):
                    annotation_mismatches.append(
                        f"{method_name} return incompatible: "
                        f"base={getattr(base_ret, '__name__', base_ret)} "
                        f"sub={getattr(sub_ret, '__name__', sub_ret)}"
                    )

            except (ValueError, TypeError):
                # Ignore methods we can't introspect (builtins, C-extensions, etc.)
                pass

    # 3) Check docstring requirements
    if not (plugin_cls.__doc__ and plugin_cls.__doc__.strip()):
        missing_docstrings.append("__class__")

    for name, member in inspect.getmembers(plugin_cls, predicate=inspect.isfunction):
        # Only check methods defined in this class, not inherited ones
        if member.__qualname__.startswith(plugin_cls.__name__):
            if not (inspect.getdoc(member) or "").strip():
                missing_docstrings.append(name)

    # Extra rule for framework META classes:
    # They must explicitly declare (override/redeclare) the base abstract methods.
    if plugin_cls in META_CLASSES:
        not_redeclared = []
        for method_name in required_methods:
            # Only count methods actually defined in the subclass body
            if method_name not in plugin_cls.__dict__:
                not_redeclared.append(method_name)
        if not_redeclared:
            errors.append(
                f"Meta interface must redeclare abstract methods from {base_cls.__name__}: {sorted(not_redeclared)}"
            )
    # 4) Abstractness policy:
    #    - Classes in META_CLASSES are framework interfaces and MUST be abstract.
    #    - All other subclasses are implementations and MUST be concrete.
    is_abstract = inspect.isabstract(plugin_cls)
    if plugin_cls in META_CLASSES:
        # Interface/meta classes should remain abstract
        if not is_abstract:
            errors.append("should be abstract (framework META class)")
    else:
        # Implementations should be instantiable
        if is_abstract:
            errors.append("still abstract")
            try:
                unimplemented_abstracts = getattr(
                    plugin_cls, "__abstractmethods__", set()
                )
            except AttributeError:
                unimplemented_abstracts = set()
            if unimplemented_abstracts:
                errors.append(
                    f"missing @abstractmethods: {sorted(unimplemented_abstracts)}"
                )

    # Collect all errors and fail if any
    if missing_methods:
        errors.append(f"missing methods: {missing_methods}")
    for name, expected, actual in signature_mismatches:
        errors.append(
            f"signature mismatch in '{name}': expected {expected}, got {actual}"
        )
    if annotation_mismatches:
        errors.append(f"annotation incompatibilities: {annotation_mismatches}")
    if missing_docstrings:
        errors.append(f"missing docstrings: {missing_docstrings}")

    assert not errors, f"{plugin_cls.__name__} failed compliance: {', '.join(errors)}"
