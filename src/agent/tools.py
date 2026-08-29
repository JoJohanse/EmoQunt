"""Agent 工具集：将 EmoQunt 现有数据/分析函数包装为 LangChain @tool。

设计原则：
- 每个 @tool 包装一个现有函数，返回 LLM 友好的 JSON 字符串（英文 key、数值摘要）。
- 防御性包装：网络/运行失败时返回 {"error": "..."}，不抛异常给 agent，让 agent 据此回退说明。
- 复用 src.data / src.backtest / src.factor / src.Strategy 现有实现，不重复逻辑。
"""

import json
import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _err(msg: str) -> str:
    """统一的错误返回格式（JSON 字符串）。"""
    return json.dumps({"error": str(msg)}, ensure_ascii=False)


def _json(obj) -> str:
    """JSON 序列化，确保中文可读。"""
    return json.dumps(obj, ensure_ascii=False, default=str)


@tool
def get_stock_quote(stock_code: str, market: str = "zh_a", days: int = 30) -> str:
    """查询个股最近 N 个交易日的行情摘要（开盘/最高/最低/收盘/成交量 + 涨跌幅）。

    Args:
        stock_code: 股票代码。A股为6位数字（如 000001），美股为字母代码（如 AAPL）。
        market: 市场，'zh_a'（A股，默认）或 'us'（美股）。
        days: 返回最近多少个交易日，默认30，最大120。
    """
    try:
        from src.data.data_manager import Stock
        days = max(5, min(int(days), 120))
        stock = Stock(stock_code, market=market)
        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days * 2 + 30)).strftime("%Y%m%d")
        df, _ = stock.get_stock_data(start_date=start, end_date=end,
                                     adjust="qfq" if market == "us" else "hfq", type="daily")
        if df is None or df.empty:
            return _err(f"无法获取 {stock_code} 的行情数据")
        df = df.tail(days).reset_index(drop=True)
        # 中文列名 → 英文（引用统一常量）
        from src.data.columns import ZH_TO_EN
        df = df.rename(columns={k: v for k, v in ZH_TO_EN.items() if k in df.columns})
        for c in ("open", "high", "low", "close", "volume"):
            if c in df.columns:
                df[c] = df[c].astype(float)
        last = df.iloc[-1]
        prev_close = df["close"].iloc[-2] if len(df) > 1 else last["close"]
        chg_pct = (last["close"] - prev_close) / prev_close * 100 if prev_close else 0.0
        name = ""
        try:
            name = stock.get_stock_name() or ""
        except Exception:
            pass
        summary = {
            "code": stock_code, "market": market, "name": name,
            "last_date": str(last.get("date", "")),
            "close": round(float(last["close"]), 2),
            "change_pct": round(chg_pct, 2),
            "high": round(float(last["high"]), 2),
            "low": round(float(last["low"]), 2),
            "volume": int(last["volume"]) if "volume" in last else None,
            "period_days": len(df),
            "period_high": round(float(df["high"].max()), 2),
            "period_low": round(float(df["low"].min()), 2),
        }
        return _json(summary)
    except Exception as e:
        logger.exception("get_stock_quote failed")
        return _err(f"行情查询失败: {e}")


