"""Agent 策略上下文注入（P4：会话绑定代码策略）。

方案（计划 D6）：不改静态系统提示词——那会击穿按语言缓存的编译产物
（agent._agent_cache），而是每请求把 strategy_id 解析为一段「策略上下文」
文本，作为一条 SystemMessage 插到最后一条用户消息之前。策略不存在时
静默跳过（仅日志），不阻断对话。

摘要内容刻意压缩（源码截断、运行/调优各取最近 3 条），控制在数千字符内：
上下文每请求都进 prompt，体积直接换算成 token 成本。
"""

import logging
from typing import List, Optional

from langchain_core.messages import BaseMessage, SystemMessage

from src.utils.i18n import get_lang

logger = logging.getLogger(__name__)

# 源码在上下文里的截断长度（防超长策略撑爆 prompt；完整源码用 get_strategy 工具取）
_SOURCE_CLIP = 2500
# 最近回测 / 调优任务各带几条
_RECENT_LIMIT = 3


def _is_en() -> bool:
    return get_lang().startswith("en")


def build_strategy_context(strategy_id: int) -> Optional[str]:
    """把策略库 id 渲染为双语上下文文本；策略不存在返回 None。

    :param strategy_id: 策略库（code 策略）id
    :return: 上下文文本（已按请求语言本地化），策略不存在时 None
    """
    from src.services.strategy_library import get_strategy_detail

    try:
        detail = get_strategy_detail(int(strategy_id))
    except Exception:
        logger.exception("策略上下文构建失败: strategy_id=%s", strategy_id)
        return None
    if detail is None:
        logger.warning("策略上下文跳过：策略不存在 strategy_id=%s", strategy_id)
        return None

    en = _is_en()
    lines: List[str] = ["[策略上下文] 当前对话绑定以下策略。" if not en else
                        "[Strategy Context] This conversation is bound to the following strategy."]
    lines.append(f"- id: {detail['id']}")
    lines.append(f"- {'名称' if not en else 'Name'}: {detail['name']}")
    lines.append(f"- {'市场' if not en else 'Market'}: {detail.get('market', 'zh_a')}")
    if detail.get("description"):
        lines.append(f"- {'描述' if not en else 'Description'}: {detail['description']}")

    effective = detail.get("params") or {}
    defaults = detail.get("default_params") or {}
    if effective:
        lines.append(f"- {'生效参数（DB 为真相）' if not en else 'Effective params (DB is the truth)'}: "
                     + ", ".join(f"{k}={v}" for k, v in effective.items()))
        drifted = {k: v for k, v in defaults.items() if k in effective and defaults[k] != effective[k]}
        if drifted:
            lines.append(f"- {'源码默认值已被参数覆盖' if not en else 'Source defaults overridden by params'}: "
                         + ", ".join(f"{k}={v}" for k, v in drifted.items()))

    source = detail.get("source") or ""
    if len(source) > _SOURCE_CLIP:
        source = source[:_SOURCE_CLIP] + ("\n...（源码过长已截断，完整源码用 get_strategy 查看）"
                                          if not en else
                                          "\n... (truncated; use get_strategy for the full source)")
    lines.append(f"\n```python\n{source}\n```")

    recent_runs = _recent_runs(int(strategy_id), en)
    if recent_runs:
        lines.append(f"\n{'最近回测' if not en else 'Recent backtest runs'}:")
        lines.extend(recent_runs)

    recent_tuning = _recent_tuning(int(strategy_id), en)
    if recent_tuning:
        lines.append(f"\n{'最近调优任务' if not en else 'Recent tuning tasks'}:")
        lines.extend(recent_tuning)

    lines.append(
        "\n（用户说「该策略 / 当前策略」即指上述策略；对它回测或调优时无需再向用户确认 id，"
        "参数调优走 create_tuning_task，参数以上述生效参数为基准。）"
        if not en else
        "\n(When the user says \"this strategy / the current strategy\" they mean the one above; "
        "no need to ask for the id when backtesting or tuning it. Tuning goes through "
        "create_tuning_task, with the effective params above as the baseline.)"
    )
    return "\n".join(lines)


