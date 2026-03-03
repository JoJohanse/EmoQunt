"""
配置加载器模块

负责加载和管理项目配置，支持YAML配置文件和环境变量
"""

import yaml
import os
import json
from typing import Any, Dict, Optional, Union
from pathlib import Path
import logging


class ConfigLoader:
    """
    配置加载器类
    """
    
    def __init__(self, config_path: Optional[str] = None, env_prefix: str = "QDT_"):
        """
        初始化配置加载器
        :param config_path: 配置文件路径
        :param env_prefix: 环境变量前缀
        """
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
        self.env_prefix = env_prefix
        self.config_data = {}
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """
        加载配置文件
        """
        try:
            # 检查配置文件是否存在
            if not os.path.exists(self.config_path):
                self.logger.warning(f"配置文件不存在: {self.config_path}")
                # 创建默认配置
                self.config_data = self._get_default_config()
            else:
                # 读取YAML配置文件
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    self.config_data = yaml.safe_load(file) or {}
                
                self.logger.info(f"成功加载配置文件: {self.config_path}")
        
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            self.config_data = self._get_default_config()
        
        # 合并环境变量
        self._merge_env_vars()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        :return: 默认配置字典
        """
        return {
            'data': {
                'storage_path': './stock_data',
                'default_market': 'zh_a',
                'default_adjust': 'hfq',
                'default_data_type': 'daily',
                'cache_enabled': True,
                'cache_duration_days': 7
            },
            'strategy': {
                'min_order_size': 100,
                'max_portfolio_percent': 0.8,
                'max_single_buy_percent': 0.2,
                'max_single_sell_percent': 0.3,
                'default_short_period': 5,
                'default_long_period': 20
            },
            'backtest': {
                'initial_capital': 100000.0,
                'commission_rate': 0.001,
                'slippage_enabled': False,
                'slippage_rate': 0.0005
            },
            'risk_management': {
                'max_daily_loss': 0.05,
                'max_drawdown': 0.15,
                'max_leverage': 1.0,
                'max_position_size': 0.1,
                'max_sector_exposure': 0.3
            },
            'factor': {
                'ic_confidence_level': 0.95,
                'quantile_number': 5,
                'winsorize_limits': {'lower': 0.025, 'upper': 0.025},
                'normalization_method': 'standard'
            },
            'api': {
                'zhi_tu': {
                    'token_env_var': 'ZHI_TU_API_TOKEN',
                    'timeout': 30,
                    'retry_times': 3
                },
                'akshare': {
                    'timeout': 30,
                    'retry_times': 3
                }
            },
            'logging': {
                'level': 'INFO',
                'log_dir': './logs',
                'backup_count': 30
            },
            'environment': {
                'debug': False,
                'random_seed': 42
            }
        }
    
    def _merge_env_vars(self):
        """
        合并环境变量到配置中
        """
        # 递归遍历配置字典，查找对应的环境变量
        def merge_recursive(config_dict, parent_key=''):
            for key, value in config_dict.items():
                full_key = f"{parent_key}_{key}".upper() if parent_key else key.upper()
                env_key = f"{self.env_prefix}{full_key}"
                
                # 检查环境变量是否存在
                env_value = os.environ.get(env_key)
                if env_value is not None:
                    # 尝试解析环境变量值
                    parsed_value = self._parse_env_value(env_value)
                    config_dict[key] = parsed_value
                    self.logger.info(f"从环境变量 {env_key} 覆盖配置项 {full_key}: {parsed_value}")
                
                # 如果值是字典，递归处理
                if isinstance(value, dict):
                    merge_recursive(value, full_key)
        
        merge_recursive(self.config_data)
    
    def _parse_env_value(self, value: str) -> Union[str, int, float, bool]:
        """
        解析环境变量值
        :param value: 环境变量字符串值
        :return: 解析后的值
        """
        # 尝试解析布尔值
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        elif value.lower() in ('false', '0', 'no', 'off', ''):
            return False
        
        # 尝试解析数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # 尝试解析JSON（用于复杂对象）
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        
        # 返回原始字符串
        return value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        :param key_path: 配置键路径，使用点号分隔，如 'data.storage_path'
        :param default: 默认值
        :return: 配置值
        """
        keys = key_path.split('.')
        value = self.config_data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            self.logger.warning(f"配置项 '{key_path}' 不存在，返回默认值: {default}")
            return default
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值
        :param key_path: 配置键路径
        :param value: 配置值
        """
        keys = key_path.split('.')
        config_ref = self.config_data
        
        # 导航到目标位置的父级
        for key in keys[:-1]:
            if key not in config_ref:
                config_ref[key] = {}
            config_ref = config_ref[key]
        
        # 设置值
        config_ref[keys[-1]] = value
        self.logger.info(f"设置配置项 '{key_path}' 为: {value}")
    
    def reload(self):
        """
        重新加载配置
        """
        self.load_config()
        self.logger.info("配置已重新加载")
    
    def save_config(self, output_path: Optional[str] = None):
        """
        保存当前配置到文件
        :param output_path: 输出路径，默认使用初始化时的路径
        """
        path = output_path or self.config_path
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as file:
                yaml.dump(self.config_data, file, default_flow_style=False, allow_unicode=True)
            
            self.logger.info(f"配置已保存到: {path}")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
    
    def get_data_config(self) -> Dict[str, Any]:
        """
        获取数据配置
        :return: 数据配置字典
        """
        return self.get('data', {})
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """
        获取策略配置
        :return: 策略配置字典
        """
        return self.get('strategy', {})
    
    def get_backtest_config(self) -> Dict[str, Any]:
        """
        获取回测配置
        :return: 回测配置字典
        """
        return self.get('backtest', {})
    
    def get_risk_management_config(self) -> Dict[str, Any]:
        """
        获取风险管理配置
        :return: 风险管理配置字典
        """
        return self.get('risk_management', {})
    
    def get_factor_config(self) -> Dict[str, Any]:
        """
        获取因子配置
        :return: 因子配置字典
        """
        return self.get('factor', {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """
        获取API配置
        :return: API配置字典
        """
        return self.get('api', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        获取日志配置
        :return: 日志配置字典
        """
        return self.get('logging', {})
    
    def get_environment_config(self) -> Dict[str, Any]:
        """
        获取环境配置
        :return: 环境配置字典
        """
        return self.get('environment', {})


