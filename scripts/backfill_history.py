"""一次性回填 docs/data/history.json,让前端走势图立即有近一年历史。

口径与线上运行完全一致:
- 标普500:multpl 月度 PE,滚动近 120 个月窗口计算分位(月度粒度,近一年约 13 个点)
- 纳斯达克100:Nasdaq 官方日线,每个交易日以"该日为终点的近 10 年窗口"计算价格分位
- 沪深300 / 中证500:蛋卷仅提供当前分位、无历史接口,自系统上线日起逐日积累

用法(在仓库根目录):
  PYTHONPATH=src python scripts/backfill_history.py
已有数据(当日真实采集值)优先,不会被回填覆盖;可重复运行。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valuation_alert.config import beijing_now          # noqa: E402
from valuation_alert.datasources.base import http_get   # noqa: E402
from valuation_alert.datasources.multpl import URL as MULTPL_URL, parse_rows  # noqa: E402
from valuation_alert.percentile import percentile_of    # noqa: E402

HISTORY = os.path.join("docs", "data", "history.json")


def backfill_sp500(months: int = 13) -> dict[str, float]:
    """multpl 月度 PE → 每月滚动 120 月分位。"""
    html = http_get(MULTPL_URL, timeout=30).text
    rows = parse_rows(html)                 # [(date, pe)] 最新在前
    series = rows[::-1]                     # 时间升序
    out: dict[str, float] = {}
    for i in range(len(series) - months, len(series)):
        date, pe = series[i]
        window = [v for _, v in series[max(0, i - 119):i + 1]]
        out[date] = percentile_of(pe, window, min_samples=60)
    return out


def backfill_ndx(days: int = 370) -> dict[str, float]:
    """Nasdaq 日线 → 每日滚动 10 年窗口价格分位(需多拉 10 年前置数据)。"""
    to = beijing_now().date()
    frm = to - timedelta(days=3650 + days)  # 10 年窗口 + 回填区间
    resp = http_get("https://api.nasdaq.com/api/quote/NDX/historical", params={
        "assetclass": "index", "fromdate": frm.isoformat(),
        "todate": to.isoformat(), "limit": "9999"}, timeout=30).json()
    rows = resp["data"]["tradesTable"]["rows"]          # 最新在前
    dates = [r["date"] for r in rows]                   # MM/DD/YYYY
    closes = [float(r["close"].replace(",", "")) for r in rows]
    series = list(zip(dates, closes))[::-1]             # 时间升序
    out: dict[str, float] = {}
    for i in range(len(series) - days, len(series)):
        m, d, y = series[i][0].split("/")
        date = f"{y}-{m}-{d}"
        window = [v for _, v in series[max(0, i - 2515):i + 1]]
        out[date] = percentile_of(series[i][1], window, min_samples=240)
    return out


def main() -> None:
    sp = backfill_sp500()
    print(f"标普500 回填 {len(sp)} 个月度点:{min(sp)} ~ {max(sp)}")
    ndx = backfill_ndx()
    print(f"纳斯达克100 回填 {len(ndx)} 个日频点:{min(ndx)} ~ {max(ndx)}")

    rows: list[dict] = []
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8") as f:
            try:
                rows = json.load(f)
            except ValueError:
                rows = []
    by_date = {r["date"]: dict(r) for r in rows}

    for date, pct in {**{d: {"SP500": v} for d, v in sp.items()},
                      **{d: {"NDX": v} for d, v in ndx.items()}}.items():
        entry = by_date.setdefault(date, {"date": date})
        for code, pct_val in pct.items():
            entry.setdefault(code, pct_val)    # 已有真实采集值不覆盖

    merged = sorted(by_date.values(), key=lambda r: r["date"])[-760:]
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"history.json 已更新:共 {len(merged)} 天(已有数据优先保留)")


if __name__ == "__main__":
    main()
