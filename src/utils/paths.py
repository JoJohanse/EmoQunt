"""
项目路径工具模块

统一管理项目根目录与各常用目录的路径计算，消除各模块中重复的
os.path.dirname(os.path.dirname(...)) 链式调用与硬编码路径。
"""

from pathlib import Path
import os

# 项目根目录：src/utils/paths.py -> parents[2] = 项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def ensure_dir(path) -> Path:
    """
    确保目录存在，不存在则递归创建。

    :param path: 目录路径（str 或 Path）
    :return: 对应的 Path 对象
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_stock_data_dir(market: str = "zh_a") -> Path:
    """获取股票数据目录"""
    return PROJECT_ROOT / "stock_data" / market


def get_logs_dir() -> Path:
    """获取日志目录"""
    return PROJECT_ROOT / "logs"


def get_output_dir() -> Path:
    """获取输出目录（图表等）"""
    return PROJECT_ROOT / "output"


def get_config_dir() -> Path:
    """获取配置文件目录"""
    return PROJECT_ROOT / "config"


def get_sentiment_save_dir() -> Path:
    """获取情感分析结果保存目录"""
    return PROJECT_ROOT / "output" / "sentiment_analysis"


def get_trendradar_dir() -> Path:
    """获取 trendradar 模块目录"""
    return PROJECT_ROOT / "nes_data" / "trendradar"


def get_user_strategies_dir() -> Path:
    """获取用户策略保存目录"""
    return PROJECT_ROOT / "src" / "Strategy" / "user_strategies"


def get_web_dir() -> Path:
    """获取 web 模板/静态资源目录"""
    return PROJECT_ROOT / "web"


def get_frontend_dist_dir() -> Path:
    """获取 Vue3 前端构建产物目录"""
    return PROJECT_ROOT / "frontend" / "dist"


def as_posix(path) -> str:
    """将路径转为正斜杠形式（用于 URL 等场景）"""
    return str(path).replace(os.sep, "/")
