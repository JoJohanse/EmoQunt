"""
Web界面 - 量化策略回测系统

提供Web界面让用户可以进行策略回测、舆情分析、每日个股推荐。

架构：本文件仅含 HTTP 路由适配器（薄层），业务编排在 src.services 深模块中。
两个前端（Jinja2 @ / 和 Vue3 SPA @ /spa/*）共享同一组 service 接口。
"""
from fastapi import FastAPI, Request, Form
from fastapi.concurrency import run_in_threadpool
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
    validate_stock_code, validate_date_range,
    validate_strategy_name, sanitize_string,
    ValidationError,
)

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
    # 数据缓存层：懒初始化连接（幂等，失败静默降级），再做连通性日志
    try:
        from src.data.db import healthcheck as _db_healthcheck, init_pool
        try:
            await run_in_threadpool(init_pool)
        except Exception as e:
            logger.debug(f"init_pool 失败（已降级）: {e}")
        try:
            logger.info(f"数据缓存层状态: {await run_in_threadpool(_db_healthcheck)}")
        except Exception as e:
            logger.warning(f"数据缓存层状态检查失败（已降级）: {e}")
    except Exception as e:
        logger.warning(f"数据缓存层状态检查失败（已降级）: {e}")
    try:
        yield
    finally:
        try:
            from src.data.db import close_pool as _db_close_pool
            _db_close_pool()
        except Exception as e:
            logger.debug(f"close_pool 失败: {e}")


app = FastAPI(title="Qdt_test Web Interface", lifespan=lifespan)
templates = Jinja2Templates(directory=str(get_web_dir() / "templates"))

ensure_dir(get_web_dir() / "static")
ensure_dir(get_web_dir() / "templates")
ensure_dir(get_logs_dir())
output_dir = str(get_output_dir())
ensure_dir(output_dir)

