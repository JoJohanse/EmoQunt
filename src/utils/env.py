"""
统一环境变量载入模块

从项目根目录的 .env 文件加载环境变量，全局只执行一次。
所有入口点与需要读取环境变量的模块应优先导入本模块，
以确保 .env 在任何 os.environ.get 调用之前被加载。

用法：
    # 在入口点/模块顶部尽早导入
    from src.utils.env import load_env, get_env
    load_env()  # 幂等，重复调用安全

    # 或直接读取（自动确保已加载）
    value = get_env("API_KEY", default="")
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 项目根目录：src/utils/env.py -> parents[2] = 项目根
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _PROJECT_ROOT / ".env"

_loaded = False


def load_env(override: bool = False) -> None:
    """
    加载项目根目录的 .env 文件。

    幂等：仅首次调用实际执行加载，后续调用为空操作。
    :param override: 是否覆盖已存在的真实环境变量（默认 False，
                     即真实环境变量优先于 .env）
    """
    global _loaded
    if _loaded:
        return
    load_dotenv(dotenv_path=str(_ENV_PATH), override=override)
    _loaded = True


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    读取环境变量，自动确保 .env 已加载。

    :param name: 环境变量名
    :param default: 默认值
    :return: 环境变量值或默认值
    """
    load_env()
    return os.environ.get(name, default)


def get_env_bool(name: str, default: bool = False) -> bool:
    """
    读取布尔型环境变量。

    :param name: 环境变量名
    :param default: 默认值
    :return: 布尔值
    """
    value = get_env(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def get_env_int(name: str, default: int = 0) -> int:
    """
    读取整型环境变量。

    :param name: 环境变量名
    :param default: 默认值
    :return: 整数值
    """
    value = get_env(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(name: str, default: float = 0.0) -> float:
    """
    读取浮点型环境变量。

    :param name: 环境变量名
    :param default: 默认值
    :return: 浮点数值
    """
    value = get_env(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


# 模块导入时自动加载 .env，确保任何导入本模块的代码都已就绪
load_env()
