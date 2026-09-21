"""核心数据结构。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IndexQuote:
    """单个指数的标准化估值快照(数据采集模块的统一输出)。"""

    code: str
    name: str
    percentile: float          # PE(或代理)历史分位,0–100
    pe: float | None = None    # 当前 PE;价格代理口径下为 None
    data_date: str = ""        # 数据日期 YYYY-MM-DD
    source_label: str = ""     # 来源与口径说明,推送/页面展示用
    proxy: bool = False        # True = 价格分位代理,非 PE 口径
    sample_size: int = 0       # 分位统计样本数(自算分位时有效)
    window_label: str = ""     # 统计窗口说明


@dataclass
class Signal:
    """一次需要推送的提醒信号。"""

    code: str
    name: str
    direction: str             # 'buy' | 'sell'
    tier_label: str            # 档位区间,如 "35–40"
    action_text: str           # 建议动作,如 "基础定投 1 倍"
    depth: int                 # 档位深度,越大越深(1x=1 ... 3x=4;75–80=1 ... ≥90=4)
    cur_percentile: float
    prev_percentile: float | None
    quote: IndexQuote

    @property
    def direction_cn(self) -> str:
        return "定投" if self.direction == "buy" else "止盈"
