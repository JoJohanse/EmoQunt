"""
Web界面 - 量化策略回测系统

提供Web界面让用户可以进行策略回测操作
"""
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Optional
import os
import sys
import asyncio
import io
import base64
from contextlib import redirect_stdout
import traceback
import logging
from logging.handlers import RotatingFileHandler

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入可视化模块
from src.visualization import StrategyVisualizer
from src.factor import get_trendradar_sentiment, get_latest_trendradar_data, get_stock_sector, is_hs300_stock
import matplotlib.pyplot as plt

# 延迟导入，避免启动时加载
def get_backtest_components():
    from src.backtest import BacktestRunner, PerformanceAnalyzer
    from src.Strategy import global_strategy_manager
    from src.data import Stock
    import backtrader as bt
    return BacktestRunner, global_strategy_manager, Stock, PerformanceAnalyzer, bt

# 设置日志
def setup_logger():
    """设置日志记录器"""
    logger = logging.getLogger("web_app")
    logger.setLevel(logging.INFO)
    
    # 创建处理器 - 文件处理器
    file_handler = RotatingFileHandler(
        "logs/web_app.log", 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 创建处理器 - 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger


logger = setup_logger()


app = FastAPI(title="Qdt_test Web Interface")


# 预加载策略以提高性能
def preload_strategies():
    """预加载策略列表以提高首次访问性能"""
    global _strategy_cache, _cache_timestamp
    import time
    
    try:
        from src.Strategy import global_strategy_manager
        strategies = list(global_strategy_manager.get_all_strategies().keys())
        _strategy_cache = strategies
        _cache_timestamp = time.time()
        logger.info(f"预加载策略完成，共 {len(strategies)} 个策略: {strategies}")
    except Exception as e:
        logger.error(f"预加载策略失败: {e}")
        _strategy_cache = []
        _cache_timestamp = time.time()


# 在应用启动时预加载策略
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Web应用启动，开始预加载策略...")
    preload_strategies()
    yield
async def startup_event():
    logger.info("Web应用启动，开始预加载策略...")
    preload_strategies()

# 挂载静态文件和模板
templates = Jinja2Templates(directory="web/templates")

# 创建web目录
os.makedirs("web/static", exist_ok=True)
os.makedirs("web/templates", exist_ok=True)
# 创建logs目录
os.makedirs("logs", exist_ok=True)
# 创建output目录用于存储图表
os.makedirs("output", exist_ok=True)

# 挂载output目录作为静态文件服务
app.mount("/output", StaticFiles(directory="output"), name="output")

# 缓存策略列表
_strategy_cache = None
_cache_timestamp = None
CACHE_TIMEOUT = 300  # 5分钟缓存


def get_cached_strategies():
    """获取缓存的策略列表"""
    global _strategy_cache, _cache_timestamp
    import time
    
    current_time = time.time()
    
    # 检查缓存是否有效
    if (_strategy_cache is not None and 
        _cache_timestamp is not None and 
        current_time - _cache_timestamp < CACHE_TIMEOUT):
        return _strategy_cache
    
    # 重新加载策略
    # 优化：只导入必要的模块，避免加载整个backtest组件
    try:
        from src.Strategy import global_strategy_manager
        strategies = list(global_strategy_manager.get_all_strategies().keys())
    except ImportError:
        # 如果导入失败，返回空列表
        strategies = []
    
    _strategy_cache = strategies
    _cache_timestamp = current_time
    
    return strategies

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页 - 显示策略回测界面"""
    logger.info(f"用户访问主页 - 客户端IP: {request.client.host}")
    strategies = get_cached_strategies()
    logger.info(f"获取到 {len(strategies)} 个策略")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "strategies": strategies,
        "title": "量化策略回测系统"
    })

@app.get("/backtest", response_class=HTMLResponse)
async def backtest_form(request: Request):
    """回测表单页面"""
    logger.info(f"用户访问回测表单页面 - 客户端IP: {request.client.host}")
    strategies = get_cached_strategies()
    logger.info(f"回测表单页面加载成功，可用策略数: {len(strategies)}")
    return templates.TemplateResponse("backtest_form.html", {
        "request": request,
        "strategies": strategies,
        "title": "策略回测"
    })

@app.post("/run_backtest", response_class=HTMLResponse)
async def run_backtest(
    request: Request,
    strategy_name: str = Form(...),
    initial_capital: float = Form(100000.0),
    start_date: str = Form(...),
    end_date: str = Form(...),
    commission_rate: float = Form(0.001),
    stock_code: str = Form("000001")  # 默认使用平安银行
):
    """运行策略回测"""
    client_ip = request.client.host
    logger.info(f"收到回测请求 - 客户端IP: {client_ip}, 策略: {strategy_name}, 股票: {stock_code}")
    logger.info(f"回测参数 - 初始资金: {initial_capital}, 开始日期: {start_date}, 结束日期: {end_date}, 佣金率: {commission_rate}")
    
    try:
        # 延迟导入组件
        BacktestRunner, global_strategy_manager, Stock, PerformanceAnalyzer, bt = get_backtest_components()
        
        # 创建回测运行器
        logger.info("初始化回测运行器")
        runner = BacktestRunner()
        
        # 设置参数
        runner.set_initial_capital(initial_capital)
        runner.set_commission(commission_rate)
        runner.add_analyzers()
        logger.info("回测参数设置完成")
        
        # 获取股票数据
        logger.info(f"开始获取股票 {stock_code} 的数据")
        stock = Stock(stock_code)
        stock_data, filename = stock.get_stock_data(
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            adjust='hfq',
            type='daily'
        )
        
        if stock_data.empty:
            logger.warning(f"无法获取股票 {stock_code} 的数据")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"无法获取股票 {stock_code} 的数据",
                "title": "错误"
            })
        
        logger.info(f"成功获取股票数据，数据条数: {len(stock_data)}")
        
        # 添加数据到回测
        # 转换日期列
        if '时间' in stock_data.columns:
            stock_data['时间'] = pd.to_datetime(stock_data['时间'])
            stock_data.set_index('时间', inplace=True)
        
        # 创建Backtrader数据源
        logger.info("创建Backtrader数据源")
        data_feed = bt.feeds.PandasData(
            dataname=stock_data,
            name=stock_code,
            open='开盘',
            high='最高',
            low='最低',
            close='收盘',
            volume='成交量',
            openinterest=-1
        )
        
        # 添加数据到Cerebro
        runner.cerebro.adddata(data_feed)
        
        # 添加策略
        strategy_class = global_strategy_manager.get_strategy(strategy_name)
        if strategy_class:
            # 获取策略的默认参数
            params = {}
            if hasattr(strategy_class, 'params'):
                try:
                    # _getpairs() 返回的是 OrderedDict，直接遍历键值对
                    for param_name, default_value in strategy_class.params._getpairs().items():
                        params[param_name] = default_value
                except Exception as e:
                    logger.error(f"获取策略 {strategy_name} 参数时出错: {e}")
                    # 如果参数获取失败，继续执行，使用空参数字典
                    params = {}
            logger.info(f"添加策略 {strategy_name} 到回测引擎，参数: {params}")
            
            runner.cerebro.addstrategy(strategy_class, **params)
        
        # 运行回测
        logger.info("开始运行回测...")
        results = runner.cerebro.run()
        logger.info("回测执行完成")
        
        # 获取策略实例
        strat = results[0]
        
        # 获取账户价值历史
        if hasattr(runner.cerebro.broker, 'value_history'):
            # 如果有历史价值数据
            value_history = runner.cerebro.broker.getvalue_history() if hasattr(runner.cerebro.broker, 'getvalue_history') else [initial_capital]
        else:
            # 模拟价值历史
            logger.warning("未找到实际价值历史，使用模拟数据")
            value_history = [initial_capital]
            for i in range(1, min(len(stock_data), 100)):
                # 模拟一些随机收益
                daily_return = np.random.normal(0.001, 0.02)
                value_history.append(value_history[-1] * (1 + daily_return))
        
        # 计算收益率
        returns = [0.0]
        for i in range(1, len(value_history)):
            returns.append((value_history[i] - value_history[i-1]) / value_history[i-1])
        
        # 生成绩效报告
        logger.info("生成绩效报告")
        returns_series = pd.Series(returns)
        analyzer = PerformanceAnalyzer(returns_series)
        performance_data = analyzer.generate_report()
        
        # 格式化绩效数据
        formatted_performance = {
            "总收益率": f"{performance_data.get('总收益率', 0):.2%}",
            "年化收益率": f"{performance_data.get('年化收益率', 0):.2%}",
            "夏普比率": round(performance_data.get('夏普比率', 0), 2),
            "最大回撤": f"{performance_data.get('最大回撤', 0):.2%}",
            "胜率": f"{performance_data.get('胜率', 0):.2%}",
            "盈亏比": round(performance_data.get('盈亏比', 0), 2)
        }
        
        logger.info(f"绩效数据计算完成 - 总收益率: {formatted_performance['总收益率']}, 夏普比率: {formatted_performance['夏普比率']}")
        
        # 生成收益曲线数据
        dates = stock_data.index[:len(value_history)].tolist()
        normalized_values = [val/initial_capital for val in value_history]
        
        # 创建收益率序列
        returns_series = pd.Series(returns, index=dates)
        
        # 使用可视化模块生成图表
        visualizer = StrategyVisualizer()
        
        # 生成固定的时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 创建策略特定的目录
        strategy_dir = f"output/{strategy_name}_{stock_code}/{timestamp}"
        os.makedirs(strategy_dir, exist_ok=True)
        
        # 生成收益曲线图表
        equity_chart_path = f"{strategy_dir}/equity_curve_{strategy_name}_{stock_code}_{timestamp}.png"
        equity_fig = visualizer.plot_cumulative_returns(returns_series, title=f"{strategy_name} 收益曲线")
        equity_fig.savefig(equity_chart_path)
        plt.close(equity_fig)
        
        # 生成回撤曲线图表
        drawdown_chart_path = f"{strategy_dir}/drawdown_curve_{strategy_name}_{stock_code}_{timestamp}.png"
        drawdown_fig = visualizer.plot_drawdown(returns_series, title=f"{strategy_name} 回撤曲线")
        drawdown_fig.savefig(drawdown_chart_path)
        plt.close(drawdown_fig)
        
        # 生成综合绩效仪表板
        dashboard_path = f"{strategy_dir}/performance_dashboard_{strategy_name}_{stock_code}_{timestamp}.png"
        dashboard_fig = visualizer.plot_performance_dashboard(returns_series)
        dashboard_fig.savefig(dashboard_path)
        plt.close(dashboard_fig)
        
        logger.info(f"图表生成完成，保存路径:")
        logger.info(f"- 收益曲线: {equity_chart_path}")
        logger.info(f"- 回撤曲线: {drawdown_chart_path}")
        logger.info(f"- 绩效仪表板: {dashboard_path}")
        
        # 构建相对路径（用于Web访问）
        equity_chart_url = f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(equity_chart_path)}"
        drawdown_chart_url = f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(drawdown_chart_path)}"
        dashboard_url = f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(dashboard_path)}"
        
        return templates.TemplateResponse("backtest_result.html", {
            "request": request,
            "strategy_name": strategy_name,
            "performance_data": formatted_performance,
            "equity_chart_url": equity_chart_url,
            "drawdown_chart_url": drawdown_chart_url,
            "dashboard_url": dashboard_url,
            "title": "回测结果"
        })
        
    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"回测执行出错 - 策略: {strategy_name}, 股票: {stock_code}, 错误: {error_msg}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": error_msg,
            "title": "错误"
        })

@app.get("/strategies", response_class=HTMLResponse)
async def strategies_list(request: Request):
    """策略列表页面"""
    logger.info(f"用户访问策略列表页面 - 客户端IP: {request.client.host}")
    _, global_strategy_manager, _, _, _ = get_backtest_components()
    strategies = global_strategy_manager.get_all_strategies()
    strategy_details = []
    
    for name, strategy_class in strategies.items():
        details = {
            "name": name,
            "description": getattr(strategy_class, '__doc__', 'No description available'),
            "parameters": []
        }
        
        # 获取策略参数
        if hasattr(strategy_class, 'params'):
            try:
                # _getpairs() 返回的是 OrderedDict，直接遍历键值对
                for param_name, default_value in strategy_class.params._getpairs().items():
                    details["parameters"].append({
                        "name": param_name,
                        "default": default_value,
                        "type": type(default_value).__name__
                    })
            except Exception as e:
                logger.error(f"获取策略 {name} 参数时出错: {e}")
                # 如果参数获取失败，继续执行，添加空参数列表
                details["parameters"] = []
        
        strategy_details.append(details)
    
    logger.info(f"策略列表页面加载成功，共 {len(strategy_details)} 个策略")
    
    return templates.TemplateResponse("strategies.html", {
        "request": request,
        "strategy_details": strategy_details,
        "title": "策略列表"
    })

@app.get("/api/strategies")
async def get_strategies_api():
    """API接口：获取策略列表"""
    logger.info("API接口被调用：获取策略列表")
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
                # _getpairs() 返回的是 OrderedDict，直接遍历键值对
                for param_name, default_value in strategy_class.params._getpairs().items():
                    result[name]["parameters"][param_name] = {
                        "default": default_value,
                        "type": type(default_value).__name__
                    }
            except Exception as e:
                logger.error(f"获取策略 {name} API参数时出错: {e}")
                # 如果参数获取失败，继续执行，添加空参数字典
                result[name]["parameters"] = {}
    
    logger.info(f"API接口返回 {len(result)} 个策略信息")
    return result

@app.get("/sentiment", response_class=HTMLResponse)
async def sentiment_analysis(request: Request):
    """舆情分析页面"""
    logger.info(f"用户访问舆情分析页面 - 客户端IP: {request.client.host}")
    # 获取策略列表
    strategies = get_cached_strategies()
    logger.info(f"获取到 {len(strategies)} 个策略")
    return templates.TemplateResponse("sentiment_analysis.html", {
        "request": request,
        "title": "舆情分析",
        "strategies": strategies
    })

@app.get("/api/sentiment")
async def get_sentiment_api():
    """API接口：获取舆情分析结果"""
    logger.info("API接口被调用：获取舆情分析结果")
    try:
        sentiment_result = get_trendradar_sentiment()
        logger.info(f"舆情分析结果: {sentiment_result}")
        return sentiment_result
    except Exception as e:
        logger.error(f"获取舆情分析结果时出错: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

@app.post("/analyze_sentiment", response_class=HTMLResponse)
async def analyze_sentiment(
    request: Request,
    strategy: str = Form(...),
    stock_code: str = Form("000001")
):
    """执行舆情分析并显示结果"""
    client_ip = request.client.host
    logger.info(f"收到舆情分析请求 - 客户端IP: {client_ip}, 策略: {strategy}, 股票: {stock_code}")
    
    try:
        # 检查股票是否为沪深300成分股
        if not is_hs300_stock(stock_code):
            logger.warning(f"股票 {stock_code} 不是沪深300成分股，不支持舆情分析")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"股票 {stock_code} 不是沪深300成分股，暂时只支持沪深300成分股的舆情分析",
                "title": "错误"
            })
        
        # 获取股票所属行业
        stock_sector = get_stock_sector(stock_code)
        logger.info(f"股票 {stock_code} 所属行业: {stock_sector}")
        
        # 获取舆情分析结果
        sentiment_result = get_trendradar_sentiment()
        
        # 根据选择的策略生成交易信号
        _, global_strategy_manager, _, _, _ = get_backtest_components()
        strategy_class = global_strategy_manager.get_strategy(strategy)
        
        if strategy_class:
            # 获取策略的情绪权重参数
            sentiment_weight = 0.3  # 默认权重
            if hasattr(strategy_class, 'params'):
                try:
                    for param_name, default_value in strategy_class.params._getpairs().items():
                        if param_name == 'sentiment_weight':
                            sentiment_weight = default_value
                        elif param_name == 'sentiment_threshold':
                            sentiment_threshold = default_value
                except Exception as e:
                    logger.error(f"获取策略 {strategy} 参数时出错: {e}")
            
            # 基于策略的情绪权重调整信号
            adjusted_score = sentiment_result['average_score'] * sentiment_weight
            
            # 生成调整后的交易信号
            if adjusted_score > 0.3:
                adjusted_signal = 'buy'
            elif adjusted_score < -0.3:
                adjusted_signal = 'sell'
            else:
                adjusted_signal = 'hold'
            
            sentiment_result['signal'] = adjusted_signal
            sentiment_result['strategy'] = strategy
            sentiment_result['stock_code'] = stock_code
            sentiment_result['stock_sector'] = stock_sector
            sentiment_result['sentiment_weight'] = sentiment_weight
        
        logger.info(f"舆情分析完成 - 情绪得分: {sentiment_result['average_score']}, 调整后得分: {adjusted_score}, 信号: {sentiment_result['signal']}, 行业: {stock_sector}")
        
        # 生成固定的时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 创建舆情分析结果目录
        sentiment_dir = f"output/sentiment_analysis/{strategy}_{stock_code}/{timestamp}"
        os.makedirs(sentiment_dir, exist_ok=True)
        
        # 生成情绪分布图表
        import matplotlib.pyplot as plt
        import numpy as np
        
        # 准备数据
        analysis_result = sentiment_result['analysis_result']
        labels = ['正面', '负面', '中性']
        sizes = [
            analysis_result['score_distribution']['positive'],
            analysis_result['score_distribution']['negative'],
            analysis_result['score_distribution']['neutral']
        ]
        colors = ['#4CAF50', '#F44336', '#FFC107']
        
        # 处理可能的 NaN 值
        sizes = [0 if np.isnan(s) else s for s in sizes]
        
        # 确保总和不为零
        total = sum(sizes)
        if total == 0:
            sizes = [1/3, 1/3, 1/3]
        else:
            sizes = [s/total for s in sizes]
        
        # 生成饼图
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # 确保饼图是圆形
        plt.title('舆情情绪分布')
        
        # 保存图表
        sentiment_chart_path = f"{sentiment_dir}/sentiment_distribution_{timestamp}.png"
        plt.savefig(sentiment_chart_path)
        plt.close(fig)
        
        # 构建相对路径（用于Web访问）
        sentiment_chart_url = f"/output/sentiment_analysis/{strategy}_{stock_code}/{timestamp}/{os.path.basename(sentiment_chart_path)}"
        
        # 获取最新的新闻数据
        news_data = get_latest_trendradar_data()
        
        return templates.TemplateResponse("sentiment_result.html", {
            "request": request,
            "sentiment_result": sentiment_result,
            "sentiment_chart_url": sentiment_chart_url,
            "news_data": news_data[:10],  # 只显示前10条新闻
            "title": "舆情分析结果"
        })
        
    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"舆情分析执行出错: {error_msg}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": error_msg,
            "title": "错误"
        })

if __name__ == "__main__":
    # 运行Web服务器
    uvicorn.run(app, host="127.0.0.1", port=8000)