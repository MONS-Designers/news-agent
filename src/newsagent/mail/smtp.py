"""Production email sender: real SMTP delivery via stdlib smtplib - same
adapter shape as ConsoleEmailSender, no new dependency, no vendor SDK."""

import base64
import re
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from newsagent.branding import PRODUCT_NAME
from newsagent.mail.base import EmailSendError, EmailSender

# render.py embeds small template assets (the logo) as data: URIs so a
# rendered digest is a single self-contained HTML string - handy for the
# browser preview / outbox file, and for ConsoleEmailSender. Real SMTP
# delivery is a different story: Gmail and other clients commonly refuse to
# render an inline data: URI at all (confirmed live, 2026-08-31 - the logo
# showed broken in an actual received email despite rendering fine in a
# browser). The universally-supported way to embed an image in an email is
# Content-ID: attach the image as its own MIME part and reference it via
# `cid:`. This rewrites any data: URI in the HTML into a `cid:` reference
# plus an attached part, right before the wire send - render.py and every
# other consumer of the HTML string stay untouched.
_DATA_URI_IMAGE = re.compile(
    r'src="data:image/(?P<subtype>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=]+)"'
)


def _inline_data_uri_images(html: str) -> tuple[str, list[MIMEImage]]:
    parts: list[MIMEImage] = []

    def _replace(match: re.Match[str]) -> str:
        cid = f"inline-image-{len(parts)}"
        part = MIMEImage(
            base64.b64decode(match.group("data")), _subtype=match.group("subtype")
        )
        part.add_header("Content-ID", f"<{cid}>")
        part.add_header("Content-Disposition", "inline")
        parts.append(part)
        return f'src="cid:{cid}"'

    return _DATA_URI_IMAGE.sub(_replace, html), parts


class SmtpEmailSender(EmailSender):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_tls = use_tls

    def send(self, to: str, subject: str, html_body: str) -> None:
        html, inline_images = _inline_data_uri_images(html_body)
        if inline_images:
            message: MIMEMultipart | MIMEText = MIMEMultipart("related")
            message.attach(MIMEText(html, "html", "utf-8"))
            for image_part in inline_images:
                message.attach(image_part)
        else:
            message = MIMEText(html, "html", "utf-8")
        message["Subject"] = subject
        message["From"] = formataddr((PRODUCT_NAME, self._from_address))
        message["To"] = to

        try:
            with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                if self._use_tls:
                    server.starttls()
                server.login(self._username, self._password)
                server.sendmail(self._from_address, [to], message.as_string())
        except (smtplib.SMTPException, OSError) as error:
            raise EmailSendError(str(error)) from error
