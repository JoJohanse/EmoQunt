"""K线服务：获取标的 OHLCV 数据，供首页看板 ECharts 蜡烛图。

提取自原 web_app.py 的 /api/kline 路由业务逻辑。
"""
import logging
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)

from src.data.columns import ZH_TO_EN as _COL_MAP


def get_kline(stock_code: str, market: str = "zh_a", days: int = 180) -> Dict:
    """获取 K 线 OHLCV 数据。

    :param stock_code: 股票代码
    :param market: 'zh_a' 或 'us'
    :param days: 最近交易日数（30-730）
    :return: {code, market, name, dates, ohlcv, volumes}
    """
    from src.data import Stock

    if market not in ("zh_a", "us"):
        market = "zh_a"
    days = max(30, min(int(days), 730))

    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    stock = Stock(stock_code, market=market)
    df, _ = stock.get_stock_data(
        start_date=start_date, end_date=end_date,
        adjust='qfq' if market == 'us' else 'hfq', type='daily',
    )
    if df is None or df.empty:
        return {"code": stock_code, "market": market, "name": "",
                "dates": [], "ohlcv": [], "volumes": []}

    df = df.rename(columns=_COL_MAP)
    for c in ('open', 'high', 'low', 'close', 'volume'):
        if c in df.columns:
            df[c] = df[c].astype(float)
    df = df.sort_values('date').tail(days).reset_index(drop=True)

    dates = df['date'].astype(str).tolist()
    ohlcv = df[['open', 'close', 'low', 'high']].values.tolist()
    volumes = df['volume'].tolist() if 'volume' in df.columns else []

    name = ''
    try:
        name = stock.get_stock_name() or ''
    except Exception:
        pass

    return {
        "code": stock_code, "market": market, "name": name,
        "dates": dates, "ohlcv": ohlcv, "volumes": volumes,
    }
