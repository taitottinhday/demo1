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
        page.set_viewport_size({"width": 1366, "height": 768})
        page.evaluate(
            """() => {
            const message = document.createElement('article');
            message.className = 'message assistant';
            message.dataset.b14 = 'true';
            message.innerHTML = '<span class="speaker">Nguồn kiểm thử</span>'
                + '<div class="body">Câu trả lời dài để kiểm tra vùng cuộn lịch sử.</div>'
                + '<details class="source-card" open><summary>Trích dẫn nguồn</summary>'
                + '<div class="quote">' + 'Source line '.repeat(120) + '</div></details>';
            document.querySelector('#messages').append(message);
            }"""
        )
        b14_metrics = page.evaluate(
            """() => {
            const sidebar = document.querySelector('.sidebar');
            const chat = document.querySelector('.chat-scroll');
            const quote = document.querySelector('[data-b14] .source-card .quote');
            const composer = document.querySelector('.composer-area').getBoundingClientRect();
            const workspace = document.querySelector('.workspace').getBoundingClientRect();
            const quoteStyle = getComputedStyle(quote);
            return {
                documentHorizontalFit: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
                sidebarHorizontalFit: sidebar.scrollWidth <= sidebar.clientWidth,
                chatCanScroll: chat.scrollHeight > chat.clientHeight,
                quoteOwnsScroll: quote.scrollHeight > quote.clientHeight
                    && ['auto', 'scroll'].includes(quoteStyle.overflowY),
                composerAtBottom: Math.abs(composer.bottom - workspace.bottom) <= 1
            };
            }"""
        )
        assert b14_metrics == {
            "documentHorizontalFit": True,
            "sidebarHorizontalFit": True,
            "chatCanScroll": True,
            "quoteOwnsScroll": False,
            "composerAtBottom": True,
        }
        page.evaluate("document.querySelector('[data-b14]')?.remove()")
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.click("#compare-open")
        page.click("#compare-submit")
        expect(page.locator("#compare-error")).to_contain_text("ít nhất 2")
        assert page.locator("#compare-0").evaluate("e => document.activeElement === e")
        page.select_option("#compare-0", "IT1")
        page.select_option("#compare-1", "IT1")
        page.click("#compare-submit")
        expect(page.locator("#compare-error")).to_contain_text("trùng")
        expect(page.locator("#compare-0")).to_have_value("IT1")
        expect(page.locator("#compare-1")).to_have_value("IT1")
        page.click("#compare-reset")
        expect(page.locator("#compare-0")).to_have_value("")
        expect(page.locator("#comparison-result")).to_be_empty()
        page.select_option("#compare-0", "IT1")
        page.select_option("#compare-1", "ITE10")
        page.click("#compare-submit")
        expect(page.locator(".comparison-table")).to_contain_text("28 - 40")
        expect(page.locator(".comparison-table")).to_contain_text("IELTS Academic 5.0")
        expect(page.locator("#comparison-result")).to_contain_text("Trợ lý tổng hợp")
        expect(page.locator("#comparison-result")).to_contain_text("xếp hạng chương trình")
        page.select_option("#compare-2", "BF1")
        expect(page.locator("#compare-stale")).to_be_visible()
        page.click("#compare-reset")
        expect(page.locator("#comparison-result")).to_be_empty()
        page.select_option("#compare-0", "IT1")
        page.select_option("#compare-1", "ITE10")
        page.click("#compare-submit")
        expect(page.locator("#comparison-result")).to_contain_text("Trợ lý tổng hợp")
        page.click("#compare-reset")
        page.select_option("#compare-0", "IT1")
        page.select_option("#compare-1", "IT2")
        page.click("#compare-submit")
        expect(page.locator(".comparison-table")).to_contain_text("không nêu")
        expect(page.locator(".comparison-table a").filter(has_text="PDF trang 16")).to_have_count(2)
        missing_block = page.locator(".comparison-assistant .comparison-summary-block").nth(2)
        expect(missing_block).to_contain_text("Không phát hiện trường dữ liệu thiếu")
        assert "IT1" not in missing_block.inner_text()
        assert "Ngoại ngữ đầu vào" not in missing_block.inner_text()
        page.locator('[data-close="compare-dialog"]').click()
        page.screenshot(path=str(output / "applicant-desktop.png"), full_page=True)
        page.click("#guide-open")
        expect(page.locator("#guide-content input[type=checkbox]")).to_have_count(3)
        page.locator('[data-close="guide-dialog"]').click()
        page.fill("#program-search", "IT1")
        page.keyboard.press("Enter")
        expect(page.locator("#program")).to_have_value("IT1")
        expect(page.locator("#program-scope")).to_be_visible()
        expect(page.locator("#program-scope-label")).to_contain_text("IT1")
        assert page.locator("#program optgroup").count() > 0
        program_name = page.locator("#program option[value='IT1']").inner_text().split(" · ", 1)[-1]
        page.fill("#program-search", program_name)
        page.keyboard.press("Enter")
        expect(page.locator("#program")).to_have_value("IT1")
        assistant_count = page.locator(".message.assistant").count()
        page.locator("#follow-up").get_by_role("button", name="Học phí IT1").click()
        expect(page.locator("#question")).to_have_value("Học phí IT1 là bao nhiêu?")
        expect(page.locator("#question-status")).to_have_text("Đã điền câu hỏi — nhấn Gửi để tra cứu")
        assert page.locator(".message.assistant").count() == assistant_count
        assert page.locator("#follow-up button").count() == len(set(page.locator("#follow-up button").all_text_contents()))
        page.click("#program-clear")
        expect(page.locator("#program")).to_have_value("")
        expect(page.locator("#program-scope")).to_be_hidden()
        page.fill("#program-search", "IT1")
        page.keyboard.press("Enter")
        page.fill("#question", "IT1 có chỉ tiêu bao nhiêu?")
        page.click("#send")
        expect(page.locator(".message.assistant").last).to_contain_text("300", timeout=20000)
        page.fill("#question", "Học phí bao nhiêu?")
        page.click("#send")
        expect(page.locator(".message.assistant").last).to_contain_text("28 - 40", timeout=20000)
        earlier = page.locator(".message.assistant").first
        earlier.get_by_role("button", name="Chưa đúng", exact=True).click()
        expect(earlier.get_by_role("button", name="Chưa đúng", exact=True)).to_have_attribute("aria-pressed", "true")
        earlier.get_by_role("button", name="Chuyển câu hỏi này cho cán bộ ↗", exact=True).click()
        expect(page.locator("#handover-question-preview")).to_contain_text("IT1 có chỉ tiêu bao nhiêu?")
        expect(page.locator("#handover-answer-preview")).to_contain_text("300")
        expect(page.locator("#handover-sources-preview")).to_contain_text("PDF trang")
        assert page.locator("#summary").input_value() == ""
        page.locator('[data-close="handover-dialog"]').click()
        page.fill("#question", "Tôi có chắc chắn trúng tuyển không?")
        page.click("#send")
        expect(page.locator(".message.assistant").last).to_contain_text("không thể cam kết", timeout=20000)
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
        staff.get_by_role("button", name="Đăng nhập", exact=True).click()
        expect(staff.locator("#dashboard")).to_be_visible()
        staff.fill("#queue-search", ticket.lower())
        expect(staff.locator(".queue-item")).to_have_count(1)
        # Claiming from the default waiting filter must switch to the new
        # status so the ticket remains selected and the reply form is shown.
        staff.locator(".queue-item").filter(has_text=ticket).click()
        staff.get_by_role("button", name="Nhận xử lý ticket →").click()
        expect(staff.locator("#status-filter")).to_have_value("in_progress")
        expect(staff.locator("#staff-reply")).to_be_visible()
        staff.fill("#queue-search", "__khong-co-ticket__")
        expect(staff.locator(".queue-empty strong")).to_have_text("Không tìm thấy ticket")
        expect(staff.locator("#clear-search")).to_be_visible()
        expect(staff.locator("#clear-filter")).to_be_visible()
        staff.locator("#clear-filter").click()
        expect(staff.locator("#status-filter")).to_have_value("")
        staff.locator("#clear-search").click()
        expect(staff.locator("#queue-search")).to_have_value("")
        expect(staff.locator(".queue-item")).to_have_count(1)
        staff.select_option("#queue-sort", "oldest")
        staff.locator(".queue-item").filter(has_text=ticket).click()
        expect(staff.locator("#staff-reply")).to_be_visible()
        draft = "Bản nháp demo: Cán bộ sẽ kiểm tra hồ sơ theo quy định."
        staff.fill("#staff-reply", draft)
        staff.wait_for_timeout(5500)
        expect(staff.locator("#staff-reply")).to_have_value(draft)
        staff.fill("#staff-reply", "Phản hồi demo: Cán bộ sẽ kiểm tra hồ sơ theo quy định; không cam kết kết quả tuyển sinh.")
        staff.get_by_role("button", name="Gửi phản hồi và đóng").click()
        expect(staff.locator("#detail .badge")).to_have_text("Đã giải quyết")
        staff.screenshot(path=str(output / "staff-desktop.png"), full_page=True)

        mobile_staff_context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mobile_staff = mobile_staff_context.new_page()
        mobile_staff.goto(base_url + "/staff")
        mobile_staff.fill("#username", cfg.staff_username)
        mobile_staff.fill("#password", cfg.staff_password)
        mobile_staff.get_by_role("button", name="Đăng nhập", exact=True).click()
        expect(mobile_staff.locator("#dashboard")).to_be_visible()
        mobile_staff.select_option("#status-filter", "")
        mobile_staff.fill("#queue-search", ticket.lower())
        expect(mobile_staff.locator(".queue-item")).to_have_count(1)
        expect(mobile_staff.locator(".queue-item .ticket-id")).to_be_visible()
        expect(mobile_staff.locator(".queue-item .badge")).to_be_visible()
        expect(mobile_staff.locator(".queue-item .ticket-owner")).to_be_visible()
        expect(mobile_staff.locator(".queue-item-action")).to_be_visible()
        assert mobile_staff.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        mobile_staff_context.close()
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
                staff.fill("#reject-reason", "Nội dung không thuộc phạm vi tư vấn tuyển sinh HUST.")
                staff.once("dialog", lambda dialog: dialog.accept())
                staff.get_by_role("button", name="Từ chối yêu cầu").click()
                expect(staff.locator("#detail .badge")).to_have_text("Đã từ chối")
                page.click("#refresh-tickets")
                expect(card.locator(".badge")).to_have_text("Đã từ chối")
                expect(card.locator(".reply-box")).to_contain_text("không thuộc phạm vi")
        page.locator('[data-close="track-dialog"]').click()
        page.reload()
        expect(page.locator("#program")).to_have_value("IT1")
        expect(page.locator(".message.assistant").last).to_contain_text("không thể cam kết")

        admin = context.new_page()
        admin.add_init_script(
            """(() => {
            const originalFetch = window.fetch.bind(window);
            window.__delayAdminOldFilter = false;
            window.fetch = (...args) => {
                const url = new URL(args[0], window.location.href);
                if (window.__delayAdminOldFilter
                    && url.pathname.endsWith('/api/v1/admin/tickets')
                    && url.searchParams.get('status') === 'in_progress') {
                    return originalFetch(...args).then(response => new Promise(resolve => {
                        window.setTimeout(() => resolve(response), 300);
                    }));
                }
                return originalFetch(...args);
            };
            })();"""
        )
        admin.goto(base_url + "/admin")
        admin.fill("#username", cfg.admin_username)
        admin.fill("#password", cfg.admin_password)
        admin.get_by_role("button", name="Đăng nhập →", exact=True).click()
        expect(admin.locator("#dashboard")).to_be_visible()
        expect(admin.locator("#metrics .kpi-card").first).to_contain_text("Công thức:")
        expect(admin.locator("#metrics .kpi-card").first).to_contain_text("Tử số / mẫu số:")
        expect(admin.locator("#data-note")).to_contain_text("Nguồn dữ liệu:")
        assert "chat_logs" not in admin.locator("body").inner_text()
        duration_values = admin.evaluate(
            """() => ({
            zero: duration(0),
            twentyThreeSeconds: duration(23),
            fiftyNineSeconds: duration(59),
            oneMinute: duration(60),
            nearHour: duration(3599),
            oneHour: duration(3600)
            })"""
        )
        assert duration_values == {
            "zero": "0 phút",
            "twentyThreeSeconds": "23 giây",
            "fiftyNineSeconds": "59 giây",
            "oneMinute": "1 phút",
            "nearHour": "59 phút",
            "oneHour": "1.0 giờ",
        }
        assert duration_values["twentyThreeSeconds"] != "0 phút"
        assert duration_values["fiftyNineSeconds"] != "0 phút"
        admin.fill("#from", "2026-01-01")
        admin.fill("#to", "2026-12-31")
        admin.click("#refresh")
        expect(admin.locator("#from")).to_have_value("2026-01-01")
        expect(admin.locator("#to")).to_have_value("2026-12-31")
        admin.get_by_role("tab", name="Ticket", exact=True).click()
        probe_ticket = page.evaluate(
            """async () => {
            const response = await fetch('/api/v1/handover', {method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({summary:'DEMO UI: admin filter regression',consent:true,request_key:crypto.randomUUID()})});
            if(!response.ok)throw new Error('Cannot create admin filter regression ticket');return response.json();
            }"""
        )
        staff.fill("#queue-search", probe_ticket["id"].lower())
        staff.click("#refresh")
        expect(staff.locator(".queue-item")).to_have_count(1)
        staff.locator(".queue-item").first.click()
        staff.get_by_role("button", name="Nhận xử lý ticket →", exact=True).click()
        expect(staff.locator("#detail .badge")).to_have_text("Đang xử lý")
        admin.click("#refresh")
        admin.select_option("#status-filter", "in_progress")
        expect(admin.locator("#ticket-rows tr.clickable").first).to_be_visible()
        regression_id = admin.locator("#ticket-rows tr.clickable").first.locator("td").first.inner_text()
        admin.locator("#ticket-rows tr.clickable").first.click()
        expect(admin.locator("#detail")).to_contain_text(regression_id)
        admin_officers = admin.evaluate(
            """async () => (await (await fetch('/api/v1/admin/officers')).json()).filter(o => o.active)"""
        )
        empty_filter_officer = next(o for o in admin_officers if o["open_tickets"] == 0)
        admin.evaluate("window.__delayAdminOldFilter = true")
        admin.select_option("#status-filter", "in_progress")
        admin.select_option("#officer-filter", str(empty_filter_officer["id"]))
        admin.select_option("#status-filter", "waiting")
        expect(admin.locator("#ticket-rows tr.clickable")).to_have_count(0)
        expect(admin.locator("#detail")).to_contain_text("Không có ticket phù hợp")
        assert regression_id not in admin.locator("#detail").inner_text()
        assert admin.locator("#detail .timeline").count() == 0
        admin.wait_for_timeout(500)
        expect(admin.locator("#ticket-rows tr.clickable")).to_have_count(0)
        admin.evaluate("window.__delayAdminOldFilter = false")
        admin.select_option("#officer-filter", "")
        admin.select_option("#status-filter", "")
        expect(admin.locator("#detail")).to_contain_text("Chưa có ticket được chọn")
        admin.get_by_role("tab", name="Cán bộ", exact=True).click()
        aria_name = admin.locator("#officer-rows input[type=checkbox]").first.get_attribute("aria-label")
        assert aria_name and ("Tài khoản cán bộ" in aria_name or "Khóa tài khoản cán bộ" in aria_name)
        admin_mobile_context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        admin_mobile = admin_mobile_context.new_page()
        admin_mobile.goto(base_url + "/admin")
        admin_mobile.fill("#username", cfg.admin_username)
        admin_mobile.fill("#password", cfg.admin_password)
        admin_mobile.get_by_role("button", name="Đăng nhập →", exact=True).click()
        expect(admin_mobile.locator("#dashboard")).to_be_visible()
        admin_mobile.get_by_role("tab", name="Cán bộ", exact=True).click()
        expect(admin_mobile.locator("#officer-rows .officer-card").first).to_be_visible()
        assert admin_mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        admin_mobile_context.close()
        for drawer_width, drawer_height in [(390, 844), (375, 812), (320, 700)]:
            drawer_context = browser.new_context(
                viewport={"width": drawer_width, "height": drawer_height}, is_mobile=True, has_touch=True
            )
            drawer_page = drawer_context.new_page()
            drawer_page.goto(base_url)
            drawer_page.locator("#program-tools-open").click()
            expect(drawer_page.locator("#program-tools.mobile-open")).to_be_visible()
            drawer_page.wait_for_timeout(300)
            drawer_metrics = drawer_page.evaluate(
                """() => {
                const drawer = document.querySelector('#program-tools');
                const rect = drawer.getBoundingClientRect();
                const visual = [...drawer.querySelectorAll('*')].map(element => {
                    const box = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return {left: box.left, right: box.right, width: box.width, height: box.height,
                        scrollWidth: element.scrollWidth, clientWidth: element.clientWidth,
                        visibility: style.visibility};
                }).filter(item => item.width > 1 && item.height > 1 && item.visibility !== 'hidden');
                return {
                    pageWidth: document.documentElement.scrollWidth,
                    clientWidth: document.documentElement.clientWidth,
                    drawerWidth: drawer.clientWidth,
                    drawerScrollWidth: drawer.scrollWidth,
                    drawerLeft: rect.left,
                    drawerRight: rect.right,
                    visualOverflow: visual.some(item => item.left < rect.left - .5 || item.right > rect.right + .5
                        || item.scrollWidth > item.clientWidth + .5)
                };
                }"""
            )
            assert drawer_metrics["pageWidth"] <= drawer_metrics["clientWidth"]
            assert drawer_metrics["drawerScrollWidth"] <= drawer_metrics["drawerWidth"] + 1
            assert 0 <= drawer_metrics["drawerLeft"] and drawer_metrics["drawerRight"] <= drawer_width + 0.5
            assert not drawer_metrics["visualOverflow"]
            assert drawer_page.evaluate("document.activeElement === document.querySelector('#program-search')")
            drawer_page.evaluate("document.querySelector('#program-tools .topics').style.minHeight='900px'")
            drawer_page.evaluate("document.querySelector('#program-tools').scrollTop=9999")
            assert drawer_page.evaluate(
                "document.querySelector('#program-tools').scrollTop > 0 && "
                "document.querySelector('#program-tools').scrollHeight > document.querySelector('#program-tools').clientHeight"
            )
            drawer_page.locator("#program-tools-close").click()
            assert drawer_page.evaluate(
                "!document.body.classList.contains('sidebar-open') && "
                "document.activeElement === document.querySelector('#program-tools-open')"
            )
            drawer_page.locator("#program-tools-open").click()
            drawer_page.wait_for_timeout(300)
            drawer_page.keyboard.press("Escape")
            assert drawer_page.evaluate(
                "!document.body.classList.contains('sidebar-open') && "
                "document.activeElement === document.querySelector('#program-tools-open')"
            )
            drawer_context.close()
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
