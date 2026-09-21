"""策略判定测试:跨阈值、档位边界、加深/减轻、首跑抑制。"""
import pytest

from valuation_alert.models import IndexQuote
from valuation_alert.strategy import evaluate
from conftest import STRATEGY_CFG


def q(pct, code="SH000300", name="沪深300", proxy=False):
    return IndexQuote(code=code, name=name, percentile=pct, proxy=proxy)


def prev(state="none", depth=0, pct=50.0):
    return {"signal_state": state, "tier_depth": depth, "cur_percentile": pct}


# ---------- 首跑抑制 ----------
def test_first_run_no_signal():
    assert evaluate(q(38.5), None, STRATEGY_CFG) is None
    assert evaluate(q(80.0), None, STRATEGY_CFG) is None
    assert evaluate(q(50.0), {}, STRATEGY_CFG) is None    # 状态条目缺 signal_state 同样保守


# ---------- 买入跨越与档位(左闭右开)----------
@pytest.mark.parametrize("pct,tier_label", [
    (39.9, "35–40"), (35.0, "35–40"),          # [35,40) → 1x
    (34.9, "25–35"), (25.0, "25–35"),          # [25,35) → 1.5x
    (24.9, "15–25"), (15.0, "15–25"),          # [15,25) → 2x
    (14.9, "0–15"), (0.0, "0–15"),             # <15 → 3x
])
def test_buy_tiers(pct, tier_label):
    s = evaluate(q(pct), prev(state="none"), STRATEGY_CFG)
    assert s is not None and s.direction == "buy" and s.tier_label == tier_label


def test_buy_threshold_edge():
    """40.0 本身不算'跌入 40 以下';40.1 在中性区不产生信号。"""
    assert evaluate(q(40.0), prev(state="none"), STRATEGY_CFG) is None
    assert evaluate(q(40.1), prev(state="none"), STRATEGY_CFG) is None


# ---------- 卖出跨越与档位(>= 触发,90 闭区间)----------
@pytest.mark.parametrize("pct,tier_label", [
    (75.0, "75–80"), (79.9, "75–80"),          # [75,80)
    (80.0, "80–85"), (84.9, "80–85"),          # [80,85)
    (85.0, "85–90"), (89.9, "85–90"),          # [85,90)
    (90.0, "≥90"), (100.0, "≥90"),             # [90,100]
])
def test_sell_tiers(pct, tier_label):
    s = evaluate(q(pct), prev(state="none"), STRATEGY_CFG)
    assert s is not None and s.direction == "sell" and s.tier_label == tier_label


def test_sell_threshold_edge():
    """74.9 尚未升入,不触发。"""
    assert evaluate(q(74.9), prev(state="none"), STRATEGY_CFG) is None


# ---------- 档位加深 / 减轻 ----------
def test_tier_deepened_triggers():
    """buy 区内 1x → 1.5x:必须再次提醒。"""
    s = evaluate(q(30.0), prev(state="buy", depth=1, pct=38.0), STRATEGY_CFG)
    assert s is not None and s.tier_label == "25–35"


def test_tier_unchanged_no_signal():
    """同方向同档位重复运行:不提醒(幂等)。"""
    assert evaluate(q(38.0), prev(state="buy", depth=1, pct=38.5), STRATEGY_CFG) is None
    assert evaluate(q(78.0), prev(state="sell", depth=1, pct=77.0), STRATEGY_CFG) is None


def test_tier_shallowed_no_signal():
    """档位减轻(1.5x → 1x):静默,仅状态更新。"""
    assert evaluate(q(38.0), prev(state="buy", depth=2, pct=30.0), STRATEGY_CFG) is None


def test_neutral_zone_resets():
    assert evaluate(q(50.0), prev(state="buy", depth=2, pct=30.0), STRATEGY_CFG) is None
    # 回到中性后再跌入 40 以下:新一轮跨阈值,触发
    s = evaluate(q(39.0), prev(state="none", pct=50.0), STRATEGY_CFG)
    assert s is not None and s.tier_label == "35–40"


# ---------- 方向切换 ----------
def test_sell_to_buy_crossing():
    s = evaluate(q(30.0), prev(state="sell", depth=1, pct=76.0), STRATEGY_CFG)
    assert s is not None and s.direction == "buy"


def test_buy_to_sell_crossing():
    s = evaluate(q(76.0), prev(state="buy", depth=1, pct=38.0), STRATEGY_CFG)
    assert s is not None and s.direction == "sell"
