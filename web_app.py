"""
Web界面 - 量化策略回测系统

提供Web界面让用户可以进行策略回测、舆情分析、每日个股推荐。

架构：本文件仅含 HTTP 路由适配器（薄层），业务编排在 src.services 深模块中。
两个前端（Jinja2 @ / 和 Vue3 SPA @ /spa/*）共享同一组 service 接口。
"""
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import logging

# 加载环境变量（幂等）
from src.utils.env import load_env
load_env()

from src.utils.paths import get_logs_dir, get_output_dir, get_web_dir, get_frontend_dist_dir, ensure_dir
from src.utils.logger import get_logger
from src.utils.validators import (
    validate_stock_code, validate_date_range, validate_initial_capital,
    validate_commission_rate, validate_strategy_name, sanitize_string,
    ValidationError,
)
# 情绪分析专用（analyze_sentiment 路由仍需直接用 is_hs300_stock/get_stock_sector）
from src.factor import get_latest_trendradar_data, get_stock_sector, is_hs300_stock

logger = get_logger("web_app")


# ---------------------------------------------------------------------------
# 应用组装 + 静态挂载
# ---------------------------------------------------------------------------
from contextlib import asynccontextmanager

# 策略列表缓存（进程级）
_strategy_cache = None
_cache_timestamp = None
CACHE_TIMEOUT = 300  # 5分钟


def _preload_strategies():
    """预加载策略列表以提高首次访问性能"""
    global _strategy_cache, _cache_timestamp
    import time
    try:
        from src.services.strategies import list_strategy_names
        strategies = list_strategy_names()
        _strategy_cache = strategies
        _cache_timestamp = time.time()
        logger.info(f"预加载策略完成，共 {len(strategies)} 个策略")
    except Exception as e:
        logger.error(f"预加载策略失败: {e}")
        _strategy_cache = []
        _cache_timestamp = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _preload_strategies()
    # 数据缓存层连通性日志（PostgreSQL + Redis；连不上不影响启动，自动降级）
    try:
        from src.data.db import healthcheck as _db_healthcheck
        logger.info(f"数据缓存层状态: {_db_healthcheck()}")
    except Exception as e:
        logger.warning(f"数据缓存层状态检查失败（已降级）: {e}")
    yield


app = FastAPI(title="Qdt_test Web Interface", lifespan=lifespan)
templates = Jinja2Templates(directory=str(get_web_dir() / "templates"))

ensure_dir(get_web_dir() / "static")
ensure_dir(get_web_dir() / "templates")
ensure_dir(get_logs_dir())
output_dir = str(get_output_dir())
ensure_dir(output_dir)

app.mount("/output", StaticFiles(directory=output_dir), name="output")
app.mount("/static", StaticFiles(directory=str(get_web_dir() / "static")), name="static")

SPA_DIST_DIR = str(get_frontend_dist_dir())
_spa_assets_dir = os.path.join(SPA_DIST_DIR, "assets")
if os.path.isdir(_spa_assets_dir):
    app.mount("/assets", StaticFiles(directory=_spa_assets_dir), name="spa-assets")


