"""因子分析服务：构建横截面因子面板 + 前瞻收益，调用 FactorAnalyzer。

激活休眠的 src/analysis/factor_analyzer.py（对标 Qlib 多因子框架）。
流程：
    HS300 成分股 → 并发取 OHLCV（命中 DB 缓存）→ 计算每 (日期,股票) 因子值
    + 下一周期前瞻收益 → FactorAnalyzer(IC/Rank IC/ICIR/分层/单调性) → JSON。

面板契约（与 FactorAnalyzer 一致）：index=日期, columns=股票代码, values=标量。
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 并发取数线程数（复用 daily_recommend 的并发模式）
try:
    _FETCH_CONCURRENCY = max(1, min(int(os.environ.get("QDT_DATA_FETCH_CONCURRENCY", "8")), 32))
except (TypeError, ValueError):
    _FETCH_CONCURRENCY = 8

# 支持的因子类型
FACTOR_TYPES = ("momentum", "rsi", "volatility", "volume_ratio")

# 因子计算参数
MOMENTUM_WINDOW = 20          # 动量：20 日收益率
RSI_PERIOD = 14               # RSI 周期
VOLATILITY_WINDOW = 20        # 波动率：20 日收益标准差
VOLUME_MA_PERIOD = 20         # 成交量比：量 / 20 日均量


def _rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """计算 RSI（Wilder 平滑）。"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder 平滑（指数移动平均）
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _compute_factor(df: pd.DataFrame, factor_type: str) -> pd.Series:
    """从单只股票的 OHLCV（DatetimeIndex, 中文列名）计算因子时序。

    :return: pd.Series，index=日期，values=因子值（已 dropna）
    """
    if df is None or df.empty or "收盘" not in df.columns:
        return pd.Series(dtype=float)
    close = pd.to_numeric(df["收盘"], errors="coerce")
    if factor_type == "momentum":
        factor = close.pct_change(MOMENTUM_WINDOW)
    elif factor_type == "rsi":
        factor = _rsi(close, RSI_PERIOD)
    elif factor_type == "volatility":
        ret = close.pct_change()
        factor = ret.rolling(VOLATILITY_WINDOW).std()
    elif factor_type == "volume_ratio":
        if "成交量" not in df.columns:
            return pd.Series(dtype=float)
        vol = pd.to_numeric(df["成交量"], errors="coerce")
        factor = vol / vol.rolling(VOLUME_MA_PERIOD).mean()
    else:
        return pd.Series(dtype=float)
    return factor.dropna()


