"""Send email through an HTTPS API (Render's free tier blocks normal SMTP ports)."""
import logging

import httpx

from .config import settings

log = logging.getLogger("linkshortener.mail")


def email_enabled() -> bool:
    return settings.email_backend in {"brevo", "resend", "console"}


def send_email(to: str, subject: str, body: str) -> bool:
    """Return True if the provider accepted the message."""
    backend = settings.email_backend
    try:
        if backend == "brevo":
            response = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
                json={
                    "sender": {"name": settings.mail_from_name, "email": settings.mail_from},
                    "to": [{"email": to}],
                    "subject": subject,
                    "textContent": body,
                },
                timeout=10,
            )
            response.raise_for_status()
            return True
        if backend == "resend":
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": f"{settings.mail_from_name} <{settings.mail_from}>",
                    "to": [to],
                    "subject": subject,
                    "text": body,
                },
                timeout=10,
            )
            response.raise_for_status()
            return True
        if backend == "console":  # development only: shows the email in the server log
            log.warning("EMAIL to=%s subject=%s\n%s", to, subject, body)
            return True
    except httpx.HTTPError:
        log.exception("Could not send email via %s", backend)
    return False
