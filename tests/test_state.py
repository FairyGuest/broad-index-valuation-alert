"""状态管理测试:连续运行幂等、状态转移正确性。"""
from valuation_alert import state as st
from valuation_alert.models import IndexQuote
from valuation_alert.strategy import evaluate
from conftest import STRATEGY_CFG


def q(pct):
    return IndexQuote(code="SH000300", name="沪深300", percentile=pct,
                      data_date="2026-09-21")


def step(state, pct, day):
    """一次运行对该指数的完整处理,返回产生的信号。"""
    quote = q(pct)
    signal = evaluate(quote, st.entry_for(state, "SH000300"), STRATEGY_CFG)
    st.apply_quote(state, quote, STRATEGY_CFG, day, signal)
    return signal


def test_multi_day_scenario():
    """核心场景链:首跑 → 加深(报)→ 同档重复(不报)→ 回升减轻(不报)→ 再加深(报)。"""
    state = st.empty_state()

    assert step(state, 38.0, "d1") is None            # 首跑:只记录
    entry = state["indices"]["SH000300"]
    assert entry["signal_state"] == "buy" and entry["tier_depth"] == 1

    assert step(state, 38.2, "d1") is None            # 同日重复运行:不重发
    assert step(state, 38.1, "d2") is None            # 次日同档:仍不重发(同档位仅报一次)

    s = step(state, 30.0, "d3")                       # 加深 1x → 1.5x:报
    assert s is not None and s.tier_label == "25–35"
    assert step(state, 30.1, "d4") is None            # 加深后同档:不重发

    assert step(state, 38.0, "d5") is None            # 回升减轻:静默
    s2 = step(state, 28.0, "d6")                      # 再次加深:报(新一轮加码)
    assert s2 is not None

    assert step(state, 50.0, "d7") is None            # 回到中性:重置
    entry = state["indices"]["SH000300"]
    assert entry["signal_state"] == "none" and entry["tier_depth"] == 0

    s3 = step(state, 39.0, "d8")                      # 新一轮跨阈值:报
    assert s3 is not None and s3.tier_label == "35–40"


def test_apply_records_signal_fields():
    state = st.empty_state()
    step(state, 50.0, "2026-09-20")               # 首跑:中性,仅建立状态
    signal = step(state, 76.0, "2026-09-21")      # 次日升破 75:触发
    assert signal is not None
    entry = state["indices"]["SH000300"]
    assert entry["signal_state"] == "sell"
    assert entry["last_signal"] == "sell:75–80"
    assert entry["last_push_date"] == "2026-09-21"


def test_save_and_load_roundtrip(tmp_path):
    state = st.empty_state()
    step(state, 38.0, "d1")
    path = str(tmp_path / "state.json")
    st.save(state, path)
    loaded = st.load(path)
    assert loaded["indices"]["SH000300"]["cur_percentile"] == 38.0
    assert loaded["updated_at"]


def test_load_missing_file():
    assert st.load("no/such/file.json") == st.empty_state()
