"""Optional UI smoke test. Install playwright separately; server must already run.

python -m scripts.check_browser --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
"""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from src.config import get_settings


def run(base_url, browser_path):
    cfg = get_settings()
    output = Path("data/processed/demo")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=browser_path, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base_url)
        expect(page.locator("#source-status")).to_contain_text("51 trang", timeout=20000)
        page.click("#compare-open")
        page.select_option("#compare-0", "IT1")
        page.select_option("#compare-1", "ITE10")
        page.click("#compare-submit")
        expect(page.locator(".comparison-table")).to_contain_text("28 - 40")
        expect(page.locator(".comparison-table")).to_contain_text("IELTS Academic 5.0")
        page.locator('[data-close="compare-dialog"]').click()
        page.screenshot(path=str(output / "applicant-desktop.png"), full_page=True)
        page.click("#guide-open")
        expect(page.locator("#guide-content input[type=checkbox]")).to_have_count(3)
        page.locator('[data-close="guide-dialog"]').click()
        page.select_option("#program", "IT1")
        page.locator("#follow-up").get_by_role("button", name="Học phí IT1").click()
        expect(page.locator("#question")).to_have_value("Học phí IT1 là bao nhiêu?")
        page.fill("#question", "IT1 có chỉ tiêu bao nhiêu?")
        page.click("#send")
        expect(page.locator(".assistant .body").last).to_contain_text("300", timeout=20000)
        page.fill("#question", "Học phí bao nhiêu?")
        page.click("#send")
        expect(page.locator(".assistant .body").last).to_contain_text("28 - 40", timeout=20000)
        earlier = page.locator(".message.assistant").first
        earlier.get_by_role("button", name="Chưa đúng", exact=True).click()
        expect(earlier.get_by_role("button", name="Chưa đúng", exact=True)).to_have_attribute("aria-pressed", "true")
        earlier.get_by_role("button", name="Chuyển câu hỏi này cho cán bộ ↗", exact=True).click()
        assert "IT1 có chỉ tiêu bao nhiêu?" in page.locator("#summary").input_value()
        assert "300" in page.locator("#summary").input_value()
        page.locator('[data-close="handover-dialog"]').click()
        page.fill("#question", "Tôi có chắc chắn trúng tuyển không?")
        page.click("#send")
        expect(page.locator(".assistant .body").last).to_contain_text("không thể cam kết", timeout=20000)
        page.click("#handover-open")
        page.fill("#summary", "DEMO UI: Cần cán bộ kiểm tra trường hợp cá nhân, không yêu cầu cam kết.")
        page.check("#consent")
        page.click("#handover-send")
        expect(page.locator("#tickets .ticket-card")).to_have_count(1)
        ticket = page.locator("#tickets .ticket-head b").inner_text()
        page.locator('[data-close="track-dialog"]').click()
        staff = context.new_page()
        staff.goto(base_url + "/staff")
        staff.fill("#username", cfg.staff_username)
        staff.fill("#password", cfg.staff_password)
        staff.get_by_role("button", name="Đăng nhập →").click()
        expect(staff.locator("#dashboard")).to_be_visible()
        staff.fill("#queue-search", ticket.lower())
        expect(staff.locator(".queue-item")).to_have_count(1)
        staff.select_option("#queue-sort", "oldest")
        staff.fill("#queue-search", "")
        staff.locator(".queue-item").filter(has_text=ticket).click()
        staff.get_by_role("button", name="Nhận xử lý →").click()
        expect(staff.locator("#reply")).to_be_visible()
        staff.fill("#reply", "Phản hồi demo: Cán bộ sẽ kiểm tra hồ sơ theo quy định; không cam kết kết quả tuyển sinh.")
        staff.get_by_role("button", name="Gửi phản hồi & đóng yêu cầu →").click()
        expect(staff.locator("#detail .badge")).to_have_text("Đã giải quyết")
        staff.screenshot(path=str(output / "staff-desktop.png"), full_page=True)
        page.evaluate('checkReplies()')
        expect(page.locator('#reply-unread')).to_contain_text('1 phản hồi mới')
        page.click('#track-open')
        page.click("#refresh-tickets")
        expect(page.locator('#reply-unread')).to_be_hidden()
        expect(page.locator("#tickets .badge")).to_have_text("Đã giải quyết")
        expect(page.locator("#tickets .reply-box")).to_contain_text("Phản hồi demo")
        # Exercise the candidate cancellation and staff rejection controls with fresh tickets.
        for action in ["cancel", "reject"]:
            created = page.evaluate(
                """async action => {
                const response = await fetch('/api/v1/handover', {method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({summary:'DEMO UI: '+action,consent:true,request_key:crypto.randomUUID()})});
                if(!response.ok)throw new Error('Cannot create demo ticket');return response.json();
            }""",
                action,
            )
            page.click("#refresh-tickets")
            card = page.locator("#tickets .ticket-card").filter(has_text=created["id"])
            if action == "cancel":
                page.once("dialog", lambda dialog: dialog.accept())
                card.get_by_role("button", name="Hủy yêu cầu").click()
                expect(card.locator(".badge")).to_have_text("Đã hủy")
            else:
                staff.click("#refresh")
                staff.locator(".queue-item").filter(has_text=created["id"]).click()
                staff.get_by_role("button", name="Ngoài phạm vi", exact=True).click()
                expect(staff.locator("#reject-reason")).to_have_value(
                    "Nội dung không thuộc phạm vi tư vấn tuyển sinh HUST."
                )
                staff.once("dialog", lambda dialog: dialog.accept())
                staff.get_by_role("button", name="Từ chối yêu cầu").click()
                expect(staff.locator("#detail .badge")).to_have_text("Đã từ chối")
                page.click("#refresh-tickets")
                expect(card.locator(".badge")).to_have_text("Đã từ chối")
                expect(card.locator(".reply-box")).to_contain_text("không thuộc phạm vi")
        page.locator('[data-close="track-dialog"]').click()
        page.reload()
        expect(page.locator("#program")).to_have_value("IT1")
        expect(page.locator(".assistant .body").last).to_contain_text("không thể cam kết")
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        m = mobile.new_page()
        m.goto(base_url)
        expect(m.locator("#source-status")).to_contain_text("51 trang", timeout=20000)
        assert m.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        m.screenshot(path=str(output / "applicant-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print("UI passed: desktop + mobile, chat, source, handover, reply, cancellation, rejection, persistence.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--browser", required=True)
    args = parser.parse_args()
    run(args.url, args.browser)
