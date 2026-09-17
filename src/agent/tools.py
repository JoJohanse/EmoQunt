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

from src.utils.i18n import vmsg

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
        df = stock.get_stock_data(start_date=start, end_date=end,
                                  adjust="qfq" if market == "us" else "hfq", type="daily")
        if df is None or df.empty:
            return _err(vmsg("agentTool.noQuoteData", "无法获取 {code} 的行情数据", code=stock_code))
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
        return _err(vmsg("agentTool.quoteFailed", "行情查询失败: {err}", err=e))


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
            return _err(vmsg("agentTool.noIndexData", "无法获取指数 {code} 的数据", code=index_code))
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
        return _err(vmsg("agentTool.indexFailed", "指数查询失败: {err}", err=e))


@tool
def run_backtest(strategy_name: str, stock_code: str, start_date: str, end_date: str,
                 market: str = "zh_a", initial_capital: float = 100000.0,
                 strategy_kind: str = "template", strategy_id: int = 0) -> str:
    """运行策略回测，返回绩效指标摘要（总收益/年化/夏普/最大回撤/胜率/盈亏比/Alpha/Beta/信息比率）。

    Args:
        strategy_name: 策略名称。template 类填策略名；code 类填策略库中的名称。
        stock_code: 股票代码。
        start_date: 开始日期 YYYY-MM-DD。
        end_date: 结束日期 YYYY-MM-DD。
        market: 市场，'zh_a'（默认）或 'us'。
        initial_capital: 初始资金，默认 100000。
        strategy_kind: 'template'（模板策略，默认）或 'code'（策略库代码策略）。
        strategy_id: strategy_kind 为 'code' 时必填的策略库 id。
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
        if strategy_kind not in ("template", "code"):
            return _err(vmsg("library.badStrategyKind", "strategy_kind 仅支持 template 或 code"))
        if strategy_kind == "code":
            from src.services.strategy_library import get_code_strategy
            row = get_code_strategy(int(strategy_id) if strategy_id else None, strategy_name)
            if row is None:
                return _err(vmsg("library.codeStrategyNotFound",
                                 "代码策略不存在（需提供有效的 strategy_id）"))
            params["strategy_kind"] = "code"
            params["strategy_id"] = int(row["id"])
            params["strategy_name"] = row["name"]
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
        return _err(vmsg("agentTool.backtestFailed", "回测失败: {err}", err=e))


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
            return _err(vmsg("agentTool.noSentimentData", "暂无舆情数据（可能需要联网抓取新闻）"))
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
        return _err(vmsg("agentTool.sentimentFailed", "舆情查询失败: {err}", err=e))


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
            return _err(vmsg("agentTool.noSector", "无法定位 {code} 的行业（可能非沪深300成分股）", code=stock_code))
        panel = load_sentiment_snapshots()
        if panel is None or panel.empty:
            return _json({"code": stock_code, "sector": sector,
                          "sentiment": None, "note": vmsg("agentTool.noSnapshots", "无历史情绪快照")})
        series, _ = build_stock_sentiment_series(panel, stock_code)
        if series is None or series.empty:
            return _json({"code": stock_code, "sector": sector,
                          "sentiment": None, "note": vmsg("agentTool.noSectorSnapshot", "快照中无该行业数据")})
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
        return _err(vmsg("agentTool.signalFailed", "个股信号查询失败: {err}", err=e))


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
        return _err(vmsg("agentTool.recommendFailed", "推荐查询失败: {err}", err=e))


@tool
def list_strategies() -> str:
    """列出所有可用的回测策略（模板策略 + 策略库代码策略）与模板。

    返回每个策略的名称、描述、种类（template/code）、id（code 类回测时需要）。
    """
    try:
        from src.Strategy.strategy_manager import load_user_strategies, get_strategy_templates
        from src.services.strategy_library import list_strategies as list_code_strategies

        user = load_user_strategies()
        templates = get_strategy_templates()
        strategies = []
        for name, cfg in user.items():
            strategies.append({
                "name": name, "description": cfg.get("description", ""),
                "kind": "template", "template": cfg.get("template", ""),
            })
        try:
            for s in list_code_strategies():
                strategies.append({
                    "name": s.get("name"), "description": s.get("description", ""),
                    "kind": "code", "id": s.get("id"), "market": s.get("market"),
                    "last_run": s.get("last_run"),
                })
        except Exception:
            pass  # 策略库不可用时仅列模板策略
        out_templates = [{"key": k, "name": v.get("name", ""), "description": v.get("description", "")}
                         for k, v in templates.items()]
        return _json({"strategies": strategies, "templates": out_templates})
    except Exception as e:
        logger.exception("list_strategies failed")
        return _err(vmsg("agentTool.strategiesFailed", "策略列表查询失败: {err}", err=e))


@tool
def create_strategy(name: str, source: str, description: str = "", market: str = "zh_a") -> str:
    """创建代码策略（AI 生成策略的落库入口）：校验源码后保存到策略库。

    Args:
        name: 策略名称（2-50字符，中文/英文/数字/下划线/连字符）。
        source: 完整 Python 源码，必须定义 initialize(context) 与 handle_data(context, data)，
                可选 STRATEGY_PARAMS 字典（带中文注释，作为可调参数）。
        description: 策略描述（一句话说明策略逻辑）。
        market: 市场，'zh_a'（默认）或 'us'。

    返回 {"id": 策略id, "params": 生效参数}。源码不合法时返回 errors 列表，应修正后重试。
    """
    try:
        from src.services.strategy_library import create_code_strategy
        result = create_code_strategy(name=name, description=description,
                                      market=market, source=source)
        return _json(result)
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.exception("create_strategy tool failed")
        return _err(vmsg("agentTool.createStrategyFailed", "创建策略失败: {err}", err=e))


@tool
def update_strategy(strategy_id: int, source: str = "", description: str = "",
                    params: str = "") -> str:
    """更新策略库代码策略（源码/描述/参数；更新前自动保存版本快照，可回滚）。

    Args:
        strategy_id: 策略库 id。
        source: 新的完整源码（传空字符串表示不修改代码）。
        description: 新描述（传空字符串表示不修改）。
        params: 新参数 JSON 字符串，如 '{"ma_window": 20}'（传空表示不修改）。
    """
    try:
        from src.services.strategy_library import update_code_strategy
        kwargs = {"strategy_id": int(strategy_id)}
        if source:
            kwargs["source"] = source
        if description:
            kwargs["description"] = description
        if params:
            try:
                kwargs["params"] = json.loads(params)
            except ValueError:
                return _err(vmsg("library.paramsInvalid", "params 必须是键值参数对象"))
        if "source" not in kwargs and "description" not in kwargs and "params" not in kwargs:
            return _err(vmsg("agentTool.updateStrategyNothing", "未提供任何要更新的字段"))
        result = update_code_strategy(**kwargs)
        return _json(result)
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.exception("update_strategy tool failed")
        return _err(vmsg("agentTool.updateStrategyFailed", "更新策略失败: {err}", err=e))


@tool
def get_strategy(strategy_id: int) -> str:
    """查看策略库代码策略详情：源码全文、生效参数、源码默认参数。

    Args:
        strategy_id: 策略库 id。
    """
    try:
        from src.services.strategy_library import get_strategy_detail
        detail = get_strategy_detail(int(strategy_id))
        if detail is None:
            return _err(vmsg("library.strategyNotFound", "策略不存在"))
        return _json(detail)
    except Exception as e:
        logger.exception("get_strategy tool failed")
        return _err(vmsg("agentTool.getStrategyFailed", "策略详情查询失败: {err}", err=e))


@tool
def create_tuning_task(strategy_kind: str, stock_code: str, start_date: str, end_date: str,
                       param_grid: str, strategy_id: int = 0, strategy_name: str = "",
                       target_metric: str = "总收益率", initial_capital: float = 100000.0,
                       market: str = "zh_a") -> str:
    """创建参数调优任务（后台并发回测所有参数组合，需用 get_tuning_status 轮询进度）。

    任务会先跑一组"基准"（当前生效参数），再跑参数网格的笛卡尔积（候选 ≤63 组，共 ≤64 组），
    按目标指标挑出最优组合。**不会自动应用参数**——应用需用户在调优详情页确认。

    Args:
        strategy_kind: 'code'（策略库代码策略，默认）或 'template'。
        stock_code: 股票代码。
        start_date: 开始日期 YYYY-MM-DD。
        end_date: 结束日期 YYYY-MM-DD。
        param_grid: 参数网格 JSON 字符串，如 '{"short_window": [3, 5, 8], "long_window": [15, 25]}'。
                    键必须是策略 STRATEGY_PARAMS 里已有的参数，每个键 1-10 个数字/布尔取值。
        strategy_id: strategy_kind 为 'code' 时的策略库 id。
        strategy_name: strategy_kind 为 'template' 时的模板策略名。
        target_metric: 优化目标，'总收益率'（默认）/ '夏普比率' / '最大回撤'（越小越好自动识别）。
        initial_capital: 初始资金，默认 100000。
        market: 市场，'zh_a'（默认）或 'us'。
    """
    try:
        from src.services.tuning import create_tuning_task as _create

        try:
            grid = json.loads(param_grid)
        except ValueError:
            return _err(vmsg("tuning.badParamGrid", "参数网格必须是非空对象（{参数名: [取值...]}）"))
        payload = {
            "strategy_kind": strategy_kind, "strategy_id": strategy_id,
            "strategy_name": strategy_name, "stock_code": stock_code,
            "start_date": start_date, "end_date": end_date,
            "param_grid": grid, "target_metric": target_metric,
            "initial_capital": initial_capital, "market": market,
        }
        result = _create(payload)
        result["note"] = vmsg("agentTool.tuningSubmittedNote",
                              "任务已在后台并发执行，稍后用 get_tuning_status(task_id={id}) 查询进度与最优组合",
                              id=result.get("id"))
        return _json(result)
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.exception("create_tuning_task tool failed")
        return _err(vmsg("agentTool.tuningCreateFailed", "创建调优任务失败: {err}", err=e))


@tool
def get_tuning_status(task_id: int) -> str:
    """查询调优任务进度与结果：各组合状态、目标指标对比、最优组合及其参数（不含净值序列）。

    Args:
        task_id: 调优任务 id（create_tuning_task 返回的 id）。
    """
    try:
        from src.services.tuning import get_tuning_detail
        # 工具只要指标/参数/进度，不要净值序列（省去 ≤64 条 zlib 解压）
        detail = get_tuning_detail(int(task_id), include_series=False)
        if detail is None:
            return _err(vmsg("tuning.taskNotFound", "调优任务不存在"))
        combos_out = []
        target = detail.get("target_metric") or "总收益率"
        for c in detail.get("combos", []):
            metrics = c.get("metrics") or {}
            row = {
                "combo_index": c.get("combo_index"), "is_baseline": c.get("is_baseline"),
                "status": c.get("status"), "params": c.get("params"),
                target: metrics.get(target),
                "夏普比率": metrics.get("夏普比率"), "最大回撤": metrics.get("最大回撤"),
            }
            if c.get("error"):
                row["error"] = c["error"]
            combos_out.append(row)
        best = detail.get("best_combo_index")
        best_out = None
        if best is not None:
            bc = next((c for c in detail.get("combos", []) if c.get("combo_index") == best), {})
            bm = bc.get("metrics") or {}
            best_out = {"combo_index": best, "params": bc.get("params"), target: bm.get(target)}
        return _json({
            "id": detail.get("id"), "status": detail.get("status"),
            "strategy_kind": detail.get("strategy_kind"), "strategy_name": detail.get("strategy_name"),
            "stock_code": detail.get("stock_code"),
            "start_date": detail.get("start_date"), "end_date": detail.get("end_date"),
            "target_metric": target, "total_combos": detail.get("total_combos"),
            "done_combos": detail.get("done_combos"),
            "succeeded_combos": detail.get("succeeded_combos"),
            "best_combo": best_out, "combos": combos_out,
            "error": detail.get("error"),
        })
    except Exception as e:
        logger.exception("get_tuning_status tool failed")
        return _err(vmsg("agentTool.tuningStatusFailed", "调优任务查询失败: {err}", err=e))


@tool
def list_backtest_runs(strategy_kind: str = "", strategy_id: int = 0, status: str = "",
                       limit: int = 10) -> str:
    """列出服务端运行历史（最新在前），返回摘要指标（不含净值序列）。

    Args:
        strategy_kind: 按种类筛选，'code' / 'template'，空为全部。
        strategy_id: 按策略库 id 筛选（strategy_kind='code' 时有效），0 为不筛。
        status: 按状态筛选，'succeeded' / 'failed' / 'running'，空为全部。
        limit: 最多返回条数，默认 10，最大 50。
    """
    try:
        from src.services.backtest_runs import list_runs
        rows = list_runs(
            strategy_kind=strategy_kind or None,
            strategy_id=int(strategy_id) if strategy_id else None,
            status=status or None, limit=max(1, min(int(limit), 50)),
        )
        runs = [{
            "id": r.get("id"), "status": r.get("status"),
            "strategy_kind": r.get("strategy_kind"), "strategy_name": r.get("strategy_name"),
            "stock_code": r.get("stock_code"), "market": r.get("market"),
            "start_date": r.get("start_date"), "end_date": r.get("end_date"),
            "总收益率": (r.get("metrics") or {}).get("总收益率"),
            "夏普比率": (r.get("metrics") or {}).get("夏普比率"),
            "最大回撤": (r.get("metrics") or {}).get("最大回撤"),
        } for r in rows]
        return _json({"count": len(runs), "runs": runs})
    except Exception as e:
        logger.exception("list_backtest_runs tool failed")
        return _err(vmsg("agentTool.runsFailed", "运行历史查询失败: {err}", err=e))


@tool
def get_run(run_id: int) -> str:
    """查看一条运行记录详情：指标全集、阶段耗时、成交笔数（不含净值/成交明细序列）。

    Args:
        run_id: 运行记录 id（list_backtest_runs 返回的 id）。
    """
    try:
        from src.services.backtest_runs import get_run_detail
        detail = get_run_detail(int(run_id))
        if detail is None:
            return _err(vmsg("library.runNotFound", "运行记录不存在"))
        return _json({
            "id": detail.get("id"), "status": detail.get("status"),
            "strategy_kind": detail.get("strategy_kind"), "strategy_name": detail.get("strategy_name"),
            "stock_code": detail.get("stock_code"), "market": detail.get("market"),
            "start_date": detail.get("start_date"), "end_date": detail.get("end_date"),
            "metrics": detail.get("metrics"), "stages": detail.get("stages"),
            "trade_count": len(detail.get("trades") or []),
            "error": detail.get("error"),
        })
    except Exception as e:
        logger.exception("get_run tool failed")
        return _err(vmsg("agentTool.runFailed", "运行记录查询失败: {err}", err=e))


@tool
def list_factors(market: str = "", q: str = "", limit: int = 20) -> str:
    """列出因子库中的 Python 因子（名称/描述/市场/标签，不含源码）。

    Args:
        market: 按市场筛选，当前仅 'zh_a'，空为全部。
        q: 按名称/描述模糊搜索。
        limit: 最多返回条数，默认 20，最大 50。
    """
    try:
        from src.services.factor_library import list_factors as _list
        rows = _list(market=market or None, q=q or "", limit=max(1, min(int(limit), 50)))
        return _json({"count": len(rows), "factors": rows})
    except Exception as e:
        logger.exception("list_factors tool failed")
        return _err(vmsg("agentTool.factorsFailed", "因子列表查询失败: {err}", err=e))


@tool
def create_factor(name: str, description: str, source: str, market: str = "zh_a",
                  tags: str = "") -> str:
    """创建 Python 因子并保存到因子库（创建前经沙箱校验，不合法返回 errors 列表）。

    Args:
        name: 因子名称（2-50字符）。
        description: 因子描述（一句话说明因子逻辑）。
        source: 完整 Python 源码，必须定义模块级 compute(df) 函数：
                df 为单只股票的日线 DataFrame（中文列：时间/开盘/最高/最低/收盘/成交量，
                时间为索引、升序），返回 pd.Series（索引与 df 对齐的因子值）。
                示例：def compute(df):\n    return df["收盘"].pct_change(20)
        market: 市场，当前仅支持 'zh_a'（A股，分析在沪深300成分股上运行）。
        tags: 逗号分隔标签（可选）。
    """
    try:
        from src.services.factor_library import create_factor as _create
        return _json(_create(name=name, description=description, market=market,
                             source=source, tags=tags))
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.exception("create_factor tool failed")
        return _err(vmsg("agentTool.createFactorFailed", "创建因子失败: {err}", err=e))


@tool
def analyze_factor(factor_id: int, start_date: str, end_date: str,
                   n_quantiles: int = 5, forward_period: int = 5) -> str:
    """运行因子横截面分析（沪深300 全样本，分钟级耗时），返回 IC 统计与分层收益摘要。

    返回 ic_mean（IC 均值，|IC|>0.03 有预测力）、ic_ir、ic_win_rate、分层平均收益、
    单调性等；净值曲线与 IC 时序图在因子库详情页查看。

    Args:
        factor_id: 因子库 id。
        start_date: 开始日期 YYYY-MM-DD。
        end_date: 结束日期 YYYY-MM-DD。
        n_quantiles: 分层数，默认 5。
        forward_period: 前瞻收益周期（交易日），默认 5。
    """
    try:
        from src.services.factor_library import analyze_user_factor
        result = analyze_user_factor(int(factor_id), start_date, end_date,
                                     n_quantiles=n_quantiles, forward_period=forward_period)
        if result.get("error"):
            return _err(result["error"])
        return _json({
            "factor": result.get("factor_type"),
            "universe_size": result.get("universe_size"),
            "ic_stats": result.get("ic_stats"),
            "monotonicity": result.get("monotonicity"),
            "quantile_stats": result.get("quantile_stats"),
            "note": vmsg("agentTool.factorAnalysisNote",
                         "IC 时序与分层累计收益图请在因子库详情页查看"),
        })
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.exception("analyze_factor tool failed")
        return _err(vmsg("agentTool.factorAnalysisFailed", "因子分析失败: {err}", err=e))


# 工具列表（供 agent 使用）
ALL_TOOLS = [
    get_stock_quote,
    get_index_quote,
    run_backtest,
    get_sentiment,
    get_stock_signal,
    get_daily_recommendations,
    list_strategies,
    create_strategy,
    update_strategy,
    get_strategy,
    create_tuning_task,
    get_tuning_status,
    list_backtest_runs,
    get_run,
    list_factors,
    create_factor,
    analyze_factor,
]
