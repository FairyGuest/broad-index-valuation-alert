"""测试公共:fixture 路径。"""
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str):
    import json
    return json.loads(fixture_text(name))


STRATEGY_CFG = {
    "buy_threshold": 40,
    "sell_threshold": 75,
    "buy_tiers": [
        {"max": 15, "multiple": 3.0, "label": "0–15", "action": "定投 3 倍,可动用备用资金"},
        {"max": 25, "multiple": 2.0, "label": "15–25", "action": "定投 2 倍"},
        {"max": 35, "multiple": 1.5, "label": "25–35", "action": "定投 1.5 倍"},
        {"max": 40, "multiple": 1.0, "label": "35–40", "action": "基础定投 1 倍"},
    ],
    "sell_tiers": [
        {"min": 90, "ratio": "清仓或仅保留极低底仓", "label": "≥90"},
        {"min": 85, "ratio": "卖出剩余大部分", "label": "85–90"},
        {"min": 80, "ratio": "再卖出 30%", "label": "80–85"},
        {"min": 75, "ratio": "卖出持仓 20%–30%", "label": "75–80"},
    ],
}
