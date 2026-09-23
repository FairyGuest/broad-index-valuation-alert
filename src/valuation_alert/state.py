"""状态管理:state/previous_percentiles.json 的读写与幂等状态转移。

状态语义:
- signal_state:指数当前所处区间 'buy' / 'sell' / 'none'(连续状态,非信号瞬间)
- tier_depth:当前档位深度;档位加深(数值变大)才允许再次提醒(策略层判断)
- 同一方向、同一档位深度下重复运行不产生信号(策略层 crossed/deepened 均不满足),
  天然满足"同日/跨日均不重复提醒"
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from .models import IndexQuote, Signal
from .strategy import buy_tier, sell_tier

STATE_FILE = os.path.join("state", "previous_percentiles.json")


def empty_state() -> dict:
    return {"updated_at": None, "indices": {}}


def materially_changed(before: dict | None, after: dict) -> bool:
    """比较两份状态是否有实质差异(忽略 updated_at 时间戳)。

    高频 cron 策略下每天运行 20+ 次,若仅因时间戳变化就写文件,会产生大量
    无意义提交并频繁触发 Pages 构建(并发部署会冲突失败)。故仅在实质
    数据变化(分位/区间/信号/日期任一变动)时才落盘。
    """
    def strip(d):
        return {k: v for k, v in (d or {}).items() if k != "updated_at"}
    return strip(before) != strip(after)


def load(path: str = STATE_FILE) -> dict:
    if not os.path.exists(path):
        return empty_state()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("indices", {})
    return data


def save(state: dict, path: str = STATE_FILE, now: datetime | None = None) -> None:
    state["updated_at"] = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)    # 原子替换,避免中断产生半写文件


def entry_for(state: dict, code: str) -> dict | None:
    return state["indices"].get(code)


def apply_quote(state: dict, quote: IndexQuote, strategy_cfg: dict, today: str,
                signal: Signal | None) -> None:
    """把本次快照落入状态:无论是否推送,分位与所处区间都更新到最新。"""
    cur = quote.percentile
    if cur < strategy_cfg["buy_threshold"]:
        new_state, depth = "buy", buy_tier(cur, strategy_cfg["buy_tiers"])["depth"]
    elif cur >= strategy_cfg["sell_threshold"]:
        new_state, depth = "sell", sell_tier(cur, strategy_cfg["sell_tiers"])["depth"]
    else:
        new_state, depth = "none", 0

    entry = state["indices"].setdefault(quote.code, {})
    entry.update({
        "name": quote.name,
        "prev_percentile": entry.get("cur_percentile"),
        "cur_percentile": cur,
        "signal_state": new_state,
        "tier_depth": depth,
        "data_date": quote.data_date,
        "source": quote.source_label,
    })
    if signal:
        entry["last_signal"] = f"{signal.direction}:{signal.tier_label}"
        entry["last_signal_date"] = today
        entry["last_push_date"] = today
