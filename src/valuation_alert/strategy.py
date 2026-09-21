"""策略判定:跨阈值检测、档位映射、信号生成(纯函数)。

区间约定(左闭右开,与需求 3.1/3.2 对齐):
- 买入信号:上次分位 >= buy_threshold 且本次 < buy_threshold(40.0 本身不算"跌入")
- 卖出信号:上次分位 < sell_threshold 且本次 >= sell_threshold(75.0 算"升入")
- 买入档位按"首个 分位 < max 命中"自上而下匹配:<15 → 3x,[15,25) → 2x,[25,35) → 1.5x,[35,40) → 1x
- 卖出档位按"首个 分位 >= min 命中"匹配:>=90 闭区间清仓,其余左闭右开
- 信号产生的两类场景:① 跨越阈值进入 buy/sell 区;② 区内档位加深(如 1x → 1.5x)
  档位减轻(如 1.5x → 1x)不产生信号,仅更新状态
"""
from __future__ import annotations

from .models import IndexQuote, Signal


def buy_tier(percentile: float, tiers: list[dict]) -> dict:
    """返回首个 max > percentile 的档位(要求 tiers 按 max 升序且覆盖到 buy_threshold)。"""
    for i, tier in enumerate(tiers):
        if percentile < tier["max"]:
            return {**tier, "depth": len(tiers) - i}   # 越靠前(阈值越低)越深
    raise ValueError(f"分位 {percentile} 未命中任何买入档位,请检查 buy_tiers 配置覆盖")


def sell_tier(percentile: float, tiers: list[dict]) -> dict:
    """返回首个 min <= percentile 的档位(要求 tiers 按 min 降序)。"""
    for i, tier in enumerate(tiers):
        if percentile >= tier["min"]:
            return {**tier, "depth": len(tiers) - i}   # 越靠前(阈值越高)越深
    raise ValueError(f"分位 {percentile} 未命中任何卖出档位,请检查 sell_tiers 配置覆盖")


def zone_of(percentile: float, strategy_cfg: dict) -> tuple[str, dict | None]:
    """返回 (区间, 当前档位):'buy'/'sell'/'none'。"""
    if percentile < strategy_cfg["buy_threshold"]:
        return "buy", buy_tier(percentile, strategy_cfg["buy_tiers"])
    if percentile >= strategy_cfg["sell_threshold"]:
        return "sell", sell_tier(percentile, strategy_cfg["sell_tiers"])
    return "none", None


def evaluate(quote: IndexQuote, prev_entry: dict | None, strategy_cfg: dict) -> Signal | None:
    """根据本次快照与上次状态条目,判定是否产生需推送的信号。

    prev_entry 为 None(该指数首次运行)时不产生信号,仅记录状态,避免上线即误报。
    """
    cur = quote.percentile
    buy_th = strategy_cfg["buy_threshold"]
    sell_th = strategy_cfg["sell_threshold"]

    if cur < buy_th:
        tier = buy_tier(cur, strategy_cfg["buy_tiers"])
        prev_state = (prev_entry or {}).get("signal_state")
        prev_depth = (prev_entry or {}).get("tier_depth", 0)
        crossed = prev_state in (None, "none", "sell") and prev_state is not None
        deepened = prev_state == "buy" and tier["depth"] > prev_depth
        if crossed or deepened:
            return _signal(quote, "buy", tier, prev_entry)
        return None

    if cur >= sell_th:
        tier = sell_tier(cur, strategy_cfg["sell_tiers"])
        prev_state = (prev_entry or {}).get("signal_state")
        prev_depth = (prev_entry or {}).get("tier_depth", 0)
        crossed = prev_state in ("none", "buy")
        deepened = prev_state == "sell" and tier["depth"] > prev_depth
        if crossed or deepened:
            return _signal(quote, "sell", tier, prev_entry)
        return None

    return None    # 中性区间(40–75):不产生信号


def _signal(quote: IndexQuote, direction: str, tier: dict, prev_entry: dict | None) -> Signal:
    if direction == "buy":
        action = f"{tier['action']}(建议 {tier['multiple']:g} 倍)"
    else:
        action = f"建议{tier['ratio']}"
    return Signal(
        code=quote.code,
        name=quote.name,
        direction=direction,
        tier_label=str(tier["label"]),
        action_text=action,
        depth=tier["depth"],
        cur_percentile=quote.percentile,
        prev_percentile=(prev_entry or {}).get("cur_percentile"),
        quote=quote,
    )
