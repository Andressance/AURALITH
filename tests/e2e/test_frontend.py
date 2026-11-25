"""Browser tests for core screens: login, playlists, playback, logout, mobile layout.

Same environment as the other e2e tests (AURALITH_E2E_URL, AURALITH_E2E_PASSWORD). The
account needs at least one track in its library.
"""

import os
import time
import uuid

import pytest

E2E_URL = os.getenv("AURALITH_E2E_URL", "").rstrip("/")
E2E_PASSWORD = os.getenv("AURALITH_E2E_PASSWORD", "")

pytestmark = pytest.mark.skipif(
    not (E2E_URL and E2E_PASSWORD), reason="set AURALITH_E2E_URL and AURALITH_E2E_PASSWORD"
)


def _open_login(page):
    page.goto(f"{E2E_URL}/")
    page.wait_for_selector("input[autocomplete='username']", timeout=20000)


def _login(context):
    page = context.new_page()
    _open_login(page)
    page.fill("input[autocomplete='username']", "owner")
    page.fill("input[autocomplete='current-password']", E2E_PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_selector(".track-grid article", timeout=20000)
    return page


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            yield browser
        finally:
            browser.close()


def test_wrong_password_shows_an_error(browser):
    from playwright.sync_api import expect

    page = browser.new_context().new_page()
    _open_login(page)
    page.fill("input[autocomplete='username']", "owner")
    page.fill("input[autocomplete='current-password']", "definitely-wrong-password")
    page.get_by_role("button", name="Entrar").click()
    expect(page.locator(".error").first).to_be_visible(timeout=10000)
    expect(page.locator(".track-grid")).to_have_count(0)


def test_create_playlist_from_sidebar_and_see_it(browser):
    from playwright.sync_api import expect

    page = _login(browser.new_context())
    name = f"E2E {uuid.uuid4().hex[:8]}"
    page.locator(".playlist-create input").fill(name)
    page.get_by_role("button", name="Crear playlist").click()
    expect(page.locator(".sidebar-library")).to_contain_text(name, timeout=10000)


def test_playing_a_track_shows_the_player_bar(browser):
    from playwright.sync_api import expect

    page = _login(browser.new_context())
    card = page.locator(".track-grid article").nth(0)
    title = card.locator("strong").inner_text()
    card.locator("button.cover").click()
    expect(page.locator(".player .now-playing")).to_contain_text(title, timeout=10000)
    time.sleep(1)
    paused = page.evaluate("() => document.querySelector('audio')?.paused")
    assert paused is False


def test_logout_returns_to_the_login_screen(browser):
    from playwright.sync_api import expect

    page = _login(browser.new_context())
    page.locator(".nav-item", has_text="Perfil").click()
    page.get_by_text("Cerrar sesión").click()
    expect(page.locator("input[autocomplete='username']")).to_be_visible(timeout=10000)


def test_library_has_no_horizontal_scroll_on_a_phone(browser):
    page = _login(browser.new_context(viewport={"width": 390, "height": 844}))
    overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"page scrolls sideways by {overflow}px at 390px wide"
