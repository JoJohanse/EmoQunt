"""行情速览服务：行业板块行情 + 市场宽度（涨跌家数），供首页看板卡片。

数据源与降级策略：
- 板块行情：akshare ``stock_board_industry_summary_ths``（同花顺行业一览，含
  板块涨跌幅/成交额/上涨下跌家数/领涨股，90 个行业一次拉全）。
- 市场宽度：同花顺各行业上涨/下跌家数求和得到全市场涨跌家数；涨停/跌停家数
  用东财涨停/跌停股池（``stock_zt_pool_em`` / ``stock_zt_pool_dtgc_em``）按最近
  交易日统计，失败时置 None 不阻塞整体。
- 东财行情快照（spot_em）与乐咕活跃度接口在部分网络环境不可达，故不作为依赖。

进程内 TTL 缓存 5 分钟（src.utils.ttl_cache 助手），避免首页多次刷新
反复打数据源。板块 DataFrame 本身也做短 TTL 缓存，避免冷缓存时 breadth 与
sectors 并行请求各打一次 THS 全量爬取。
"""
import concurrent.futures
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 秒
_CACHE = TTLCache()


def _to_num(value, default: float = 0.0):
    """akshare 各源数值列可能混入字符串/'-'，统一安全转 float。

    传 Series 返回 Series（向量化），传标量返回标量。
    """
    import pandas as pd
    if hasattr(value, "map"):  # pd.Series
        return pd.to_numeric(value, errors="coerce").fillna(default)
    try:
        f = float(value)
        return f if f == f else default  # 过滤 NaN
    except (TypeError, ValueError):
        return default


def _call_with_timeout(fn, timeout: float, *args, **kwargs):
    """在独立线程中执行 fn，超过 timeout 秒则放弃并返回 None。

    akshare 底层 requests.get 未设置 timeout，网络异常时可能无限挂起；
    用该包装避免占满 FastAPI 共享线程池。
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        fut = executor.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning(f"akshare 调用超时({timeout}s)已跳过: {fn.__name__}")
            return None
        except Exception:
            raise


def _pool_size(fetcher, start: datetime, timeout: float = 5.0) -> Optional[int]:
    """按日期从新到旧尝试拉取涨/跌停股池，返回家数；全部失败返回 None。

    lookback 仅 3 天（够覆盖周末/节假日），单次调用 5s 硬超时，避免线程池饥饿。
    fetcher 为 None（akshare 未导出该函数）时直接返回 None。
    """
    if fetcher is None:
        return None
    d = start
    for _ in range(3):
        try:
            df = _call_with_timeout(fetcher, timeout, date=d.strftime('%Y%m%d'))
            if df is not None and len(df) > 0:
                return int(len(df))
        except Exception as e:
            logger.debug(f"股池查询失败 {d:%Y%m%d}: {e}")
        d -= timedelta(days=1)
    return None


def _load_sector_df():
    import akshare as ak
    return ak.stock_board_industry_summary_ths()


def _get_sector_df_cached():
    """带 TTL 的板块 DataFrame 单例，供两个对外函数共享，避免冷缓存双爬。"""
    return _CACHE.get_or_set("_ths_df", _load_sector_df, ttl=_CACHE_TTL)


def get_sector_board() -> Dict[str, Any]:
    """行业板块行情列表（按涨跌幅降序），供首页热力图/排行榜。

    :return: {sectors: [{name, chg_pct, turnover, net_inflow, up_count,
              down_count, leader, leader_chg}], updated_at}
    """
    def _fetch() -> Dict[str, Any]:
        df = _get_sector_df_cached()
        sectors: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            sectors.append({
                "name": str(r.get("板块", "")),
                "chg_pct": round(_to_num(r.get("涨跌幅")), 2),
                "turnover": round(_to_num(r.get("总成交额")), 2),
                "net_inflow": round(_to_num(r.get("净流入")), 2),
                "up_count": int(_to_num(r.get("上涨家数"))),
                "down_count": int(_to_num(r.get("下跌家数"))),
                "leader": str(r.get("领涨股", "") or ""),
                "leader_chg": round(_to_num(r.get("领涨股-涨跌幅")), 2),
            })
        sectors.sort(key=lambda s: s["chg_pct"], reverse=True)
        return {
            "sectors": sectors,
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    try:
        return _CACHE.get_or_set("sector_board", _fetch, ttl=_CACHE_TTL)
    except Exception as e:
        logger.error(f"获取行业板块行情失败: {e}", exc_info=True)
        raise


def get_market_breadth() -> Dict[str, Any]:
    """市场宽度概览：全市场涨跌家数 + 涨停/跌停家数 + 板块涨跌分布。

    涨跌家数为同花顺 90 个行业的上涨/下跌家数之和（近似全市场）；
    涨停/跌停来自东财股池，网络不可达时为 null，不阻塞主流程。
    """
    def _fetch() -> Dict[str, Any]:
        df = _get_sector_df_cached()
        up = int(_to_num(df["上涨家数"]).sum())
        down = int(_to_num(df["下跌家数"]).sum())
        chg = df["涨跌幅"].apply(_to_num)
        rising_sectors = int((chg > 0).sum())

        # 股池函数可能随 akshare 版本更名，缺失时不影响主流程
        try:
            import akshare as ak
            zt_fn = getattr(ak, "stock_zt_pool_em", None)
            dt_fn = getattr(ak, "stock_zt_pool_dtgc_em", None)
        except Exception:
            zt_fn = dt_fn = None
        now = datetime.now()
        limit_up = _pool_size(zt_fn, now)
        limit_down = _pool_size(dt_fn, now)

        top = df.loc[chg.idxmax()]
        return {
            "up": up,
            "down": down,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "rising_sectors": rising_sectors,
            "total_sectors": int(len(df)),
            "top_sector": {
                "name": str(top.get("板块", "")),
                "chg_pct": round(_to_num(top.get("涨跌幅")), 2),
            },
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    try:
        return _CACHE.get_or_set("market_breadth", _fetch, ttl=_CACHE_TTL)
    except Exception as e:
        logger.error(f"获取市场宽度失败: {e}", exc_info=True)
        raise
