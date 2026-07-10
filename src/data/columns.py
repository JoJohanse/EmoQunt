"""统一的 OHLCV 列名契约。

全站行情数据使用中文列名（开盘/最高/最低/收盘/成交量/时间），
此前散落在 data_manager(×3)、backtest_manager、daily_recommend、technical、tools、web_app(kline)
各写一份字面量映射。本模块统一为唯一来源，各消费者引用常量。

使用方式：
    from src.data.columns import OHLCV_COLS, EN_TO_ZH, ZH_TO_EN

    # akshare/yfinance 英文列 → 中文
    df = df.rename(columns=EN_TO_ZH)

    # 中文列 → 英文（API 输出用）
    df = df.rename(columns=ZH_TO_EN)
"""

# 中文列名常量
DATE = '时间'
OPEN = '开盘'
HIGH = '最高'
LOW = '最低'
CLOSE = '收盘'
VOLUME = '成交量'
AMOUNT = '成交额'
TURNOVER = '换手率'
OUTSTANDING_SHARE = '流通股数'

# 英文 → 中文重命名映射（data 源 → 内部统一 schema）
EN_TO_ZH = {
    'date': DATE, 'day': DATE,
    'open': OPEN, 'high': HIGH, 'low': LOW, 'close': CLOSE,
    'volume': VOLUME, 'amount': AMOUNT,
    'turnover': TURNOVER, 'outstanding_share': OUTSTANDING_SHARE,
}

# 中文 → 英文重命名映射（内部 schema → API/agent 输出）
ZH_TO_EN = {
    DATE: 'date', OPEN: 'open', HIGH: 'high', LOW: 'low',
    CLOSE: 'close', VOLUME: 'volume', AMOUNT: 'amount',
    TURNOVER: 'turnover', OUTSTANDING_SHARE: 'outstanding_share',
}
