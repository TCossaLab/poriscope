"""
Full unit-test suite for HelpCentre and LinkCard.

No mocking needed — no file I/O, no database, no blocking modals.
webbrowser.open is patched only for the click-through tests.

Run with:
    pytest test_help.py -v
    pytest test_help.py --cov=poriscope --cov-report=html
"""

from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QEnterEvent, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication

from poriscope.views.help import HelpCentre, LinkCard

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def hc(qt_app):
    widget = HelpCentre()
    qt_app.processEvents()
    return widget


@pytest.fixture
def black_card(qt_app):
    return LinkCard(
        title="Test Card",
        url="https://example.com",
        icon_path_normal="",
        icon_path_hover="",
        initial_bg="black",
    )


@pytest.fixture
def white_card(qt_app):
    return LinkCard(
        title="White Card",
        url="https://example.org",
        icon_path_normal="",
        icon_path_hover="",
        initial_bg="white",
    )


# ===========================================================================
# LinkCard — instantiation
# ===========================================================================


class TestLinkCardInstantiation:
    def test_url_stored(self, black_card):
        assert black_card._url == "https://example.com"

    def test_initial_bg_stored(self, black_card):
        assert black_card._initial_bg == "black"

    def test_title_label_text(self, black_card):
        assert black_card._title_label.text() == "Test Card"

    def test_url_label_text(self, black_card):
        assert black_card._url_label.text() == "https://example.com"

    def test_white_card_creates(self, white_card):
        assert white_card._initial_bg == "white"


# ===========================================================================
# LinkCard — _refresh (hover states)
# ===========================================================================


class TestLinkCardRefresh:
    """
    The card's background is asserted as ``background-color: <colour>``.

    A bare ``"black" in styleSheet()`` is always true, because every card draws a
    ``2px solid black`` border whatever its background.
    """

    def test_black_card_resting_background_is_black(self, black_card):
        black_card._refresh(hovered=False)
        assert "background-color: black" in black_card.styleSheet()

    def test_black_card_hovered_stylesheet_contains_white(self, black_card):
        black_card._refresh(hovered=True)
        assert "white" in black_card.styleSheet()

    def test_white_card_resting_stylesheet_contains_white(self, white_card):
        white_card._refresh(hovered=False)
        assert "white" in white_card.styleSheet()

    def test_white_card_hovered_background_is_black(self, white_card):
        white_card._refresh(hovered=True)
        assert "background-color: black" in white_card.styleSheet()

    def test_title_label_white_on_black_resting(self, black_card):
        black_card._refresh(hovered=False)
        assert "white" in black_card._title_label.styleSheet()

    def test_title_label_black_on_white_hovered(self, black_card):
        black_card._refresh(hovered=True)
        assert "black" in black_card._title_label.styleSheet()

    def test_url_label_has_underline_resting(self, black_card):
        black_card._refresh(hovered=False)
        assert "underline" in black_card._url_label.styleSheet()

    def test_url_label_has_underline_hovered(self, black_card):
        black_card._refresh(hovered=True)
        assert "underline" in black_card._url_label.styleSheet()

    def test_white_card_title_black_resting(self, white_card):
        white_card._refresh(hovered=False)
        assert "black" in white_card._title_label.styleSheet()

    def test_white_card_title_white_hovered(self, white_card):
        white_card._refresh(hovered=True)
        assert "white" in white_card._title_label.styleSheet()

    def test_refresh_toggle(self, black_card):
        black_card._refresh(hovered=True)
        style_hovered = black_card.styleSheet()
        black_card._refresh(hovered=False)
        style_resting = black_card.styleSheet()
        assert style_hovered != style_resting


# ===========================================================================
# LinkCard — _load_icon
# ===========================================================================


def _has_icon(card: LinkCard) -> bool:
    """
    Whether the card's icon label is showing a pixmap.

    :param card: the card to inspect
    :type card: LinkCard
    :return: True when an icon was set on the label
    :rtype: bool
    """
    return not card._icon_label.pixmap().isNull()


class TestLinkCardLoadIcon:
    """A path that cannot be drawn leaves the icon empty; one that can is shown."""

    def test_empty_path_no_error(self, black_card):
        black_card._load_icon("")
        assert not _has_icon(black_card)

    def test_nonexistent_path_no_error(self, black_card):
        black_card._load_icon("/nonexistent/path/icon.svg")
        assert not _has_icon(black_card)

    def test_nonexistent_png_no_error(self, black_card):
        black_card._load_icon("/nonexistent/path/icon.png")
        assert not _has_icon(black_card)

    def test_valid_svg_file_loads(self, black_card, tmp_path):
        svg = tmp_path / "test.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
            '<circle cx="32" cy="32" r="32" fill="black"/></svg>'
        )
        black_card._load_icon(str(svg))
        assert _has_icon(black_card)

    def test_invalid_svg_no_error(self, black_card, tmp_path):
        bad = tmp_path / "bad.svg"
        bad.write_text("not svg content")
        black_card._load_icon(str(bad))
        assert not _has_icon(black_card)

    def test_valid_png_file_loads(self, black_card, tmp_path):
        # Written by Qt itself, so the file is a PNG Qt can read back.
        image = QImage(4, 4, QImage.Format_ARGB32)
        image.fill(QColor("white"))
        png = tmp_path / "test.png"
        assert image.save(str(png), "PNG")
        black_card._load_icon(str(png))
        assert _has_icon(black_card)


