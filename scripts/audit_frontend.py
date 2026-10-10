"""Responsive/accessibility smoke audit for the public frontend.

The backend must be running before this command:

    python -m scripts.audit_frontend --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
"""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

VIEWPORTS = [
    (1366, 768),
    (1440, 900),
    (1280, 1024),
    (768, 1024),
    (390, 844),
]


def assert_no_horizontal_scroll(page, label):
    values = page.evaluate(
        """() => ({
          viewport: window.innerWidth,
          document: document.documentElement.scrollWidth,
          body: document.body.scrollWidth
        })"""
    )
    assert values["document"] <= values["viewport"] + 1, f"{label}: document tràn ngang {values}"
    assert values["body"] <= values["viewport"] + 1, f"{label}: body tràn ngang {values}"


def assert_visible_controls_have_names(page, label):
    missing_inputs = page.locator("input:visible, textarea:visible, select:visible").evaluate_all(
        """els => els.filter(el => {
          if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return false;
          if (el.labels && el.labels.length) return false;
          return !el.closest('label');
        }).map(el => el.id || el.name || el.tagName)"""
    )
    assert not missing_inputs, f"{label}: input chưa có label {missing_inputs}"

    missing_buttons = page.locator("button:visible").evaluate_all(
        """els => els.filter(el => {
          const name = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
          return !name;
        }).map(el => el.id || el.className || 'button')"""
    )
    assert not missing_buttons, f"{label}: button chưa có accessible name {missing_buttons}"


def assert_source_status_ready(page):
    status = page.locator("#source-status")
    expect(status).to_contain_text("PDF có thể tra cứu", timeout=20000)
    expect(status).to_contain_text("chương trình", timeout=20000)


def audit_applicant(page, base_url, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
    assert_source_status_ready(page)
    assert_no_horizontal_scroll(page, f"ứng viên {width}x{height}")
    assert_visible_controls_have_names(page, f"ứng viên {width}x{height}")

    if width <= 900:
        page.locator("#program-tools-open").click()
        expect(page.locator("#program-tools.mobile-open")).to_be_visible()
    page.fill("#program-search", "IT1")
    page.keyboard.press("Enter")
    expect(page.locator("#program")).to_have_value("IT1")
    if width <= 900:
        page.locator("#program-tools-close").click()
        expect(page.locator("#program-tools")).not_to_be_visible()
    suggestions = page.locator("#follow-up .small-action")
    expect(suggestions).to_have_count(3)
    for suggestion in suggestions.all():
        expect(suggestion).to_be_visible()
        assert suggestion.bounding_box()["height"] >= 28
    page.get_by_role("button", name="Học phí IT1").click()
    expect(page.locator("#question")).to_have_value("Học phí IT1 là bao nhiêu?")
    assert_no_horizontal_scroll(page, f"gợi ý thí sinh {width}x{height}")

    history = page.locator("#messages")
    assert history.evaluate("el => ['auto', 'scroll'].includes(getComputedStyle(el).overflowY)")
    chat = page.locator(".chat-shell")
    assert chat.bounding_box()["height"] <= height + 2

    if width <= 900:
        expect(page.locator("#program-tools-open")).to_be_visible()
        page.locator("#program-tools-open").click()
        assert "mobile-open" in (page.locator("#program-tools").get_attribute("class") or "")
        page.locator("#program-tools-close").click()
        expect(page.locator("#program-tools")).not_to_be_visible()
        for button in page.locator(".topics button").all():
            assert button.bounding_box()["height"] >= 40
        question_box = page.locator("#question").bounding_box()
        assert question_box["y"] + question_box["height"] <= height + 3, f"chat input bị khuất: {question_box}"


def audit_auth_page(page, url, label, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    assert_no_horizontal_scroll(page, f"{label} {width}x{height}")
    assert_visible_controls_have_names(page, f"{label} {width}x{height}")


def audit_keyboard_and_compare(page, base_url):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
    assert_source_status_ready(page)
    page.locator("#compare-open").click()
    page.locator("#compare-submit").click()
    expect(page.locator("#compare-error")).to_contain_text("ít nhất 2")
    assert page.locator("#compare-0").evaluate("el => document.activeElement === el")
    page.select_option("#compare-0", "IT1")
    page.select_option("#compare-1", "IT1")
    page.locator("#compare-submit").click()
    expect(page.locator("#compare-error")).to_contain_text("trùng")
    page.locator("#compare-reset").click()
    expect(page.locator("#comparison-result")).to_be_empty()
    assert page.locator("#compare-0").evaluate("el => document.activeElement === el")
    page.locator('[data-close="compare-dialog"]').click()

    page.locator("#program-search").fill("IT1")
    page.keyboard.press("Enter")
    expect(page.locator("#program")).to_have_value("IT1")
    page.locator("#question").focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement && document.activeElement !== document.body")
    assert page.locator("[aria-live]").count() >= 3

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
    assert_source_status_ready(page)
    page.locator("#program-tools-open").focus()
    page.keyboard.press("Enter")
    assert "mobile-open" in (page.locator("#program-tools").get_attribute("class") or "")
    page.keyboard.press("Escape")
    expect(page.locator("#program-tools")).not_to_be_visible()


def run(base_url, browser_path):
    with sync_playwright() as playwright:
        launch_options = {"headless": True}
        if browser_path:
            launch_options["executable_path"] = browser_path
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        for width, height in VIEWPORTS:
            audit_applicant(page, base_url, width, height)
        audit_keyboard_and_compare(page, base_url)
        for width, height in ((1440, 900), (390, 844)):
            audit_auth_page(page, f"{base_url}/staff", "staff", width, height)
            audit_auth_page(page, f"{base_url}/admin", "admin", width, height)
            audit_auth_page(page, f"{base_url}/account", "account", width, height)
            audit_auth_page(page, f"{base_url}/staff/activate", "staff-activate", width, height)
        assert not page_errors, f"Lỗi JavaScript: {page_errors}"
        browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--browser", default=None)
    args = parser.parse_args()
    if args.browser and not Path(args.browser).exists():
        raise SystemExit(f"Không tìm thấy browser: {args.browser}")
    run(args.url.rstrip("/"), args.browser)
    print("Responsive/accessibility/keyboard audit passed for 5 applicant viewports and staff/admin checks.")


if __name__ == "__main__":
    main()