def _recent_runs(strategy_id: int, en: bool) -> List[str]:
    """最近成功回测的一行式摘要（指标中文键保持 API 契约）。"""
    from src.services.backtest_runs import list_runs

    try:
        runs = list_runs(strategy_kind="code", strategy_id=strategy_id, status="succeeded",
                         limit=_RECENT_LIMIT)
    except Exception:
        logger.exception("策略上下文读取回测历史失败: strategy_id=%s", strategy_id)
        return []
    out = []
    for r in runs:
        m = r.get("metrics") or {}
        out.append(
            "- run #{id} {stock} {start}~{end}: 总收益率 {ret}, 夏普 {sharpe}, 最大回撤 {mdd}".format(
                id=r.get("id"), stock=r.get("stock_code"),
                start=r.get("start_date"), end=r.get("end_date"),
                ret=m.get("总收益率"), sharpe=m.get("夏普比率"), mdd=m.get("最大回撤"),
            ) if not en else
            "- run #{id} {stock} {start}~{end}: total return {ret}, Sharpe {sharpe}, max drawdown {mdd}".format(
                id=r.get("id"), stock=r.get("stock_code"),
                start=r.get("start_date"), end=r.get("end_date"),
                ret=m.get("总收益率"), sharpe=m.get("夏普比率"), mdd=m.get("最大回撤"),
            )
        )
    return out


def _recent_tuning(strategy_id: int, en: bool) -> List[str]:
    """最近调优任务的一行式摘要（含状态与最优组合）。"""
    from src.services.tuning import list_tuning_tasks

    try:
        tasks = list_tuning_tasks(strategy_kind="code", strategy_id=strategy_id, limit=_RECENT_LIMIT)
    except Exception:
        logger.exception("策略上下文读取调优历史失败: strategy_id=%s", strategy_id)
        return []
    out = []
    for t in tasks:
        best = f", {'最优' if not en else 'best'}=#{t['best_combo_index']}" if t.get("best_combo_index") is not None else ""
        # 注意：str.format 模板里不能内嵌 Python 条件表达式（会被当成字段名解析），
        # 单位词必须先在模板外求值
        unit = "组" if not en else " combos"
        out.append(
            "- tuning task #{id} [{status}] {combos}{unit}{best}".format(
                id=t.get("id"), status=t.get("status"),
                combos=t.get("total_combos"), unit=unit, best=best,
            )
        )
    return out


def coerce_strategy_id(raw) -> Optional[int]:
    """请求体里的 strategy_id → int 或 None（前端可能传数字、数字字符串或 null/空串/0）。"""
    if raw in (None, "", 0):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def insert_context(messages: List[BaseMessage], text: Optional[str]) -> List[BaseMessage]:
    """把已构建的上下文文本插到最后一条用户消息前（text 为空原样返回）。

    与 build_strategy_context 分离：SSE 路径先在线程池里构建文本
    （含 SQLite 查询，不能占用事件循环），再在协程内做纯列表拼接。
    """
    if not text:
        return messages
    ctx = SystemMessage(content=text)
    # 找最后一条 HumanMessage：上下文紧贴当前问题，语义是"带着这份资料回答下面这句"
    insert_at = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        from langchain_core.messages import HumanMessage
        if isinstance(messages[i], HumanMessage):
            insert_at = i
            break
    return [*messages[:insert_at], ctx, *messages[insert_at:]]


def with_strategy_context(messages: List[BaseMessage], strategy_id: Optional[int]) -> List[BaseMessage]:
    """同步便捷入口（线程池路径用）：按 id 构建上下文并插入。"""
    if not strategy_id:
        return messages
    return insert_context(messages, build_strategy_context(strategy_id))
