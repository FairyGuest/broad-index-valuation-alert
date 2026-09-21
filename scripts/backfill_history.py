"""一次性回填 docs/data/history.json:四个指数近一年的分位走势。

数据源:蛋卷指数估值历史接口(与当前值同源)
  GET https://danjuanfunds.com/djapi/index_eva/pe_history/{code}?day=all
  → data.index_eva_pe_growths[] = {pe, ts}(约周频,2016-09 至今,恰为近10年窗口)

算法:对近一年的每个历史点,计算该点 PE 在"序列起点至该点"(≈近10年)中的
经验分位。与官方当前分位复现误差约 0.4~2 个百分点(官方为精确日频),
走势曲线可接受;页面当前值仍使用官方 pe_percentile。

已有数据(当日真实采集值)优先,不会被覆盖;可重复运行。
用法(仓库根目录):PYTHONPATH=src python scripts/backfill_history.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valuation_alert.config import load_indices_cfg            # noqa: E402
from valuation_alert.datasources.base import http_get          # noqa: E402
from valuation_alert.percentile import percentile_of           # noqa: E402

HISTORY = os.path.join("docs", "data", "history.json")
URL = "https://danjuanfunds.com/djapi/index_eva/pe_history/{code}?day=all"
CST = timezone(timedelta(hours=8))
BACKFILL_DAYS = 365


def backfill(code: str) -> dict[str, float]:
    """返回 {YYYY-MM-DD: 分位} —— 近一年各历史点的滚动(近10年)PE 分位。"""
    data = http_get(URL.format(code=code), timeout=30).json()
    rows = data["data"]["index_eva_pe_growths"]
    points = [(datetime.fromtimestamp(r["ts"] / 1000, CST).date(), r["pe"]) for r in rows]
    cutoff = points[-1][0] - timedelta(days=BACKFILL_DAYS)
    out: dict[str, float] = {}
    for i, (date, pe) in enumerate(points):
        if date < cutoff:
            continue
        window = [p for _, p in points[:i + 1]]
        if len(window) < 60:
            continue
        out[date.isoformat()] = percentile_of(pe, window, min_samples=60)
    return out


def main() -> None:
    codes = [i["code"] for i in load_indices_cfg()["indices"]]
    series: dict[str, dict[str, float]] = {}
    for code in codes:
        series[code] = backfill(code)
        n = len(series[code])
        print(f"{code}: 回填 {n} 个点" + (f"({min(series[code].values()):.0f}%~{max(series[code].values()):.0f}%)" if n else ""))

    rows: list[dict] = []
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8") as f:
            try:
                rows = json.load(f)
            except ValueError:
                rows = []
    by_date = {r["date"]: dict(r) for r in rows}
    for code, pts in series.items():
        for date, pct in pts.items():
            by_date.setdefault(date, {"date": date}).setdefault(code, pct)  # 真实采集值优先

    merged = sorted(by_date.values(), key=lambda r: r["date"])[-760:]
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"history.json 已更新:共 {len(merged)} 天")


if __name__ == "__main__":
    main()