app.mount("/output", StaticFiles(directory=output_dir), name="output")
app.mount("/static", StaticFiles(directory=str(get_web_dir() / "static")), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """全站安全响应头（nosniff / 禁止内嵌 iframe / 收敛 Referrer 与浏览器权限）。

    不加 CSP：模板与 SPA 依赖 CDN 资源 + 内联脚本，严格 CSP 会直接破坏页面，
    详见 docs/research/setup-security-benchmark.md。
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

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
    from src.services.system import needs_setup_guide
    return templates.TemplateResponse("index.html", {
        "request": request, "strategies": _get_cached_strategies(),
        "title": "量化策略回测系统", "nav_active": "home",
        "show_setup_banner": needs_setup_guide(),
    })


@app.get("/setup", response_class=HTMLResponse)
def setup_guide_page(request: Request):
    """初次安装引导页：环境自检 + 分步安装 + 常用命令说明。

    plain def：内部探测 PostgreSQL/Redis（短超时），走 FastAPI 线程池避免阻塞事件循环。
    """
    from src.services.system import get_setup_status
    status = get_setup_status()
    return templates.TemplateResponse("setup.html", {
        "request": request, "title": "安装引导", "nav_active": "setup",
        "checks": status["checks"], "needs_setup": status["needs_setup"],
        "generated_at": status["generated_at"],
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
def run_backtest(
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
    from src.services.backtest import normalize_market, run_with_charts, validate_backtest_params

    strategy_name = sanitize_string(strategy_name, 50)
    stock_code = sanitize_string(stock_code, 10)
    market = normalize_market(market)
    logger.info(f"收到回测请求 - 策略: {strategy_name}, 股票: {stock_code}, 市场: {market}")
    try:
        # 校验统一走 services.backtest（错误文案与响应形状与既有行为逐字一致）
        params, error = validate_backtest_params({
            "strategy_name": strategy_name, "stock_code": stock_code,
            "start_date": start_date, "end_date": end_date,
            "initial_capital": initial_capital,
            "commission_rate": commission_rate, "market": market,
        })
        if error:
            raise ValidationError(error)
        result = run_with_charts(output_dir=output_dir, **params)
        return templates.TemplateResponse("backtest_result.html", {
            "request": request, "strategy_name": params["strategy_name"],
            "performance_data": result["performance_data"],
            "equity_chart_url": result["equity_chart_url"],
            "drawdown_chart_url": result["drawdown_chart_url"],
            "dashboard_url": result["dashboard_url"],
            "title": "回测结果", "nav_active": "backtest", "market": params["market"],
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
def sentiment_analysis(request: Request):
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


@app.post("/refresh_sentiment", response_class=HTMLResponse)
def refresh_sentiment_page(request: Request):
    """强制刷新舆情分析缓存（HTML）。

    POST-only：刷新会触发爬取与缓存写入等副作用，GET 形式易被跨站
    <img>/<a> 触发（CSRF），见 OWASP 对状态变更 GET 的建议。
    """
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
def daily_recommend_page(request: Request):
    """每日推荐页面（HTML）"""
    try:
        from src.services.recommend import get_recommendation
        data = get_recommendation()
        return templates.TemplateResponse("daily_recommend.html", {
            "request": request, "data": data, "title": "每日股票推荐", "nav_active": "recommend",
        })
    except Exception as e:
        return _handle_error(request, e, "每日推荐页面加载")


@app.post("/refresh_recommend", response_class=HTMLResponse)
def refresh_recommend_page(request: Request):
    """刷新每日推荐（HTML）。POST-only，理由同 /refresh_sentiment。"""
    try:
        from src.services.recommend import refresh_recommendation
        data = refresh_recommendation()
        return templates.TemplateResponse("daily_recommend.html", {
            "request": request, "data": data, "title": "每日股票推荐", "nav_active": "recommend",
        })
    except Exception as e:
        return _handle_error(request, e, "每日推荐刷新")


@app.post("/analyze_sentiment", response_class=HTMLResponse)
def analyze_sentiment(request: Request, strategy: str = Form(...), stock_code: str = Form("000001")):
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

        from src.services.sentiment import analyze_stock_sentiment
        result = analyze_stock_sentiment(strategy, stock_code)

        return templates.TemplateResponse("sentiment_result.html", {
            "request": request, "sentiment_result": result["sentiment_result"],
            "sentiment_chart_url": result["sentiment_chart_url"],
            "news_data": result["news_data"], "title": "舆情分析结果", "nav_active": "sentiment",
        })
    except ValidationError as e:
        return _handle_error(request, e, "舆情分析参数验证")
    except ValueError as e:
        # HS300 业务规则错误（service 抛出）直接向用户展示文案；其余 ValueError 记日志
        logger.warning(f"舆情分析业务错误: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request, "error": str(e), "title": "错误",
        })
    except Exception as e:
        return _handle_error(request, e, "舆情分析执行")


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
        from src.services.backtest import run_json, validate_backtest_params
        payload = await request.json()
        params, error = validate_backtest_params(payload)
        if error:
            return JSONResponse({"error": error}, status_code=400)
        return await run_in_threadpool(run_json, **params)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        # 500 不回显异常细节（可能泄露内部路径/依赖），完整堆栈只进日志
        logger.error(f"回测API失败: {e}", exc_info=True)
        return JSONResponse({"error": "回测失败，请稍后重试"}, status_code=500)


@app.post("/api/strategies/compare")
async def compare_strategies_api(request: Request):
    """策略对比：在同一标的上运行多个策略，返回对齐净值曲线 + 指标表（Vue3）。"""
    try:
        from src.services.backtest import validate_compare_params
        from src.services.strategy_compare import compare_strategies
        payload = await request.json()
        params, error = validate_compare_params(payload)
        if error:
            return JSONResponse({"error": error}, status_code=400)
        return await run_in_threadpool(compare_strategies, **params)
    except Exception as e:
        logger.error(f"策略对比API失败: {e}", exc_info=True)
        return JSONResponse({"error": "策略对比失败，请稍后重试"}, status_code=500)


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
        return await run_in_threadpool(
            analyze_factor,
            factor_type=factor_type, start_date=start_date, end_date=end_date,
            universe=universe, n_quantiles=n_quantiles, forward_period=forward_period,
        )
    except Exception as e:
        logger.error(f"因子分析API失败: {e}", exc_info=True)
        return JSONResponse({"error": "因子分析失败，请稍后重试"}, status_code=500)


@app.get("/api/kline")
def get_kline_api(stock_code: str, market: str = "zh_a", days: int = 180,
                  period: str = "day", adjust: str = "", kind: str = "",
                  start_date: str = "", end_date: str = ""):
    """K线 OHLCV 数据（供首页看板蜡烛图）

    period=day/week/month；adjust=qfq/hfq/nfq；
    kind=index 强制按指数取数（000001 这类二义代码用），留空则自动识别；
    start_date 提供时进入区间模式（忽略 days 裁剪），供回测买卖点对齐历史区间。
    """
    try:
        valid, error = validate_stock_code(stock_code, market=market)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        from src.services.kline import get_kline
        return get_kline(stock_code, market, days, period, adjust or None, kind,
                         start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}", exc_info=True)
        return JSONResponse({"error": "获取K线数据失败，请稍后重试"}, status_code=500)


@app.get("/api/sentiment/data")
def get_sentiment_data_api():
    """舆情数据（JSON，供 Vue3）"""
    try:
        from src.services.sentiment import get_sentiment_data
        return get_sentiment_data()
    except Exception as e:
        logger.error(f"获取舆情数据失败: {e}", exc_info=True)
        return JSONResponse({"error": "获取舆情数据失败，请稍后重试"}, status_code=500)


@app.get("/api/sentiment")
def get_sentiment_api():
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


@app.get("/api/sentiment/calendar")
async def get_sentiment_calendar_api():
    """情绪历史日历（JSON，供 Vue3 首页/舆情页）。

    仅读取本地快照 JSON，数据量小；用 run_in_threadpool 包裹扫描，避免
    阻塞事件循环。失败返回空列表，不抛 500。
    """
    try:
        from src.services.sentiment_calendar import get_sentiment_calendar
        return await run_in_threadpool(get_sentiment_calendar)
    except Exception as e:
        logger.error(f"获取情绪日历失败: {e}", exc_info=True)
        return []


@app.get("/api/system/setup-status")
def get_setup_status_api():
    """安装引导自检（JSON，供 SPA / 外部脚本）。

    plain def：含 PostgreSQL/Redis 短超时探测，走线程池避免阻塞事件循环。
    """
    from src.services.system import get_setup_status
    return get_setup_status()


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
def get_daily_recommend_api():
    """每日推荐（JSON，供 Vue3）"""
    try:
        from src.services.recommend import get_recommendation
        return get_recommendation()
    except Exception as e:
        logger.error(f"获取每日推荐失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/daily-recommend/refresh")
def refresh_daily_recommend_api():
    """刷新每日推荐（JSON）"""
    try:
        from src.services.recommend import refresh_recommendation
        return refresh_recommendation()
    except Exception as e:
        logger.error(f"刷新每日推荐失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/market/sectors")
def get_market_sectors_api():
    """行业板块行情（同花顺源，含涨跌幅/成交额/领涨股，供首页热力图）。

    plain def：akshare 网络拉取较慢，走线程池避免阻塞事件循环；
    服务层自带 5 分钟进程内缓存。
    """
    try:
        from src.services.market import get_sector_board
        return get_sector_board()
    except Exception as e:
        logger.error(f"获取行业板块行情失败: {e}", exc_info=True)
        return JSONResponse({"error": "获取板块行情失败，请稍后重试"}, status_code=500)


@app.get("/api/market/breadth")
def get_market_breadth_api():
    """市场宽度概览（涨跌家数 + 涨停/跌停家数，供首页风向标条）。"""
    try:
        from src.services.market import get_market_breadth
        return get_market_breadth()
    except Exception as e:
        logger.error(f"获取市场宽度失败: {e}", exc_info=True)
        return JSONResponse({"error": "获取市场宽度失败，请稍后重试"}, status_code=500)


@app.get("/api/data/source-health")
def get_source_health_api():
    """数据源健康心跳（各数据源最近 7 次取数成败，供首页心跳条）。

    进程内存态：仅记录本进程真实发起过的取数（未启用的源无记录），重启清零。
    """
    try:
        from src.data.source_health import snapshot
        return {"sources": snapshot()}
    except Exception as e:
        logger.error(f"获取数据源健康失败: {e}", exc_info=True)
        return JSONResponse({"error": "获取数据源健康失败"}, status_code=500)


# ===========================================================================
# AI 投资助手（SSE 流式 + 同步）
# ===========================================================================
@app.post("/api/agent/chat")
async def agent_chat(request: Request):
    """AI 投资助手对话（SSE 流式）

    注意：请求体必须在返回 StreamingResponse **之前**读完——
    若把 await request.json() 放进响应生成器，在 BaseHTTPMiddleware
    之下 body 将永远不可读（挂起直至客户端断开，ClientDisconnect）。
    """
    import json as _json
    try:
        payload = await request.json()
        messages = payload.get("messages", [])
    except Exception:
        messages = []

    async def event_stream():
        try:
            if not messages:
                yield 'data: {"type":"error","content":"消息不能为空"}\n\n'
                return
            from src.agent import stream_agent_events
            # 消费统一事件生成器（薄适配器：仅把元组格式化为 SSE）
            async for evt in stream_agent_events(messages):
                if evt[0] == "token":
                    yield "data: " + _json.dumps({"type": "token", "content": evt[1]}, ensure_ascii=False) + "\n\n"
                elif evt[0] == "tool_start":
                    yield "data: " + _json.dumps({"type": "tool_start", "name": evt[1], "args": evt[2]}, ensure_ascii=False) + "\n\n"
                elif evt[0] == "tool":
                    tool_payload = {"type": "tool", "name": evt[1], "args": evt[2], "result": evt[3]}
                    yield "data: " + _json.dumps(tool_payload, ensure_ascii=False) + "\n\n"
                elif evt[0] == "done":
                    yield 'data: {"type":"done"}\n\n'
                elif evt[0] == "error":
                    yield 'data: ' + _json.dumps({"type": "error", "content": evt[1]}, ensure_ascii=False) + '\n\n'
        except Exception as e:
            logger.exception("Agent SSE 失败")
            # SSE 错误通道同样不回显异常细节，只给用户可理解的提示
            yield 'data: ' + _json.dumps(
                {"type": "error", "content": "AI 助手服务异常，请稍后重试"},
                ensure_ascii=False) + '\n\n'

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
        return {"reply": await run_in_threadpool(run_agent, messages)}
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        logger.error(f"Agent 同步对话失败: {e}", exc_info=True)
        return JSONResponse({"error": "对话失败，请稍后重试"}, status_code=500)


if __name__ == "__main__":
    import argparse
    from src.utils.env import get_env, get_env_int

    parser = argparse.ArgumentParser(
        prog="web_app.py",
        description="EmoQunt Web 服务：FastAPI 后端 + 两个前端（/ Jinja2，/spa/ Vue3 SPA）",
    )
    parser.add_argument(
        "--host", default=get_env("QDT_WEB_HOST", "127.0.0.1"),
        help="监听地址，默认 127.0.0.1（仅本机可访问）。改为 0.0.0.0 会暴露到局域网，"
             "请确认信任网络环境。可用环境变量 QDT_WEB_HOST 持久覆盖")
    parser.add_argument(
        "--port", type=int, default=get_env_int("QDT_WEB_PORT", 8000),
        help="监听端口，默认 8000。可用环境变量 QDT_WEB_PORT 持久覆盖")
    parser.add_argument(
        "--check-env", action="store_true",
        help="只运行安装自检（Python/.env/Key/前端构建/缓存层），打印结果后退出，不启动服务")
    args = parser.parse_args()

    if args.check_env:
        from src.services.system import run_setup_check_cli
        raise SystemExit(run_setup_check_cli())

    uvicorn.run(app, host=args.host, port=args.port)
