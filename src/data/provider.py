"""KlineProvider 深模块：DB 命中 → 网络回退链 → 列名契约 → DB 回填，单点收口。

语义等价重构：三条平行路径（Stock.get_stock_data / get_index_data / get_us_index_data）
中重复的四步模式收口于此。静默降级语义与中文列名契约保持一致；已知微差：
- adjust 的 nfq→'' 映射收口于此，但 minute 分支仍保留在 data_manager（不属日线）。
- 非法 adjust 值静默映射为 ''（原版 KeyError→空返回）。
"""
from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class KlineProvider:
    """行情获取深模块：DB命中→网络回退链→列名契约→DB回填，单点收口。"""

    def __init__(self, fetcher: Optional[Callable] = None):
        """构造器可注入 fetcher，便于测试与薄壳组装。

        :param fetcher: 可调用对象，签名 ``fetcher(start, end, adjust_str) -> DataFrame``
                        其中 adjust_str 为 akshare 风格 ''/qfq/hfq（'' 表示不复权）。
                        兼容仅接收 (start, end) 的旧签名。
        """
        self._fetcher = fetcher

    def fetch_daily(
        self,
        code: str,
        market: str,
        adjust: str,
        start: str,
        end: str,
        is_index: bool = False,
        fetcher: Optional[Callable] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """统一的日线获取入口。

        :param code: 代码（个股为裸 6 位如 '600938' / 美股 'AAPL' / 指数 '000300'/'SP500'）
        :param market: 'zh_a' / 'us'
        :param adjust: 'nfq' / 'qfq' / 'hfq'
        :param start: 'YYYYMMDD'
        :param end: 'YYYYMMDD'
        :param is_index: 是否指数（影响 DB 的 is_index 列）
        :param fetcher: 本次调用专用 fetcher（优先于构造时注入）
        :return: (DataFrame, file_name)；网络全败或空数据时返回 (empty, '')
        """
        file_name = f"{code}_{adjust}_daily_{start}_{end}.csv"

        # a) 先查 DB 缓存，命中直接返回
        try:
            from src.data import db as _db

            _cached = _db.get_cached_range(
                code, market, adjust, start, end, is_index=is_index
            )
            if _cached is not None and not _cached.empty:
                logger.info(f"DB 缓存命中 {code} ({market}/{adjust}): {len(_cached)} 行")
                return _cached, file_name
        except Exception as _e:  # noqa: F841
            logger.debug(f"DB 缓存查询失败，回退网络链: {_e}")

        # b) 未命中调 fetcher
        actual_fetcher = fetcher if fetcher is not None else self._fetcher
        if actual_fetcher is None:
            logger.debug("未提供 fetcher，返回空")
            return pd.DataFrame(), ""

        # 将 'nfq' 映射为 ''，与原 adjust_map 一致
        _adjust_map = {"nfq": "", "qfq": "qfq", "hfq": "hfq", "": ""}
        adjust_str = _adjust_map.get(adjust, "")

        try:
            df = actual_fetcher(start, end, adjust_str)
        except Exception as e:
            logger.warning(f"fetcher 执行失败: {e}")
            return pd.DataFrame(), ""

        # c) 空兜底
        if df is None or df.empty:
            return pd.DataFrame(), ""

        # c) 统一列名契约：清理 'index' 列 + EN_TO_ZH
        if "index" in df.columns:
            df = df.drop("index", axis=1)

        from src.data.columns import EN_TO_ZH

        rename_map = {k: v for k, v in EN_TO_ZH.items() if k in df.columns}
        if rename_map:
            df = df.rename(columns=rename_map)

        # d) 回填 DB
        try:
            from src.data import db as _db

            _db.save_daily(df, code, market, adjust, is_index=is_index)
        except Exception as _e:  # noqa: F841
            logger.debug(f"DB 缓存回填失败（不影响主流程）: {_e}")

        return df, file_name
