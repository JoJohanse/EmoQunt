"""KlineProvider 深模块：DB 命中（含增量补拉）→ 网络回退链 → 列名契约 → DB 回填。

语义等价重构：三条平行路径（Stock.get_stock_data / get_index_data / get_us_index_data）
中重复的四步模式收口于此。静默降级语义与中文列名契约保持一致；已知微差：
- adjust 的 nfq→'' 映射收口于此，但 minute 分支仍保留在 data_manager（不属日线）。
- 非法 adjust 值静默映射为 ''（原版 KeyError→空返回）。

Round3 增量补拉：DB 命中不再无条件直返——旧语义 PG 部分覆盖即命中，头/尾
缺口永不补（SWR 后台刷新同样命中 PG，刷不出新 bar）。现在命中后检查覆盖
缺口，仅向网络补拉缺口窗口并合并回填（同 key 10 分钟节流，防数据源暂无新
数据时反复出网）；补拉失败/空静默退回旧缓存（可用性优先）。合并后裁剪回
[start, end] 契约窗口（部分源无区间参数会整段返回）。

已知权衡：qfq/hfq 缺口补拉行与存量行可能来自不同源，除权基准或有微差；
平台取免费源本就存在口径漂移，正确性收益（数据存在且新鲜）大于该风险。
"""
from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

import pandas as pd

from src.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

# 增量补拉节流：同 (code, market, adjust, is_index) 10 分钟内至多出网一次
_TOPUP_THROTTLE_S = 600
_TOPUP_GATES = TTLCache()


class KlineProvider:
    """行情获取深模块：DB命中（含增量补拉）→网络回退链→列名契约→DB回填。"""

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
        actual_fetcher = fetcher if fetcher is not None else self._fetcher

        # a) 先查 DB 缓存；命中后若头/尾有覆盖缺口则增量补拉（见 _topup_gap）
        try:
            from src.data import db as _db

            _cached = _db.get_cached_range(
                code, market, adjust, start, end, is_index=is_index
            )
            if _cached is not None and not _cached.empty:
                logger.info(f"DB 缓存命中 {code} ({market}/{adjust}): {len(_cached)} 行")
                return self._topup_gap(
                    _cached, code, market, adjust, start, end, is_index, actual_fetcher
                ), file_name
        except Exception as _e:  # noqa: F841
            logger.debug(f"DB 缓存查询失败，回退网络链: {_e}")

        # b) 未命中调 fetcher
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

    # ------------------------------------------------------------------
    # 增量补拉（Round3）
    # ------------------------------------------------------------------
    @staticmethod
    def _fetch_window(fetcher: Callable, start: str, end: str,
                      adjust_str: str, code: str) -> Optional[pd.DataFrame]:
        """补拉一个缺口窗口并统一列名契约；失败/空返回 None（静默，可用性优先）。"""
        try:
            df = fetcher(start, end, adjust_str)
        except Exception as e:
            logger.info(f"增量补拉失败 {code} [{start}..{end}]: {e}")
            return None
        if df is None or df.empty:
            return None
        if "index" in df.columns:
            df = df.drop("index", axis=1)
        from src.data.columns import EN_TO_ZH

        rename_map = {k: v for k, v in EN_TO_ZH.items() if k in df.columns}
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    def _topup_gap(
        self,
        cached: pd.DataFrame,
        code: str,
        market: str,
        adjust: str,
        start: str,
        end: str,
        is_index: bool,
        fetcher: Optional[Callable],
    ) -> pd.DataFrame:
        """DB 命中后的覆盖检查与增量补拉（语义见模块 docstring Round3 段）。

        任何意外都退回旧缓存——补拉是"锦上添花"，绝不因它让原本可用的
        命中路径失败。
        """
        try:
            if fetcher is None or cached.empty or "时间" not in cached.columns:
                return cached
            dates = pd.to_datetime(cached["时间"], errors="coerce").dropna()
            if dates.empty:
                return cached
            cov_start, cov_end = dates.min(), dates.max()
            need_start = pd.to_datetime(str(start)) if start else None
            need_end = pd.to_datetime(str(end)) if end else None
            head_gap = need_start is not None and cov_start > need_start
            tail_gap = need_end is not None and cov_end < need_end
            # 尾部假缺口：最新一根距今天不足 1 个自然日（当日未收盘/周末节假日
            # 数据源本就无新 bar），视为已新鲜，不补——避免无谓出网。
            if tail_gap and (pd.Timestamp.now().normalize() - cov_end.normalize()) < pd.Timedelta(days=1):
                tail_gap = False
            if not head_gap and not tail_gap:
                return cached
            if _TOPUP_GATES.mark((code, market, adjust, bool(is_index)), ttl=_TOPUP_THROTTLE_S):
                return cached  # 10 分钟内已尝试过，直接回旧值

            _adjust_map = {"nfq": "", "qfq": "qfq", "hfq": "hfq", "": ""}
            adjust_str = _adjust_map.get(adjust, "")
            frames = []
            if head_gap:
                head_end = (cov_start - pd.Timedelta(days=1)).strftime("%Y%m%d")
                frames.append(self._fetch_window(fetcher, str(start), head_end, adjust_str, code))
            if tail_gap:
                tail_start = (cov_end + pd.Timedelta(days=1)).strftime("%Y%m%d")
                frames.append(self._fetch_window(fetcher, tail_start, str(end), adjust_str, code))
            frames = [f for f in frames if f is not None and not f.empty]
            if not frames:
                return cached

            merged = pd.concat([cached] + frames, ignore_index=True)
            merged["时间"] = pd.to_datetime(merged["时间"], errors="coerce")
            merged = merged.dropna(subset=["时间"])
            # 同日多行取网络新值（concat 顺序在后 + 稳定排序 → keep='last' 命中新帧）
            merged = (merged.sort_values("时间")
                            .drop_duplicates(subset="时间", keep="last")
                            .reset_index(drop=True))
            # 裁剪回请求窗口（新浪等源无区间参数会整段返回，不能让窗口外数据漏进契约）
            if need_start is not None:
                merged = merged[merged["时间"] >= need_start]
            if need_end is not None:
                merged = merged[merged["时间"] <= need_end]
            if merged.empty:
                return cached

            try:
                from src.data import db as _db

                for f in frames:
                    _db.save_daily(f, code, market, adjust, is_index=is_index)
            except Exception as e:  # noqa: F841
                logger.debug(f"增量补拉回填失败（不影响主流程）: {e}")
            logger.info(f"增量补拉 {code} ({market}/{adjust}): 头补={head_gap} 尾补={tail_gap} "
                        f"新增 {sum(len(f) for f in frames)} 行")
            return merged
        except Exception as e:  # noqa: BLE001 - 补拉绝不拖垮命中路径
            logger.debug(f"增量补拉异常，退回旧缓存 {code}: {e}")
            return cached
