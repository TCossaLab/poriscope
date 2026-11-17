"""
The Conditioning tab's status-bar readout: what the toolbar shows for the cursor's position.

Each panel's noise axes are insets of its pore-size axes, and matplotlib reports the cursor's
coordinates on the axes it hit-tests, which never include insets: over the noise half of a
panel the toolbar showed a pore size, never the 1 Hz noise. The readout instead names the
cycle nearest the cursor and that cycle's measured values.
"""

from typing import Any, Dict, Iterator, List

import numpy as np
import pytest
from matplotlib.axes import Axes
from matplotlib.backend_bases import MouseEvent

from poriscope.plugins.analysistabs.ConditioningView import ConditioningView


def _entry(channel: int, psd: Dict[str, Dict[str, List[float]]]) -> Dict[str, Any]:
    cycles = np.arange(1.0, 7.0)
    return {
        "channel": channel,
        "cycles": cycles,
        "measured": cycles + 0.25,
        "max_target": np.full(6, 9.0),
        "min_target": np.full(6, 8.0),
        "disabled": False,
        "psd": {
            polarity: {key: np.asarray(values) for key, values in result.items()}
            for polarity, result in psd.items()
        },
    }


@pytest.fixture
def view(qapp: Any) -> Iterator[ConditioningView]:
    v = ConditioningView()
    yield v
    v.close()
    v.deleteLater()


def _draw(view: ConditioningView, *entries: Dict[str, Any]) -> List[Axes]:
    view.draw_conditioning(list(entries), 1e9, 2e9, 1e-4, True)
    return [ax for ax in view.figure.axes if ax.get_title()]


def _hover(view: ConditioningView, ax: Axes, cycle: float, height: float) -> str:
    """
    Move the mouse to a cycle, at a height given as a fraction of the panel, and return the
    toolbar's coordinate text.
    """
    x = ax.transData.transform((cycle, 0.0))[0]
    y = ax.transAxes.transform((0.0, height))[1]
    MouseEvent("motion_notify_event", view.canvas, x, y)._process()
    return str(view.toolbar.locLabel.text())


def test_over_the_noise_half_the_toolbar_shows_that_cycles_noise(
    view: ConditioningView,
) -> None:
    psd = {
        "+": {"cycles": [2.0, 4.0, 6.0], "one_hz": [0.5, 0.0234, 7.0]},
        "-": {"cycles": [2.0, 4.0, 6.0], "one_hz": [0.1, 0.0411, 3.0]},
    }
    (ax,) = _draw(view, _entry(5, psd))
    expected = (
        "Channel 5, cycle 4: pore size 4.25 nm, PSD+ 1 Hz noise 0.0234 pA²/Hz, "
        "PSD- 1 Hz noise 0.0411 pA²/Hz"
    )
    assert _hover(view, ax, 3.8, 0.75) == expected
    assert _hover(view, ax, 4.2, 0.25) == expected


def test_a_cycle_without_a_psd_shows_only_its_pore_size(
    view: ConditioningView,
) -> None:
    psd = {"+": {"cycles": [2.0, 4.0], "one_hz": [0.5, 0.0234]}}
    (ax,) = _draw(view, _entry(5, psd))
    assert _hover(view, ax, 3.0, 0.75) == "Channel 5, cycle 3: pore size 3.25 nm"


def test_every_psd_of_one_polarity_at_a_cycle_is_shown(
    view: ConditioningView,
) -> None:
    psd = {"+": {"cycles": [2.0, 2.0], "one_hz": [0.5, 0.25]}}
    (ax,) = _draw(view, _entry(5, psd))
    assert _hover(view, ax, 2.0, 0.75) == (
        "Channel 5, cycle 2: pore size 2.25 nm, PSD+ 1 Hz noise 0.5, 0.25 pA²/Hz"
    )


def test_each_panel_reads_its_own_channel(view: ConditioningView) -> None:
    left, right = _draw(
        view,
        _entry(1, {"+": {"cycles": [2.0], "one_hz": [0.5]}}),
        _entry(7, {"+": {"cycles": [2.0], "one_hz": [9.0]}}),
    )
    assert _hover(view, left, 2.0, 0.75).endswith("PSD+ 1 Hz noise 0.5 pA²/Hz")
    assert _hover(view, right, 2.0, 0.75).startswith("Channel 7, cycle 2:")
    assert _hover(view, right, 2.0, 0.75).endswith("PSD+ 1 Hz noise 9 pA²/Hz")
