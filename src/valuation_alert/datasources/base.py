"""数据源适配器公共基座。"""
from __future__ import annotations

import abc

import requests

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
DEFAULT_TIMEOUT = 15


class DataError(RuntimeError):
    """数据源获取/解析失败。"""


def http_get(url: str, params: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT},
                            timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:    # 网络错误、超时、4xx/5xx 统一归为数据源失败
        raise DataError(f"请求失败 {url}: {e}") from e


class DataSource(abc.ABC):
    """每个数据源实现 get_quote;index_cfg 为 indices.yaml 中该指数的配置节点。"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    @abc.abstractmethod
    def get_quote(self, index_cfg: dict):
        """返回 models.IndexQuote;失败抛 DataError。"""
