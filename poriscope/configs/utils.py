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

import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

# Opacity applied to the disabled-state icon variant. Lower = more faded.
DISABLED_ICON_OPACITY = 0.35

# Default tint colors used when the icon itself doesn't hardcode a color
# (i.e. SVGs authored with fill="currentColor", or plain-alpha PNGs).
DARK_MODE_ICON_COLOR = "#ffffff"
LIGHT_MODE_ICON_COLOR = "#000000"

# Icon load/theme results are cached so repeated get_icon() calls for the
# same (name, resolved color) so repeated calls are cheap.
_icon_cache: dict[tuple[str, str], QIcon] = {}

# Disk cache for tinted icons written out as real files, for callers that
# need a filesystem path rather than a QIcon (Qt stylesheet "image: url()"
# references can't take an in-memory pixmap directly). Cleared on each
# process start since it's derived, disposable output.
_TINTED_ICON_DIR = os.path.join(tempfile.gettempdir(), "poriscope_icons")
_tinted_path_cache: dict[tuple[str, str], str] = {}


def is_dark_mode() -> bool:
    """
    Determine whether the application is currently in dark mode.

    Uses the app's QPalette window color as the source of truth, so this
    stays correct whether dark mode came from the OS, a manual toggle, or
    an application stylesheet that sets the palette.

    :return: True if the app palette is dark, False otherwise.
    :rtype: bool
    """
    app = QApplication.instance()
    if app is None:
        return False
    palette = app.palette()
    bg = palette.color(palette.ColorRole.Window)
    # Perceptual lightness, 0 (black) - 255 (white)
    return bg.lightness() < 128


def _tint_pixmap(pixmap: QPixmap, color: QColor) -> QPixmap:
    """
    Recolor the opaque parts of a pixmap to a solid color, preserving alpha.

    Works for both SVG-rendered pixmaps (fill="currentColor" icons render
    as opaque-on-transparent, so this repaints them) and plain PNGs.

    :param pixmap: Source pixmap to tint.
    :type pixmap: QPixmap
    :param color: Color to apply.
    :type color: QColor
    :return: A new, tinted pixmap the same size as the source.
    :rtype: QPixmap
    """
    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.GlobalColor.transparent)

    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()

    return tinted


def _fade_pixmap(pixmap: QPixmap, opacity: float) -> QPixmap:
    """
    Produce a faded copy of a pixmap for use as a disabled-state icon.

    Buttons in this app apply a stylesheet ("border: none; background:
    transparent;"), which switches Qt to QStyleSheetStyle. That style does
    not reliably auto-generate a grayed-out disabled icon the way the
    native style does, so QToolButtons here stay full-opacity even when
    setEnabled(False) is called. Baking an explicit QIcon.Disabled pixmap
    sidesteps that and restores the expected "grayed out" look.

    :param pixmap: Source (normal-state) pixmap.
    :type pixmap: QPixmap
    :param opacity: Opacity to apply, from 0.0 (invisible) to 1.0 (opaque).
    :type opacity: float
    :return: A faded copy of the pixmap, same size, alpha preserved.
    :rtype: QPixmap
    """
    faded = QPixmap(pixmap.size())
    faded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(faded)
    painter.setOpacity(opacity)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()

    return faded


def clear_icon_cache() -> None:
    """
    Clear the cached icons.

    Call this if icons need to be forcibly re-rendered outside of a normal
    theme change (e.g. icon files were replaced on disk at runtime).
    """
    _icon_cache.clear()


def get_icon(name: str, color: str | None = None) -> QIcon:
    """
    Load an icon by filename from the icons directory, tinted for the
    current theme (or an explicit color override).

    Icons are expected to be authored with fill="currentColor" (SVG) or as
    plain shapes with transparency (PNG) so they can be recolored here.
    Results are cached per (name, resolved color) so repeated calls are cheap.

    :param name: Icon filename, e.g. "trash.svg" or "edit.png".
    :type name: str
    :param color: Optional explicit hex color (e.g. "#ff0000") to force,
        bypassing theme detection. Leave as None for automatic light/dark
        selection.
    :type color: str | None
    :return: The loaded, tinted icon, or an empty QIcon if the file is missing.
    :rtype: QIcon
    """
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "icons"))
    path = os.path.join(base, name)

    if not os.path.exists(path):
        return QIcon()

    dark = is_dark_mode()
    resolved_color = color or (DARK_MODE_ICON_COLOR if dark else LIGHT_MODE_ICON_COLOR)

    cache_key = (name, resolved_color)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    pixmap = QPixmap(path)
    if pixmap.isNull():
        return QIcon()

    tinted = _tint_pixmap(pixmap, QColor(resolved_color))
    disabled = _fade_pixmap(tinted, DISABLED_ICON_OPACITY)

    icon = QIcon()
    icon.addPixmap(tinted, QIcon.Mode.Normal)
    icon.addPixmap(disabled, QIcon.Mode.Disabled)

    _icon_cache[cache_key] = icon
    return icon


def get_themed_icon_path(name: str, color: str | None = None) -> str:
    """
    Tint an icon for the current theme (or an explicit color) and return
    a real filesystem path to the result.

    Use this instead of get_icon() when a QIcon object won't work -- most
    notably Qt stylesheet "image: url(...)" references (e.g. a custom
    QComboBox::down-arrow), which require an actual file path rather than
    an in-memory pixmap. Results are cached to disk per (name, color) so
    repeated calls for the same combination are cheap.

    :param name: Icon filename, e.g. "arrowdown-black.png".
    :type name: str
    :param color: Optional explicit hex color (e.g. "#ff0000") to force,
        bypassing theme detection. Leave as None for automatic light/dark
        selection.
    :type color: str | None
    :return: Filesystem path to the tinted PNG, or "" if the source icon
        is missing.
    :rtype: str
    """
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "icons"))
    source_path = os.path.join(base, name)

    if not os.path.exists(source_path):
        return ""

    dark = is_dark_mode()
    resolved_color = color or (DARK_MODE_ICON_COLOR if dark else LIGHT_MODE_ICON_COLOR)

    cache_key = (name, resolved_color)
    cached = _tinted_path_cache.get(cache_key)
    if cached and os.path.exists(cached):
        return cached

    pixmap = QPixmap(source_path)
    if pixmap.isNull():
        return ""

    tinted = _tint_pixmap(pixmap, QColor(resolved_color))

    os.makedirs(_TINTED_ICON_DIR, exist_ok=True)
    stem, _ext = os.path.splitext(name)
    safe_color = resolved_color.lstrip("#")
    out_path = os.path.join(_TINTED_ICON_DIR, f"{stem}_{safe_color}.png")
    tinted.save(out_path, "PNG")

    _tinted_path_cache[cache_key] = out_path
    return out_path
