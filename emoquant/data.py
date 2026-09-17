"""emoquant.data —— 数据 API。

防未来函数默认值（与 code_loader 的 phase 语义一致）：
- ``get_price`` 的 ``end`` 缺省：initialize 阶段 = 回测结束日（允许一次性预热
  全区间指标历史，示例模式按当日下标取 rolling 值，无未来函数）；
  handle_data 阶段 = 当前交易日（逐 bar 拉数看不到未来）；
  显式传入超过回测结束日的 end 会被截断。
- 情绪快照无论阶段都只暴露"当前交易日及之前"。

预热历史请在 initialize 内显式传入更早的 start。
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from emoquant._runtime import get_host

# 交易日历缓存（进程级：回测期间日期集合不变；TTL 防止长期驻留进程过期）
_calendar_cache: dict = {}
_calendar_lock = threading.Lock()
_sentiment_panel_cache: Optional[pd.DataFrame] = None
_sentiment_cache_time: float = 0.0
_SENTIMENT_TTL_SECONDS = 600.0


def get_price(code: Optional[str] = None, start: str = "", end: Optional[str] = None,
              market: Optional[str] = None, adjust: Optional[str] = None) -> pd.DataFrame:
    """获取日线 OHLCV（DataFrame，date 索引，open/high/low/close/volume）。

    :param code: 股票代码，缺省 = 回测标的
    :param start: 开始日期 YYYY-MM-DD（必填）
    :param end: 结束日期。缺省时按阶段取值：initialize = 回测结束日（预热），
        handle_data = 当前交易日；显式传入超过回测结束日会被截断（防未来函数）
    :param market: 'zh_a'/'us'，缺省 = 回测市场
    :param adjust: 复权，缺省跟随回测（A股 hfq / 美股 qfq）
    """
    host = get_host()
    return host.get_price(code=code, start=start, end=end, market=market, adjust=adjust)


def get_prev_trade_date(date: str, exchange: str = "SH", n: int = 1) -> Optional[str]:
    """取 date 之前第 n 个 A 股交易日（YYYY-MM-DD）。

    :param date: 参考日期 YYYY-MM-DD
    :param exchange: 交易所（预留参数，当前统一使用 A 股日历）
    :param n: 往前第几个交易日，默认 1
    :return: 交易日字符串；无法计算时返回 None
    """
    dates = _trading_dates_around(date)
    prior = [d for d in dates if d < str(date)]
    if len(prior) < n:
        return None
    return prior[-n]


def get_sentiment(code: Optional[str] = None, as_of: Optional[str] = None) -> Optional[dict]:
    """查询个股所属行业的最近情绪快照（只用当日及之前快照，避免未来函数）。

    :param code: A 股 6 位代码，缺省 = 回测标的（美股返回 None）
    :param as_of: 截止日期 YYYY-MM-DD，缺省 = 回测当前交易日
    :return: {"date": "YYYY-MM-DD", "score": float, "sector": str} 或 None
    """
    host = get_host()
    return host.get_sentiment(code=code, as_of=as_of)


def get_factor(*args, **kwargs):
    """因子库数据接口（P3 因子库上线后开放，当前未实现）。"""
    raise NotImplementedError("get_factor 将随因子库功能开放，当前版本不可用")


# ---------------------------------------------------------------------------
# 内部：交易日历（基于上证指数日线，经 data_manager 多源回退链）
# ---------------------------------------------------------------------------
def _trading_dates_around(date: str) -> list:
    """取 date 前后各约两年的 A 股交易日字符串列表（升序，带进程级缓存）。"""
    key = str(date)[:4]  # 按年分段缓存
    with _calendar_lock:
        cached = _calendar_cache.get(key)
    if cached is not None:
        return cached

    from src.data.data_manager import get_index_data

    d = datetime.strptime(str(date)[:10], "%Y-%m-%d")
    start = (d - timedelta(days=760)).strftime("%Y%m%d")
    end = (d + timedelta(days=760)).strftime("%Y%m%d")
    dates: list = []
    try:
        df = get_index_data("000001", start_date=start, end_date=end, market="zh_a")
        if df is not None and not df.empty and "时间" in df.columns:
            idx = pd.to_datetime(df["时间"])
            dates = sorted({t.strftime("%Y-%m-%d") for t in idx})
    except Exception:
        dates = []
    with _calendar_lock:
        _calendar_cache[key] = dates
    return dates
