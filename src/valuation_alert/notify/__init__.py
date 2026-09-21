"""通知渠道工厂:notify.yaml + 环境变量 → Notifier 实例列表。"""
from __future__ import annotations

import logging
import os

from .base import Notifier, NotifierError, send_with_retry
from .serverchan import ServerChanNotifier
from .smtp import SmtpNotifier
from .telegram import TelegramNotifier

log = logging.getLogger(__name__)


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def build_notifiers(notify_cfg: dict) -> tuple[list[Notifier], list[Notifier]]:
    """返回 (主渠道列表, 降级渠道列表)。配置缺失的渠道记警告并跳过,不阻塞运行。"""
    primary: list[Notifier] = []
    fallback: list[Notifier] = []
    for ch in notify_cfg.get("channels", []):
        if not ch.get("enabled", True):
            continue
        try:
            notifier = _build_one(ch)
        except NotifierError as e:
            log.warning("跳过渠道 %s:%s", ch.get("name"), e)
            continue
        # telegram 为降级渠道,其余为主渠道(同发互为冗余)
        (fallback if ch.get("type") == "telegram" else primary).append(notifier)
    return primary, fallback


def _build_one(ch: dict) -> Notifier:
    t = ch.get("type")
    if t == "serverchan":
        return ServerChanNotifier(_env(ch.get("key_env", "SERVERCHAN_SENDKEY")))
    if t == "smtp":
        return SmtpNotifier(
            host=ch.get("host", "smtp.qq.com"),
            port=int(ch.get("port", 465)),
            user=_env(ch.get("user_env", "SMTP_USER")),
            password=_env(ch.get("password_env", "SMTP_AUTH_CODE")),
            to=_env(ch.get("to_env", "SMTP_TO")),
        )
    if t == "telegram":
        return TelegramNotifier(
            token=_env(ch.get("token_env", "TELEGRAM_BOT_TOKEN")),
            chat_id=_env(ch.get("chat_id_env", "TELEGRAM_CHAT_ID")),
        )
    raise NotifierError(f"未知渠道类型:{t}")


__all__ = ["Notifier", "NotifierError", "build_notifiers", "send_with_retry"]
