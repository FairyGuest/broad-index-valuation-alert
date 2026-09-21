"""窗口分位计算(纯函数,无副作用)。

口径:经验分布函数——序列中 <= 当前值的样本占比。
"""
from __future__ import annotations


class InsufficientSamples(ValueError):
    """历史样本不足以支撑可信的分位数。"""


def percentile_of(value: float, series: list[float], min_samples: int = 240) -> float:
    """计算 value 在 series 中的历史百分位(0–100,保留 1 位小数)。

    series 含当前值自身亦可(对结果影响 <= 1/n,可忽略)。
    样本数低于 min_samples 时抛出 InsufficientSamples,由上层跳过并告警。
    """
    xs = [x for x in series if x is not None]
    if len(xs) < min_samples:
        raise InsufficientSamples(f"样本数 {len(xs)} 低于最小要求 {min_samples}")
    below = sum(1 for x in xs if x <= value)
    return round(100.0 * below / len(xs), 1)