@tool
def get_index_quote(index_code: str = "000300", market: str = "zh_a", days: int = 30) -> str:
    """查询指数最近 N 个交易日的行情摘要。A股默认沪深300(000300)，美股默认标普500(SP500)。

    Args:
        index_code: 指数代码。A股如 000300/000001；美股用 SP500/NASDAQ/DOWJONES/NASDAQ100。
        market: 市场，'zh_a'（默认）或 'us'。
        days: 最近交易日数，默认30。
    """
    try:
        from src.data.data_manager import get_index_data
        from datetime import datetime, timedelta
        days = max(5, min(int(days), 120))
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days * 2 + 30)).strftime("%Y%m%d")
        df = get_index_data(index_code, start_date=start, end_date=end, market=market)
        if df is None or df.empty:
            return _err(f"无法获取指数 {index_code} 的数据")
        df = df.tail(days).reset_index(drop=True)
        col_map = {"时间": "date", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        for c in ("close", "high", "low"):
            if c in df.columns:
                df[c] = df[c].astype(float)
        last = df.iloc[-1]
        prev = df["close"].iloc[-2] if len(df) > 1 else last["close"]
        chg = (last["close"] - prev) / prev * 100 if prev else 0.0
        return _json({
            "index": index_code, "market": market,
            "last_date": str(last.get("date", "")),
            "close": round(float(last["close"]), 2),
            "change_pct": round(chg, 2),
            "period_days": len(df),
            "period_high": round(float(df["high"].max()), 2),
            "period_low": round(float(df["low"].min()), 2),
        })
    except Exception as e:
        logger.exception("get_index_quote failed")
        return _err(f"指数查询失败: {e}")


@tool
def run_backtest(strategy_name: str, stock_code: str, start_date: str, end_date: str,
                 market: str = "zh_a", initial_capital: float = 100000.0) -> str:
    """运行策略回测，返回绩效指标摘要（总收益/年化/夏普/最大回撤/胜率/Alpha/Beta/信息比率）。

    Args:
        strategy_name: 策略名称（须已存在，如 'test'）。
        stock_code: 股票代码。
        start_date: 开始日期 YYYY-MM-DD。
        end_date: 结束日期 YYYY-MM-DD。
        market: 市场，'zh_a'（默认）或 'us'。
        initial_capital: 初始资金，默认 100000。
    """
    try:
        from src.services.backtest import run_json, validate_backtest_params
        # 统一经 services.backtest 校验入口（与双前端路由共用同一校验链/默认基准映射）
        params, error = validate_backtest_params({
            "strategy_name": strategy_name, "stock_code": stock_code,
            "start_date": start_date, "end_date": end_date,
            "initial_capital": initial_capital, "market": market,
        })
        if error:
            return _err(error)
        result = run_json(**params)
        m = result.get("metrics", {})
        # 摘要：仅指标，不含完整时序（太长）；键名为 LLM 友好的 *_pct 形态，
        # 底层数值转换统一走 serialize.safe_float
        from src.utils.serialize import safe_float
        summary = {
            "strategy": strategy_name, "stock": stock_code, "market": params["market"],
            "total_return_pct": round(safe_float(m.get("总收益率", 0)) * 100, 2),
            "annual_return_pct": round(safe_float(m.get("年化收益率", 0)) * 100, 2),
            "sharpe": round(safe_float(m.get("夏普比率", 0)), 3),
            "max_drawdown_pct": round(safe_float(m.get("最大回撤", 0)) * 100, 2),
            "win_rate_pct": round(safe_float(m.get("胜率", 0)) * 100, 2),
            "profit_loss_ratio": round(safe_float(m.get("盈亏比", 0)), 3),
        }
        if "Alpha" in m:
            summary["alpha_pct"] = round(safe_float(m["Alpha"]) * 100, 2)
        if "Beta" in m:
            summary["beta"] = round(safe_float(m["Beta"]), 3)
        if "信息比率" in m:
            summary["info_ratio"] = round(safe_float(m["信息比率"]), 3)
        return _json(summary)
    except Exception as e:
        logger.exception("run_backtest tool failed")
        return _err(f"回测失败: {e}")


@tool
def get_sentiment(top_n: int = 10) -> str:
    """查询当日板块情绪排行与整体舆情（热门新闻数、平均情绪、top板块及其成分股）。

    Args:
        top_n: 返回前 N 个板块，默认10。
    """
    try:
        from src.factor.sentiment import get_or_generate_sentiment_data
        data, news = get_or_generate_sentiment_data()
        if not data:
            return _err("暂无舆情数据（可能需要联网抓取新闻）")
        sectors = data.get("top_sectors", [])[:top_n]
        out_sectors = []
        for s in sectors:
            stocks = [{"code": st.get("code"), "name": st.get("name")}
                      for st in (s.get("stocks") or [])[:3]]
            out_sectors.append({"name": s.get("name"), "sentiment": s.get("sentiment"),
                                "sample_stocks": stocks})
        return _json({
            "update_time": data.get("timestamp", ""),
            "news_count": len(news) if news else 0,
            "average_score": round(data.get("average_score", 0), 3),
            "signal": data.get("signal", ""),
            "top_sectors": out_sectors,
        })
    except Exception as e:
        logger.exception("get_sentiment failed")
        return _err(f"舆情查询失败: {e}")


@tool
def get_stock_signal(stock_code: str) -> str:
    """查询某只 A 股所属行业、最近情绪快照得分与交易信号（基于历史情绪快照，避免未来函数）。

    Args:
        stock_code: A股6位代码（如 000001）。
    """
    try:
        from src.data.data_manager import load_sentiment_snapshots, build_stock_sentiment_series
        from src.factor.daily_recommend import StockSectorMapper
        mapper = StockSectorMapper()
        sector = mapper.get_sector_by_code(stock_code)
        if not sector:
            return _err(f"无法定位 {stock_code} 的行业（可能非沪深300成分股）")
        panel = load_sentiment_snapshots()
        if panel is None or panel.empty:
            return _json({"code": stock_code, "sector": sector,
                          "sentiment": None, "note": "无历史情绪快照"})
        series, _ = build_stock_sentiment_series(panel, stock_code)
        if series is None or series.empty:
            return _json({"code": stock_code, "sector": sector,
                          "sentiment": None, "note": "快照中无该行业数据"})
        latest = float(series.iloc[-1])
        latest_date = str(series.index[-1].date())
        # 信号阈值（与 sentiment_config 一致）
        signal = "buy" if latest >= 0.3 else ("sell" if latest <= -0.3 else "hold")
        return _json({
            "code": stock_code, "sector": sector,
            "latest_sentiment": round(latest, 3), "latest_date": latest_date,
            "signal": signal, "snapshot_count": len(series),
        })
    except Exception as e:
        logger.exception("get_stock_signal failed")
        return _err(f"个股信号查询失败: {e}")


@tool
def get_daily_recommendations(top_n: int = 10) -> str:
    """查询当日个股推荐（综合评分排名，含板块、评分、推荐理由）。

    Args:
        top_n: 返回前 N 只，默认10。
    """
    try:
        from src.factor.daily_recommend import get_cached_recommendation
        data = get_cached_recommendation()
        recs = (data or {}).get("recommendations", [])[:top_n]
        out = [{
            "rank": r.get("rank"), "code": r.get("code"), "name": r.get("name"),
            "sector": r.get("sector"), "score": r.get("score"), "reason": r.get("reason"),
        } for r in recs]
        top_sectors = [{"name": s.get("name"), "sentiment": s.get("sentiment")}
                       for s in (data or {}).get("top_sectors", [])[:3]]
        return _json({
            "date": (data or {}).get("date", ""),
            "top_sectors": top_sectors,
            "recommendations": out,
        })
    except Exception as e:
        logger.exception("get_daily_recommendations failed")
        return _err(f"推荐查询失败: {e}")


@tool
def list_strategies() -> str:
    """列出所有可用的回测策略（名称、描述、是否自定义、模板）与策略模板。"""
    try:
        from src.Strategy.strategy_manager import load_user_strategies, get_strategy_templates
        user = load_user_strategies()
        templates = get_strategy_templates()
        strategies = []
        for name, cfg in user.items():
            strategies.append({
                "name": name, "description": cfg.get("description", ""),
                "is_user_strategy": True, "template": cfg.get("template", ""),
            })
        out_templates = [{"key": k, "name": v.get("name", ""), "description": v.get("description", "")}
                         for k, v in templates.items()]
        return _json({"strategies": strategies, "templates": out_templates})
    except Exception as e:
        logger.exception("list_strategies failed")
        return _err(f"策略列表查询失败: {e}")


# 工具列表（供 agent 使用）
ALL_TOOLS = [
    get_stock_quote,
    get_index_quote,
    run_backtest,
    get_sentiment,
    get_stock_signal,
    get_daily_recommendations,
    list_strategies,
]
