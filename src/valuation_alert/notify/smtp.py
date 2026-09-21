"""邮件:SMTP SSL(主渠道,与 Server酱同发,留档 + 附页面链接)。

QQ 邮箱:设置 → 账号 → 开启 SMTP 服务 → 生成授权码(非登录密码)。
"""
from __future__ import annotations
import smtplib
from email.header import Header
from email.mime.text import MIMEText

from .base import Notifier, NotifierError


class SmtpNotifier(Notifier):
    name = "email"

    def __init__(self, host: str, port: int, user: str, password: str,
                 to: str, timeout: int = 20):
        if not all([host, port, user, password, to]):
            raise NotifierError("SMTP 配置不完整(host/port/user/password/to)")
        self.host, self.port = host, int(port)
        self.user, self.password, self.to = user, password, to
        self.timeout = timeout

    def send(self, title: str, body: str) -> bool:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(title, "utf-8")
        msg["From"] = self.user
        msg["To"] = self.to
        with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout) as smtp:
            smtp.login(self.user, self.password)
            smtp.sendmail(self.user, [self.to], msg.as_string())
        return True
