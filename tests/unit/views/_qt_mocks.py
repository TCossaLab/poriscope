"""
Shared stand-ins for building analysis-tab views without real Qt widgets.

Constructing a view for real costs roughly half a second - the widget tree, the
Matplotlib canvases and the controls panel - and most view tests exercise plain
Python logic that does not need any of it. These helpers let a test module build
the view with ``__new__`` and supply only what the code under test actually
touches.

What must NOT be mocked, learned the hard way:

* the view's ``logger``. It is a class attribute (``logging.getLogger(__name__)``)
  so it resolves on its own, and replacing it silently blinds every ``caplog``
  assertion in the module.
* anything a test reads state back from. ``assert view.canvas is not None`` and
  ``combo.count() == 3`` pass vacuously against a MagicMock. Tests that do that,
  or that emit a real Qt signal to prove a connection exists, need the real
  widget fixture instead.
"""

from unittest.mock import MagicMock

from PySide6.QtCore import Signal


class FakeSignal:
    """
    Minimal stand-in for a Qt Signal.

    Tests use two styles against these: asserting on the emit call
    (``sig.emit.assert_called_once_with(...)``) and connecting a callback then
    asserting it received the payload. A bare MagicMock records the connect but
    never delivers, so this keeps a real slot list and dispatches to it, while
    leaving ``emit`` a MagicMock so call assertions keep working.
    """

    def __init__(self) -> None:
        self._slots: list = []
        self.emit = MagicMock(side_effect=self._deliver)

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def disconnect(self, slot=None) -> None:
        if slot is None:
            self._slots.clear()
        elif slot in self._slots:
            self._slots.remove(slot)

    def _deliver(self, *args, **kwargs) -> None:
        for slot in list(self._slots):
            slot(*args, **kwargs)


def mock_axes() -> MagicMock:
    """A stand-in Axes whose hist() returns a realistic (n, bins, patches)."""
    ax = MagicMock()
    ax.hist.return_value = ([1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0], [])
    return ax


class _FigureState:
    """
    Backs a stand-in Figure so the state tests read back is really tracked.

    Several tests plot and then assert on what the figure ended up holding -
    how many axes it has, or whether constrained layout was turned on. A bare
    MagicMock hands back a fresh Mock from get_axes() or get_constrained_layout()
    and those assertions become meaningless, so both are kept for real.
    """

    def __init__(self) -> None:
        self.axes: list = []
        self.constrained_layout: bool = False

    def add_subplot(self, *args, **kwargs) -> MagicMock:
        ax = mock_axes()
        self.axes.append(ax)
        return ax

    def get_axes(self) -> list:
        return list(self.axes)

    def clear(self, *args, **kwargs) -> None:
        self.axes.clear()

    def set_constrained_layout(self, value=True, *args, **kwargs) -> None:
        self.constrained_layout = bool(value)

    def set_layout_engine(self, engine=None, *args, **kwargs) -> None:
        """
        Mirror Matplotlib's link between the layout engine and this flag.

        Real code reaches for set_layout_engine("constrained"), and on a real
        Figure that is what makes get_constrained_layout() report True; a test
        asserting the latter would otherwise never see the former.
        """
        self.constrained_layout = engine == "constrained"

    def get_constrained_layout(self) -> bool:
        return self.constrained_layout


def mock_figure() -> MagicMock:
    """A stand-in Figure that really tracks its axes and constrained layout."""
    state = _FigureState()
    fig = MagicMock()
    fig.add_subplot = MagicMock(side_effect=state.add_subplot)
    fig.get_axes = MagicMock(side_effect=state.get_axes)
    fig.clear = MagicMock(side_effect=state.clear)
    fig.set_constrained_layout = MagicMock(side_effect=state.set_constrained_layout)
    fig.set_layout_engine = MagicMock(side_effect=state.set_layout_engine)
    fig.get_constrained_layout = MagicMock(side_effect=state.get_constrained_layout)
    fig.axes = state.axes  # same list object, so it reflects additions
    return fig


def shadow_signals(instance, cls) -> None:
    """
    Replace every Qt Signal declared on ``cls`` with a FakeSignal on ``instance``.

    A view built with ``__new__`` has no C++ QObject behind it, so emitting a
    class-level Signal raises "Signal source has been deleted". Signals are found
    by introspection rather than listed by name, so one added later is covered
    without touching this helper.

    :param instance: the view being assembled.
    :param cls: the class whose declared signals should be shadowed.
    """
    for name in dir(cls):
        if isinstance(getattr(cls, name, None), Signal):
            setattr(instance, name, FakeSignal())
