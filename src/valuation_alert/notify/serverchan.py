"""Server酱 Turbo:微信服务号推送(主渠道)。

文档:https://sct.ftqq.com/  POST https://sctapi.ftqq.com/{SENDKEY}.send
title 上限 32 字符(微信模板消息限制),desp 支持 Markdown。
"""
from __future__ import annotations

import requests

from .base import Notifier, NotifierError

API = "https://sctapi.ftqq.com/{}.send"
TITLE_LIMIT = 32


class ServerChanNotifier(Notifier):
    name = "serverchan"

    def __init__(self, sendkey: str, timeout: int = 15):
        if not sendkey:
            raise NotifierError("Server酱 SendKey 未配置(环境变量 SERVERCHAN_SENDKEY)")
        self.sendkey = sendkey
        self.timeout = timeout

    def send(self, title: str, body: str) -> bool:
        resp = requests.post(
            API.format(self.sendkey),
            data={"title": title[:TITLE_LIMIT], "desp": body},
            timeout=self.timeout,
        )
        data = resp.json()
        return resp.status_code == 200 and data.get("code") == 0
