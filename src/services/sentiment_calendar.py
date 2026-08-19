"""情绪历史日历服务：扫描本地情绪快照，输出按日期升序的单日情绪摘要。

供首页/舆情页的情绪日历组件使用（GET /api/sentiment/calendar）。
仅读取本地 JSON，不做任何联网/重分析，失败时返回空列表。
"""
import glob
import json
import logging
import os
from typing import Dict, List

from src.utils.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

SENTIMENT_RESULTS_DIR = PROJECT_ROOT / 'nes_data' / 'sentiment_results'


def get_sentiment_calendar(snapshots_dir: str = None) -> List[Dict]:
    """扫描历史情绪快照，返回按日期升序的单日情绪摘要。

    :param snapshots_dir: 快照目录，默认 ``<项目根>/nes_data/sentiment_results``
    :return: ``[{date, sectors_count, top_sentiment, top_sector_name, news_count}, ...]``，
             无快照或读取失败时返回 ``[]``。
    """
    try:
        dir_path = snapshots_dir or str(SENTIMENT_RESULTS_DIR)
        if not os.path.isdir(dir_path):
            return []

        files = sorted(glob.glob(os.path.join(dir_path, '*.json')))
        records: List[Dict] = []
        for fp in files:
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"读取情绪快照失败，跳过 {fp}: {e}")
                continue

            # 日期优先取快照内 date 字段，其次文件名 YYYYMMDD，最后 timestamp
            date = data.get('date')
            if not date:
                stem = os.path.splitext(os.path.basename(fp))[0]
                if stem.isdigit() and len(stem) == 8:
                    date = f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}"
                else:
                    date = (data.get('timestamp') or '')[:10]

            all_sectors = data.get('all_sectors') or []
            top_sectors = data.get('top_sectors') or []

            # top_sectors 已是按情绪降序的榜单，首个即当日最强板块
            top_sector = top_sectors[0] if top_sectors else (
                max(all_sectors, key=lambda s: (s or {}).get('sentiment', 0))
                if all_sectors else None
            )
            top_sentiment = 0
            top_sector_name = ''
            if top_sector:
                try:
                    top_sentiment = int(top_sector.get('sentiment', 0))
                except (TypeError, ValueError):
                    top_sentiment = 0
                top_sector_name = str(top_sector.get('name') or '')

            ds = str(date or '').strip()
            # 仅保留合法 YYYY-MM-DD，避免空日期排到最前
            if not ds or len(ds) != 10 or ds[4] != '-' or ds[7] != '-':
                continue
            records.append({
                'date': ds,
                'sectors_count': len(all_sectors),
                'top_sentiment': top_sentiment,
                'top_sector_name': top_sector_name,
                'news_count': int(data.get('news_count', 0) or 0),
            })

        records.sort(key=lambda r: r['date'])
        return records
    except Exception as e:
        logger.error(f"加载情绪日历失败: {e}", exc_info=True)
        return []
