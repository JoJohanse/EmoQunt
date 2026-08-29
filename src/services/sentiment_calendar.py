"""情绪历史日历服务：扫描本地情绪快照，输出按日期升序的单日情绪摘要。

供首页/舆情页的情绪日历组件使用（GET /api/sentiment/calendar）。
仅读取本地 JSON，不做任何联网/重分析，失败时返回空列表。

快照解析契约（glob → JSON → 日期回退 → 行业展开）已收进
``src/data/sentiment_snapshots.py``（SnapshotStore，唯一实现），本模块只保留
对外 API 并委托按日聚合。日期回退语义随 SnapshotStore 统一为
**文件名 YYYYMMDD → date 字段 → timestamp 字段**（历史上本模块为
date → 文件名 → timestamp，与回测侧分叉；B5 架构评审归一，文件内 date
字段与文件名不一致时以文件名为准）。
"""
import logging
from typing import Dict, List

from src.data.sentiment_snapshots import build_daily_summaries

logger = logging.getLogger(__name__)


def get_sentiment_calendar(snapshots_dir: str = None) -> List[Dict]:
    """扫描历史情绪快照，返回按日期升序的单日情绪摘要。

    :param snapshots_dir: 快照目录，默认 ``<项目根>/nes_data/sentiment_results``
    :return: ``[{date, sectors_count, top_sentiment, top_sector_name, news_count}, ...]``，
             无快照或读取失败时返回 ``[]``。
    """
    try:
        return build_daily_summaries(snapshots_dir)
    except Exception as e:
        logger.error(f"加载情绪日历失败: {e}", exc_info=True)
        return []
