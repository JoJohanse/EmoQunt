"""取数回退链统一 runner：逐源尝试 → health 打点 → 回退下一源，全败返回空。

深模块、小接口：调用方只负责按优先级组装 ``(source_name, callable)`` 有序列表，
"try 源 → record_source_health → 空则下一个" 的重复模式收口于此。异常与空
DataFrame 都视为该源失败；打点、warning 日志与回退推进均为 runner 独占职责。

每源硬超时（Round3）：akshare/yfinance/tushare 底层 requests 未设 timeout，
单个挂死调用会永久占住 FastAPI 共享线程池并阻塞整条回退链——超时（默认
``QDT_SOURCE_TIMEOUT`` 秒，30s；传 0 关闭）即视为该源失败，推进下一源。
Python 线程不可强杀：超时后弃等，后台线程继续跑到自然结束（daemon，不阻塞
进程退出），同源并发调用不受影响。

用法（见 data_manager 三条回退链）::

    chain = [
        ('tushare', lambda: fetch_tushare(...)),
        ('sina', lambda: fetch_sina(...)),
    ]
    df = run_source_chain(chain, logger=logger, context="A股 000001 日线")
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

import pandas as pd

from src.data.source_health import record as record_source_health

# 单个数据源描述：(源名, 取数 callable)。callable 无参调用，返回 DataFrame。
SourceEntry = Tuple[str, Callable[[], pd.DataFrame]]

# 每源默认硬超时（秒）；QDT_SOURCE_TIMEOUT=0 关闭超时
DEFAULT_SOURCE_TIMEOUT = 30.0


def source_timeout() -> float:
    """读每源硬超时配置（秒）。<=0 表示关闭（同步直调）。"""
    from src.utils.env import get_env_float

    return get_env_float("QDT_SOURCE_TIMEOUT", DEFAULT_SOURCE_TIMEOUT)


def _call_with_timeout(fn: Callable[[], pd.DataFrame], timeout: float,
                       logger: logging.Logger, source: str) -> pd.DataFrame:
    """带硬超时地执行取数 callable；超时抛 TimeoutError（调用方按失败回退）。

    daemon 线程 + join(timeout) 非阻塞模式：超时后本函数立刻返回控制权，
    挂死的网络调用留在后台线程自然消亡。结果经 dict 传递（线程间无共享状态）。
    """
    outcome: Dict[str, Any] = {}

    def _runner() -> None:
        try:
            outcome["df"] = fn()
        except BaseException as e:  # noqa: BLE001 - 后台线程内异常必须带回主线程
            outcome["err"] = e

    t = threading.Thread(target=_runner, daemon=True, name=f"qdt-source-{source}")
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"数据源 {source} 超时（>{timeout:g}s），已放弃等待")
    if "err" in outcome:
        raise outcome["err"]
    return outcome.get("df")


def run_source_chain(
    chain: Sequence[SourceEntry],
    *,
    logger: logging.Logger,
    context: str,
    timeout: Optional[float] = None,
) -> pd.DataFrame:
    """按顺序尝试各数据源，返回首个成功源的数据。

    :param chain: (source_name, fetch_callable) 有序列表，按优先级排列；
                  fetch_callable 无参调用，返回 DataFrame（None/空视为失败）。
    :param logger: 日志对象，用于记录单源失败/空数据与全链失败的 warning。
    :param context: 上下文描述（如 "个股 000001 日线"），仅用于日志定位。
    :param timeout: 单源硬超时秒数；None 用 QDT_SOURCE_TIMEOUT（默认 30s），
                    <=0 关闭超时（同步直调）。
    :return: 首个成功源返回的 DataFrame；全部失败（或 chain 为空）返回空 DataFrame。
    """
    if timeout is None:
        timeout = source_timeout()
    for name, fetch in chain:
        try:
            df = _call_with_timeout(fetch, timeout, logger, name) if timeout and timeout > 0 else fetch()
        except Exception as e:
            logger.warning(f"[{context}] 数据源 {name} 获取失败: {e}，尝试下一源")
            record_source_health(name, False)
            continue
        if df is None or df.empty:
            logger.warning(f"[{context}] 数据源 {name} 返回空数据，尝试下一源")
            record_source_health(name, False)
            continue
        record_source_health(name, True)
        return df
    logger.warning(f"[{context}] 所有数据源均失败")
    return pd.DataFrame()
