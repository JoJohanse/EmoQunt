"""启动预热：lifespan 起后台守护线程，把首页首屏行情拉进本地缓存（quote_cache）。

效果：即使 market_cache.db 为空的首次访问，用户打开首页时缓存已热——
overview 单请求毫秒级返回，不再吃 5-7 秒冷爬。预热失败静默（守护线程，
不影响服务可用性）；环境变量 QDT_STARTUP_WARMUP=0 可关闭。
"""
import logging
import threading
from typing import Optional

from src.utils.env import get_env_bool

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

# 默认自选里的非指数标的（与前端 stores/watchlist.ts 的 DEFAULT_ITEMS 同步维护；
# 用户自改自选后，多出的标的由首访 overview 的 watch 参数按需拉取并缓存）
DEFAULT_WATCH_CODES = [("AAPL", "us"), ("MSFT", "us"), ("TSLA", "us")]


def start_warmup() -> Optional[threading.Thread]:
    """幂等启动预热线程（进程内只起一次）；返回线程或 None（关闭/已启动）。"""
    global _started
    if not get_env_bool("QDT_STARTUP_WARMUP", True):
        logger.info("行情预热已通过 QDT_STARTUP_WARMUP=0 关闭")
        return None
    with _lock:
        if _started:
            return None
        _started = True
    t = threading.Thread(target=_warm, name="qdt-warmup", daemon=True)
    t.start()
    logger.info("行情预热线程已启动（后台填充 quote_cache）")
    return t


def _warm() -> None:
    from src.services.kline import get_kline
    from src.services.market import get_market_overview

    try:
        overview = get_market_overview()  # 指数 + 宽度 + 板块（全部走 SWR 缓存）
        ok = sum(1 for i in overview["indices"] if i.get("close") is not None)
        logger.info("行情预热完成: 指数 %d/%d, 宽度=%s, 板块=%s",
                    ok, len(overview["indices"]),
                    overview["breadth"] is not None, overview["sectors"] is not None)
    except Exception:
        logger.warning("行情预热失败（首次访问将同步拉取）", exc_info=True)
        return
    for code, market in DEFAULT_WATCH_CODES:
        try:
            get_kline(code, market, days=30)
        except Exception as e:
            logger.warning("预热默认自选 %s 失败: %s", code, e)
    logger.info("默认自选预热完成")
