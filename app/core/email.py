from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings


logger = logging.getLogger(__name__)


def is_email_delivery_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> bool:
    if not is_email_delivery_configured():
        logger.warning("SMTP is not configured, skipping email delivery")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        if settings.SMTP_FROM_NAME
        else settings.SMTP_FROM_EMAIL
    )
    message["To"] = to_email
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        if settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)

        with server:
            if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.error("Failed to send email notification: %s", exc)
        return False
