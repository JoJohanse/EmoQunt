# coding=utf-8
"""情绪快照存储（SnapshotStore）—— ``nes_data/sentiment_results/{YYYYMMDD}.json`` 解析契约的唯一实现。

快照文件契约
------------
快照位于 ``<项目根>/nes_data/sentiment_results/{YYYYMMDD}.json``，单文件结构::

    {
      "date": "YYYY-MM-DD",                              # 可选
      "timestamp": "YYYY-MM-DD HH:MM:SS",                # 可选
      "news_count": 123,                                 # 可选
      "top_sectors": [{"name": ..., "sentiment": ...}],  # 可选，按情绪降序的榜单
      "all_sectors": [                                   # 行业面板必需
          {"name": "石油行业", "sentiment": 60,
           "stocks": [{"code": "600938", "name": "中国海油"}, ...]},
          ...
      ]
    }

``sentiment`` 为 0-100 量表（50 为中性）。本模块统一归一化为 -1..1：
``(s - 50) / 50``，越界裁剪到 [-1, 1]，缺失/不可解析记为中性 0.0。

日期回退决策（归一）
--------------------
快照日期统一按 **文件名 YYYYMMDD → 文件内 ``date`` 字段 → ``timestamp`` 字段**
顺序解析；三者均不可解析时跳过该文件。

历史上回测侧（原 ``data_manager.load_sentiment_snapshots``）与日历侧（原
``sentiment_calendar.get_sentiment_calendar``）顺序分叉：日历侧为
date → 文件名 → timestamp。B5 架构评审（2026-08）统一为"文件名优先"——
文件名即目录命名契约 ``{YYYYMMDD}.json``，最能代表快照生成日；文件内
``date``/``timestamp`` 字段仅作文件名不可解析（非 8 位日期）时的兜底。

前瞻安全（look-ahead-safe）
--------------------------
本模块只做全量加载与按日聚合，不提供任何"访问未来快照"的路径；
调用方（回测情绪过滤、个股信号）必须只使用不晚于回测日/交易日的
最近历史快照（"截至该日最近的快照值"语义）。
"""
import glob
import json
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.utils.paths import PROJECT_ROOT

# 默认快照目录：<项目根>/nes_data/sentiment_results
DEFAULT_SNAPSHOTS_DIR = PROJECT_ROOT / 'nes_data' / 'sentiment_results'

# 情绪量表归一化常量：0-100（50 为中性）→ -1..1
_SENTIMENT_NEUTRAL = 50.0
_SENTIMENT_SCALE = 50.0


def normalize_sentiment(raw) -> float:
    """将 0-100 情绪量表归一化到 -1..1。

    :param raw: 快照中的 ``sentiment`` 原始值（数值或可转数值的类型）
    :return: ``(raw - 50) / 50`` 裁剪到 [-1, 1]；缺失/不可解析时返回中性 0.0
    """
    try:
        norm = (float(raw) - _SENTIMENT_NEUTRAL) / _SENTIMENT_SCALE
    except (TypeError, ValueError):
        return 0.0
    return max(-1.0, min(1.0, norm))


def resolve_snapshot_date(file_path: str, data: dict) -> Optional[pd.Timestamp]:
    """解析单个快照的日期（统一回退：文件名 → date 字段 → timestamp 字段）。

    :param file_path: 快照文件路径（取文件名 stem 尝试 YYYYMMDD 严格解析）
    :param data: 已加载的快照 JSON 内容
    :return: 快照日期；三者均不可解析时返回 None（调用方应跳过该文件）
    """
    stem = os.path.splitext(os.path.basename(file_path))[0]
    try:
        return pd.to_datetime(stem, format='%Y%m%d')
    except Exception:
        pass
    raw = data.get('date') or data.get('timestamp')
    if raw:
        try:
            return pd.to_datetime(raw)
        except Exception:
            return None
    return None


def snapshot_files(snapshots_dir=None) -> List[str]:
    """返回快照目录下按文件名排序的 JSON 文件路径列表。

    :param snapshots_dir: 快照目录，默认 ``<项目根>/nes_data/sentiment_results``
    """
    dir_path = str(snapshots_dir or DEFAULT_SNAPSHOTS_DIR)
    return sorted(glob.glob(os.path.join(dir_path, '*.json')))


def load_snapshot_records(snapshots_dir=None) -> List[Dict]:
    """逐文件解析快照，返回按日期升序的记录列表（唯一解析入口）。

    每条记录::

        {
            'date': pd.Timestamp,           # 统一回退后的快照日期
            'path': str,                    # 来源文件路径
            'all_sectors': [...],           # 原始行业列表（含 stocks 成分）
            'top_sectors': [...],           # 原始最强板块榜单（可能为空）
            'news_count': int,              # 当日新闻数（缺省 0）
            'scores': {行业名: 归一化分数},  # -1..1，缺失行业分数记 0.0
        }

    JSON 损坏、日期不可解析的文件被跳过；含 ``all_sectors`` 的文件才计入
    ``scores``（空行业列表的快照仍保留其余原始字段，供日历统计展示）。
    """
    records: List[Dict] = []
    for fp in snapshot_files(snapshots_dir):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue

        snap_date = resolve_snapshot_date(fp, data)
        if snap_date is None:
            continue

        sectors = data.get('all_sectors') or []
        scores = {}
        for sec in sectors:
            name = (sec or {}).get('name')
            if name is None:
                continue
            # 缺失/不可解析记为中性 0.0，避免快照间因某行业缺失产生 NaN 列
            scores[name] = normalize_sentiment((sec or {}).get('sentiment'))

        try:
            news_count = int(data.get('news_count', 0) or 0)
        except (TypeError, ValueError):
            news_count = 0

        records.append({
            'date': snap_date,
            'path': fp,
            'all_sectors': sectors,
            'top_sectors': data.get('top_sectors') or [],
            'news_count': news_count,
            'scores': scores,
        })
    records.sort(key=lambda r: r['date'])
    return records


