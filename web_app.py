"""
Web界面 - 量化策略回测系统

提供Web界面让用户可以进行策略回测、舆情分析、每日个股推荐
"""
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import pandas as pd
import numpy as np
from datetime import datetime
import os
import traceback
import logging
from logging.handlers import RotatingFileHandler

# 加载环境变量
from src.utils.env import load_env
load_env()

from src.utils.paths import PROJECT_ROOT, get_logs_dir, get_output_dir, get_web_dir, get_frontend_dist_dir, ensure_dir
from src.utils.logger import get_logger

from src.factor import get_trendradar_sentiment, get_latest_trendradar_data, get_stock_sector, is_hs300_stock
from src.utils.validators import (
    validate_stock_code, validate_date_range, validate_initial_capital,
    validate_commission_rate, validate_strategy_name, sanitize_string,
    ValidationError
)

# 延迟导入，避免启动时加载
def get_backtest_components():
    from src.backtest import BacktestRunner, PerformanceAnalyzer
    from src.Strategy import global_strategy_manager
    from src.data import Stock
    import backtrader as bt
    return BacktestRunner, global_strategy_manager, Stock, PerformanceAnalyzer, bt

logger = get_logger("web_app")


def extract_strategy_params(strategy_class, strategy_name: str = "") -> list:
    """从 backtrader 策略类提取参数列表"""
    parameters = []
    if hasattr(strategy_class, 'params'):
        try:
            for param_name, default_value in strategy_class.params._getpairs().items():
                parameters.append({
                    "name": param_name,
                    "default": default_value,
                    "type": type(default_value).__name__
                })
        except (AttributeError, TypeError) as e:
            logger.warning(f"获取策略 {strategy_name} 参数时出错: {e}")
    return parameters


# 预加载策略以提高性能
def preload_strategies():
    """预加载策略列表以提高首次访问性能"""
    global _strategy_cache, _cache_timestamp
    import time
    
    try:
        from src.Strategy.strategy_manager import load_user_strategies
        strategies = list(load_user_strategies().keys())
        _strategy_cache = strategies
        _cache_timestamp = time.time()
        logger.info(f"预加载策略完成，共 {len(strategies)} 个策略")
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        _strategy_cache = []
        _cache_timestamp = time.time()
    except Exception as e:
        logger.error(f"预加载策略失败: {e}")
        _strategy_cache = []
        _cache_timestamp = time.time()


# 在应用启动时预加载策略
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    preload_strategies()
    yield


app = FastAPI(title="Qdt_test Web Interface", lifespan=lifespan)

# 挂载静态文件和模板
templates = Jinja2Templates(directory=str(get_web_dir() / "templates"))

# 创建web目录
ensure_dir(get_web_dir() / "static")
ensure_dir(get_web_dir() / "templates")
# 创建logs目录
ensure_dir(get_logs_dir())
# 创建output目录用于存储图表
output_dir = str(get_output_dir())
ensure_dir(output_dir)

# 挂载output目录作为静态文件服务
app.mount("/output", StaticFiles(directory=output_dir), name="output")
# 挂载web/static作为全站静态资源（CSS/JS/favicon）
app.mount("/static", StaticFiles(directory=str(get_web_dir() / "static")), name="static")

# Vue3 SPA 构建产物目录（npm run build 后产物在 frontend/dist）
SPA_DIST_DIR = str(get_frontend_dist_dir())
# 挂载 SPA 静态资源（assets 子目录），仅在已构建时挂载
_spa_assets_dir = os.path.join(SPA_DIST_DIR, "assets")
if os.path.isdir(_spa_assets_dir):
    app.mount("/assets", StaticFiles(directory=_spa_assets_dir), name="spa-assets")


