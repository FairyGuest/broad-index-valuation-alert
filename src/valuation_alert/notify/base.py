"""通知渠道公共基座:抽象接口 + 重试。"""
from __future__ import annotations

import abc
import logging
import time

log = logging.getLogger(__name__)


class Notifier(abc.ABC):
    """一个推送渠道。send 成功返回 True,失败抛出/返回 False 由 send_with_retry 兜底。"""

    name: str = "base"

    @abc.abstractmethod
    def send(self, title: str, body: str) -> bool: ...


class NotifierError(RuntimeError):
    """渠道配置缺失或发送失败。"""


def send_with_retry(notifier: Notifier, title: str, body: str,
                    attempts: int = 3, backoff_seconds: list[int] | None = None) -> bool:
    """指数退避重试;全部失败返回 False(不抛异常,由编排层决定是否降级)。"""
    backoff = backoff_seconds or [5, 30, 120]
    for i in range(1, attempts + 1):
        try:
            if notifier.send(title, body):
                log.info("推送成功:%s(第 %d 次尝试)", notifier.name, i)
                return True
            log.warning("推送返回失败:%s(第 %d 次尝试)", notifier.name, i)
        except Exception as e:    # 网络/协议错误统一捕获记录
            log.warning("推送异常:%s(第 %d 次尝试):%s", notifier.name, i, e)
        if i < attempts:
            time.sleep(backoff[min(i - 1, len(backoff) - 1)])
    return False