def load_sentiment_snapshots(snapshots_dir: str = None) -> pd.DataFrame:
    """扫描本地历史情绪快照，构建"快照日期 × 行业"的情绪分数面板。

    用于回测中的情绪过滤：某回测日只能使用"截至该日最近的历史快照"，
    以避免未来函数（lookahead bias）。

    :param snapshots_dir: 快照目录，默认为项目根下 nes_data/sentiment_results
    :return: DataFrame，index=快照日期（DatetimeIndex, name='日期'），
             columns=行业名称（如"石油行业"），值为归一化情绪分数(-1..1)。
             无快照时返回空 DataFrame。
    """
    try:
        records = load_snapshot_records(snapshots_dir)
        if not records:
            return pd.DataFrame()

        # 面板仅收录含有效行业分数的快照（空 all_sectors 的文件不产生行）
        dates = []
        rows = []
        for rec in records:
            if rec['scores']:
                dates.append(rec['date'])
                rows.append(rec['scores'])
        if not rows:
            return pd.DataFrame()

        panel = pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name='日期'))
        panel = panel.sort_index()
        # 不同快照间行业集合可能不一致（个别快照缺某行业），缺失填中性 0.0
        panel = panel.fillna(0.0)
        return panel
    except Exception as e:
        print(f"加载情绪快照失败: {e}")
        return pd.DataFrame()


def build_stock_sentiment_series(
    panel: pd.DataFrame, stock_code: str, snapshots_dir=None,
) -> 'Tuple[pd.Series, object]':
    """从情绪面板中提取某只股票所属行业的情绪时间序列。

    通过各快照 all_sectors[i]['stocks'] 中的成分代码定位行业。若同一股票在多个
    行业出现，取第一个匹配。返回的序列可直接用于回测过滤：某回测日取"截至该日
    最近的快照值"，避免未来函数。

    :param panel: load_sentiment_snapshots() 返回的面板（index=日期, columns=行业名）
    :param stock_code: 不带前缀的 6 位股票代码，如 '000001'（容忍 sh/sz 前缀）
    :param snapshots_dir: 成分股扫描用的快照目录，默认项目根下 nes_data/sentiment_results
    :return: (series, sector_name)。series 的 index 为快照日期，值为归一化情绪分数；
             若无法定位行业，series 为空、sector_name 为 None。
    """
    try:
        code = str(stock_code).zfill(6)
        # 去掉可能的 sh/sz 前缀
        if code.startswith(('sh', 'sz')):
            code = code[2:]
        code = code.zfill(6)

        if panel is None or panel.empty:
            return pd.Series(dtype=float), None

        # 优先通过行业映射器定位行业（覆盖快照未显式列出的股票），
        # 失败时回退到扫描快照的成分股代码。
        sector_name = None
        try:
            from src.factor.daily_recommend import StockSectorMapper
            mapper = StockSectorMapper()
            sector_name = mapper.get_sector_by_code(code)
        except Exception:
            sector_name = None

        # 若映射器没结果或映射出的行业不在面板里，回退到成分股扫描
        if not sector_name or sector_name not in panel.columns:
            found = None
            for rec in load_snapshot_records(snapshots_dir):
                for sec in rec['all_sectors']:
                    for st in (sec or {}).get('stocks', []):
                        if str((st or {}).get('code', '')).zfill(6) == code:
                            found = (sec or {}).get('name')
                            break
                    if found:
                        break
                if found:
                    break
            if found and found in panel.columns:
                sector_name = found
            elif sector_name not in panel.columns:
                sector_name = None

        if not sector_name or sector_name not in panel.columns:
            return pd.Series(dtype=float), None

        series = panel[sector_name].copy()
        series.name = sector_name
        return series, sector_name
    except Exception as e:
        print(f"构建股票情绪序列失败: {e}")
        return pd.Series(dtype=float), None


def build_daily_summaries(snapshots_dir=None) -> List[Dict]:
    """按日聚合快照，输出情绪日历所需的逐日摘要（按日期升序）。

    最强板块优先取快照内 ``top_sectors[0]``（已是降序榜单），缺省时回退为
    ``all_sectors`` 中 0-100 原始分最高者；``top_sentiment`` 保留 0-100 原始
    量表（不做 -1..1 归一化），与历史日历展示口径一致。

    :param snapshots_dir: 快照目录，默认 ``<项目根>/nes_data/sentiment_results``
    :return: ``[{date, sectors_count, top_sentiment, top_sector_name, news_count}, ...]``，
             无快照时返回 ``[]``。
    """
    summaries: List[Dict] = []
    for rec in load_snapshot_records(snapshots_dir):
        all_sectors = rec['all_sectors']
        top_sectors = rec['top_sectors']

        # top_sectors 已是按情绪降序的榜单，首个即当日最强板块
        top_sector = top_sectors[0] if top_sectors else (
            max(all_sectors, key=lambda s: (s or {}).get('sentiment', 0))
            if all_sectors else None
        )
        top_sentiment = 0
        top_sector_name = ''
        if top_sector:
            try:
                top_sentiment = int((top_sector or {}).get('sentiment', 0))
            except (TypeError, ValueError):
                top_sentiment = 0
            top_sector_name = str((top_sector or {}).get('name') or '')

        summaries.append({
            'date': rec['date'].strftime('%Y-%m-%d'),
            'sectors_count': len(all_sectors),
            'top_sentiment': top_sentiment,
            'top_sector_name': top_sector_name,
            'news_count': rec['news_count'],
        })
    return summaries
