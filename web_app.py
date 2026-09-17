"""
Web界面 - 量化策略回测系统

提供Web界面让用户可以进行策略回测、舆情分析、每日个股推荐。

架构：本文件仅含 HTTP 路由适配器（薄层），业务编排在 src.services 深模块中。
两个前端（Jinja2 @ / 和 Vue3 SPA @ /spa/*）共享同一组 service 接口。
"""
from fastapi import FastAPI, Request, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse, RedirectResponse
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
from src.utils.i18n import (
    LANG_COOKIE, get_lang, i18n_js_bundle, normalize_lang, set_request_lang, t, tr_error, vmsg,
)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 策略列表缓存归 src.services.strategies 所有（读走缓存、变更自动失效）
    from src.services.strategies import ensure_loaded as _ensure_strategies_loaded
    _ensure_strategies_loaded()
    # 业务库（策略库/运行历史）：幂等建表 + 遗留运行清扫（queued/running → failed）
    try:
        from src.store.db import init_db as _init_store
        await run_in_threadpool(_init_store)
    except Exception as e:
        logger.warning(f"业务库初始化失败（策略库/运行历史不可用）: {e}")
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
            from src.services.task_runner import shutdown_executor
            shutdown_executor(wait=False)
        except Exception as e:
            logger.debug(f"任务执行器关闭失败: {e}")
        try:
            from src.data.db import close_pool as _db_close_pool
            _db_close_pool()
        except Exception as e:
            logger.debug(f"close_pool 失败: {e}")


app = FastAPI(title="Qdt_test Web Interface", lifespan=lifespan)
templates = Jinja2Templates(directory=str(get_web_dir() / "templates"))

# 模板 i18n 全局：t() 取文案、lang() 取当前语言、i18n_js() 供内联脚本注入 window.__I18N__
templates.env.globals["t"] = t
templates.env.globals["lang"] = get_lang
templates.env.globals["i18n_js"] = i18n_js_bundle

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


@app.middleware("http")
async def add_request_language(request: Request, call_next):
    """请求语言解析：把 emoqunt_lang cookie 写入 i18n 的 ContextVar。

    注册在安全响应头中间件之后（即更外层），`call_next` 会在写入语言之后
    才派生下游任务，因此 ContextVar 能传播到 async 路由与线程池里的 `def` 路由
    （含 Jinja2 渲染与服务层 vmsg 消息）。cookie 缺失/非法一律回落 zh-CN。
    """
    set_request_lang(request.cookies.get(LANG_COOKIE))
    return await call_next(request)

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
        f"<h1>{t('spa.notBuiltTitle', 'Vue3 前端未构建')}</h1>"
        f"<p>{t('spa.notBuiltBody', '请在 frontend/ 目录执行 <code>npm install &amp;&amp; npm run build</code>')}</p>",
        status_code=503,
    )


