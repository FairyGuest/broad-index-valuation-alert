"""A股指数估值:蛋卷(雪球)指数估值接口。

接口:GET https://danjuanfunds.com/djapi/index_eva/dj(无鉴权,带浏览器 UA)
字段:index_code / name / pe / pe_percentile(0–1 小数,需 ×100)/ ts(数据日毫秒时间戳)
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import IndexQuote
from .base import DataError, DataSource, http_get

URL = "https://danjuanfunds.com/djapi/index_eva/dj"
BEIJING = ZoneInfo("Asia/Shanghai")


class DanjuanSource(DataSource):
    def __init__(self, raw: str | None = None, timeout: int = 15):
        super().__init__(timeout)
        self._raw = raw    # 测试时注入离线响应

    def get_quote(self, index_cfg: dict) -> IndexQuote:
        code = index_cfg["code"]
        try:
            text = self._raw if self._raw is not None else http_get(URL, timeout=self.timeout).text
            items = json.loads(text)["data"]["items"]
        except (KeyError, TypeError, ValueError) as e:
            raise DataError(f"蛋卷接口响应结构异常: {e}") from e

        for it in items:
            if it.get("index_code") == code:
                return self._to_quote(it, index_cfg)
        raise DataError(f"蛋卷返回中未找到指数 {code}")

    @staticmethod
    def _to_quote(it: dict, index_cfg: dict) -> IndexQuote:
        code = index_cfg["code"]
        pe = it.get("pe") or 0
        pct_frac = it.get("pe_percentile") or 0
        if not (0 < pct_frac <= 1):
            # 蛋卷对亏损/异常指数会返回 0 分位,按数据缺失处理
            raise DataError(f"{code} pe_percentile 异常:{pct_frac}(蛋卷可能未提供该指数分位)")
        if pe <= 0:
            raise DataError(f"{code} PE 异常:{pe}")

        ts = it.get("ts")
        if ts:
            data_date = datetime.fromtimestamp(ts / 1000, tz=BEIJING).strftime("%Y-%m-%d")
        else:
            data_date = ""
        return IndexQuote(
            code=code,
            name=it.get("name") or index_cfg["name"],
            percentile=round(pct_frac * 100, 1),
            pe=round(float(pe), 2),
            data_date=data_date,
            source_label=index_cfg.get("source_label", "蛋卷"),
            proxy=False,
            window_label="近10年",
        )
