"""纳斯达克100:Nasdaq 官方历史行情 API(价格分位代理口径)。

接口:GET https://api.nasdaq.com/api/quote/NDX/historical?assetclass=index
      &fromdate=YYYY-MM-DD&todate=YYYY-MM-DD&limit=9999(无鉴权,带浏览器 UA)
结构:data.tradesTable.rows[]({date: '09/18/2026', close: '29,644.17'}),最新在前。
口径说明:纳指100 无免费 PE 历史序列(已实测),V1 用近 10 年收盘价分位作代理,
推送与页面强制标注"价格代理,非 PE 口径"。
"""
from __future__ import annotations

from datetime import timedelta

from ..config import beijing_now
from ..models import IndexQuote
from ..percentile import percentile_of
from .base import DataError, DataSource, http_get

URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"


class NasdaqSource(DataSource):
    def __init__(self, raw_json: dict | None = None, timeout: int = 20):
        super().__init__(timeout)
        self._raw = raw_json

    def get_quote(self, index_cfg: dict) -> IndexQuote:
        code = index_cfg["code"]
        symbol = index_cfg.get("symbol", "NDX")
        window_days = int(index_cfg.get("window_days", 3650))
        to = beijing_now().date()
        frm = to - timedelta(days=window_days)

        try:
            if self._raw is not None:
                data = self._raw
            else:
                resp = http_get(URL.format(symbol=symbol), params={
                    "assetclass": "index",
                    "fromdate": frm.isoformat(),
                    "todate": to.isoformat(),
                    "limit": "9999",
                }, timeout=self.timeout)
                data = resp.json()
            rows = data["data"]["tradesTable"]["rows"]
        except (KeyError, TypeError, ValueError) as e:
            raise DataError(f"Nasdaq 接口响应结构异常: {e}") from e

        try:
            closes = [float(r["close"].replace(",", "")) for r in rows]
        except (KeyError, AttributeError, ValueError) as e:
            raise DataError(f"Nasdaq 收盘价解析失败: {e}") from e

        try:
            cur = closes[0]
            pct = percentile_of(cur, closes, min_samples=240)
            m, d, y = rows[0]["date"].split("/")
            data_date = f"{y}-{m}-{d}"
        except (IndexError, ValueError) as e:
            raise DataError(f"Nasdaq 数据不足或日期解析失败: {e}") from e

        return IndexQuote(
            code=code,
            name=index_cfg["name"],
            percentile=pct,
            pe=None,
            data_date=data_date,
            source_label=index_cfg.get("source_label", "Nasdaq"),
            proxy=True,
            sample_size=len(closes),
            window_label=f"近10年(日频价格,{len(closes)}个样本)",
        )
