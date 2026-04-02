import asyncio
import smtplib
from email.message import EmailMessage

from app.config import get_settings

settings = get_settings()


class EmailService:
    async def send_verification_code(
        self,
        to_email: str,
        code: str,
        booking_label: str,
    ) -> None:
        await asyncio.to_thread(self._send_verification_code_sync, to_email, code, booking_label)

    def _send_verification_code_sync(
        self,
        to_email: str,
        code: str,
        booking_label: str,
    ) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise RuntimeError("SMTP is not configured")

        msg = EmailMessage()
        msg["Subject"] = "Apartello — код подтверждения"
        msg["From"] = settings.smtp_from_email
        msg["To"] = to_email
        msg.set_content(
            f"""
Здравствуйте!

Ваш код подтверждения для входа в Telegram-бот Apartello:

{code}

Бронь: {booking_label}

Код действует {settings.email_otp_ttl_minutes} минут.
Если вы не запрашивали код, просто проигнорируйте это письмо.
""".strip()
        )

        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
            return

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
