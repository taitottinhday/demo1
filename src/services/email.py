"""SMTP delivery for student account verification and password reset codes."""

import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape


class EmailDeliveryError(RuntimeError):
    """The configured SMTP server could not accept a message."""


class SmtpMailer:
    def __init__(self, settings):
        self.settings = settings

    @property
    def configured(self):
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_user
            and self.settings.smtp_password
            and self.settings.smtp_from
        )

    def send_code(self, recipient: str, code: str, purpose: str, name: str = "") -> None:
        if not self.configured:
            raise EmailDeliveryError("SMTP is not configured.")
        if purpose == "verify":
            subject = "Confirm your admissions account email"
            title = "Confirm your email address"
            intro = "Use the code below to finish creating your student account:"
        else:
            subject = "Reset your admissions account password"
            title = "Reset your password"
            intro = "Use the code below to create a new password:"
        greeting = f"Hello {name}," if name else "Hello,"
        minutes = self.settings.verification_code_minutes
        text = (
            f"{greeting}\n\n{intro}\n\n{code}\n\n"
            f"This code expires in {minutes} minutes. If you did not request this, ignore this email."
        )
        html = (
            '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#123b3d">'
            f"<h2>{escape(title)}</h2><p>{escape(greeting)}</p><p>{escape(intro)}</p>"
            f'<p style="font-size:30px;letter-spacing:8px;font-weight:700">{code}</p>'
            f"<p>This code expires in <b>{minutes} minutes</b>. If you did not request this, ignore this email.</p>"
            "</body></html>"
        )
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((self.settings.smtp_from_name, self.settings.smtp_from))
        message["To"] = recipient
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        self._deliver(message)

    def send_login_notice(self, recipient: str, name: str = "", method: str = "Google", ip: str = "") -> None:
        """Notify the account owner after a successful sign-in."""
        if not self.configured:
            raise EmailDeliveryError("SMTP is not configured.")
        local_time = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M:%S")
        greeting = f"Xin chào {name}," if name else "Xin chào bạn,"
        location = ip or "Không xác định"
        subject = "Bạn vừa đăng nhập vào Trợ lý tuyển sinh X"
        text = (
            f"{greeting}\n\n"
            "Tài khoản của bạn vừa đăng nhập thành công vào Trợ lý tuyển sinh X.\n\n"
            f"Phương thức: {method}\nThời gian: {local_time} (GMT+7)\nĐịa chỉ IP: {location}\n\n"
            "Nếu đây không phải là bạn, hãy đổi mật khẩu và liên hệ quản trị viên ngay."
        )
        html = (
            '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#123b3d">'
            f"<h2>{escape(subject)}</h2><p>{escape(greeting)}</p>"
            "<p>Tài khoản của bạn vừa đăng nhập thành công vào Trợ lý tuyển sinh X.</p>"
            f"<p><b>Phương thức:</b> {escape(method)}<br>"
            f"<b>Thời gian:</b> {escape(local_time)} (GMT+7)<br>"
            f"<b>Địa chỉ IP:</b> {escape(location)}</p>"
            "<p>Nếu đây không phải là bạn, hãy đổi mật khẩu và liên hệ quản trị viên ngay.</p>"
            "</body></html>"
        )
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((self.settings.smtp_from_name, self.settings.smtp_from))
        message["To"] = recipient
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        self._deliver(message)

    def _deliver(self, message: EmailMessage) -> None:
        try:
            context = ssl.create_default_context()
            if self.settings.smtp_security == "ssl" or not self.settings.smtp_starttls:
                with smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout,
                    context=context,
                ) as server:
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(
                    self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.smtp_timeout
                ) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                    server.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("SMTP delivery failed.") from exc
