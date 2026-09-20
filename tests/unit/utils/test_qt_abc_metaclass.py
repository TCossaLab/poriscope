"""
The Qt-aware ABC metaclass, and the PySide6 defect it exists for.

``@abstractmethod`` does not work on a Qt class by itself: a naive
``class Foo(QWidget, abc.ABC)`` raises a metaclass conflict at definition time, and a
metaclass that merely inherits ``ABCMeta`` and Shiboken's type **instantiates while
abstract methods remain**. ``QObjectABCMeta.__call__`` is what refuses, so these tests
exercise it rather than the inheritance.

One class serves both hierarchies, so the tests run it against ``QObject`` and
``QWidget`` alike.
"""

import abc

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from poriscope.utils.QObjectABCMeta import QObjectABCMeta

QT_BASES = [pytest.param(QObject, id="QObject"), pytest.param(QWidget, id="QWidget")]


def test_one_metaclass_serves_both_hierarchies():
    """
    ``type(QObject)`` and ``type(QWidget)`` are both ``Shiboken.ObjectType``, so the two
    metaclasses this project carried were built from identical ingredients. That is why
    one class can serve both, and why the ``QWidgetABCMeta`` name was removed rather
    than kept as an alias.
    """
    assert type(QObject) is type(QWidget)
    assert issubclass(QObjectABCMeta, type(QWidget))


@pytest.mark.parametrize("qt_base", QT_BASES)
def test_an_abstract_subclass_cannot_be_instantiated(qt_base, qtbot):
    """Both hierarchies: the refusal is the whole point of the class."""

    class Abstract(qt_base, metaclass=QObjectABCMeta):
        @abc.abstractmethod
        def required(self) -> None: ...

    assert Abstract.__abstractmethods__ == frozenset({"required"})
    with pytest.raises(TypeError, match="required"):
        Abstract()


@pytest.mark.parametrize("qt_base", QT_BASES)
def test_a_concrete_subclass_still_builds(qt_base, qtbot):
    """The guard must refuse the abstract class and nothing else."""

    class Abstract(qt_base, metaclass=QObjectABCMeta):
        @abc.abstractmethod
        def required(self) -> None: ...

    class Concrete(Abstract):
        def required(self) -> None:
            return None

    instance = Concrete()
    assert instance.required() is None


def test_shiboken_alone_would_let_an_abstract_class_through(qtbot):
    """
    The defect being worked around, asserted rather than described.

    A metaclass that inherits ``ABCMeta`` and Shiboken's type computes
    ``__abstractmethods__`` correctly and then ignores it at instantiation. If this test
    ever fails, PySide6 has started honouring abstractness and ``__call__`` could go.
    """

    class WithoutTheGuard(abc.ABCMeta, type(QObject)):  # type: ignore[misc]
        pass

    class Abstract(QWidget, metaclass=WithoutTheGuard):
        @abc.abstractmethod
        def required(self) -> None: ...

    assert Abstract.__abstractmethods__ == frozenset({"required"})
    Abstract()  # no TypeError: this is the defect
