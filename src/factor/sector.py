import os
import csv
from typing import Dict, Optional


class StockSectorMapper:
    """
    股票行业映射器 - 根据股票代码查找所属行业
    """
    
    def __init__(self):
        """
        初始化股票行业映射器
        """
        self.stock_sector_map = self._load_stock_sector_map()
    
    def _load_stock_sector_map(self) -> Dict[str, str]:
        """
        加载股票行业映射数据
        
        Returns:
            Dict[str, str]: 股票代码到行业的映射
        """
        stock_sector_map = {}
        
        # 沪深300成分股列表路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(base_dir, "stock_data", "沪深300", "沪深300成分股列表.csv")
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stock_code = row['股票代码'].strip()
                    sector = row['行业'].strip()
                    stock_sector_map[stock_code] = sector
            
            print(f"成功加载 {len(stock_sector_map)} 只股票的行业信息")
        except Exception as e:
            print(f"加载股票行业映射失败: {e}")
        
        return stock_sector_map
    
    def get_sector_by_code(self, stock_code: str) -> Optional[str]:
        """
        根据股票代码获取所属行业
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Optional[str]: 行业名称，如果未找到返回 None
        """
        # 去除可能的后缀，如 "000001.SZ" 或 "600000.SH"
        stock_code = stock_code.split('.')[0]
        return self.stock_sector_map.get(stock_code)
    
    def is_hs300_stock(self, stock_code: str) -> bool:
        """
        检查股票是否为沪深300成分股
        
        Args:
            stock_code: 股票代码
            
        Returns:
            bool: 是否为沪深300成分股
        """
        # 去除可能的后缀，如 "000001.SZ" 或 "600000.SH"
        stock_code = stock_code.split('.')[0]
        return stock_code in self.stock_sector_map


# 全局实例
stock_sector_mapper = StockSectorMapper()


def get_stock_sector(stock_code: str) -> Optional[str]:
    """
    获取股票所属行业的便捷函数
    
    Args:
        stock_code: 股票代码
        
    Returns:
        Optional[str]: 行业名称，如果未找到返回 None
    """
    return stock_sector_mapper.get_sector_by_code(stock_code)


def is_hs300_stock(stock_code: str) -> bool:
    """
    检查股票是否为沪深300成分股的便捷函数
    
    Args:
        stock_code: 股票代码
        
    Returns:
        bool: 是否为沪深300成分股
    """
    return stock_sector_mapper.is_hs300_stock(stock_code)