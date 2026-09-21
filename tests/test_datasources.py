"""数据源解析测试:基于真实接口响应快照(tests/fixtures/)。"""
import pytest

from valuation_alert.datasources import DataError
from valuation_alert.datasources.danjuan import DanjuanSource
from valuation_alert.datasources.multpl import MultplSource, parse_rows
from valuation_alert.datasources.nasdaq import NasdaqSource
from conftest import fixture_json, fixture_text


# ---------- 蛋卷(A股 + 美股) ----------
def test_danjuan_sh000300():
    src = DanjuanSource(raw=fixture_text("danjuan_eva.json"))
    quote = src.get_quote({"code": "SH000300", "name": "沪深300",
                           "source_label": "蛋卷·PE分位(近10年)"})
    assert quote.name == "沪深300"
    assert 0 < quote.percentile <= 100
    assert quote.pe > 0
    assert not quote.proxy
    assert quote.data_date  # YYYY-MM-DD,来自 ts 时间戳


def test_danjuan_us_indices():
    """蛋卷列表接口同样覆盖标普500与纳指100(四指数同源同口径)。"""
    src = DanjuanSource(raw=fixture_text("danjuan_eva.json"))
    spx = src.get_quote({"code": "SP500", "name": "标普500"})
    ndx = src.get_quote({"code": "NDX", "name": "纳斯达克100"})
    assert spx.percentile == 57.2 and spx.pe == pytest.approx(25.16, abs=0.01)
    assert ndx.percentile == 48.8 and ndx.pe == pytest.approx(30.48, abs=0.01)
    assert not ndx.proxy    # 已是真实 PE 口径,不再是价格代理


def test_danjuan_sh000905():
    src = DanjuanSource(raw=fixture_text("danjuan_eva.json"))
    quote = src.get_quote({"code": "SH000905", "name": "中证500"})
    assert 0 < quote.percentile <= 100


def test_danjuan_code_not_found():
    src = DanjuanSource(raw=fixture_text("danjuan_eva.json"))
    with pytest.raises(DataError):
        src.get_quote({"code": "XX999999", "name": "不存在"})


def test_danjuan_bad_payload():
    src = DanjuanSource(raw='{"unexpected": true}')
    with pytest.raises(DataError):
        src.get_quote({"code": "SH000300", "name": "沪深300"})


# ---------- multpl(标普500) ----------
def test_multpl_parse_rows():
    rows = parse_rows(fixture_text("multpl_pe.html"))
    assert len(rows) > 1000            # 1871 年至今约 1800+ 行
    assert rows[0][0] == "2026-09-18"  # 快照最新行:Sep 18, 2026
    assert rows[0][1] == pytest.approx(26.07, abs=0.01)


def test_multpl_quote():
    src = MultplSource(html=fixture_text("multpl_pe.html"))
    quote = src.get_quote({"code": "SP500", "name": "标普500", "window": 120})
    assert 0 <= quote.percentile <= 100
    assert quote.sample_size == 120
    assert quote.data_date == "2026-09-18"
    assert not quote.proxy


def test_multpl_insufficient_history():
    src = MultplSource(html=fixture_text("multpl_pe.html"))
    with pytest.raises(DataError):
        src.get_quote({"code": "SP500", "name": "标普500", "window": 99999})


# ---------- Nasdaq(纳指100 价格代理) ----------
def test_nasdaq_quote():
    src = NasdaqSource(raw_json=fixture_json("nasdaq_ndx_hist.json"))
    quote = src.get_quote({"code": "NDX", "name": "纳斯达克100",
                           "source_label": "Nasdaq·价格分位", "proxy": True})
    assert 0 <= quote.percentile <= 100
    assert quote.pe is None
    assert quote.proxy is True
    assert quote.sample_size == 2513   # 快照:10 年日线
    assert quote.data_date == "2026-09-18"


def test_nasdaq_close_comma_cleaned():
    """收盘价带千分位逗号(如 '29,644.17'),必须正确清洗。"""
    src = NasdaqSource(raw_json=fixture_json("nasdaq_ndx_hist.json"))
    quote = src.get_quote({"code": "NDX", "name": "纳斯达克100"})
    assert 0 < quote.percentile <= 100
