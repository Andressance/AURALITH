"""Browser test of the jam flow across two sessions of the same account.

Needs a running API and web app, plus Playwright with a Chromium channel:

    AURALITH_E2E_URL=http://localhost:5173 AURALITH_E2E_PASSWORD=... python -m pytest tests/e2e

Skipped unless both variables are set, so the default test run never needs a browser.
The account needs at least two tracks in its library.
"""

import os

import pytest

E2E_URL = os.getenv("AURALITH_E2E_URL", "").rstrip("/")
E2E_PASSWORD = os.getenv("AURALITH_E2E_PASSWORD", "")

pytestmark = pytest.mark.skipif(
    not (E2E_URL and E2E_PASSWORD), reason="set AURALITH_E2E_URL and AURALITH_E2E_PASSWORD"
)


def _login(context):
    page = context.new_page()
    page.goto(f"{E2E_URL}/")
    page.fill("input[autocomplete='username']", "owner")
    page.fill("input[autocomplete='current-password']", E2E_PASSWORD)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_selector(".track-grid article", timeout=20000)
    return page


def test_jam_plays_and_queues_for_both_members():
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            host = _login(browser.new_context())
            host.get_by_role("button", name="Jam").click()
            host.get_by_role("button", name="Crear jam").click()
            code = host.locator(".jam-code strong").inner_text(timeout=10000).strip()

            guest = _login(browser.new_context())
            guest.get_by_role("button", name="Jam").click()
            guest.fill(".jam-start input", code)
            guest.get_by_role("button", name="Entrar", exact=True).click()
            expect(guest.locator(".jam-people")).to_contain_text("owner", timeout=10000)

            # Playing from the library makes the track the jam's current one for both.
            host.get_by_role("button", name="Inicio").click()
            host.locator(".track-grid article").nth(0).locator("button.cover").click()
            host.get_by_role("button", name="Jam").click()
            title = host.locator(".jam-now-text strong").inner_text(timeout=10000)
            expect(guest.locator(".jam-now-text strong")).to_have_text(title, timeout=10000)

            # A track queued as next appears in both queues, and skipping removes it.
            host.get_by_role("button", name="Inicio").click()
            card = host.locator(".track-grid article").nth(1)
            card.hover()
            card.locator("button[aria-label='Reproducir después']").click()
            host.get_by_role("button", name="Jam").click()
            queue = ".jam-panel >> nth=0 >> .jam-row"
            expect(host.locator(queue)).to_have_count(1, timeout=10000)
            expect(guest.locator(queue)).to_have_count(1, timeout=10000)
            guest.get_by_role("button", name="⏭ Siguiente").click()
            expect(host.locator(queue)).to_have_count(0, timeout=10000)
            expect(guest.locator(queue)).to_have_count(0, timeout=10000)
        finally:
            browser.close()
