import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "user_strategies")

USER_STRATEGY_MARKER = "__user_strategy__"

def ensure_save_dir():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR, exist_ok=True)
        logger.info(f"创建用户策略保存目录: {SAVE_DIR}")

def get_strategies_file():
    ensure_save_dir()
    return os.path.join(SAVE_DIR, "strategies.json")

def load_user_strategies() -> Dict:
    """加载用户策略"""
    file_path = get_strategies_file()
    if not os.path.exists(file_path):
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"加载了 {len(data)} 个用户策略")
        return data
    except Exception as e:
        logger.error(f"加载用户策略失败: {e}")
        return {}

def save_user_strategies(strategies: Dict) -> bool:
    """保存所有用户策略"""
    try:
        file_path = get_strategies_file()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(strategies, f, ensure_ascii=False, indent=2)
        logger.info(f"保存了 {len(strategies)} 个用户策略")
        return True
    except Exception as e:
        logger.error(f"保存用户策略失败: {e}")
        return False

def save_user_strategy(name: str, config: Dict) -> bool:
    """保存单个用户策略"""
    strategies = load_user_strategies()
    config[USER_STRATEGY_MARKER] = True
    config['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    strategies[name] = config
    return save_user_strategies(strategies)

def get_user_strategy(name: str) -> Optional[Dict]:
    """获取单个用户策略"""
    strategies = load_user_strategies()
    return strategies.get(name)

def delete_user_strategy(name: str) -> bool:
    """删除用户策略"""
    strategies = load_user_strategies()
    if name in strategies:
        del strategies[name]
        return save_user_strategies(strategies)
    return False

def is_user_strategy(name: str) -> bool:
    """检查是否为用户策略"""
    strategies = load_user_strategies()
    return name in strategies

def get_strategy_templates() -> Dict:
    """获取所有可用的策略模板"""
    try:
        from .Strategy import STRATEGY_TEMPLATES
        return STRATEGY_TEMPLATES
    except ImportError:
        logger.warning("无法加载策略模板")
        return {}

def get_strategy_template(template_name: str) -> Optional[Dict]:
    """获取指定策略模板"""
    templates = get_strategy_templates()
    return templates.get(template_name)