@app.get("/spa/{full_path:path}")
async def spa_fallback(full_path: str):
    """Vue3 SPA history 路由回退。"""
    index_path = os.path.join(SPA_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(
        "<h1>Vue3 前端未构建</h1><p>请在 frontend/ 目录执行 <code>npm install &amp;&amp; npm run build</code></p>",
        status_code=503,
    )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _clear_strategy_cache():
    global _strategy_cache, _cache_timestamp
    _strategy_cache = None
    _cache_timestamp = None


def _get_cached_strategies():
    """获取缓存的策略名列表（仅用户策略，供下拉框）"""
    global _strategy_cache, _cache_timestamp
    import time
    now = time.time()
    if (_strategy_cache is not None and _cache_timestamp is not None
            and now - _cache_timestamp < CACHE_TIMEOUT):
        return _strategy_cache
    try:
        from src.services.strategies import list_strategy_names
        _strategy_cache = list_strategy_names()
        logger.info(f"加载用户策略列表: {_strategy_cache}")
    except Exception as e:
        logger.error(f"加载用户策略失败: {e}")
        _strategy_cache = []
    _cache_timestamp = now
    return _strategy_cache


def _api_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def _handle_error(request: Request, error: Exception, operation: str = "操作") -> HTMLResponse:
    """HTML 路由统一错误处理"""
    if isinstance(error, ValidationError):
        logger.warning(f"{operation}验证失败: {str(error)}")
        error_msg = str(error)
    elif isinstance(error, ValueError):
        logger.warning(f"{operation}参数错误: {str(error)}")
        error_msg = str(error)
    else:
        logger.error(f"{operation}执行出错: {str(error)}", exc_info=True)
        error_msg = f"{operation}执行失败，请稍后重试"
    return templates.TemplateResponse("error.html", {
        "request": request, "error": error_msg, "title": "错误",
    })


# ===========================================================================
# HTML 页面路由（Jinja2 前端）— 薄适配器，业务委托 services
# ===========================================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, "strategies": _get_cached_strategies(),
        "title": "量化策略回测系统", "nav_active": "home",
    })


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_form(request: Request):
    preselected_strategy = request.query_params.get("strategy_name", "")
    preselected_market = request.query_params.get("market", "zh_a")
    if preselected_market not in ('zh_a', 'us'):
        preselected_market = "zh_a"
    return templates.TemplateResponse("backtest_form.html", {
        "request": request, "strategies": _get_cached_strategies(),
        "title": "策略回测", "nav_active": "backtest",
        "preselected_strategy": preselected_strategy,
        "preselected_market": preselected_market,
    })


@app.post("/run_backtest", response_class=HTMLResponse)
async def run_backtest(
    request: Request,
    strategy_name: str = Form(...),
    initial_capital: float = Form(100000.0),
    start_date: str = Form(...),
    end_date: str = Form(...),
    commission_rate: float = Form(0.001),
    stock_code: str = Form("000001"),
    market: str = Form("zh_a"),
):
    """运行策略回测（HTML 结果页）"""
    strategy_name = sanitize_string(strategy_name, 50)
    stock_code = sanitize_string(stock_code, 10)
    market = market if market in ('zh_a', 'us') else 'zh_a'
    logger.info(f"收到回测请求 - 策略: {strategy_name}, 股票: {stock_code}, 市场: {market}")
    try:
        # 校验
        for fn, arg, label in [
            (validate_strategy_name, strategy_name, "策略名称"),
            (validate_stock_code, stock_code, "股票代码"),
        ]:
            valid, error = fn(arg, market=market) if fn is validate_stock_code else fn(arg)
            if not valid:
                raise ValidationError(error)
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            raise ValidationError(error)
        valid, error = validate_initial_capital(initial_capital)
        if not valid:
            raise ValidationError(error)
        valid, error = validate_commission_rate(commission_rate)
        if not valid:
            raise ValidationError(error)

        from src.backtest.backtest_manager import run_backtest_with_charts
        benchmark_index = "SP500" if market == 'us' else "000300"
        result = run_backtest_with_charts(
            strategy_name=strategy_name, stock_code=stock_code,
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, commission_rate=commission_rate,
            output_dir=output_dir, benchmark_index=benchmark_index, market=market,
        )
        return templates.TemplateResponse("backtest_result.html", {
            "request": request, "strategy_name": strategy_name,
            "performance_data": result["performance_data"],
            "equity_chart_url": result["equity_chart_url"],
            "drawdown_chart_url": result["drawdown_chart_url"],
            "dashboard_url": result["dashboard_url"],
            "title": "回测结果", "nav_active": "backtest", "market": market,
        })
    except ValidationError as e:
        return _handle_error(request, e, "回测参数验证")
    except Exception as e:
        return _handle_error(request, e, "回测执行")


