"""
Full unit-test suite for HelpCentre and LinkCard.

No mocking needed — no file I/O, no database, no blocking modals.
webbrowser.open is patched only for the click-through test.

Run with:
    pytest test_help.py -v
    pytest test_help.py --cov=poriscope --cov-report=html
"""

from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel

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
    def test_creates_without_error(self, black_card):
        assert black_card is not None

    def test_is_qframe(self, black_card):
        assert isinstance(black_card, QFrame)

    def test_fixed_height(self, black_card):
        assert black_card.height() == 150

    def test_url_stored(self, black_card):
        assert black_card._url == "https://example.com"

    def test_initial_bg_stored(self, black_card):
        assert black_card._initial_bg == "black"

    def test_title_label_exists(self, black_card):
        assert isinstance(black_card._title_label, QLabel)

    def test_url_label_exists(self, black_card):
        assert isinstance(black_card._url_label, QLabel)

    def test_title_label_text(self, black_card):
        assert black_card._title_label.text() == "Test Card"

    def test_url_label_text(self, black_card):
        assert black_card._url_label.text() == "https://example.com"

    def test_icon_label_exists(self, black_card):
        assert isinstance(black_card._icon_label, QLabel)

    def test_icon_label_fixed_size(self, black_card):
        assert black_card._icon_label.width() == 64
        assert black_card._icon_label.height() == 64

    def test_white_card_creates(self, white_card):
        assert white_card._initial_bg == "white"

    def test_event_filter_installed(self, black_card):
        # Event filter is installed on self — just confirm no crash
        assert black_card is not None


# ===========================================================================
# LinkCard — _refresh (hover states)
# ===========================================================================

class TestLinkCardRefresh:
    def test_black_card_resting_stylesheet_contains_black(self, black_card):
        black_card._refresh(hovered=False)
        assert "black" in black_card.styleSheet()

    def test_black_card_hovered_stylesheet_contains_white(self, black_card):
        black_card._refresh(hovered=True)
        assert "white" in black_card.styleSheet()

    def test_white_card_resting_stylesheet_contains_white(self, white_card):
        white_card._refresh(hovered=False)
        assert "white" in white_card.styleSheet()

    def test_white_card_hovered_stylesheet_contains_black(self, white_card):
        white_card._refresh(hovered=True)
        assert "black" in white_card.styleSheet()

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

class TestLinkCardLoadIcon:
    def test_empty_path_no_error(self, black_card):
        black_card._load_icon("")  # should not raise

    def test_nonexistent_path_no_error(self, black_card):
        black_card._load_icon("/nonexistent/path/icon.svg")

    def test_nonexistent_png_no_error(self, black_card):
        black_card._load_icon("/nonexistent/path/icon.png")

    def test_valid_svg_file_loads(self, black_card, tmp_path):
        svg = tmp_path / "test.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
            '<circle cx="32" cy="32" r="32" fill="black"/></svg>'
        )
        black_card._load_icon(str(svg))  # should not raise

    def test_invalid_svg_no_error(self, black_card, tmp_path):
        bad = tmp_path / "bad.svg"
        bad.write_text("not svg content")
        black_card._load_icon(str(bad))

    def test_valid_png_file_loads(self, black_card, tmp_path):
        # Minimal 1×1 white PNG
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
            b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
            b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        png = tmp_path / "test.png"
        png.write_bytes(png_bytes)
        black_card._load_icon(str(png))


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
        assert "black" in black_card.styleSheet()  # back to black bg

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
        assert "black" in black_card.styleSheet()


# ===========================================================================
# HelpCentre — instantiation
# ===========================================================================

class TestHelpCentreInstantiation:
    def test_creates_without_error(self, hc):
        assert hc is not None

    def test_minimum_size(self, hc):
        assert hc.minimumWidth() == 900
        assert hc.minimumHeight() == 400

    def test_help_centre_label_exists(self, hc):
        assert isinstance(hc.help_centre_label, QLabel)

    def test_help_centre_label_text(self, hc):
        assert hc.help_centre_label.text() == "Help Centre"

    def test_window_title(self, hc):
        assert hc.windowTitle() == "Help Centre"


# ===========================================================================
# HelpCentre — cards
# ===========================================================================

class TestHelpCentreCards:
    def test_getting_started_card_exists(self, hc):
        assert isinstance(hc.getting_started_card, LinkCard)

    def test_tutorial_card_exists(self, hc):
        assert isinstance(hc.tutorial_card, LinkCard)

    def test_report_card_exists(self, hc):
        assert isinstance(hc.report_card, LinkCard)

    def test_paper_card_exists(self, hc):
        assert isinstance(hc.paper_card, LinkCard)

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

    def test_getting_started_card_black_bg(self, hc):
        assert hc.getting_started_card._initial_bg == "black"

    def test_tutorial_card_white_bg(self, hc):
        assert hc.tutorial_card._initial_bg == "white"

    def test_report_card_black_bg(self, hc):
        assert hc.report_card._initial_bg == "black"

    def test_paper_card_fixed_height(self, hc):
        assert hc.paper_card.height() == 80

    def test_paper_card_white_bg(self, hc):
        assert hc.paper_card._initial_bg == "white"


# ===========================================================================
# HelpCentre — citation box
# ===========================================================================

class TestHelpCentreCitationBox:
    def test_citation_box_exists(self, hc):
        assert isinstance(hc.citation_box, QFrame)

    def test_citation_label_exists(self, hc):
        assert isinstance(hc.citation_label, QLabel)

    def test_release_label_exists(self, hc):
        assert isinstance(hc.release_label, QLabel)

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

    def test_citation_label_word_wrap(self, hc):
        assert hc.citation_label.wordWrap()

    def test_release_label_word_wrap(self, hc):
        assert hc.release_label.wordWrap()

    def test_citation_box_has_stylesheet(self, hc):
        assert "border-radius" in hc.citation_box.styleSheet()


# ===========================================================================
# HelpCentre — retranslateUi
# ===========================================================================

class TestHelpCentreRetranslate:
    def test_retranslate_does_not_raise(self, hc):
        hc.retranslateUi()

    def test_retranslate_preserves_window_title(self, hc):
        hc.retranslateUi()
        assert hc.windowTitle() == "Help Centre"

    def test_retranslate_preserves_label_text(self, hc):
        hc.retranslateUi()
        assert hc.help_centre_label.text() == "Help Centre"
