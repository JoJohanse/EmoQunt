"""K线服务：获取标的 OHLCV 数据，供首页看板 ECharts 蜡烛图。

提取自原 web_app.py 的 /api/kline 路由业务逻辑。
周期（日/周/月）在服务端聚合：数据链路统一取日线，再按真实交易日分组，
周线/月线的日期标签取组内最后一个交易日（与主流行情软件一致）。
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

from src.data.columns import ZH_TO_EN as _COL_MAP

_PERIODS = ("day", "week", "month")
# 各周期底层取数的自然日窗口系数：日线自然日≈交易日×1.5，周/月按更长窗口聚合后裁剪
_PERIOD_WINDOW_FACTOR = {"day": 1.5, "week": 7.5, "month": 32}
_MAX_WINDOW_DAYS = 6000
_ADJUSTS = ("qfq", "hfq", "nfq")

# A股指数代码 → 展示名。000001 与平安银行（个股）二义，不进自动识别表，
# 仅当前端显式传 kind='index' 时才按上证指数处理。
INDEX_NAMES = {
    "000001": "上证指数",
    "000300": "沪深300",
    "399001": "深证成指",
    "399006": "创业板指",
    "399300": "沪深300",
}
_US_INDEX_CODES = ("SP500", "NASDAQ", "DOWJONES", "NASDAQ100")


def _resolve_is_index(stock_code: str, market: str, kind: str) -> bool:
    """kind 显式指定优先；否则按无歧义规则自动识别指数代码。"""
    if kind == "index":
        return True
    if market == "us":
        return stock_code.upper() in _US_INDEX_CODES
    if stock_code in INDEX_NAMES and stock_code != "000001":
        return True
    # 深交所 399 开头只会是指数（个股为 000/002/300 开头）
    return market == "zh_a" and len(stock_code) == 6 and stock_code.startswith("399")


def _period_group_key(dates: pd.Series, period: str) -> pd.Series:
    """交易日分组的键：周=ISO 年-周号，月=年-月。跨年周归入 ISO 年避免错切。"""
    dt = pd.to_datetime(dates)
    if period == "week":
        iso = dt.dt.isocalendar()
        return iso["year"].astype(int).astype(str) + "-W" + iso["week"].astype(int).astype(str).str.zfill(2)
    return dt.dt.strftime("%Y-%m")


def _aggregate(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """日线 DataFrame 按周/月聚合为 OHLCV（date 取组内最后一个实际交易日）。"""
    if period == "day" or df.empty:
        return df
    df = df.copy()
    df["_key"] = _period_group_key(df["date"], period)
    agg = df.groupby("_key", sort=True).agg(
        date=("date", "last"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        **({"volume": ("volume", "sum")} if "volume" in df.columns else {}),
    ).reset_index()
    return agg


def get_kline(stock_code: str, market: str = "zh_a", days: int = 180,
              period: str = "day", adjust: Optional[str] = None,
              kind: str = "", start_date: str = "", end_date: str = "") -> Dict:
    """获取 K 线 OHLCV 数据。

    :param stock_code: 股票/指数代码
    :param market: 'zh_a' 或 'us'
    :param days: 返回的 K 线根数（30-730）；提供 start_date 时忽略（区间模式）
    :param period: 周期 'day'/'week'/'month'，周/月由日线服务端聚合
    :param adjust: 复权 'qfq'/'hfq'/'nfq'；None 时沿用旧默认（A股 hfq、美股 qfq）；指数忽略
    :param kind: '' 自动识别 / 'index' 强制按指数取数（用于 000001 这类二义代码）
    :param start_date: 可选区间起点 YYYY-MM-DD 或 YYYYMMDD；提供后按区间取数（回测买卖点对齐用）
    :param end_date: 可选区间终点，默认今天
    :return: {code, market, name, dates, ohlcv, volumes, period, adjust, kind}
    """
    from src.data import Stock

    if market not in ("zh_a", "us"):
        market = "zh_a"
    days = max(30, min(int(days), 730))
    period = period if period in _PERIODS else "day"
    if adjust is None or adjust == "":
        adjust = "qfq" if market == "us" else "hfq"
    elif adjust not in _ADJUSTS:
        adjust = "nfq"
    is_index = _resolve_is_index(stock_code, market, kind)
    if is_index:
        # 指数无复权概念
        adjust = "nfq"

    # 区间模式：显式给出起点时按 [start, end] 取数（不做 tail(days) 裁剪，
    # 仅以 _MAX_WINDOW_DAYS 兜底），供回测买卖点等需要与历史区间对齐的场景
    start_date = str(start_date or "").replace("-", "")
    end_date = str(end_date or "").replace("-", "")
    range_mode = len(start_date) == 8 and start_date.isdigit()
    if range_mode:
        if len(end_date) != 8 or not end_date.isdigit():
            end_date = datetime.now().strftime('%Y%m%d')
        window_days = min(
            max(30, (datetime.strptime(end_date, '%Y%m%d') - datetime.strptime(start_date, '%Y%m%d')).days + 1),
            _MAX_WINDOW_DAYS,
        )
    else:
        # 周/月需更长的日线窗口才能聚出 days 根
        window_days = int(days * _PERIOD_WINDOW_FACTOR[period]) + 10
        window_days = min(window_days, _MAX_WINDOW_DAYS)
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=window_days)).strftime('%Y%m%d')

    if is_index:
        from src.data.data_manager import get_index_data
        df = get_index_data(stock_code, start_date, end_date, market)
        name = INDEX_NAMES.get(stock_code, "")
    else:
        stock = Stock(stock_code, market=market)
        df, _ = stock.get_stock_data(
            start_date=start_date, end_date=end_date,
            adjust=adjust, type='daily',
        )
        name = ''
        try:
            name = stock.get_stock_name() or ''
        except Exception:
            pass
    if df is None or df.empty:
        return {"code": stock_code, "market": market, "name": name or "",
                "dates": [], "ohlcv": [], "volumes": [],
                "period": period, "adjust": adjust,
                "kind": "index" if is_index else ""}

    df = df.rename(columns=_COL_MAP)
    for c in ('open', 'high', 'low', 'close', 'volume'):
        if c in df.columns:
            df[c] = df[c].astype(float)
    df = df.sort_values('date').reset_index(drop=True)

    try:
        df = _aggregate(df, period)
    except Exception as e:
        logger.warning("K线 %s 周期聚合失败，回退日线: %s", stock_code, e)
        df = df.tail(days).reset_index(drop=True)
        period = "day"
    if not range_mode:
        df = df.tail(days).reset_index(drop=True)

    dates = df['date'].astype(str).tolist()
    ohlcv = df[['open', 'close', 'low', 'high']].values.tolist()
    volumes = df['volume'].tolist() if 'volume' in df.columns else []

    return {
        "code": stock_code, "market": market, "name": name or "",
        "dates": dates, "ohlcv": ohlcv, "volumes": volumes,
        "period": period, "adjust": adjust,
        "kind": "index" if is_index else "",
    }