@app.get("/strategies", response_class=HTMLResponse)
async def strategies_list(request: Request):
    """策略列表页面（HTML）"""
    try:
        from src.services.strategies import list_strategy_details, get_templates
        strategy_details = list_strategy_details()
        return templates.TemplateResponse("strategies.html", {
            "request": request, "strategy_details": strategy_details,
            "templates": get_templates(), "title": "策略列表", "nav_active": "strategies",
        })
    except Exception as e:
        return _handle_error(request, e, "策略列表加载")


@app.get("/sentiment", response_class=HTMLResponse)
async def sentiment_analysis(request: Request):
    """舆情分析页面（HTML）"""
    try:
        from src.services.sentiment import get_sentiment_data
        data = get_sentiment_data()
        return templates.TemplateResponse("sentiment_analysis.html", {
            "request": request, "title": "舆情分析", "nav_active": "sentiment",
            "news_list": data["news_list"], "sectors": data["sectors"],
            "news_count": data["news_count"], "update_time": data["update_time"],
        })
    except Exception as e:
        return _handle_error(request, e, "舆情分析页面加载")


@app.get("/refresh_sentiment", response_class=HTMLResponse)
async def refresh_sentiment_page(request: Request):
    """强制刷新舆情分析缓存（HTML）"""
    try:
        from src.services.sentiment import refresh_sentiment
        data = refresh_sentiment()
        logger.info("舆情分析刷新成功")
        return templates.TemplateResponse("sentiment_analysis.html", {
            "request": request, "title": "舆情分析", "nav_active": "sentiment",
            "news_list": data["news_list"], "sectors": data["sectors"],
            "news_count": data["news_count"], "update_time": data["update_time"],
        })
    except Exception as e:
        return _handle_error(request, e, "舆情分析刷新")


@app.get("/daily_recommend", response_class=HTMLResponse)
async def daily_recommend_page(request: Request):
    """每日推荐页面（HTML）"""
    try:
        from src.services.recommend import get_recommendation
        data = get_recommendation()
        return templates.TemplateResponse("daily_recommend.html", {
            "request": request, "data": data, "title": "每日股票推荐", "nav_active": "recommend",
        })
    except Exception as e:
        return _handle_error(request, e, "每日推荐页面加载")


@app.get("/refresh_recommend", response_class=HTMLResponse)
async def refresh_recommend_page(request: Request):
    """刷新每日推荐（HTML）"""
    try:
        from src.services.recommend import refresh_recommendation
        data = refresh_recommendation()
        return templates.TemplateResponse("daily_recommend.html", {
            "request": request, "data": data, "title": "每日股票推荐", "nav_active": "recommend",
        })
    except Exception as e:
        return _handle_error(request, e, "每日推荐刷新")


