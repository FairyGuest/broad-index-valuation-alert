"""编排入口:采集 → 校验 → 判定 → 推送 → 状态与前端数据落盘。

用法:
  python -m valuation_alert.main               # 正式运行(推送 + 写状态)
  python -m valuation_alert.main --dry-run     # 采集与判定照常,只打印消息,不推送不落盘
  python -m valuation_alert.main --test-push   # 向所有已配置渠道发一条测试消息
"""
from __future__ import annotations

import argparse
import copy
import logging
import sys
import time
from datetime import date

from . import docsdata, message, state as state_mod
from .config import DEFAULT_CONFIG_DIR, beijing_now, in_schedule_window, load_indices_cfg, load_notify_cfg
from .datasources import DataError, build_source
from .models import IndexQuote, Signal
from .notify import build_notifiers, send_with_retry
from .strategy import evaluate

log = logging.getLogger("valuation_alert")

# 数据新鲜度告警阈值(天):蛋卷/纳指为日频,multpl 为月频
STALE_DAYS = {"danjuan": 15, "nasdaq": 15, "multpl": 75}


def collect(indices: list[dict]) -> tuple[list[IndexQuote], list[str]]:
    quotes, skipped = [], []
    for index_cfg in indices:
        name, source_name = index_cfg["name"], index_cfg["source"]
        source = build_source(source_name)
        t0 = time.monotonic()
        try:
            quote = source.get_quote(index_cfg)
        except DataError as e:
            log.warning("%s 采集失败(%s):%s", name, source_name, e)
            skipped.append(name)
            continue
        elapsed = time.monotonic() - t0
        log.info("%s 采集成功(%s,%.1fs):分位 %.1f%%,数据日期 %s",
                 name, source_name, elapsed, quote.percentile, quote.data_date)
        stale_days = STALE_DAYS.get(source_name, 15)
        try:
            data_age = (beijing_now().date() - date.fromisoformat(quote.data_date)).days
        except ValueError:
            data_age = -1
        if data_age > stale_days:
            log.warning("%s 数据已过期(%d 天),继续使用但消息中标注", name, data_age)
            quote.source_label += f"(数据已{data_age}天未更新)"
        quotes.append(quote)
    return quotes, skipped


def push(title: str, body: str, notify_cfg: dict) -> bool:
    primary, fallback = build_notifiers(notify_cfg)
    if not primary and not fallback:
        log.error("没有任何可用推送渠道(检查环境变量/Secrets)")
        return False
    results = [send_with_retry(n, title, body,
                               notify_cfg.get("retry", {}).get("attempts", 3),
                               notify_cfg.get("retry", {}).get("backoff_seconds"))
               for n in primary]
    if results and not any(results):
        log.warning("主渠道全部失败,降级到备用渠道")
        results += [send_with_retry(n, title, body) for n in fallback]
    return any(results)


def _send_or_preview(title: str, body: str, dry_run: bool, kind: str,
                     notify_cfg: dict) -> bool:
    """统一出口:dry-run 打印预览,正式运行推送。返回是否'已送达'。"""
    if dry_run:
        print(f"\n===== DRY-RUN {kind}消息预览 =====\n标题:{title}\n\n{body}\n============================")
        return True
    log.info("推送消息(%s):%s", kind, title)
    return push(title, body, notify_cfg)