def _fetch_one(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """取单只股票 OHLCV（中文列名，DatetimeIndex 升序）。失败返回空。"""
    try:
        from src.data.data_manager import Stock
        stock = Stock(code, market="zh_a")
        df = stock.get_stock_data(
            start_date=start_date, end_date=end_date, adjust="qfq", type="daily",
        )
        if df is None or df.empty or "时间" not in df.columns:
            return pd.DataFrame()
        df["时间"] = pd.to_datetime(df["时间"])
        df = df.set_index("时间").sort_index()
        return df
    except Exception as e:
        logger.debug(f"因子分析取数失败 {code}: {e}")
        return pd.DataFrame()


def _build_panels(
    codes: List[str], start_date: str, end_date: str, factor_type: str, forward_period: int,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """构建因子面板 + 前瞻收益面板。

    :return: (factor_panel, forward_returns_panel, fetched_count)
    """
    factor_series_dict: Dict[str, pd.Series] = {}
    fwd_ret_dict: Dict[str, pd.Series] = {}
    fetched = 0

    def _work(code):
        nonlocal fetched
        df = _fetch_one(code, start_date, end_date)
        if df.empty:
            return
        fetched += 1
        f = _compute_factor(df, factor_type)
        if f.empty:
            return
        factor_series_dict[code] = f
        # 前瞻收益：未来 N 日收益（shift(-N)），对齐到因子日期
        close = pd.to_numeric(df["收盘"], errors="coerce")
        fwd = close.shift(-forward_period) / close - 1
        fwd_ret_dict[code] = fwd.dropna()

    # 并发取数（面板构建受 I/O 限制，线程池有效）
    with ThreadPoolExecutor(max_workers=_FETCH_CONCURRENCY) as ex:
        list(ex.map(_work, codes))

    if not factor_series_dict:
        return pd.DataFrame(), pd.DataFrame(), fetched

    factor_panel = pd.DataFrame(factor_series_dict)
    fwd_panel = pd.DataFrame(fwd_ret_dict)
    if fwd_panel.empty:
        return pd.DataFrame(), pd.DataFrame(), fetched

    # 对齐到公共日期 + 公共股票（取交集）
    common_codes = sorted(set(factor_panel.columns) & set(fwd_panel.columns))
    if not common_codes:
        return pd.DataFrame(), pd.DataFrame(), fetched
    factor_panel = factor_panel[common_codes].sort_index()
    fwd_panel = fwd_panel[common_codes].sort_index()
    common_idx = factor_panel.index.intersection(fwd_panel.index)
    factor_panel = factor_panel.loc[common_idx]
    fwd_panel = fwd_panel.loc[common_idx]
    return factor_panel, fwd_panel, fetched


def analyze_factor(
    factor_type: str,
    start_date: str,
    end_date: str,
    universe: str = "hs300",
    n_quantiles: int = 5,
    forward_period: int = 5,
) -> Dict:
    """因子分析主入口。

    :return: JSON 可序列化的 dict（IC 统计/IC 时序/分层/单调性），或 {"error": ...}
    """
    from src.analysis import FactorAnalyzer
    from src.data.data_manager import get_hs300_stocks

    if factor_type not in FACTOR_TYPES:
        return {"error": f"不支持的因子类型: {factor_type}（可选 {FACTOR_TYPES}）"}

    # 股票池
    try:
        codes = get_hs300_stocks()
    except Exception as e:
        return {"error": f"获取股票池失败: {e}"}
    if not codes:
        return {"error": "股票池为空"}
    # 限制规模以保证响应时间（HS300 全量首跑慢；可后续加预热）
    # 这里不强制限制，依赖 DB 缓存 + 并发取数提速

    sd = start_date.replace("-", "")
    ed = end_date.replace("-", "")

    factor_panel, fwd_panel, fetched = _build_panels(
        codes, sd, ed, factor_type, forward_period,
    )
    if factor_panel.empty or fwd_panel.empty:
        return {"error": f"有效数据不足（取到 {fetched} 只），无法构建因子面板"}

    try:
        analyzer = FactorAnalyzer(factor_panel, fwd_panel)
        ic_series = analyzer.calculate_ic()            # pearson IC
        rank_ic_series = analyzer.calculate_rank_ic()
        ic_stats = analyzer.calculate_ic_stats()        # dict
        quant = analyzer.quantile_analysis(n_quantiles) # dict
        mono = analyzer.factor_monotonicity(n_quantiles)  # dict
    except Exception as e:
        logger.warning(f"FactorAnalyzer 执行失败: {e}")
        return {"error": f"因子分析计算失败: {e}"}

    # ---- 序列化（FactorAnalyzer 返回嵌套 dict + Series/DataFrame）----
    def round_or_none(v, ndigits=6):
        """数值四舍五入；NaN/inf/非数值返回 None（区别于 utils.serialize.safe_float
        返回 0.0 —— 因子分析中缺失值用 None 比 0.0 更准确，0 会误导为"无预测力")。"""
        try:
            fv = float(v)
            return round(fv, ndigits) if np.isfinite(fv) else None
        except (TypeError, ValueError):
            return None

    ic_stats_out = {
        "ic_mean": round_or_none(ic_stats.get("ic_mean")),
        "rank_ic_mean": round_or_none(ic_stats.get("rank_ic_mean")),
        "ic_ir": round_or_none(ic_stats.get("ic_ir")),
        "rank_ic_ir": round_or_none(ic_stats.get("rank_ic_ir")),
        "ic_win_rate": round_or_none(ic_stats.get("ic_win_rate")),
        "rank_ic_win_rate": round_or_none(ic_stats.get("rank_ic_win_rate")),
        "ic_positive_rate": round_or_none(ic_stats.get("ic_positive_rate")),
    }

    # IC 时序（对齐 ic / rank_ic）
    ic_df = pd.DataFrame({"ic": ic_series, "rank_ic": rank_ic_series}).dropna()
    ic_series_out = [
        {"date": d.strftime("%Y-%m-%d"),
         "ic": round_or_none(row["ic"]), "rank_ic": round_or_none(row["rank_ic"])}
        for d, row in ic_df.iterrows()
    ]

    # 分层统计
    quantile_stats = quant.get("quantile_stats", {}) or {}
    quant_rows = []
    for q in sorted(quantile_stats.keys()):
        s = quantile_stats[q] or {}
        quant_rows.append({
            "quantile": q,
            "mean_return": round_or_none(s.get("mean_return")),
            "sharpe_ratio": round_or_none(s.get("sharpe_ratio")),
            "win_rate": round_or_none(s.get("win_rate")),
        })

    # 分层累计收益（quantile_returns DataFrame → 每组 cumprod）
    quant_returns = quant.get("quantile_returns")
    quant_cum_out: List[Dict] = []
    if isinstance(quant_returns, pd.DataFrame) and not quant_returns.empty:
        cum = (1 + quant_returns.fillna(0)).cumprod()
        quant_cols = list(cum.columns)
        for d, row in cum.iterrows():
            quant_cum_out.append({
                "date": d.strftime("%Y-%m-%d"),
                "values": [round_or_none(v, 4) for v in row[quant_cols].tolist()],
            })
        # 附列名（前端需要）
        quant_cum_meta = quant_cols
    else:
        quant_cum_meta = []

    return {
        "factor_type": factor_type,
        "ic_stats": ic_stats_out,
        "ic_series": ic_series_out,
        "quantile_stats": quant_rows,
        "quantile_cumreturns": quant_cum_out,
        "quantile_labels": quant_cum_meta,
        "monotonicity": {
            "monotonic": bool(mono.get("monotonic", False)),
            "monotonicity_ratio": round_or_none(mono.get("monotonicity_ratio")),
        },
        "universe_size": len(factor_panel.columns),
        "fetched_count": fetched,
        "date_range": {"start": str(factor_panel.index.min().date()),
                       "end": str(factor_panel.index.max().date())},
    }
