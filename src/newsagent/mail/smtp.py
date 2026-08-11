"""Production email sender: real SMTP delivery via stdlib smtplib — same
adapter shape as ConsoleEmailSender, no new dependency, no vendor SDK."""

import smtplib
from email.mime.text import MIMEText

from newsagent.mail.base import EmailSendError, EmailSender


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
        message = MIMEText(html_body, "html", "utf-8")
        message["Subject"] = subject
        message["From"] = self._from_address
        message["To"] = to

        try:
            with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                if self._use_tls:
                    server.starttls()
                server.login(self._username, self._password)
                server.sendmail(self._from_address, [to], message.as_string())
        except (smtplib.SMTPException, OSError) as error:
            raise EmailSendError(str(error)) from error
