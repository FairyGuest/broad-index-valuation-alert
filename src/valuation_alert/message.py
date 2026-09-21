"""消息模板:把信号列表 + 全量快照渲染为推送标题与正文。

正文为"纯文本 + 轻量符号",在 Server酱(Markdown)与邮件(plain)中均保持可读。
"""
from __future__ import annotations

from .models import IndexQuote, Signal


def render_title(signals: list[Signal]) -> str:
    deepest = max(signals, key=lambda s: s.depth)
    verb = "定投" if deepest.direction == "buy" else "止盈"
    if len(signals) > 1:
        return f"估值提醒:{deepest.name} 等{len(signals)}个指数进入{verb}区间"
    return f"估值提醒:{deepest.name} 已进入{verb}区间"


def _signal_line(s: Signal) -> list[str]:
    prev_txt = f"(上次 {s.prev_percentile:g}%," if s.prev_percentile is not None else "("
    if s.direction == "buy":
        head = f"【买入】{s.name}:PE 分位 {s.cur_percentile:g}% {prev_txt}跌破 40%)"
    else:
        head = f"【止盈】{s.name}:PE 分位 {s.cur_percentile:g}% {prev_txt}升破 75%)"
    lines = [head, f"  档位 {s.tier_label} | {s.action_text}"]
    metric = f"PE {s.quote.pe:g}" if s.quote.pe is not None else "价格代理口径"
    lines.append(f"  数据日期 {s.quote.data_date} | {metric} | 来源:{s.quote.source_label}")
    if s.quote.proxy:
        lines.append("  * 注意:该指数为价格分位代理,非 PE 口径,仅供方向参考")
    return lines


def _watch_line(q: IndexQuote) -> str:
    metric = f"PE {q.pe:g}" if q.pe is not None else "价格代理,非 PE 口径"
    return (f"【观察】{q.name}:分位 {q.percentile:g}%({metric},"
            f"数据日期 {q.data_date},来源:{q.source_label})")


def render_body(signals: list[Signal], quotes: list[IndexQuote],
                skipped: list[str], pages_url: str = "") -> str:
    sig_codes = {s.code for s in signals}
    lines: list[str] = []
    for s in signals:
        lines.extend(_signal_line(s))
    watched = [q for q in quotes if q.code not in sig_codes]
    if watched:
        lines.append("")
        lines.append("—— 其余指数(仅展示,不触发提醒)——")
        lines.extend(_watch_line(q) for q in watched)
    if skipped:
        lines.append("")
        lines.append(f"—— 采集失败已跳过:{'、'.join(skipped)}(下次运行自动重试)——")
    lines.append("")
    lines.append(f"采集状态:{len(quotes)}/{len(quotes) + len(skipped)} 个指数成功")
    if pages_url:
        lines.append(f"查看详情:{pages_url}")
    return "\n".join(lines)


def render_test_body(now_txt: str, pages_url: str = "") -> str:
    lines = ["这是一条测试消息:估值提醒系统配置成功。",
             f"发出时间:{now_txt}(北京时间)",
             "正式提醒只在分位数跨越阈值(40% / 75%)或档位加深时发送。"]
    if pages_url:
        lines.append(f"估值页面:{pages_url}")
    return "\n".join(lines)


def render_baseline(quotes, strategy_cfg: dict, skipped: list[str],
                    pages_url: str = "") -> tuple[str, str]:
    """首跑基线报告:告知当前各指数状态,此后仅在变化时提醒。"""
    from .strategy import zone_of
    lines = ["系统首次运行,以下为当前估值状态基线:",
             "(此后仅在分位跨越 40%/75% 或档位加深时提醒)"]
    for q in quotes:
        zone, tier = zone_of(q.percentile, strategy_cfg)
        metric = f"PE {q.pe:g}" if q.pe is not None else "价格代理"
        if zone == "buy":
            info = f"定投区 {q.percentile:g}% → {tier['label']} 档:{tier['action']}"
        elif zone == "sell":
            info = f"止盈区 {q.percentile:g}% → {tier['label']} 档:建议{tier['ratio']}"
        else:
            info = f"中性区 {q.percentile:g}%(40%–75% 之间,不提醒)"
        lines.append(f"【{q.name}】{info}({metric},{q.data_date},{q.source_label})")
    if skipped:
        lines.append(f"采集失败:{'、'.join(skipped)}")
    if pages_url:
        lines.append(f"查看详情:{pages_url}")
    return "估值提醒系统已上线:当前状态基线", "\n".join(lines)