@app.get("/spa/{full_path:path}")
async def spa_fallback(full_path: str):
    """Vue3 SPA history 路由回退：未匹配的路径返回 index.html，由前端路由接管。"""
    index_path = os.path.join(SPA_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(
        "<h1>Vue3 前端未构建</h1><p>请在 frontend/ 目录执行 <code>npm install &amp;&amp; npm run build</code></p>",
        status_code=503,
    )


# 缓存策略列表
_strategy_cache = None
_cache_timestamp = None
CACHE_TIMEOUT = 300  # 5分钟缓存

# 舆情分析缓存
_sentiment_cache = None
_sentiment_cache_time = None
SENTIMENT_CACHE_TIMEOUT = 3600  # 1小时缓存


def get_cached_strategies():
    """获取缓存的策略列表 - 只返回用户策略"""
    global _strategy_cache, _cache_timestamp
    import time
    
    current_time = time.time()
    
    # 检查缓存是否有效
    if (_strategy_cache is not None and 
        _cache_timestamp is not None and 
        current_time - _cache_timestamp < CACHE_TIMEOUT):
        return _strategy_cache
    
    # 只从用户策略JSON文件读取策略列表
    try:
        from src.Strategy.strategy_manager import load_user_strategies
        user_strategies = load_user_strategies()
        strategies = list(user_strategies.keys())
        logger.info(f"加载用户策略列表: {strategies}")
    except ImportError as e:
        logger.error(f"导入策略管理模块失败: {e}")
        strategies = []
    except Exception as e:
        logger.error(f"加载用户策略失败: {e}")
        strategies = []
    
    _strategy_cache = strategies
    _cache_timestamp = current_time
    
    return strategies


def clear_strategy_cache():
    """Invalidate the in-process strategy list cache after strategy mutations."""
    global _strategy_cache, _cache_timestamp
    _strategy_cache = None
    _cache_timestamp = None


def api_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def handle_error(request: Request, error: Exception, operation: str = "操作") -> HTMLResponse:
    """
    统一错误处理函数
    
    :param request: 请求对象
    :param error: 异常对象
    :param operation: 操作名称
    :return: 错误页面响应
    """
    if isinstance(error, ValidationError):
        # 验证错误，不记录堆栈
        logger.warning(f"{operation}验证失败: {str(error)}")
        error_msg = str(error)
    elif isinstance(error, ValueError):
        # 值错误
        logger.warning(f"{operation}参数错误: {str(error)}")
        error_msg = str(error)
    else:
        # 其他错误，记录详细信息但不暴露给用户
        logger.error(f"{operation}执行出错: {str(error)}", exc_info=True)
        error_msg = f"{operation}执行失败，请稍后重试"
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": error_msg,
        "title": "错误"
    })


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页 - 显示策略回测界面"""
    logger.info(f"用户访问主页 - 客户端IP: {request.client.host}")
    strategies = get_cached_strategies()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "strategies": strategies,
        "title": "量化策略回测系统",
        "nav_active": "home"
    })


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_form(request: Request):
    """回测表单页面"""
    logger.info(f"用户访问回测表单页面 - 客户端IP: {request.client.host}")
    strategies = get_cached_strategies()
    # 支持从策略列表跳转预选策略：/backtest?strategy_name=xxx
    preselected_strategy = request.query_params.get("strategy_name", "")
    # 支持市场预选：/backtest?market=us
    preselected_market = request.query_params.get("market", "zh_a")
    if preselected_market not in ('zh_a', 'us'):
        preselected_market = "zh_a"
    return templates.TemplateResponse("backtest_form.html", {
        "request": request,
        "strategies": strategies,
        "title": "策略回测",
        "nav_active": "backtest",
        "preselected_strategy": preselected_strategy,
        "preselected_market": preselected_market
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
    market: str = Form("zh_a")
):
    """运行策略回测"""
    client_ip = request.client.host

    # 清理输入
    strategy_name = sanitize_string(strategy_name, 50)
    stock_code = sanitize_string(stock_code, 10)
    # 市场仅允许 zh_a / us
    market = market if market in ('zh_a', 'us') else 'zh_a'

    logger.info(f"收到回测请求 - 客户端IP: {client_ip}, 策略: {strategy_name}, 股票: {stock_code}, 市场: {market}")

    try:
        # 验证策略名称
        valid, error = validate_strategy_name(strategy_name)
        if not valid:
            raise ValidationError(error)

        # 验证股票代码（按市场）
        valid, error = validate_stock_code(stock_code, market=market)
        if not valid:
            raise ValidationError(error)

        # 验证日期范围
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            raise ValidationError(error)

        # 验证初始资金
        valid, error = validate_initial_capital(initial_capital)
        if not valid:
            raise ValidationError(error)

        # 验证佣金费率
        valid, error = validate_commission_rate(commission_rate)
        if not valid:
            raise ValidationError(error)

        from src.backtest.backtest_manager import run_backtest_with_charts

        # 美股基准为标普500，A股基准为沪深300
        benchmark_index = "SP500" if market == 'us' else "000300"

        result = run_backtest_with_charts(
            strategy_name=strategy_name,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            output_dir=output_dir,
            benchmark_index=benchmark_index,
            market=market,
        )

        return templates.TemplateResponse("backtest_result.html", {
            "request": request,
            "strategy_name": strategy_name,
            "performance_data": result["performance_data"],
            "equity_chart_url": result["equity_chart_url"],
            "drawdown_chart_url": result["drawdown_chart_url"],
            "dashboard_url": result["dashboard_url"],
            "title": "回测结果",
            "nav_active": "backtest",
            "market": market
        })
        
    except ValidationError as e:
        return handle_error(request, e, "回测参数验证")
    except ImportError as e:
        logger.error(f"导入回测模块失败: {e}")
        return handle_error(request, Exception("回测功能暂时不可用"), "回测")
    except Exception as e:
        return handle_error(request, e, "回测执行")


@app.get("/refresh_sentiment", response_class=HTMLResponse)
async def refresh_sentiment_page(request: Request):
    """强制刷新舆情分析缓存"""
    global _sentiment_cache, _sentiment_cache_time
    
    client_ip = request.client.host
    logger.info(f"用户刷新舆情分析 - 客户端IP: {client_ip}")
    
    try:
        sentiment_result = get_trendradar_sentiment()
        _sentiment_cache = sentiment_result
        _sentiment_cache_time = datetime.now()
        logger.info("舆情分析刷新成功")

        # 从刷新后的结果中提取板块得分与新闻（修复原先渲染空数据的问题）
        sectors = []
        if sentiment_result and 'top_sectors' in sentiment_result:
            sectors = sentiment_result['top_sectors']
        news_list = []
        try:
            from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
            has_recent, txt_file = check_recent_txt_exists(max_age_seconds=SENTIMENT_CACHE_TIMEOUT)
            if has_recent:
                news_list = parse_trendradar_txt(txt_file) or []
        except Exception:
            news_list = []

        return templates.TemplateResponse("sentiment_analysis.html", {
            "request": request,
            "title": "舆情分析",
            "news_list": news_list[:20],
            "sectors": sectors,
            "news_count": len(news_list),
            "update_time": _sentiment_cache_time.strftime('%Y-%m-%d %H:%M:%S'),
            "nav_active": "sentiment"
        })
    except ImportError as e:
        logger.error(f"导入舆情模块失败: {e}")
        return handle_error(request, Exception("舆情分析功能暂时不可用"), "舆情刷新")
    except Exception as e:
        return handle_error(request, e, "舆情分析刷新")


@app.get("/strategies", response_class=HTMLResponse)
async def strategies_list(request: Request):
    """策略列表页面"""
    logger.info(f"用户访问策略列表页面 - 客户端IP: {request.client.host}")
    
    try:
        from src.Strategy.strategy_manager import load_user_strategies, get_strategy_templates
        
        user_strategies = load_user_strategies()
        strategy_templates = get_strategy_templates()
        
        _, global_strategy_manager, _, _, _ = get_backtest_components()
        strategies = global_strategy_manager.get_all_strategies()
        strategy_details = []
        
        for name, strategy_class in strategies.items():
            details = {
                "name": name,
                "description": getattr(strategy_class, '__doc__', 'No description available'),
                "parameters": [],
                "is_user_strategy": False
            }
            
            details["parameters"] = extract_strategy_params(strategy_class, name)
            
            strategy_details.append(details)
        
        for name, config in user_strategies.items():
            template_name = config.get("template", "sentiment_ma")
            template = strategy_templates.get(template_name, {})
            details = {
                "name": name,
                "description": config.get("description", ""),
                "parameters": config.get("parameters", []),
                "template": template_name,
                "template_name": template.get("name", ""),
                "is_user_strategy": True
            }
            strategy_details.append(details)
        
        logger.info(f"策略列表页面加载成功，共 {len(strategy_details)} 个策略")
        
        return templates.TemplateResponse("strategies.html", {
            "request": request,
            "strategy_details": strategy_details,
            "templates": strategy_templates,
            "title": "策略列表",
            "nav_active": "strategies"
        })
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return handle_error(request, Exception("策略列表功能暂时不可用"), "策略列表")
    except Exception as e:
        return handle_error(request, e, "策略列表加载")


@app.get("/api/strategies")
async def get_strategies_api():
    """API接口：获取策略列表"""
    logger.info("API接口被调用：获取策略列表")
    
    try:
        _, global_strategy_manager, _, _, _ = get_backtest_components()
        strategies = global_strategy_manager.get_all_strategies()
        result = {}
        for name, strategy_class in strategies.items():
            result[name] = {
                "name": name,
                "description": getattr(strategy_class, '__doc__', 'No description available'),
                "parameters": {}
            }
            
            if hasattr(strategy_class, 'params'):
                try:
                    for param_name, default_value in strategy_class.params._getpairs().items():
                        result[name]["parameters"][param_name] = {
                            "default": default_value,
                            "type": type(default_value).__name__
                        }
                except (AttributeError, TypeError) as e:
                    logger.warning(f"获取策略 {name} API参数时出错: {e}")
                    result[name]["parameters"] = {}
        
        logger.info(f"API接口返回 {len(result)} 个策略信息")
        return result
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        return api_error("获取策略列表失败", 500)


@app.get("/api/strategies/list")
async def get_strategies_list_api():
    """API接口：获取策略列表（数组形式，含参数，供 Vue3 前端使用）"""
    logger.info("API接口被调用：获取策略列表（数组）")
    try:
        from src.Strategy.strategy_manager import load_user_strategies, get_strategy_templates
        user_strategies = load_user_strategies()
        strategy_templates = get_strategy_templates()
        _, global_strategy_manager, _, _, _ = get_backtest_components()
        builtin = global_strategy_manager.get_all_strategies()
        details = []
        for name, strategy_class in builtin.items():
            tmpl = strategy_templates.get('sentiment_ma', {})
            details.append({
                "name": name,
                "description": getattr(strategy_class, '__doc__', '') or '',
                "parameters": [],
                "template": "sentiment_ma",
                "template_name": tmpl.get("name", ""),
                "is_user_strategy": False,
            })
        for name, config in user_strategies.items():
            tmpl_name = config.get("template", "sentiment_ma")
            tmpl = strategy_templates.get(tmpl_name, {})
            details.append({
                "name": name,
                "description": config.get("description", ""),
                "parameters": config.get("parameters", []),
                "template": tmpl_name,
                "template_name": tmpl.get("name", ""),
                "is_user_strategy": True,
            })
        return details
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        return api_error("获取策略列表失败", 500)


@app.post("/api/backtest/run")
async def run_backtest_api(request: Request):
    """API接口：运行回测，返回 JSON 时序数据（供 Vue3 ECharts 动态绘制）"""
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

        # 参数校验
        valid, error = validate_strategy_name(strategy_name)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        valid, error = validate_stock_code(stock_code, market=market)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)
        valid, error = validate_date_range(start_date, end_date)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)

        from src.backtest.backtest_manager import run_backtest_json
        benchmark_index = "SP500" if market == "us" else "000300"
        result = run_backtest_json(
            strategy_name=strategy_name,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            benchmark_index=benchmark_index,
            market=market,
        )
        return result
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"回测API失败: {e}")
        return JSONResponse({"error": f"回测失败: {e}"}, status_code=500)


@app.get("/api/kline")
async def get_kline_api(
    stock_code: str,
    market: str = "zh_a",
    days: int = 180,
):
    """API接口：获取标的 K 线 OHLCV 数据（JSON，供首页看板 ECharts 蜡烛图）"""
    try:
        from datetime import datetime, timedelta
        from src.data import Stock
        if market not in ("zh_a", "us"):
            market = "zh_a"
        days = max(30, min(int(days), 730))
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        # 校验股票代码
        valid, error = validate_stock_code(stock_code, market=market)
        if not valid:
            return JSONResponse({"error": error}, status_code=400)

        stock = Stock(stock_code, market=market)
        df, _ = stock.get_stock_data(
            start_date=start_date, end_date=end_date,
            adjust='qfq' if market == 'us' else 'hfq', type='daily',
        )
        if df is None or df.empty:
            return {"code": stock_code, "market": market, "name": "",
                    "dates": [], "ohlcv": [], "volumes": []}
        # 中文列名 -> OHLCV
        col_map = {'时间': 'date', '开盘': 'open', '最高': 'high',
                   '最低': 'low', '收盘': 'close', '成交量': 'volume'}
        df = df.rename(columns=col_map)
        for c in ('open', 'high', 'low', 'close', 'volume'):
            if c in df.columns:
                df[c] = df[c].astype(float)
        # 排序并取最近 days 个交易日
        df = df.sort_values('date').tail(days).reset_index(drop=True)
        dates = df['date'].astype(str).tolist()
        # ECharts 蜡烛图：[open, close, low, high]
        ohlcv = df[['open', 'close', 'low', 'high']].values.tolist()
        volumes = df['volume'].tolist() if 'volume' in df.columns else []
        name = ''
        try:
            name = stock.get_stock_name() or ''
        except Exception:
            pass
        return {
            "code": stock_code,
            "market": market,
            "name": name,
            "dates": dates,
            "ohlcv": ohlcv,
            "volumes": volumes,
        }
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return JSONResponse({"error": f"获取K线数据失败: {e}"}, status_code=500)


@app.get("/api/sentiment/data")
async def get_sentiment_data_api():
    """API接口：获取舆情数据（JSON，供 Vue3 前端）"""
    try:
        from src.factor.sentiment import get_or_generate_sentiment_data
        sentiment_data, news_data = get_or_generate_sentiment_data()
        sectors = []
        if sentiment_data and 'top_sectors' in sentiment_data:
            sectors = sentiment_data['top_sectors']
        return {
            "news_list": (news_data or [])[:20],
            "sectors": sectors,
            "news_count": len(news_data or []),
            "update_time": sentiment_data.get('timestamp', '') if sentiment_data else '',
        }
    except Exception as e:
        logger.error(f"获取舆情数据失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/daily-recommend")
async def get_daily_recommend_api():
    """API接口：获取每日推荐（JSON，供 Vue3 前端）"""
    try:
        from src.factor.daily_recommend import get_cached_recommendation
        return get_cached_recommendation()
    except Exception as e:
        logger.error(f"获取每日推荐失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/daily-recommend/refresh")
async def refresh_daily_recommend_api():
    """API接口：刷新每日推荐（JSON）"""
    try:
        from src.factor.daily_recommend import refresh_recommendation, reload_sentiment
        reload_sentiment()
        return refresh_recommendation()
    except Exception as e:
        logger.error(f"刷新每日推荐失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/strategies/detail/{strategy_name}")
async def get_strategy_detail(strategy_name: str):
    """API接口：获取单个策略详情"""
    logger.info(f"API接口被调用：获取策略详情 - {strategy_name}")
    
    # 清理和验证策略名称
    strategy_name = sanitize_string(strategy_name, 50)
    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return api_error(error, 400)
    
    try:
        from src.Strategy.strategy_manager import get_user_strategy, is_user_strategy
        
        user_strategy = get_user_strategy(strategy_name)
        
        if user_strategy:
            return {
                "name": strategy_name,
                "description": user_strategy.get("description", ""),
                "template": user_strategy.get("template", "sentiment_ma"),
                "parameters": user_strategy.get("parameters", []),
                "is_user_strategy": True
            }
        
        _, global_strategy_manager, _, _, _ = get_backtest_components()
        strategy_class = global_strategy_manager.get_strategy(strategy_name)
        
        if not strategy_class:
            return api_error("策略不存在", 404)
        
        parameters = extract_strategy_params(strategy_class, strategy_name)
        
        return {
            "name": strategy_name,
            "description": getattr(strategy_class, '__doc__', ''),
            "parameters": parameters,
            "is_user_strategy": False
        }
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"获取策略详情失败: {e}")
        return api_error("获取策略详情失败", 500)


@app.post("/api/strategies/create_new")
async def create_strategy(request: Request):
    """API接口：用户自定义参数创建新策略"""
    logger.info("API接口被调用：用户自定义参数创建新策略")
    
    try:
        from src.Strategy.strategy_manager import save_user_strategy, is_user_strategy
        
        body = await request.json()
        name = sanitize_string(body.get("name", ""), 50).strip()
        description = sanitize_string(body.get("description", ""), 200)
        template_name = sanitize_string(body.get("template", "sentiment_ma"), 20)
        parameters = body.get("parameters", [])
        
        # 验证策略名称
        valid, error = validate_strategy_name(name)
        if not valid:
            return api_error(error, 400)
        
        if is_user_strategy(name):
            return api_error("策略名称已存在", 400)
        
        if not parameters or len(parameters) == 0:
            return api_error("自定义参数不能为空", 400)
        
        config = {
            "description": description,
            "template": template_name,
            "parameters": parameters,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if save_user_strategy(name, config):
            clear_strategy_cache()
            logger.info(f"用户策略 {name} 创建成功（自定义参数）")
            return {"success": True, "name": name}
        else:
            return api_error("保存策略失败", 500)
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        return api_error("创建策略失败", 500)


@app.post("/api/strategies/create_from_template")
async def create_strategy_from_template(request: Request):
    """API接口：根据模板创建新策略（使用模板默认参数）"""
    logger.info("API接口被调用：根据模板创建新策略")
    
    try:
        from src.Strategy.strategy_manager import save_user_strategy, is_user_strategy, get_strategy_template
        
        body = await request.json()
        name = sanitize_string(body.get("name", ""), 50).strip()
        description = sanitize_string(body.get("description", ""), 200)
        template_name = sanitize_string(body.get("template", "sentiment_ma"), 20)
        
        # 验证策略名称
        valid, error = validate_strategy_name(name)
        if not valid:
            return api_error(error, 400)
        
        if is_user_strategy(name):
            return api_error("策略名称已存在", 400)
        
        template = get_strategy_template(template_name)
        if not template:
            return api_error("无效的策略模板", 400)
        
        base_params = template.get("base_params", [])
        parameters = []
        for param in base_params:
            parameters.append({
                "name": param.get("name"),
                "value": param.get("default"),
                "label": param.get("label", param.get("name")),
                "type": param.get("type")
            })
        logger.info(f"使用模板 {template_name} 的默认参数: {parameters}")
        
        config = {
            "description": description,
            "template": template_name,
            "parameters": parameters,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if save_user_strategy(name, config):
            clear_strategy_cache()
            logger.info(f"用户策略 {name} 创建成功（基于模板 {template_name}）")
            return {"success": True, "name": name, "parameters": parameters}
        else:
            return api_error("保存策略失败", 500)
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        return api_error("创建策略失败", 500)


@app.get("/api/strategies/templates")
async def get_strategy_templates_api():
    """API接口：获取策略模板列表"""
    logger.info("API接口被调用：获取策略模板列表")
    
    try:
        from src.Strategy.strategy_manager import get_strategy_templates
        templates = get_strategy_templates()
        result = {}
        for name, template in templates.items():
            result[name] = {
                "name": template.get("name", ""),
                "description": template.get("description", ""),
                "parameters": template.get("base_params", [])
            }
        return result
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"获取策略模板失败: {e}")
        return api_error("获取策略模板失败", 500)


@app.put("/api/strategies/{strategy_name}")
async def update_strategy(strategy_name: str, request: Request):
    """API接口：更新策略"""
    logger.info(f"API接口被调用：更新策略 - {strategy_name}")
    
    # 清理和验证策略名称
    strategy_name = sanitize_string(strategy_name, 50)
    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return api_error(error, 400)
    
    try:
        from src.Strategy.strategy_manager import get_user_strategy, save_user_strategy
        
        if not get_user_strategy(strategy_name):
            return api_error("只能修改用户创建的策略", 403)
        
        body = await request.json()
        description = sanitize_string(body.get("description", ""), 200)
        parameters = body.get("parameters", [])
        template = sanitize_string(body.get("template", "sentiment_ma"), 20)
        
        config = {
            "description": description,
            "template": template,
            "parameters": parameters
        }
        
        if save_user_strategy(strategy_name, config):
            clear_strategy_cache()
            logger.info(f"用户策略 {strategy_name} 更新成功")
            return {"success": True, "name": strategy_name}
        else:
            return api_error("保存策略失败", 500)
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"更新策略失败: {e}")
        return api_error("更新策略失败", 500)


@app.delete("/api/strategies/{strategy_name}")
async def delete_strategy(strategy_name: str):
    """API接口：删除策略"""
    logger.info(f"API接口被调用：删除策略 - {strategy_name}")
    
    # 清理和验证策略名称
    strategy_name = sanitize_string(strategy_name, 50)
    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return api_error(error, 400)
    
    try:
        from src.Strategy.strategy_manager import delete_user_strategy, is_user_strategy
        
        if not is_user_strategy(strategy_name):
            return api_error("只能删除用户创建的策略", 403)
        
        if delete_user_strategy(strategy_name):
            clear_strategy_cache()
            logger.info(f"用户策略 {strategy_name} 删除成功")
            return {"success": True}
        else:
            return api_error("删除策略失败", 500)
    except ImportError as e:
        logger.error(f"导入策略模块失败: {e}")
        return api_error("策略功能暂时不可用", 503)
    except Exception as e:
        logger.error(f"删除策略失败: {e}")
        return api_error("删除策略失败", 500)


@app.get("/sentiment", response_class=HTMLResponse)
async def sentiment_analysis(request: Request):
    """舆情分析页面 - 展示当天热门新闻和板块得分"""
    logger.info(f"用户访问舆情分析页面 - 客户端IP: {request.client.host}")
    
    try:
        from src.factor.sentiment import get_or_generate_sentiment_data
        
        sentiment_data, news_data = get_or_generate_sentiment_data()
        
        sectors = []
        if sentiment_data and 'top_sectors' in sentiment_data:
            sectors = sentiment_data['top_sectors']
        
        return templates.TemplateResponse("sentiment_analysis.html", {
            "request": request,
            "title": "舆情分析",
            "news_list": news_data[:20] if news_data else [],
            "sectors": sectors,
            "news_count": len(news_data) if news_data else 0,
            "update_time": sentiment_data.get('timestamp', '') if sentiment_data else '',
            "nav_active": "sentiment"
        })
    except ImportError as e:
        logger.error(f"导入舆情模块失败: {e}")
        return handle_error(request, Exception("舆情分析功能暂时不可用"), "舆情分析")
    except Exception as e:
        return handle_error(request, e, "舆情分析页面加载")


@app.get("/api/sentiment")
async def get_sentiment_api():
    """API接口：获取舆情分析结果"""
    global _sentiment_cache, _sentiment_cache_time
    
    logger.info("API接口被调用：获取舆情分析结果")
    
    try:
        from src.factor.sentiment import get_or_generate_sentiment_data, calculate_sentiment_factor
        from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
        
        has_recent, txt_file = check_recent_txt_exists(max_age_seconds=SENTIMENT_CACHE_TIMEOUT)
        if has_recent:
            logger.info(f"存在1小时内的txt文件: {txt_file}，从文件读取数据")
            news_data = parse_trendradar_txt(txt_file)
            if news_data:
                sentiment_result = calculate_sentiment_factor(news_data)
                _sentiment_cache = sentiment_result
                _sentiment_cache_time = datetime.now()
                return sentiment_result
        
        sentiment_data, news_data = get_or_generate_sentiment_data(force_refresh=True)
        
        if sentiment_data:
            sentiment_result = {
                'analysis_result': {
                    'industry_details': [
                        {'industry': s['name'], 'score': s['sentiment'] / 100} 
                        for s in sentiment_data.get('all_sectors', [])
                    ]
                },
                'average_score': sum(s['sentiment'] for s in sentiment_data.get('all_sectors', [])) / max(len(sentiment_data.get('all_sectors', [])), 1) / 100
            }
            _sentiment_cache = sentiment_result
            _sentiment_cache_time = datetime.now()
            return sentiment_result
        else:
            return {'error': '无法获取舆情数据', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    except ImportError as e:
        logger.error(f"导入舆情模块失败: {e}")
        return {'error': '舆情功能暂时不可用', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Exception as e:
        logger.error(f"获取舆情分析结果时出错: {e}")
        return {
            'error': '获取舆情数据失败',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


@app.get("/daily_recommend", response_class=HTMLResponse)
async def daily_recommend_page(request: Request):
    """每日推荐页面"""
    client_ip = request.client.host
    logger.info(f"用户访问每日推荐页面 - 客户端IP: {client_ip}")
    
    try:
        from src.factor.daily_recommend import get_cached_recommendation
        recommend_data = get_cached_recommendation()
        logger.info(f"每日推荐数据加载成功，推荐股票数: {len(recommend_data.get('recommendations', []))}")
        
        return templates.TemplateResponse("daily_recommend.html", {
            "request": request,
            "data": recommend_data,
            "title": "每日股票推荐",
            "nav_active": "recommend"
        })
    except ImportError as e:
        logger.error(f"导入推荐模块失败: {e}")
        return handle_error(request, Exception("每日推荐功能暂时不可用"), "每日推荐")
    except Exception as e:
        return handle_error(request, e, "每日推荐页面加载")


@app.get("/refresh_recommend", response_class=HTMLResponse)
async def refresh_recommend_page(request: Request):
    """刷新每日推荐"""
    client_ip = request.client.host
    logger.info(f"用户刷新每日推荐 - 客户端IP: {client_ip}")
    
    try:
        from src.factor.daily_recommend import refresh_recommendation, reload_sentiment
        reload_sentiment()
        recommend_data = refresh_recommendation()
        logger.info(f"每日推荐刷新成功，推荐股票数: {len(recommend_data.get('recommendations', []))}")
        
        return templates.TemplateResponse("daily_recommend.html", {
            "request": request,
            "data": recommend_data,
            "title": "每日股票推荐",
            "nav_active": "recommend"
        })
    except ImportError as e:
        logger.error(f"导入推荐模块失败: {e}")
        return handle_error(request, Exception("每日推荐功能暂时不可用"), "每日推荐刷新")
    except Exception as e:
        return handle_error(request, e, "每日推荐刷新")


@app.post("/analyze_sentiment", response_class=HTMLResponse)
async def analyze_sentiment(
    request: Request,
    strategy: str = Form(...),
    stock_code: str = Form("000001")
):
    """执行舆情分析并显示结果"""
    client_ip = request.client.host
    
    # 清理输入
    strategy = sanitize_string(strategy, 50)
    stock_code = sanitize_string(stock_code, 10)
    
    logger.info(f"收到舆情分析请求 - 客户端IP: {client_ip}, 策略: {strategy}, 股票: {stock_code}")
    
    try:
        # 验证股票代码
        valid, error = validate_stock_code(stock_code)
        if not valid:
            raise ValidationError(error)
        
        # 验证策略名称
        valid, error = validate_strategy_name(strategy)
        if not valid:
            raise ValidationError(error)
        
        from src.factor.sentiment import get_or_generate_sentiment_data
        from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
        
        if not is_hs300_stock(stock_code):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"股票 {stock_code} 不是沪深300成分股，暂时只支持沪深300成分股的舆情分析",
                "title": "错误"
            })
        
        stock_sector = get_stock_sector(stock_code)
        logger.info(f"股票 {stock_code} 所属行业: {stock_sector}")
        
        has_recent, txt_file = check_recent_txt_exists(max_age_seconds=SENTIMENT_CACHE_TIMEOUT)
        if has_recent:
            news_data = parse_trendradar_txt(txt_file)
            if news_data:
                from src.factor.sentiment import calculate_sentiment_factor
                sentiment_result = calculate_sentiment_factor(news_data)
            else:
                from src.factor import get_trendradar_sentiment
                sentiment_result = get_trendradar_sentiment()
        else:
            from src.factor import get_trendradar_sentiment
            sentiment_result = get_trendradar_sentiment()
        
        from src.Strategy.strategy_manager import get_user_strategy
        user_config = get_user_strategy(strategy)
        
        sentiment_weight = 0.3
        if user_config and 'parameters' in user_config:
            for param in user_config['parameters']:
                if param.get('name') == 'sentiment_weight':
                    sentiment_weight = float(param.get('default', 0.3))
        
        adjusted_score = sentiment_result.get('average_score', 0) * sentiment_weight
        adjusted_signal = 'buy' if adjusted_score > 0.3 else ('sell' if adjusted_score < -0.3 else 'hold')
        
        sentiment_result['signal'] = adjusted_signal
        sentiment_result['strategy'] = strategy
        sentiment_result['stock_code'] = stock_code
        sentiment_result['stock_sector'] = stock_sector
        sentiment_result['sentiment_weight'] = sentiment_weight
        
        logger.info(f"舆情分析完成 - 得分: {sentiment_result['average_score']}, 调整后: {adjusted_score}, 信号: {adjusted_signal}")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sentiment_dir = f"output/sentiment_analysis/{strategy}_{stock_code}/{timestamp}"
        os.makedirs(sentiment_dir, exist_ok=True)
        
        sentiment_chart_url = generate_sentiment_chart(sentiment_result, sentiment_dir, timestamp)
        
        news_data = get_latest_trendradar_data()
        
        save_sentiment_analysis_result(sentiment_result, strategy, stock_code, stock_sector, news_data)
        
        return templates.TemplateResponse("sentiment_result.html", {
            "request": request,
            "sentiment_result": sentiment_result,
            "sentiment_chart_url": sentiment_chart_url,
            "news_data": news_data[:10] if news_data else [],
            "title": "舆情分析结果",
            "nav_active": "sentiment"
        })
        
    except ValidationError as e:
        return handle_error(request, e, "舆情分析参数验证")
    except ImportError as e:
        logger.error(f"导入舆情模块失败: {e}")
        return handle_error(request, Exception("舆情分析功能暂时不可用"), "舆情分析")
    except Exception as e:
        return handle_error(request, e, "舆情分析执行")


def generate_sentiment_chart(sentiment_result: dict, sentiment_dir: str, timestamp: str) -> str:
    """生成舆情分析图表"""
    import matplotlib.pyplot as plt
    import numpy as np
    
    analysis_result = sentiment_result.get('analysis_result', {})
    score_dist = analysis_result.get('score_distribution', {})
    labels = ['正面', '负面', '中性']
    sizes = [
        score_dist.get('positive', 0) or 0,
        score_dist.get('negative', 0) or 0,
        score_dist.get('neutral', 0) or 0
    ]
    colors = ['#4CAF50', '#F44336', '#FFC107']
    sizes = [0 if np.isnan(s) else s for s in sizes]
    
    total = sum(sizes)
    if total == 0:
        sizes = [1/3, 1/3, 1/3]
    else:
        sizes = [s/total for s in sizes]
    
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    plt.title('舆情情绪分布')
    
    chart_path = os.path.join(sentiment_dir, f"sentiment_distribution_{timestamp}.png")
    plt.savefig(chart_path)
    plt.close(fig)

    rel_path = os.path.relpath(chart_path, output_dir).replace(os.sep, "/")
    return f"/output/{rel_path}"


def save_sentiment_analysis_result(sentiment_result: dict, strategy: str, stock_code: str, stock_sector: str, news_data: list):
    """保存舆情分析结果"""
    try:
        from src.factor.sentiment import process_industry_details, save_sentiment_result
        
        industry_details = sentiment_result.get('analysis_result', {}).get('industry_details', [])
        all_sectors_list, top_sectors_list = process_industry_details(industry_details)
        
        save_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": strategy,
            "stock_code": stock_code,
            "stock_sector": stock_sector,
            "average_score": sentiment_result.get('average_score', 0),
            "signal": sentiment_result.get('signal', 'hold'),
            "all_sectors": all_sectors_list,
            "top_sectors": top_sectors_list,
            "news_count": len(news_data) if news_data else 0
        }
        save_sentiment_result(save_data)
        logger.info("舆情分析结果已保存")
    except ImportError as e:
        logger.warning(f"导入保存模块失败: {e}")
    except Exception as e:
        logger.warning(f"保存舆情结果失败: {e}")


if __name__ == "__main__":
    # 运行Web服务器
    uvicorn.run(app, host="127.0.0.1", port=8000)
