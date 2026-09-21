"""消息模板与前端数据输出测试。"""
import json

from valuation_alert import docsdata, message
from valuation_alert.models import IndexQuote, Signal
from conftest import STRATEGY_CFG


def make_quote(pct, code="SH000300", name="沪深300", pe=13.4, proxy=False):
    return IndexQuote(code=code, name=name, percentile=pct, pe=pe,
                      data_date="2026-09-18", source_label="蛋卷·PE分位(近10年)",
                      proxy=proxy, window_label="近10年")


def test_digest_renders_zones_and_delta():
    quotes = [make_quote(38.2), make_quote(78.9, "SH000905", "中证500")]
    prev_map = {"SH000300": 41.5, "SH000905": 78.9}   # 一跌入、一持平
    title, body = message.render_digest(quotes, prev_map, STRATEGY_CFG, [], "", "2026-09-21")
    assert title == "估值日报:四指数分位一览"
    # 每指数成块:标题行 / 分位行 / 建议行,块间空行(Server酱 Markdown 靠空行分段)
    assert "【沪深300】🟢定投区 · 35–40 档" in body
    assert "分位 38.2%(较上次 -3.3 个点)· PE 13.4" in body
    assert "【中证500】🔴止盈区 · 75–80 档" in body
    assert "较上次持平" in body
    assert "四指数估值状态 · 2026-09-21" in body
    assert body.count("\n\n") >= 3    # 指数块之间确实有空行分段


def test_digest_without_prev():
    _, body = message.render_digest([make_quote(65.0)], {}, STRATEGY_CFG, ["中证500"], "")
    assert "首次记录" in body
    assert "中性区" in body
    assert "⚠️ 采集失败:中证500" in body


def test_title_single_and_multi():
    s1 = Signal("SH000300", "沪深300", "buy", "35–40", "x", 1, 38.2, 41.5, make_quote(38.2))
    assert message.render_title([s1]) == "估值提醒:沪深300 已进入定投区间"
    s2 = Signal("NDX", "纳斯达克100", "sell", "≥90", "y", 4, 91.0, 74.0, make_quote(91.0))
    assert message.render_title([s1, s2]) == "估值提醒:纳斯达克100 等2个指数进入止盈区间"


def test_body_contains_required_fields():
    buy = Signal("SH000300", "沪深300", "buy", "35–40", "基础定投 1 倍(建议 1 倍)", 1,
                 38.2, 41.5, make_quote(38.2))
    proxy_q = make_quote(72.0, "NDX", "纳斯达克100", pe=None, proxy=True)
    body = message.render_body([buy], [buy.quote, proxy_q], ["中证500"], "https://x.io")
    for kw in ["【买入】", "38.2", "41.5", "跌破 40%", "35–40", "基础定投",
               "数据日期 2026-09-18", "非 PE 口径", "采集失败已跳过:中证500",
               "采集状态:2/3", "https://x.io"]:
        assert kw in body, f"正文缺少:{kw}"
    # 代理指数必须出现口径警示
    assert "非 PE 口径" in body


def test_latest_and_history_roundtrip(tmp_path):
    quotes = [make_quote(38.2), make_quote(78.9, "SH000905", "中证500")]
    docsdata.write_latest(quotes, STRATEGY_CFG, "2026-09-21 18:30", str(tmp_path))
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    by_code = {i["code"]: i for i in latest["indices"]}
    assert by_code["SH000300"]["zone"] == "buy"
    assert by_code["SH000300"]["tier"]["label"] == "35–40"
    assert by_code["SH000905"]["zone"] == "sell"
    assert latest["thresholds"] == {"buy": 40, "sell": 75}

    docsdata.append_history(quotes, "2026-09-21", str(tmp_path))
    docsdata.append_history(quotes, "2026-09-22", str(tmp_path))
    docsdata.append_history(quotes, "2026-09-21", str(tmp_path))   # 同日覆盖
    rows = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert [r["date"] for r in rows] == ["2026-09-21", "2026-09-22"]
    assert rows[0]["SH000300"] == 38.2
