"""配置加载与校验。"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

DEFAULT_CONFIG_DIR = "config"


def beijing_now() -> datetime:
    """统一的北京时间(Actions runner 为 UTC,不能依赖系统时区)。"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def _load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误(应为映射):{path}")
    return data


def load_indices_cfg(config_dir: str = DEFAULT_CONFIG_DIR) -> dict:
    cfg = _load_yaml(os.path.join(config_dir, "indices.yaml"))
    strategy = cfg.get("strategy", {})
    buy_tiers = strategy.get("buy_tiers", [])
    sell_tiers = strategy.get("sell_tiers", [])
    if not buy_tiers or not sell_tiers:
        raise ValueError("buy_tiers / sell_tiers 不能为空")
    if buy_tiers[-1]["max"] != strategy.get("buy_threshold"):
        raise ValueError("buy_tiers 最浅档的 max 必须等于 buy_threshold,否则存在无法命中的分位")
    if sell_tiers[-1]["min"] != strategy.get("sell_threshold"):
        raise ValueError("sell_tiers 最浅档的 min 必须等于 sell_threshold")
    codes = [i["code"] for i in cfg["indices"]]
    if len(codes) != len(set(codes)):
        raise ValueError(f"指数代码重复:{codes}")
    return cfg


def load_notify_cfg(config_dir: str = DEFAULT_CONFIG_DIR) -> dict:
    return _load_yaml(os.path.join(config_dir, "notify.yaml"))