# 全局配置实例
_config_loader = None


def get_config() -> ConfigLoader:
    """
    获取全局配置实例
    :return: 配置加载器实例
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def init_config(config_path: Optional[str] = None, env_prefix: str = "QDT_") -> ConfigLoader:
    """
    初始化全局配置实例
    :param config_path: 配置文件路径
    :param env_prefix: 环境变量前缀
    :return: 配置加载器实例
    """
    global _config_loader
    _config_loader = ConfigLoader(config_path, env_prefix)
    return _config_loader


# 便捷的配置访问函数
def get(key_path: str, default: Any = None) -> Any:
    """
    获取配置值的便捷函数
    :param key_path: 配置键路径
    :param default: 默认值
    :return: 配置值
    """
    return get_config().get(key_path, default)


def set(key_path: str, value: Any):
    """
    设置配置值的便捷函数
    :param key_path: 配置键路径
    :param value: 配置值
    """
    get_config().set(key_path, value)


def reload():
    """
    重新加载配置的便捷函数
    """
    get_config().reload()


if __name__ == "__main__":
    # 示例使用
    print("配置加载器示例")
    print("=" * 50)
    
    # 初始化配置
    config = init_config()
    
    # 获取不同类型的配置
    data_config = config.get_data_config()
    print(f"数据存储路径: {data_config.get('storage_path')}")
    print(f"默认市场类型: {data_config.get('default_market')}")
    
    strategy_config = config.get_strategy_config()
    print(f"最小交易单位: {strategy_config.get('min_order_size')}")
    print(f"最大持仓比例: {strategy_config.get('max_portfolio_percent')}")
    
    backtest_config = config.get_backtest_config()
    print(f"初始资金: {backtest_config.get('initial_capital')}")
    print(f"佣金费率: {backtest_config.get('commission_rate')}")
    
    # 获取单个配置项
    storage_path = config.get('data.storage_path')
    print(f"存储路径 (单个获取): {storage_path}")
    
    # 设置配置项
    config.set('data.test_value', 'hello_world')
    test_value = config.get('data.test_value')
    print(f"测试值: {test_value}")
    
    # 测试环境变量覆盖（如果设置了的话）
    # 例如，可以在命令行设置: QDT_DATA_STORAGE_PATH=/custom/path
    print(f"当前存储路径: {config.get('data.storage_path')}")
    
    print("=" * 50)
    print("配置加载器示例完成")