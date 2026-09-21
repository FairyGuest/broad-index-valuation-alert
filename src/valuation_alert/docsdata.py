"""前端数据文件输出:docs/data/latest.json / history.json / signals.json。

latest 每次运行覆盖;history 每交易日一档(同日覆盖);signals 仅在有信号时追加。
"""
from __future__ import annotations

import json
import os

from .models import IndexQuote, Signal
from .strategy import zone_of

DOCS_DATA_DIR = os.path.join("docs", "data")

ZONE_LABELS = {"buy": "定投区", "sell": "止盈区", "none": "中性区"}


def write_latest(quotes: list[IndexQuote], strategy_cfg: dict,
                 updated_at: str, data_dir: str = DOCS_DATA_DIR) -> str:
    payload = {
        "updated_at": updated_at,
        "thresholds": {"buy": strategy_cfg["buy_threshold"],
                       "sell": strategy_cfg["sell_threshold"]},
        "indices": [],
    }
    for q in quotes:
        zone, tier = zone_of(q.percentile, strategy_cfg)
        payload["indices"].append({
            "code": q.code, "name": q.name,
            "pe": q.pe, "percentile": q.percentile,
            "proxy": q.proxy, "data_date": q.data_date,
            "source_label": q.source_label, "window_label": q.window_label,
            "sample_size": q.sample_size,
            "zone": zone, "zone_label": ZONE_LABELS[zone],
            "tier": tier and {"label": tier["label"],
                              "action": _tier_action(tier, zone)},
        })
    return _write_json(os.path.join(data_dir, "latest.json"), payload)


def _tier_action(tier: dict, zone: str) -> str:
    if zone == "buy":
        return f"{tier['action']}(建议 {tier['multiple']:g} 倍)"
    return f"建议{tier['ratio']}"


def append_history(quotes: list[IndexQuote], today: str,
                   data_dir: str = DOCS_DATA_DIR) -> str:
    """每日一档,同日覆盖;结构 [{date, <code>: 分位, ...}],供走势图。"""
    path = os.path.join(data_dir, "history.json")
    rows: list[dict] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                rows = json.load(f)
            except ValueError:
                rows = []
    rows = [r for r in rows if r.get("date") != today]
    row = {"date": today}
    row.update({q.code: q.percentile for q in quotes})
    rows.append(row)
    rows.sort(key=lambda r: r.get("date", ""))    # 同日覆盖后保持时间序
    rows = rows[-760:]    # 上限约 3 年,控制文件体积
    return _write_json(path, rows)


def append_signals(signals: list[Signal], today: str, now_txt: str,
                   data_dir: str = DOCS_DATA_DIR) -> str | None:
    if not signals:
        return None
    path = os.path.join(data_dir, "signals.json")
    rows: list[dict] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                rows = json.load(f)
            except ValueError:
                rows = []
    for s in signals:
        rows.append({
            "time": now_txt, "date": today, "code": s.code, "name": s.name,
            "direction": s.direction, "direction_cn": s.direction_cn,
            "tier": s.tier_label, "action": s.action_text,
            "percentile": s.cur_percentile,
            "prev_percentile": s.prev_percentile,
        })
    rows = rows[-200:]
    return _write_json(path, rows)


def _write_json(path: str, payload) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path