@app.post("/analyze_sentiment", response_class=HTMLResponse)
async def analyze_sentiment(request: Request, strategy: str = Form(...), stock_code: str = Form("000001")):
    """执行个股舆情分析并显示结果（HTML）"""
    strategy = sanitize_string(strategy, 50)
    stock_code = sanitize_string(stock_code, 10)
    logger.info(f"收到舆情分析请求 - 策略: {strategy}, 股票: {stock_code}")
    try:
        valid, error = validate_stock_code(stock_code)
        if not valid:
            raise ValidationError(error)
        valid, error = validate_strategy_name(strategy)
        if not valid:
            raise ValidationError(error)

        if not is_hs300_stock(stock_code):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"股票 {stock_code} 不是沪深300成分股，暂时只支持沪深300成分股的舆情分析",
                "title": "错误",
            })

        stock_sector = get_stock_sector(stock_code)
        from src.factor.sentiment import calculate_sentiment_factor
        from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
        has_recent, txt_file = check_recent_txt_exists(max_age_seconds=3600)
        if has_recent:
            news_data = parse_trendradar_txt(txt_file)
            sentiment_result = calculate_sentiment_factor(news_data) if news_data else _get_trendradar_sentiment()
        else:
            sentiment_result = _get_trendradar_sentiment()

        from src.Strategy.strategy_manager import get_user_strategy
        user_config = get_user_strategy(strategy)
        sentiment_weight = 0.3
        if user_config and 'parameters' in user_config:
            for param in user_config['parameters']:
                if param.get('name') == 'sentiment_weight':
                    sentiment_weight = float(param.get('default', param.get('value', 0.3)))

        adjusted_score = sentiment_result.get('average_score', 0) * sentiment_weight
        adjusted_signal = 'buy' if adjusted_score > 0.3 else ('sell' if adjusted_score < -0.3 else 'hold')
        sentiment_result.update(signal=adjusted_signal, strategy=strategy,
                                stock_code=stock_code, stock_sector=stock_sector,
                                sentiment_weight=sentiment_weight)

        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sentiment_dir = f"output/sentiment_analysis/{strategy}_{stock_code}/{timestamp}"
        os.makedirs(sentiment_dir, exist_ok=True)
        sentiment_chart_url = _generate_sentiment_chart(sentiment_result, sentiment_dir, timestamp)
        news_data = get_latest_trendradar_data() or []
        _save_sentiment_result(sentiment_result, strategy, stock_code, stock_sector, news_data)

        return templates.TemplateResponse("sentiment_result.html", {
            "request": request, "sentiment_result": sentiment_result,
            "sentiment_chart_url": sentiment_chart_url,
            "news_data": news_data[:10], "title": "舆情分析结果", "nav_active": "sentiment",
        })
    except ValidationError as e:
        return _handle_error(request, e, "舆情分析参数验证")
    except Exception as e:
        return _handle_error(request, e, "舆情分析执行")


def _get_trendradar_sentiment():
    from src.factor import get_trendradar_sentiment
    return get_trendradar_sentiment()


