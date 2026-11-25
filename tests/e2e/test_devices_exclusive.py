"""Browser test: one account on two devices plays one track at a time.

Same environment as test_jam_flow.py (AURALITH_E2E_URL, AURALITH_E2E_PASSWORD).
"""

import os
import time

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


def _audio_paused(page):
    return page.evaluate("() => document.querySelector('audio')?.paused")


def test_starting_playback_on_one_device_pauses_the_other():
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            first = _login(browser.new_context())
            second = _login(browser.new_context())
            devices = ".nav-item"
            first.locator(devices, has_text="Dispositivos").click()
            second.locator(devices, has_text="Dispositivos").click()
            expect(first.locator(".devices-panel")).to_contain_text("este dispositivo", timeout=15000)
            expect(second.locator(".devices-panel")).to_contain_text("este dispositivo", timeout=15000)

            first.get_by_role("button", name="Inicio").click()
            first.locator(".track-grid article").nth(0).locator("button.cover").click()
            time.sleep(2)
            assert _audio_paused(first) is False

            second.get_by_role("button", name="Inicio").click()
            second.locator(".track-grid article").nth(1).locator("button.cover").click()
            time.sleep(3)
            assert _audio_paused(second) is False
            assert _audio_paused(first) is True

            # Both panels agree: exactly one device is playing.
            time.sleep(2)
            states = second.locator(".devices-panel .device-info span").all_inner_texts()
            assert len([state for state in states if state.startswith("Sonando")]) == 1, states
        finally:
            browser.close()
