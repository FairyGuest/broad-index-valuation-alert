"""标普500 PE 历史:multpl.com 月度 PE 表(1871 年至今)。

页面:GET https://www.multpl.com/s-p-500-pe-ratio/table/by-month
结构:<tr><td>Sep 18, 2026</td><td><abbr title="Estimate">†</abbr>26.07</td></tr>(最新在前)
分位:最新 PE 在近 N 个月(默认 120,即 10 年)窗口内的经验分布百分位。
"""
from __future__ import annotations

import re
from datetime import datetime

from ..models import IndexQuote
from ..percentile import percentile_of
from .base import DataError, DataSource, http_get

URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
ROW_RE = re.compile(
    r"<td[^>]*>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*"
    r"<td[^>]*>\s*(?:<abbr[^>]*>[^<]*</abbr>|&#x2002;)?\s*([0-9]+(?:\.[0-9]+)?)\s*</td>",
    re.S,
)
# 不用 strptime("%b"):Windows 默认中文 locale 下英文月名解析会失败
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def parse_rows(html: str) -> list[tuple[str, float]]:
    """返回 [(日期字符串, PE)],最新在前。"""
    rows = []
    for date_str, value in ROW_RE.findall(html):
        month, day, year = date_str.replace(",", "").split()
        rows.append((f"{year}-{MONTHS[month]:02d}-{int(day):02d}", float(value)))
    return rows


class MultplSource(DataSource):
    def __init__(self, html: str | None = None, timeout: int = 15):
        super().__init__(timeout)
        self._html = html

    def get_quote(self, index_cfg: dict) -> IndexQuote:
        code = index_cfg["code"]
        html = self._html if self._html is not None else http_get(URL, timeout=self.timeout).text
        rows = parse_rows(html)
        window = int(index_cfg.get("window", 120))
        if len(rows) < window:
            raise DataError(f"multpl 历史行数不足:{len(rows)} < {window},页面结构可能已改版")

        cur_date, cur_pe = rows[0]
        series = [v for _, v in rows[:window]]
        try:
            pct = percentile_of(cur_pe, series, min_samples=window)
        except ValueError as e:
            raise DataError(f"{code} 分位计算失败:{e}") from e

        return IndexQuote(
            code=code,
            name=index_cfg["name"],
            percentile=pct,
            pe=cur_pe,
            data_date=cur_date,
            source_label=index_cfg.get("source_label", "multpl"),
            proxy=False,
            sample_size=len(series),
            window_label=f"近10年(月度,{len(series)}个样本)",
        )