def run(dry_run: bool = False, test_push: bool = False,
        config_dir: str = DEFAULT_CONFIG_DIR) -> int:
    # GitHub 对定时任务调度不可靠(实测连续丢失),策略改为高频 cron + 窗口自检:
    # 定时触发只在北京时间 09:15–20:00 窗口内执行,窗口外秒退(不耗额度);
    # 手动触发(workflow_dispatch)不受限制。
    import os
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not in_schedule_window(beijing_now()):
        log.info("非运行窗口(北京 09:15–20:00 之外),定时触发跳过")
        return 0

    indices_cfg = load_indices_cfg(config_dir)
    notify_cfg = load_notify_cfg(config_dir)
    strategy_cfg = indices_cfg["strategy"]
    now = beijing_now()
    today, now_txt = now.date().isoformat(), now.strftime("%Y-%m-%d %H:%M")
    pages_url = notify_cfg.get("pages_url", "")

    if test_push:
        title = "估值提醒系统:测试消息"
        body = message.render_test_body(now_txt, pages_url)
        ok = push(title, body, notify_cfg)
        log.info("测试消息%s", "已发送" if ok else "发送失败")
        return 0 if ok else 1

    quotes, skipped = collect(indices_cfg["indices"])
    if not quotes:
        log.error("全部指数采集失败,推送告警后退出")
        push("估值提醒系统:运行失败告警",
             f"{now_txt}(北京时间)所有指数采集失败,请检查 GitHub Actions 日志。"
             f"\n数据源可能变动或限流。", notify_cfg)
        return 1

    state = state_mod.load()
    old_state = copy.deepcopy(state)    # 深拷贝快照(apply_quote 原地修改嵌套结构)
    is_baseline = not state["indices"]    # 首跑:无任何指数状态
    prev_map = {code: (state_mod.entry_for(state, code) or {}).get("cur_percentile")
                for code in (i["code"] for i in indices_cfg["indices"])}
    signals: list[Signal] = []
    for quote in quotes:
        entry = state_mod.entry_for(state, quote.code)
        signal = evaluate(quote, entry, strategy_cfg)
        state_mod.apply_quote(state, quote, strategy_cfg, today, signal)
        if signal:
            signals.append(signal)
            log.info("产生信号:%s %s %s 档(%s→%.1f%%)", quote.name, signal.direction_cn,
                     signal.tier_label,
                     f"{signal.prev_percentile:g}%" if signal.prev_percentile is not None else "首日",
                     signal.cur_percentile)
    log.info("判定完成:%d 个信号,%d 指数成功,%d 跳过", len(signals), len(quotes), len(skipped))

    # 消息决策(每日最多推送一条):信号 > 首跑基线 > 每日日报
    daily_digest = notify_cfg.get("daily_digest", False)
    digested_today = state.get("last_digest_date") == today
    if signals:
        title = message.render_title(signals)
        body = message.render_body(signals, quotes, skipped, pages_url)
        sent = _send_or_preview(title, body, dry_run, "信号", notify_cfg)
    elif is_baseline:
        title, body = message.render_baseline(quotes, strategy_cfg, skipped, pages_url)
        sent = _send_or_preview(title, body, dry_run, "首跑基线", notify_cfg)
    elif daily_digest and not digested_today:
        title, body = message.render_digest(quotes, prev_map, strategy_cfg,
                                            skipped, pages_url, today)
        sent = _send_or_preview(title, body, dry_run, "日报", notify_cfg)
    else:
        sent = False
        if dry_run:
            reason = "今日已推送过" if digested_today else "daily_digest 关闭"
            print(f"\n===== DRY-RUN:无信号且无需日报({reason}),今日不推送 =====")
    # 推送成功(或 dry-run 预览过)才记当日已发,保证幂等;渠道全失败则下次运行重试
    if sent and (signals or is_baseline or daily_digest):
        state["last_digest_date"] = today

    if dry_run:
        print("DRY-RUN:不写入状态与前端数据")
        return 0

    if not state_mod.materially_changed(old_state, state):
        log.info("数据无实质变化,跳过落盘(避免高频提交触发 Pages 构建冲突)")
        return 0

    state_mod.save(state, now=now)
    docsdata.write_latest(quotes, strategy_cfg, now_txt)
    docsdata.append_history(quotes, today)
    docsdata.append_signals(signals, today, now_txt)
    log.info("状态与前端数据已更新(state/ + docs/data/)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="宽基估值分位定投提醒系统")
    parser.add_argument("--dry-run", action="store_true", help="只打印消息,不推送不落盘")
    parser.add_argument("--test-push", action="store_true", help="发送测试消息验证推送配置")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    return run(dry_run=args.dry_run, test_push=args.test_push, config_dir=args.config_dir)


if __name__ == "__main__":
    sys.exit(main())