def _generate_sentiment_chart(sentiment_result, sentiment_dir, timestamp):
    """生成舆情分析图表（辅助函数，仅 analyze_sentiment 用）"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    analysis_result = sentiment_result.get('analysis_result', {})
    score_dist = analysis_result.get('score_distribution', {})
    sizes = [score_dist.get('positive', 0) or 0, score_dist.get('negative', 0) or 0, score_dist.get('neutral', 0) or 0]
    colors = ['#4CAF50', '#F44336', '#FFC107']
    sizes = [0 if (s is None or np.isnan(s)) else s for s in sizes]
    total = sum(sizes)
    sizes = [1/3, 1/3, 1/3] if total == 0 else [s / total for s in sizes]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(sizes, labels=['正面', '负面', '中性'], colors=colors, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    plt.title('舆情情绪分布')
    chart_path = os.path.join(sentiment_dir, f"sentiment_distribution_{timestamp}.png")
    plt.savefig(chart_path)
    plt.close(fig)
    rel_path = os.path.relpath(chart_path, output_dir).replace(os.sep, "/")
    return f"/output/{rel_path}"


def _save_sentiment_result(sentiment_result, strategy, stock_code, stock_sector, news_data):
    """保存舆情分析结果（辅助函数）"""
    try:
        from src.factor.sentiment import process_industry_details, save_sentiment_result
        from datetime import datetime
        industry_details = sentiment_result.get('analysis_result', {}).get('industry_details', [])
        all_sectors_list, top_sectors_list = process_industry_details(industry_details)
        save_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": strategy, "stock_code": stock_code, "stock_sector": stock_sector,
            "average_score": sentiment_result.get('average_score', 0),
            "signal": sentiment_result.get('signal', 'hold'),
            "all_sectors": all_sectors_list, "top_sectors": top_sectors_list,
            "news_count": len(news_data) if news_data else 0,
        }
        save_sentiment_result(save_data)
    except Exception as e:
        logger.warning(f"保存舆情结果失败: {e}")


# ===========================================================================
# JSON API 路由（Vue3 SPA 前端）— 薄适配器，业务委托 services
# ===========================================================================
@app.get("/api/strategies/list")
async def get_strategies_list_api():
    """策略列表（数组形式，供 Vue3）"""
    try:
        from src.services.strategies import list_strategy_details
        return list_strategy_details()
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        return _api_error("获取策略列表失败", 500)


@app.get("/api/strategies")
async def get_strategies_api():
    """策略列表（字典形式，旧接口）"""
    try:
        from src.services.strategies import list_strategy_details
        details = list_strategy_details()
        return {d["name"]: d for d in details}
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        return _api_error("获取策略列表失败", 500)


@app.get("/api/strategies/detail/{strategy_name}")
async def get_strategy_detail(strategy_name: str):
    strategy_name = sanitize_string(strategy_name, 50)
    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return _api_error(error, 400)
    try:
        from src.services.strategies import get_strategy_detail as _get_detail
        detail = _get_detail(strategy_name)
        if detail is None:
            return _api_error("策略不存在", 404)
        return detail
    except Exception as e:
        logger.error(f"获取策略详情失败: {e}")
        return _api_error("获取策略详情失败", 500)


@app.get("/api/strategies/templates")
async def get_strategy_templates_api():
    try:
        from src.services.strategies import get_templates
        return get_templates()
    except Exception as e:
        logger.error(f"获取策略模板失败: {e}")
        return _api_error("获取策略模板失败", 500)


@app.post("/api/strategies/create_new")
async def create_strategy(request: Request):
    try:
        body = await request.json()
        name = sanitize_string(body.get("name", ""), 50).strip()
        description = sanitize_string(body.get("description", ""), 200)
        template_name = sanitize_string(body.get("template", "sentiment_ma"), 20)
        parameters = body.get("parameters", [])
        valid, error = validate_strategy_name(name)
        if not valid:
            return _api_error(error, 400)
        from src.services.strategies import create_strategy as _create
        result = _create(name, description, template_name, parameters)
        if "error" in result:
            return _api_error(result["error"], 400)
        _clear_strategy_cache()
        return result
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        return _api_error("创建策略失败", 500)


@app.post("/api/strategies/create_from_template")
async def create_strategy_from_template(request: Request):
    try:
        body = await request.json()
        name = sanitize_string(body.get("name", ""), 50).strip()
        description = sanitize_string(body.get("description", ""), 200)
        template_name = sanitize_string(body.get("template", "sentiment_ma"), 20)
        valid, error = validate_strategy_name(name)
        if not valid:
            return _api_error(error, 400)
        from src.services.strategies import create_from_template
        result = create_from_template(name, description, template_name)
        if "error" in result:
            return _api_error(result["error"], 400)
        _clear_strategy_cache()
        return result
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        return _api_error("创建策略失败", 500)


@app.put("/api/strategies/{strategy_name}")
async def update_strategy(strategy_name: str, request: Request):
    strategy_name = sanitize_string(strategy_name, 50)
    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return _api_error(error, 400)
    try:
        body = await request.json()
        description = sanitize_string(body.get("description", ""), 200)
        parameters = body.get("parameters", [])
        template = sanitize_string(body.get("template", "sentiment_ma"), 20)
        from src.services.strategies import update_strategy as _update
        result = _update(strategy_name, description, template, parameters)
        if "error" in result:
            return _api_error(result["error"], 403 if "不存在" in result["error"] else 500)
        _clear_strategy_cache()
        return result
    except Exception as e:
        logger.error(f"更新策略失败: {e}")
        return _api_error("更新策略失败", 500)


@app.delete("/api/strategies/{strategy_name}")
async def delete_strategy(strategy_name: str):
    strategy_name = sanitize_string(strategy_name, 50)
    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return _api_error(error, 400)
    try:
        from src.services.strategies import delete_strategy as _delete
        result = _delete(strategy_name)
        if "error" in result:
            return _api_error(result["error"], 403 if "不存在" in result["error"] else 500)
        _clear_strategy_cache()
        return result
    except Exception as e:
        logger.error(f"删除策略失败: {e}")
        return _api_error("删除策略失败", 500)


@app.post("/api/backtest/run")
async def run_backtest_api(request: Request):
    """运行回测（JSON 时序，供 Vue3 ECharts）"""
    try:
        payload = await request.json()
        strategy_name = sanitize_string(str(payload.get("strategy_name", "")), 50)
        stock_code = sanitize_string(str(payload.get("stock_code", "")), 10)
        market = payload.get("market", "zh_a")
        if market not in ("zh_a", "us"):
            market = "zh_a"
        start_date = str(payload.get("start_date", ""))
        end_date = str(payload.get("end_date", ""))
        initial_capital = float(payload.get("initial_capital", 100000.0))
        commission_rate = float(payload.get("commission_rate", 0.0003))

        # 完整校验（修复原 JSON 路径漏校验资金/佣金的问题）
        for fn, arg in [(validate_strategy_name, strategy_name), (validate_stock_code, stock_code)]:
            valid, error = fn(arg, market=market) if fn is validate_stock_code else fn(arg)
            if not valid:
                return JSONResponse({"error": error}, status_code=400)
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        valid, error = validate_initial_capital(initial_capital)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        valid, error = validate_commission_rate(commission_rate)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)

        from src.backtest.backtest_manager import run_backtest_json
        benchmark_index = "SP500" if market == "us" else "000300"
        return run_backtest_json(
            strategy_name=strategy_name, stock_code=stock_code,
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital, commission_rate=commission_rate,
            benchmark_index=benchmark_index, market=market,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"回测API失败: {e}")
        return JSONResponse({"error": f"回测失败: {e}"}, status_code=500)


@app.post("/api/strategies/compare")
async def compare_strategies_api(request: Request):
    """策略对比：在同一标的上运行多个策略，返回对齐净值曲线 + 指标表（Vue3）。"""
    try:
        payload = await request.json()
        names = payload.get("strategy_names") or []
        if not isinstance(names, list) or not names:
            return JSONResponse({"error": "strategy_names 必须是非空数组"}, status_code=400)
        names = [sanitize_string(str(n), 50) for n in names][:5]
        stock_code = sanitize_string(str(payload.get("stock_code", "")), 10)
        market = payload.get("market", "zh_a")
        if market not in ("zh_a", "us"):
            market = "zh_a"
        start_date = str(payload.get("start_date", ""))
        end_date = str(payload.get("end_date", ""))
        initial_capital = float(payload.get("initial_capital", 100000.0))
        commission_rate = float(payload.get("commission_rate", 0.0003))

        valid, error = validate_stock_code(stock_code, market=market)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)

        from src.services.strategy_compare import compare_strategies
        return compare_strategies(
            strategy_names=names, stock_code=stock_code,
            start_date=start_date, end_date=end_date,
            market=market, initial_capital=initial_capital,
            commission_rate=commission_rate,
        )
    except Exception as e:
        logger.error(f"策略对比API失败: {e}")
        return JSONResponse({"error": f"策略对比失败: {e}"}, status_code=500)


@app.post("/api/factor/analyze")
async def analyze_factor_api(request: Request):
    """因子分析：在 HS300 上构建因子面板，返回 IC/分层/单调性（对标 Qlib）。"""
    try:
        payload = await request.json()
        factor_type = str(payload.get("factor_type", "momentum"))
        if factor_type not in ("momentum", "rsi", "volatility", "volume_ratio"):
            return JSONResponse(
                {"error": "factor_type 必须是 momentum/rsi/volatility/volume_ratio"}, status_code=400)
        start_date = str(payload.get("start_date", ""))
        end_date = str(payload.get("end_date", ""))
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        universe = str(payload.get("universe", "hs300"))
        n_quantiles = int(payload.get("n_quantiles", 5))
        forward_period = int(payload.get("forward_period", 5))

        from src.services.factor import analyze_factor
        return analyze_factor(
            factor_type=factor_type, start_date=start_date, end_date=end_date,
            universe=universe, n_quantiles=n_quantiles, forward_period=forward_period,
        )
    except Exception as e:
        logger.error(f"因子分析API失败: {e}")
        return JSONResponse({"error": f"因子分析失败: {e}"}, status_code=500)


@app.get("/api/kline")
async def get_kline_api(stock_code: str, market: str = "zh_a", days: int = 180):
    try:
        valid, error = validate_stock_code(stock_code, market=market)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        from src.services.kline import get_kline
        return get_kline(stock_code, market, days)
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return JSONResponse({"error": f"获取K线数据失败: {e}"}, status_code=500)


@app.get("/api/sentiment/data")
async def get_sentiment_data_api():
    """舆情数据（JSON，供 Vue3）"""
    try:
        from src.services.sentiment import get_sentiment_data
        return get_sentiment_data()
    except Exception as e:
        logger.error(f"获取舆情数据失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/sentiment")
async def get_sentiment_api():
    """舆情分析结果（旧 JSON 接口，含行业详情）"""
    try:
        from src.services.sentiment import get_sentiment_data
        data = get_sentiment_data()
        return {"news_count": data["news_count"], "update_time": data["update_time"],
                "sectors": data["sectors"]}
    except Exception as e:
        logger.error(f"获取舆情分析结果时出错: {e}")
        from datetime import datetime
        return {"error": "获取舆情数据失败", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


@app.get("/api/health")
async def health_api():
    """健康检查：返回数据缓存层（PostgreSQL + Redis）连通性，便于运维确认状态。

    任一层连不上不影响主流程（data_manager 自动降级到 CSV + 网络回退链）。
    """
    try:
        from src.data.db import healthcheck as _db_healthcheck
        return {"status": "ok", "caches": _db_healthcheck()}
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/api/daily-recommend")
async def get_daily_recommend_api():
    """每日推荐（JSON，供 Vue3）"""
    try:
        from src.services.recommend import get_recommendation
        return get_recommendation()
    except Exception as e:
        logger.error(f"获取每日推荐失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/daily-recommend/refresh")
async def refresh_daily_recommend_api():
    """刷新每日推荐（JSON）"""
    try:
        from src.services.recommend import refresh_recommendation
        return refresh_recommendation()
    except Exception as e:
        logger.error(f"刷新每日推荐失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ===========================================================================
# AI 投资助手（SSE 流式 + 同步）
# ===========================================================================
@app.post("/api/agent/chat")
async def agent_chat(request: Request):
    """AI 投资助手对话（SSE 流式）"""
    async def event_stream():
        import json as _json
        try:
            payload = await request.json()
            messages = payload.get("messages", [])
            if not messages:
                yield 'data: {"type":"error","content":"消息不能为空"}\n\n'
                return
            from src.agent.agent import stream_agent_events
            # 消费统一事件生成器（薄适配器：仅把元组格式化为 SSE）
            async for evt in stream_agent_events(messages):
                if evt[0] == "token":
                    yield "data: " + _json.dumps({"type": "token", "content": evt[1]}, ensure_ascii=False) + "\n\n"
                elif evt[0] == "tool":
                    payload = {"type": "tool", "name": evt[1], "args": evt[2], "result": evt[3]}
                    yield "data: " + _json.dumps(payload, ensure_ascii=False) + "\n\n"
                elif evt[0] == "done":
                    yield 'data: {"type":"done"}\n\n'
                elif evt[0] == "error":
                    yield 'data: ' + _json.dumps({"type": "error", "content": evt[1]}, ensure_ascii=False) + '\n\n'
        except Exception as e:
            logger.exception("Agent SSE 失败")
            import json as _json
            yield 'data: ' + _json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + '\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/agent/chat/sync")
async def agent_chat_sync(request: Request):
    """AI 投资助手对话（非流式）"""
    try:
        payload = await request.json()
        messages = payload.get("messages", [])
        if not messages:
            return JSONResponse({"error": "消息不能为空"}, status_code=400)
        from src.agent import run_agent
        return {"reply": run_agent(messages)}
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        logger.error(f"Agent 同步对话失败: {e}")
        return JSONResponse({"error": f"对话失败: {e}"}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
