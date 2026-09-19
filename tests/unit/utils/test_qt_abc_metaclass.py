"""
The Qt-aware ABC metaclass, and the PySide6 defect it exists for.

``@abstractmethod`` does not work on a Qt class by itself: a naive
``class Foo(QWidget, abc.ABC)`` raises a metaclass conflict at definition time, and a
metaclass that merely inherits ``ABCMeta`` and Shiboken's type **instantiates while
abstract methods remain**. ``QObjectABCMeta.__call__`` is what refuses, so these tests
exercise it rather than the inheritance.

``QWidgetABCMeta`` is the same class under a second name - both are re-exported from
``poriscope.exposed``, so both are kept - and the tests run over both to pin that.
"""

import abc

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from poriscope.utils.QObjectABCMeta import QObjectABCMeta
from poriscope.utils.QWidgetABCMeta import QWidgetABCMeta

METACLASSES = [
    pytest.param(QObjectABCMeta, id="QObjectABCMeta"),
    pytest.param(QWidgetABCMeta, id="QWidgetABCMeta"),
]
QT_BASES = [pytest.param(QObject, id="QObject"), pytest.param(QWidget, id="QWidget")]


def test_the_two_names_are_one_class():
    """
    ``type(QObject)`` and ``type(QWidget)`` are both ``Shiboken.ObjectType``, so the two
    metaclasses this project carried were built from identical ingredients. They are one
    class now; the second name is kept because ``exposed.py`` publishes it.
    """
    assert QWidgetABCMeta is QObjectABCMeta
    assert type(QObject) is type(QWidget)


@pytest.mark.parametrize("meta", METACLASSES)
@pytest.mark.parametrize("qt_base", QT_BASES)
def test_an_abstract_subclass_cannot_be_instantiated(meta, qt_base, qtbot):
    """Both names, both hierarchies: the refusal is the whole point of the class."""

    class Abstract(qt_base, metaclass=meta):
        @abc.abstractmethod
        def required(self) -> None: ...

    assert Abstract.__abstractmethods__ == frozenset({"required"})
    with pytest.raises(TypeError, match="required"):
        Abstract()


@pytest.mark.parametrize("meta", METACLASSES)
@pytest.mark.parametrize("qt_base", QT_BASES)
def test_a_concrete_subclass_still_builds(meta, qt_base, qtbot):
    """The guard must refuse the abstract class and nothing else."""

    class Abstract(qt_base, metaclass=meta):
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
