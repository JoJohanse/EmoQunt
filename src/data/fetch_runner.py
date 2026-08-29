"""取数回退链统一 runner：逐源尝试 → health 打点 → 回退下一源，全败返回空。

深模块、小接口：调用方只负责按优先级组装 ``(source_name, callable)`` 有序列表，
"try 源 → record_source_health → 空则下一个" 的重复模式收口于此。异常与空
DataFrame 都视为该源失败；打点、warning 日志与回退推进均为 runner 独占职责。

用法（见 data_manager 三条回退链）::

    chain = [
        ('tushare', lambda: fetch_tushare(...)),
        ('sina', lambda: fetch_sina(...)),
    ]
    df = run_source_chain(chain, logger=logger, context="A股 000001 日线")
"""
from __future__ import annotations

import logging
from typing import Callable, Sequence, Tuple

import pandas as pd

from src.data.source_health import record as record_source_health

# 单个数据源描述：(源名, 取数 callable)。callable 无参调用，返回 DataFrame。
SourceEntry = Tuple[str, Callable[[], pd.DataFrame]]


def run_source_chain(
    chain: Sequence[SourceEntry],
    *,
    logger: logging.Logger,
    context: str,
) -> pd.DataFrame:
    """按顺序尝试各数据源，返回首个成功源的数据。

    :param chain: (source_name, fetch_callable) 有序列表，按优先级排列；
                  fetch_callable 无参调用，返回 DataFrame（None/空视为失败）。
    :param logger: 日志对象，用于记录单源失败/空数据与全链失败的 warning。
    :param context: 上下文描述（如 "个股 000001 日线"），仅用于日志定位。
    :return: 首个成功源返回的 DataFrame；全部失败（或 chain 为空）返回空 DataFrame。
    """
    for name, fetch in chain:
        try:
            df = fetch()
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