# ---------------------------------------------------------------------------
# 语言切换
# ---------------------------------------------------------------------------
def _safe_next_url(next_url: str) -> str:
    """
    校验语言切换的重定向目标：仅接受站内绝对路径。

    拒绝 ``//host`` 这类协议相对 URL 与含反斜杠的变体（开放重定向），
    非法取值一律回落首页。

    :param next_url: 原始 next 参数
    :return: 可安全重定向的站内路径
    """
    candidate = (next_url or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return "/"
    return candidate


@app.get("/set-lang")
async def set_language(lang: str = "", next: str = "/"):
    """切换界面语言：写入 emoqunt_lang cookie 后重定向回站内 next。

    cookie 需被模板内联脚本读取，故 httponly=False；有效期一年。lang 非法
    （不在 SUPPORTED_LANGS 别名内）时回落默认语言 zh-CN。
    """
    response = RedirectResponse(_safe_next_url(next), status_code=302)
    response.set_cookie(
        LANG_COOKIE, normalize_lang(lang),
        max_age=60 * 60 * 24 * 365, path="/", httponly=False, samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _api_error(message: str, status_code: int) -> JSONResponse:
    """JSON 错误响应（出口统一过 tr_error：服务层中文文案 → 英文）。

    注意：状态码由调用方在**翻译之前**决定（如 `403 if "不存在" in ...`），
    tr_error 只改出口文案、不改判定依据。
    """
    return JSONResponse(status_code=status_code, content={"error": tr_error(message)})


def _handle_error(request: Request, error: Exception, operation: str = "操作") -> HTMLResponse:
    """HTML 路由统一错误处理"""
    if isinstance(error, ValidationError):
        logger.warning(f"{operation}验证失败: {str(error)}")
        # 校验消息已在 validators 产出点本地化（vmsg），tr_error 仅兜住服务层中文
        error_msg = tr_error(str(error))
    elif isinstance(error, ValueError):
        logger.warning(f"{operation}参数错误: {str(error)}")
        error_msg = tr_error(str(error))
    else:
        logger.error(f"{operation}执行出错: {str(error)}", exc_info=True)
        op = vmsg(f"common.op.{operation}", operation)
        error_msg = vmsg("common.opFailed", "{op}执行失败，请稍后重试", op=op)
    return templates.TemplateResponse("error.html", {
        "request": request, "error": error_msg, "title": t("title.error", "错误"),
    })


# ===========================================================================
# HTML 页面路由（Jinja2 前端）— 薄适配器，业务委托 services
# ===========================================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    from src.services.strategies import list_strategy_names
    from src.services.system import needs_setup_guide
    return templates.TemplateResponse("index.html", {
        "request": request, "strategies": list_strategy_names(),
        "title": t("title.home", "量化策略回测系统"), "nav_active": "home",
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
        "request": request, "title": t("title.setup", "安装引导"), "nav_active": "setup",
        "checks": status["checks"], "needs_setup": status["needs_setup"],
        "generated_at": status["generated_at"],
    })


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_form(request: Request):
    from src.services.strategies import list_strategy_names
    preselected_strategy = request.query_params.get("strategy_name", "")
    preselected_market = request.query_params.get("market", "zh_a")
    if preselected_market not in ('zh_a', 'us'):
        preselected_market = "zh_a"
    return templates.TemplateResponse("backtest_form.html", {
        "request": request, "strategies": list_strategy_names(),
        "title": t("title.backtest", "策略回测"), "nav_active": "backtest",
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
            "title": t("title.backtestResult", "回测结果"), "nav_active": "backtest", "market": params["market"],
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
            "templates": get_templates(), "title": t("title.strategies", "策略列表"), "nav_active": "strategies",
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
            "request": request, "title": t("title.sentiment", "舆情分析"), "nav_active": "sentiment",
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
            "request": request, "title": t("title.sentiment", "舆情分析"), "nav_active": "sentiment",
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
            "request": request, "data": data,
            "title": t("title.dailyRecommend", "每日股票推荐"), "nav_active": "recommend",
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
            "request": request, "data": data,
            "title": t("title.dailyRecommend", "每日股票推荐"), "nav_active": "recommend",
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
            "news_data": result["news_data"], "title": t("title.sentimentResult", "舆情分析结果"), "nav_active": "sentiment",
        })
    except ValidationError as e:
        return _handle_error(request, e, "舆情分析参数验证")
    except ValueError as e:
        # HS300 业务规则错误（service 抛出）直接向用户展示文案；其余 ValueError 记日志
        logger.warning(f"舆情分析业务错误: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request, "error": tr_error(str(e)), "title": t("title.error", "错误"),
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
            return JSONResponse({"error": tr_error(error)}, status_code=400)
        return await run_in_threadpool(run_json, **params)
    except ValueError as e:
        return JSONResponse({"error": tr_error(str(e))}, status_code=400)
    except Exception as e:
        # 500 不回显异常细节（可能泄露内部路径/依赖），完整堆栈只进日志
        logger.error(f"回测API失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("回测失败，请稍后重试")}, status_code=500)


@app.post("/api/strategies/compare")
async def compare_strategies_api(request: Request):
    """策略对比：在同一标的上运行多个策略，返回对齐净值曲线 + 指标表（Vue3）。"""
    try:
        from src.services.backtest import validate_compare_params
        from src.services.strategy_compare import compare_strategies
        payload = await request.json()
        params, error = validate_compare_params(payload)
        if error:
            return JSONResponse({"error": tr_error(error)}, status_code=400)
        return await run_in_threadpool(compare_strategies, **params)
    except Exception as e:
        logger.error(f"策略对比API失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("策略对比失败，请稍后重试")}, status_code=500)


@app.post("/api/factor/analyze")
async def analyze_factor_api(request: Request):
    """因子分析：在 HS300 上构建因子面板，返回 IC/分层/单调性（对标 Qlib）。"""
    try:
        payload = await request.json()
        factor_type = str(payload.get("factor_type", "momentum"))
        if factor_type not in ("momentum", "rsi", "volatility", "volume_ratio"):
            return JSONResponse(
                {"error": tr_error("factor_type 必须是 momentum/rsi/volatility/volume_ratio")},
                status_code=400)
        start_date = str(payload.get("start_date", ""))
        end_date = str(payload.get("end_date", ""))
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            return JSONResponse({"error": tr_error(error)}, status_code=400)
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
        return JSONResponse({"error": tr_error("因子分析失败，请稍后重试")}, status_code=500)


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
            return JSONResponse({"error": tr_error(error)}, status_code=400)
        from src.services.kline import get_kline
        return get_kline(stock_code, market, days, period, adjust or None, kind,
                         start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("获取K线数据失败，请稍后重试")}, status_code=500)


@app.get("/api/sentiment/data")
def get_sentiment_data_api():
    """舆情数据（JSON，供 Vue3）"""
    try:
        from src.services.sentiment import get_sentiment_data
        return get_sentiment_data()
    except Exception as e:
        logger.error(f"获取舆情数据失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("获取舆情数据失败，请稍后重试")}, status_code=500)


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
        return {"error": tr_error("获取舆情数据失败"), "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


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
        return JSONResponse({"error": tr_error("获取板块行情失败，请稍后重试")}, status_code=500)


@app.get("/api/market/breadth")
def get_market_breadth_api():
    """市场宽度概览（涨跌家数 + 涨停/跌停家数，供首页风向标条）。"""
    try:
        from src.services.market import get_market_breadth
        return get_market_breadth()
    except Exception as e:
        logger.error(f"获取市场宽度失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("获取市场宽度失败，请稍后重试")}, status_code=500)


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
        return JSONResponse({"error": tr_error("获取数据源健康失败")}, status_code=500)


# ===========================================================================
# 策略库 v2（代码策略 CRUD/校验/版本）+ 运行历史（异步回测）
# 业务编排在 src.services.strategy_library / backtest_runs；错误契约：
# ValueError 含"不存在" → 404，其余 ValueError → 400（出口过 tr_error）。
# ===========================================================================
def _v2_error_response(e: ValueError) -> JSONResponse:
    """v2 统一错误映射：找不到资源 → 404，参数/校验问题 → 400。"""
    message = tr_error(str(e))
    status = 404 if "不存在" in str(e) else 400
    return JSONResponse({"error": message}, status_code=status)


# ---- 运行历史 ----
@app.post("/api/v2/backtest/runs")
async def v2_submit_backtest_run(request: Request):
    """提交异步回测（立即返回 run id，结果经 GET 轮询/历史页查看）。"""
    try:
        payload = await request.json()
        from src.services.backtest_runs import submit_run
        return await run_in_threadpool(submit_run, payload)
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"提交回测运行失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("提交回测失败，请稍后重试")}, status_code=500)


@app.get("/api/v2/backtest/runs")
def v2_list_backtest_runs(strategy_kind: str = "", strategy_id: int = 0, market: str = "",
                          status: str = "", limit: int = 50, offset: int = 0):
    """运行历史列表（摘要，不含时序）。"""
    try:
        from src.services.backtest_runs import list_runs
        return {"runs": list_runs(
            strategy_kind=strategy_kind or None, strategy_id=strategy_id or None,
            market=market or None, status=status or None, limit=limit, offset=offset,
        )}
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"查询运行历史失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("查询运行历史失败，请稍后重试")}, status_code=500)


@app.get("/api/v2/backtest/runs/{run_id:int}")
def v2_get_backtest_run(run_id: int):
    """运行详情（含指标/净值/成交全量与阶段耗时）。"""
    try:
        from src.services.backtest_runs import get_run_detail
        run = get_run_detail(run_id)
        if run is None:
            return JSONResponse({"error": tr_error("运行记录不存在")}, status_code=404)
        return run
    except Exception as e:
        logger.error(f"查询运行详情失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("查询运行详情失败，请稍后重试")}, status_code=500)


# ---- 代码策略 ----
@app.get("/api/v2/strategies")
def v2_list_strategies(market: str = "", q: str = "", limit: int = 200, offset: int = 0):
    """策略库列表（卡片：不含源码全文，附最近成功回测摘要）。"""
    try:
        from src.services.strategy_library import list_strategies
        return {"strategies": list_strategies(market=market or None, q=q or "",
                                              limit=limit, offset=offset)}
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"查询策略库失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("查询策略库失败，请稍后重试")}, status_code=500)


@app.post("/api/v2/strategies")
async def v2_create_strategy(request: Request):
    """创建代码策略（名称/市场/描述/源码/参数；源码先过 ast 校验）。"""
    try:
        payload = await request.json()
        from src.services.strategy_library import create_code_strategy
        return await run_in_threadpool(
            create_code_strategy,
            str(payload.get("name", "")), str(payload.get("description", "")),
            str(payload.get("market", "zh_a")), str(payload.get("source", "")),
            payload.get("params"), str(payload.get("tags", "")),
        )
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"创建代码策略失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("创建策略失败，请稍后重试")}, status_code=500)


@app.post("/api/v2/strategies/validate")
def v2_validate_strategy_source(payload: dict = None):
    """源码校验（编辑器实时调用）：返回 {ok, errors, params(默认参数)}。"""
    try:
        from src.services.strategy_library import validate_source
        return validate_source((payload or {}).get("source", ""))
    except Exception as e:
        logger.error(f"源码校验失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("校验失败，请稍后重试")}, status_code=500)


@app.get("/api/v2/strategies/{strategy_id:int}")
def v2_get_strategy(strategy_id: int):
    """策略详情（含源码与生效参数）。"""
    try:
        from src.services.strategy_library import get_strategy_detail
        detail = get_strategy_detail(strategy_id)
        if detail is None:
            return JSONResponse({"error": tr_error("策略不存在")}, status_code=404)
        return detail
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"查询策略详情失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("查询策略失败，请稍后重试")}, status_code=500)


@app.put("/api/v2/strategies/{strategy_id:int}")
async def v2_update_strategy(strategy_id: int, request: Request):
    """更新代码策略（先快照版本；仅更新传入字段）。"""
    try:
        payload = await request.json()
        from src.services.strategy_library import update_code_strategy
        return await run_in_threadpool(
            update_code_strategy,
            strategy_id,
            payload.get("description"), payload.get("source"), payload.get("params"),
            payload.get("tags"),
            str(payload["market"]) if "market" in payload else None,
            str(payload.get("note", "")),
        )
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"更新代码策略失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("更新策略失败，请稍后重试")}, status_code=500)


@app.delete("/api/v2/strategies/{strategy_id:int}")
def v2_delete_strategy(strategy_id: int):
    """删除代码策略（删除前自动快照）。"""
    try:
        from src.services.strategy_library import delete_code_strategy
        return delete_code_strategy(strategy_id)
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"删除代码策略失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("删除策略失败，请稍后重试")}, status_code=500)


@app.get("/api/v2/strategies/{strategy_id:int}/versions")
def v2_list_strategy_versions(strategy_id: int):
    """版本列表（新→旧，不含源码全文）。"""
    try:
        from src.services.strategy_library import list_versions
        return {"versions": list_versions(strategy_id)}
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"查询版本列表失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("查询版本失败，请稍后重试")}, status_code=500)


@app.get("/api/v2/strategies/versions/{version_id:int}")
def v2_get_strategy_version(version_id: int):
    """版本全文（源码+参数）。"""
    try:
        from src.services.strategy_library import get_version_source
        version = get_version_source(version_id)
        if version is None:
            return JSONResponse({"error": tr_error("版本不存在")}, status_code=404)
        return version
    except Exception as e:
        logger.error(f"查询版本详情失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("查询版本失败，请稍后重试")}, status_code=500)


@app.post("/api/v2/strategies/{strategy_id:int}/versions/{version_id:int}/restore")
def v2_restore_strategy_version(strategy_id: int, version_id: int):
    """回滚到指定版本（当前态先快照）。"""
    try:
        from src.services.strategy_library import restore_version
        return restore_version(strategy_id, version_id)
    except ValueError as e:
        return _v2_error_response(e)
    except Exception as e:
        logger.error(f"版本回滚失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("版本回滚失败，请稍后重试")}, status_code=500)


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
                yield 'data: ' + _json.dumps(
                    {"type": "error", "content": tr_error("消息不能为空")}, ensure_ascii=False) + '\n\n'
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
                {"type": "error", "content": tr_error("AI 助手服务异常，请稍后重试")},
                ensure_ascii=False) + '\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/agent/chat/sync")
async def agent_chat_sync(request: Request):
    """AI 投资助手对话（非流式）"""
    try:
        payload = await request.json()
        messages = payload.get("messages", [])
        if not messages:
            return JSONResponse({"error": tr_error("消息不能为空")}, status_code=400)
        from src.agent import run_agent
        return {"reply": await run_in_threadpool(run_agent, messages)}
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        logger.error(f"Agent 同步对话失败: {e}", exc_info=True)
        return JSONResponse({"error": tr_error("对话失败，请稍后重试")}, status_code=500)


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
