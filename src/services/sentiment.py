"""舆情服务：舆情数据获取/刷新的业务编排。

统一了原 /sentiment (HTML)、/api/sentiment/data (JSON)、/refresh_sentiment (HTML)
三个路由共享的业务逻辑，以及个股舆情分析编排。
"""
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


def get_sentiment_data() -> Dict:
    """获取舆情数据（不强制刷新）。

    统一了原 /sentiment 与 /api/sentiment/data 的业务逻辑。
    :return: {news_list, sectors, news_count, update_time}
    """
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


def refresh_sentiment() -> Dict:
    """强制刷新舆情数据（重新抓取+分析）。

    统一了原 /refresh_sentiment 的业务逻辑。
    :return: {news_list, sectors, news_count, update_time}
    """
    from src.factor import get_trendradar_sentiment

    sentiment_result = get_trendradar_sentiment()
    sectors = []
    if sentiment_result and 'top_sectors' in sentiment_result:
        sectors = sentiment_result['top_sectors']

    news_list = []
    try:
        from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
        has_recent, txt_file = check_recent_txt_exists(max_age_seconds=3600)
        if has_recent:
            news_list = parse_trendradar_txt(txt_file) or []
    except Exception:
        news_list = []

    return {
        "news_list": news_list[:20],
        "sectors": sectors,
        "news_count": len(news_list),
        "update_time": sentiment_result.get('timestamp', '') if sentiment_result else '',
    }


def analyze_stock_sentiment(strategy: str, stock_code: str) -> Dict:
    """个股舆情分析编排（深模块）。

    吸收原 web_app.py /analyze_sentiment 路由的完整编排逻辑：
    HS300 校验、板块映射、TrendRadar 新闻读取、情绪因子计算、
    sentiment_weight 加权与信号生成、饼图落盘、结果持久化。

    假定入参已通过路由层校验（股票代码/策略名格式）；但 HS300 成分
    检查属于业务规则，保留在 service 层。

    :param strategy: 用户策略名
    :param stock_code: 股票代码（6 位）
    :return: {"sentiment_result": dict, "sentiment_chart_url": str, "news_data": [...]}
    :raises ValueError: 当股票不是沪深300成分股时
    """
    from src.factor import get_stock_sector, is_hs300_stock

    if not is_hs300_stock(stock_code):
        raise ValueError(f"股票 {stock_code} 不是沪深300成分股，暂时只支持沪深300成分股的舆情分析")

    stock_sector = get_stock_sector(stock_code)

    # 新闻与情绪因子
    from src.factor.sentiment import calculate_sentiment_factor
    from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
    has_recent, txt_file = check_recent_txt_exists(max_age_seconds=3600)
    if has_recent:
        news_data = parse_trendradar_txt(txt_file)
        sentiment_result = calculate_sentiment_factor(news_data) if news_data else _get_trendradar_sentiment()
    else:
        sentiment_result = _get_trendradar_sentiment()

    # sentiment_weight：保持原有优先级 default > value > 0.3（委托单点，保持行为不变）
    from src.Strategy.strategy_manager import get_user_strategy
    from src.Strategy.param_spec import resolve_sentiment_weight
    user_config = get_user_strategy(strategy)
    params = user_config.get('parameters', []) if isinstance(user_config, dict) else []
    sentiment_weight = resolve_sentiment_weight(params)

    adjusted_score = sentiment_result.get('average_score', 0) * sentiment_weight
    adjusted_signal = 'buy' if adjusted_score > 0.3 else ('sell' if adjusted_score < -0.3 else 'hold')
    sentiment_result.update(signal=adjusted_signal, strategy=strategy,
                            stock_code=stock_code, stock_sector=stock_sector,
                            sentiment_weight=sentiment_weight)

    # 图表落盘
    from datetime import datetime
    from src.utils.paths import get_output_dir
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = str(get_output_dir())
    sentiment_dir = os.path.join(output_dir, "sentiment_analysis", f"{strategy}_{stock_code}", timestamp)
    os.makedirs(sentiment_dir, exist_ok=True)
    sentiment_chart_url = _generate_sentiment_chart(sentiment_result, sentiment_dir, timestamp, output_dir)

    # 最新新闻与持久化
    from src.factor import get_latest_trendradar_data
    news_data = get_latest_trendradar_data() or []
    _save_sentiment_result(sentiment_result, strategy, stock_code, stock_sector, news_data)

    return {
        "sentiment_result": sentiment_result,
        "sentiment_chart_url": sentiment_chart_url,
        "news_data": news_data[:10],
    }


def _get_trendradar_sentiment():
    """获取 TrendRadar 情绪（兜底路径）。"""
    from src.factor import get_trendradar_sentiment
    return get_trendradar_sentiment()


def _generate_sentiment_chart(sentiment_result, sentiment_dir, timestamp, output_dir):
    """生成舆情分析图表（原样搬移，Agg backend、配色与 1/3 兜底不变）。"""
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
    """保存舆情分析结果（原样搬移）。"""
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
