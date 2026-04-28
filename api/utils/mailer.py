"""
Email utility for sending password reset codes via Gmail SMTP.
"""
import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..core.config import Config

logger = logging.getLogger(__name__)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465


def send_reset_code_email(to_email: str, code: str) -> bool:
    """
    Send a password reset code email via Gmail SMTP.

    Args:
        to_email: Recipient email address.
        code: The 6-digit reset code (plaintext, for display in email).

    Returns:
        True if sent successfully, False otherwise.
    """
    sender = Config.GMAIL_USER
    password = Config.GMAIL_APP_PASSWORD

    if not sender or not password:
        logger.error("Gmail credentials not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD.")
        return False

    subject = "YumeZone — Password Reset Code"

    html_body = f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="420" cellpadding="0" cellspacing="0"
               style="background:#141414;border-radius:16px;border:1px solid #222;padding:40px;">
          <tr>
            <td align="center" style="padding-bottom:24px;">
              <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">YumeZone</h1>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom:8px;">
              <p style="margin:0;color:#999;font-size:14px;">Your password reset code is:</p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:20px 0;">
              <div style="display:inline-block;background:#1a1a2e;border:2px solid #6c5ce7;
                          border-radius:12px;padding:16px 36px;letter-spacing:12px;
                          font-size:32px;font-weight:700;color:#a29bfe;font-family:monospace;">
                {code}
              </div>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-top:16px;">
              <p style="margin:0;color:#666;font-size:13px;">
                This code expires in <strong style="color:#e17055;">5 minutes</strong>.
              </p>
              <p style="margin:8px 0 0;color:#555;font-size:12px;">
                If you didn't request this, you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    # Plain-text fallback
    text_body = (
        f"YumeZone — Password Reset\n\n"
        f"Your reset code is: {code}\n\n"
        f"This code expires in 5 minutes.\n"
        f"If you didn't request this, ignore this email."
    )
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())

        logger.info(f"Reset code email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail SMTP authentication failed. Check GMAIL_USER / GMAIL_APP_PASSWORD.")
        return False
    except Exception as e:
        logger.error(f"Failed to send reset code email to {to_email}: {e}")
        return False
