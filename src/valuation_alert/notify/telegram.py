"""Telegram Bot(降级渠道;Actions runner 在海外,发送无障碍)。"""
from __future__ import annotations

import requests

from .base import Notifier, NotifierError

API = "https://api.telegram.org/bot{}/sendMessage"


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(self, token: str, chat_id: str, timeout: int = 15):
        if not token or not chat_id:
            raise NotifierError("Telegram token/chat_id 未配置")
        self.token, self.chat_id = token, chat_id
        self.timeout = timeout

    def send(self, title: str, body: str) -> bool:
        resp = requests.post(
            API.format(self.token),
            json={"chat_id": self.chat_id, "text": f"{title}\n\n{body}"},
            timeout=self.timeout,
        )
        data = resp.json()
        return resp.status_code == 200 and data.get("ok") is True