# ===========================================================================
# LinkCard — eventFilter
# ===========================================================================


class TestLinkCardEventFilter:
    def test_enter_event_triggers_hover(self, black_card):
        enter = QEvent(QEvent.Enter)
        black_card.eventFilter(black_card, enter)
        assert "white" in black_card.styleSheet()  # hovered → white bg

    def test_leave_event_restores_resting(self, black_card):
        enter = QEvent(QEvent.Enter)
        black_card.eventFilter(black_card, enter)
        leave = QEvent(QEvent.Leave)
        black_card.eventFilter(black_card, leave)
        assert "background-color: black" in black_card.styleSheet()

    def test_mouse_release_opens_url(self, black_card):
        with patch("webbrowser.open") as mock_open:
            release = QEvent(QEvent.MouseButtonRelease)
            black_card.eventFilter(black_card, release)
            mock_open.assert_called_once_with("https://example.com")

    def test_unrelated_event_no_refresh(self, black_card):
        black_card._refresh(hovered=False)
        style_before = black_card.styleSheet()
        move = QEvent(QEvent.MouseMove)
        black_card.eventFilter(black_card, move)
        assert black_card.styleSheet() == style_before

    def test_event_on_other_obj_ignored(self, black_card, white_card):
        enter = QEvent(QEvent.Enter)
        black_card.eventFilter(white_card, enter)  # obj is not self
        # black_card styling unchanged (event was for white_card)
        assert "background-color: black" in black_card.styleSheet()


class TestLinkCardReceivesItsOwnEvents:
    """
    Events delivered by Qt, not by calling ``eventFilter`` directly.

    The tests above call the filter by hand, so they pass whether or not the card
    ever installed it; these go through ``QApplication.sendEvent``, which reaches the
    filter only if the card registered it on itself.
    """

    def test_hovering_and_leaving_restyle_the_card(self, black_card):
        point = QPointF(5, 5)
        QApplication.sendEvent(black_card, QEnterEvent(point, point, point))
        assert "background-color: white" in black_card.styleSheet()

        QApplication.sendEvent(black_card, QEvent(QEvent.Leave))
        assert "background-color: black" in black_card.styleSheet()

    def test_clicking_the_card_opens_its_url(self, black_card):
        point = QPointF(5, 5)
        release = QMouseEvent(
            QEvent.MouseButtonRelease,
            point,
            point,
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        with patch("webbrowser.open") as mock_open:
            QApplication.sendEvent(black_card, release)
        mock_open.assert_called_once_with("https://example.com")


# ===========================================================================
# HelpCentre — instantiation
# ===========================================================================


class TestHelpCentreInstantiation:
    def test_help_centre_label_text(self, hc):
        assert hc.help_centre_label.text() == "Help Centre"

    def test_window_title(self, hc):
        assert hc.windowTitle() == "Help Centre"


# ===========================================================================
# HelpCentre — cards
# ===========================================================================


class TestHelpCentreCards:
    def test_getting_started_card_url(self, hc):
        assert "youtube" in hc.getting_started_card._url

    def test_tutorial_card_url(self, hc):
        assert "tcossalab.github.io" in hc.tutorial_card._url

    def test_report_card_url(self, hc):
        assert "github.com" in hc.report_card._url

    def test_paper_card_url(self, hc):
        assert "jors" in hc.paper_card._url

    def test_getting_started_card_title(self, hc):
        assert "Tutorial" in hc.getting_started_card._title_label.text()

    def test_tutorial_card_title(self, hc):
        assert "Documentation" in hc.tutorial_card._title_label.text()

    def test_report_card_title(self, hc):
        assert "Report" in hc.report_card._title_label.text()


# ===========================================================================
# HelpCentre — citation box
# ===========================================================================


class TestHelpCentreCitationBox:
    def test_citation_label_contains_doi(self, hc):
        assert "10.5334" in hc.citation_label.text()

    def test_citation_label_contains_authors(self, hc):
        assert "González" in hc.citation_label.text()

    def test_citation_label_contains_journal(self, hc):
        assert "Journal of Open Research Software" in hc.citation_label.text()

    def test_citation_label_opens_external_links(self, hc):
        assert hc.citation_label.openExternalLinks()

    def test_release_label_contains_github(self, hc):
        assert "github.com" in hc.release_label.text()

    def test_release_label_opens_external_links(self, hc):
        assert hc.release_label.openExternalLinks()

    def test_citation_box_has_stylesheet(self, hc):
        assert "border-radius" in hc.citation_box.styleSheet()
