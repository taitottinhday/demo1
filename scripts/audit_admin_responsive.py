"""Browser regression check for responsive admin tabs on an isolated local app.

The demo-login POST is deliberately restricted to localhost so this script can
never create a session on a hosted deployment.
"""

import argparse
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

VIEWPORTS = [(360, 800), (390, 844), (768, 1024), (1024, 768), (1440, 900)]


def audit(base_url: str, browser_path: str | None) -> None:
    host = urlparse(base_url).hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Chỉ chạy audit demo trên ứng dụng local (localhost/127.0.0.1).")

    with sync_playwright() as playwright:
        options = {"headless": True}
        if browser_path:
            options["executable_path"] = browser_path
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(f"{base_url}/admin", wait_until="domcontentloaded")

        # This endpoint only issues an isolated demo session on the local app.
        response = page.request.post(f"{base_url}/api/v1/demo/admin")
        assert response.ok, f"Local admin demo login returned HTTP {response.status}"
        page.reload(wait_until="domcontentloaded")
        dashboard = page.locator("#dashboard")
        expect(dashboard).to_be_visible(timeout=10000)
        tabs = page.locator(".admin-tabs [role=tab]")
        expect(tabs).to_have_count(4)

        for width, height in VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            metrics = page.evaluate(
                """() => {
                  const nav = document.querySelector('.admin-tabs');
                  const tabs = [...nav.querySelectorAll('[role=tab]')];
                  return {
                    viewport: innerWidth,
                    document: document.documentElement.scrollWidth,
                    body: document.body.scrollWidth,
                    nav: {left: nav.getBoundingClientRect().left,
                          right: nav.getBoundingClientRect().right,
                          clientWidth: nav.clientWidth,
                          scrollWidth: nav.scrollWidth},
                    tabs: tabs.map(tab => {
                      const rect = tab.getBoundingClientRect();
                      return {name: tab.innerText.trim(), left: rect.left,
                              right: rect.right, visible: rect.width > 0 && rect.height > 0};
                    })
                  };
                }"""
            )
            assert metrics["document"] <= width + 1, f"document tràn ngang {width}x{height}: {metrics}"
            assert metrics["body"] <= width + 1, f"body tràn ngang {width}x{height}: {metrics}"
            assert metrics["nav"]["left"] >= -1 and metrics["nav"]["right"] <= width + 1, (
                f"tablist vượt viewport {width}x{height}: {metrics}"
            )
            assert metrics["nav"]["scrollWidth"] <= metrics["nav"]["clientWidth"] + 1, (
                f"tab bị cắt trong tablist {width}x{height}: {metrics}"
            )
            assert all(tab["visible"] and tab["left"] >= -1 and tab["right"] <= width + 1
                       for tab in metrics["tabs"]), f"tab không nhìn thấy {width}x{height}: {metrics}"

        # Native button tabs must remain keyboard operable with a visible focus ring.
        tickets = page.locator('.admin-tabs [data-tab="tickets"]')
        tickets.focus()
        focus = tickets.evaluate(
            "el => ({style: getComputedStyle(el).outlineStyle, width: getComputedStyle(el).outlineWidth})"
        )
        assert focus["style"] != "none" and float(focus["width"].replace("px", "")) >= 2, (
            f"Tab không có focus ring rõ: {focus}"
        )
        page.keyboard.press("Enter")
        expect(tickets).to_have_attribute("aria-selected", "true")
        expect(page.locator("#tab-tickets")).to_be_visible()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--browser", default=None)
    args = parser.parse_args()
    audit(args.url.rstrip("/"), args.browser)
    print("Admin responsive/keyboard audit passed at 360, 390, 768, 1024 and 1440 px.")


if __name__ == "__main__":
    main()
