"""业务 SQLite 存储层：策略库（代码策略）+ 回测运行记录 + 参数调优任务 + 因子库。

与行情缓存层 src/data/db.py（PostgreSQL/Redis，可选降级）职责分离：
本模块是策略/运行/调优的**唯一真相**，故障上抛而非静默降级。

工程约定（对齐 docs/plans/pandaai-style-platform-plan.md D2/D3/D4）：
- 标准库 sqlite3，WAL + busy_timeout；每线程独立连接（threading.local），
  HTTP 线程池与任务执行器线程并存互不串扰；
- 建表幂等（CREATE TABLE IF NOT EXISTS）；库文件路径可用环境变量
  ``QDT_STORE_DB_PATH`` 覆盖（测试隔离用），默认 ``data/emoqunt.db``；
- 启动清扫：init_db() 把遗留 queued/running 的运行/调优任务/调优组合批量
  标记 failed（进程内执行器无持久队列，重启即丢）；
- 回测时序存储：equity 数组 zlib+base64（dates/trades/metrics 为 JSON 文本），
  drawdown/daily_returns 可由 equity 派生不落库；调优组合净值降采样 ≤240 点；
- 终态写入全部走条件 UPDATE（``WHERE status IN ('queued','running')``），
  超时看门狗"放弃等待"后迟到的完成结果不会覆盖 failed 状态。

模板策略不存这里：strategies.json 仍是模板策略唯一真相（v2 方案决策）。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import threading
import zlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.env import get_env

logger = logging.getLogger(__name__)

# 终态集合
RUN_ACTIVE_STATUSES = ("queued", "running")
RUN_FINAL_STATUSES = ("succeeded", "failed", "cancelled")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    market TEXT NOT NULL DEFAULT 'zh_a',
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategies_updated ON strategies(updated_at DESC);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    strategy_kind TEXT NOT NULL DEFAULT 'template',
    strategy_id INTEGER,
    stock_code TEXT NOT NULL,
    market TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    commission_rate REAL NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT,
    metrics_json TEXT,
    dates_json TEXT,
    equity_zlib TEXT,
    trades_json TEXT,
    stages_json TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON backtest_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_strategy ON backtest_runs(strategy_kind, strategy_id);

CREATE TABLE IF NOT EXISTS strategy_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    tags TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_versions_strategy ON strategy_versions(strategy_id, id DESC);

CREATE TABLE IF NOT EXISTS tuning_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_kind TEXT NOT NULL DEFAULT 'code',
    strategy_id INTEGER,
    strategy_name TEXT NOT NULL,
    market TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    commission_rate REAL NOT NULL,
    param_grid_json TEXT NOT NULL DEFAULT '{}',
    grid_keys_json TEXT NOT NULL DEFAULT '[]',
    target_metric TEXT NOT NULL DEFAULT '总收益率',
    target_metric_desc INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'queued',
    total_combos INTEGER NOT NULL DEFAULT 0,
    done_combos INTEGER NOT NULL DEFAULT 0,
    succeeded_combos INTEGER NOT NULL DEFAULT 0,
    best_combo_index INTEGER,
    error TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tuning_tasks_strategy ON tuning_tasks(strategy_kind, strategy_id);

CREATE TABLE IF NOT EXISTS tuning_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    combo_index INTEGER NOT NULL,
    is_baseline INTEGER NOT NULL DEFAULT 0,
    params_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT,
    metrics_json TEXT,
    dates_json TEXT,
    equity_zlib TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tuning_runs_task ON tuning_runs(task_id, combo_index);

CREATE TABLE IF NOT EXISTS factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    market TEXT NOT NULL DEFAULT 'zh_a',
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_factors_updated ON factors(updated_at DESC);

CREATE TABLE IF NOT EXISTS factor_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_factor_versions_factor ON factor_versions(factor_id, id DESC);
"""

_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def get_db_path():
    """业务库文件路径（环境变量 QDT_STORE_DB_PATH 可覆盖，测试用）。"""
    import os

    override = get_env("QDT_STORE_DB_PATH", "")
    if override:
        return override
    from src.utils.paths import get_data_dir

    return str(get_data_dir() / "emoqunt.db")


def _connect() -> sqlite3.Connection:
    """新建连接并设置 pragmas（每线程连接共享这些设置）。父目录不存在时先创建。"""
    path = get_db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_conn() -> sqlite3.Connection:
    """取当前线程连接（懒建；init_db 未调用时隐式初始化）。"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    """幂等建表 + 启动清扫（遗留 queued/running 标 failed）。线程安全。"""
    global _initialized
    with _init_lock:
        conn = get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()
        if not _initialized:
            cur = conn.execute(
                f"UPDATE backtest_runs SET status='failed', error=?, updated_at=? "
                f"WHERE status IN ('queued','running')",
                ("服务重启，任务中断", _now()),
            )
            if cur.rowcount:
                logger.warning("启动清扫：已把 %d 个中断运行标记为 failed", cur.rowcount)
            cur = conn.execute(
                "UPDATE tuning_tasks SET status='failed', error=?, updated_at=? "
                "WHERE status IN ('queued','running')",
                ("服务重启，任务中断", _now()),
            )
            if cur.rowcount:
                logger.warning("启动清扫：已把 %d 个中断调优任务标记为 failed", cur.rowcount)
            conn.execute(
                "UPDATE tuning_runs SET status='failed', error=?, updated_at=? "
                "WHERE status IN ('queued','running')",
                ("服务重启，任务中断", _now()),
            )
            conn.commit()
            _initialized = True


def _ensure_init() -> None:
    if not _initialized:
        init_db()


def reset_for_tests() -> None:
    """测试隔离：关闭当前线程连接并复位初始化标记（生产代码勿用）。

    改变 QDT_STORE_DB_PATH 后必须调用，否则线程缓存的连接仍指向旧库。
    """
    global _initialized
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _local.conn = None
    with _init_lock:
        _initialized = False


# ---------------------------------------------------------------------------
# 代码策略（strategies 表）CRUD 原语——服务层见 src/services/strategy_library.py
# ---------------------------------------------------------------------------
def insert_strategy(name: str, market: str, description: str, source: str,
                    params: Dict[str, Any], tags: str = "") -> int:
    """插入代码策略，返回新 id。名称唯一由表约束保证（冲突上抛 IntegrityError）。"""
    _ensure_init()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO strategies (name, market, description, source, params_json, tags, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, market, description, source, json.dumps(params, ensure_ascii=False), tags, _now(), _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_strategy_row(strategy_id: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()


def get_strategy_row_by_name(name: str) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM strategies WHERE name = ?", (name,)).fetchone()


def list_strategy_rows(market: Optional[str] = None, q: str = "",
                       limit: int = 200, offset: int = 0) -> List[sqlite3.Row]:
    """策略列表（q 对名称/描述/标签做 LIKE；按 updated_at 降序）。"""
    _ensure_init()
    sql = "SELECT * FROM strategies WHERE 1=1"
    args: List[Any] = []
    if market:
        sql += " AND market = ?"
        args.append(market)
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE ? OR description LIKE ? OR tags LIKE ?)"
        args += [like, like, like]
    sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    args += [int(limit), int(offset)]
    return get_conn().execute(sql, args).fetchall()


def update_strategy_row(strategy_id: int, fields: Dict[str, Any]) -> bool:
    """更新指定列（白名单键），返回是否有行被更新。updated_at 自动刷新。"""
    _ensure_init()
    allowed = {"name", "market", "description", "source", "params_json", "tags"}
    sets, args = [], []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        sets.append(f"{key} = ?")
        args.append(value)
    if not sets:
        return False
    sets.append("updated_at = ?")
    args.append(_now())
    args.append(strategy_id)
    conn = get_conn()
    cur = conn.execute(f"UPDATE strategies SET {', '.join(sets)} WHERE id = ?", args)
    conn.commit()
    return cur.rowcount > 0


def delete_strategy_row(strategy_id: int) -> bool:
    _ensure_init()
    conn = get_conn()
    cur = conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# 策略版本（strategy_versions 表）——"更新即快照 + 回滚"
# ---------------------------------------------------------------------------
def insert_strategy_version(strategy_id: int, name: str, market: str, description: str,
                            source: str, params: Dict[str, Any], tags: str, note: str = "") -> int:
    """为策略插入一条版本快照（更新/删除前调用），返回版本 id。"""
    _ensure_init()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO strategy_versions (strategy_id, name, market, description, source, params_json, tags, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (strategy_id, name, market, description, source, json.dumps(params, ensure_ascii=False),
         tags, note, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_strategy_versions(strategy_id: int, limit: int = 50) -> List[sqlite3.Row]:
    """版本列表（新→旧；不含 source 大字段）。"""
    _ensure_init()
    return get_conn().execute(
        "SELECT id, strategy_id, name, market, description, tags, note, created_at "
        "FROM strategy_versions WHERE strategy_id = ? ORDER BY id DESC LIMIT ?",
        (strategy_id, int(limit)),
    ).fetchall()


def get_strategy_version(version_id: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM strategy_versions WHERE id = ?", (version_id,)).fetchone()


def prune_strategy_versions(strategy_id: int, keep: int = 20) -> None:
    """只保留最近 keep 个版本（快照含全文，防膨胀）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "DELETE FROM strategy_versions WHERE strategy_id = ? AND id NOT IN "
        "(SELECT id FROM strategy_versions WHERE strategy_id = ? ORDER BY id DESC LIMIT ?)",
        (strategy_id, strategy_id, int(keep)),
    )
    conn.commit()


def row_to_strategy_dict(row: sqlite3.Row, include_source: bool = True) -> Dict[str, Any]:
    """行 → API dict（params_json 反序列化）。"""
    out = {
        "id": row["id"],
        "name": row["name"],
        "market": row["market"],
        "description": row["description"],
        "tags": row["tags"],
        "params": json.loads(row["params_json"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_source:
        out["source"] = row["source"]
    return out


# ---------------------------------------------------------------------------
# 回测运行记录（backtest_runs 表）
# ---------------------------------------------------------------------------
def create_run(params: Dict[str, Any], strategy_kind: str = "template",
               strategy_id: Optional[int] = None) -> int:
    """登记一次回测运行（status=queued），返回 run id。

    :param params: validate_backtest_params 归一后的参数 dict
    """
    _ensure_init()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO backtest_runs (strategy_name, strategy_kind, strategy_id, stock_code, market, "
        "start_date, end_date, initial_capital, commission_rate, params_json, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)",
        (params["strategy_name"], strategy_kind, strategy_id, params["stock_code"], params["market"],
         params["start_date"], params["end_date"], params["initial_capital"], params["commission_rate"],
         json.dumps(params, ensure_ascii=False), _now(), _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def set_run_running(run_id: int) -> None:
    _ensure_init()
    conn = get_conn()
    conn.execute("UPDATE backtest_runs SET status='running', updated_at=? WHERE id=? AND status='queued'",
                 (_now(), run_id))
    conn.commit()


def fail_run_if_active(run_id: int, error: str) -> None:
    """把活跃运行标记 failed（条件更新：迟到的完成/超时竞争不会互相覆盖）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute("UPDATE backtest_runs SET status='failed', error=?, updated_at=? WHERE id=? AND status IN ('queued','running')",
                 (error[:2000], _now(), run_id))
    conn.commit()


def finish_run_if_active(run_id: int, metrics: Dict[str, Any], dates: List[str],
                         equity: List[float], trades: List[Dict[str, Any]],
                         stages: List[Dict[str, Any]], duration_ms: int) -> None:
    """写入成功结果（条件更新，仅 running 态生效）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "UPDATE backtest_runs SET status='succeeded', metrics_json=?, dates_json=?, equity_zlib=?, "
        "trades_json=?, stages_json=?, duration_ms=?, updated_at=? WHERE id=? AND status IN ('queued','running')",
        (json.dumps(metrics, ensure_ascii=False), json.dumps(dates), _pack_series(equity),
         json.dumps(trades, ensure_ascii=False), json.dumps(stages), int(duration_ms), _now(), run_id),
    )
    conn.commit()


def get_run_row(run_id: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM backtest_runs WHERE id = ?", (run_id,)).fetchone()


def list_run_rows(strategy_kind: Optional[str] = None, strategy_id: Optional[int] = None,
                  market: Optional[str] = None, status: Optional[str] = None,
                  limit: int = 50, offset: int = 0) -> List[sqlite3.Row]:
    """运行记录列表（摘要，不含时序大字段）。"""
    _ensure_init()
    sql = ("SELECT id, strategy_name, strategy_kind, strategy_id, stock_code, market, start_date, end_date, "
           "initial_capital, commission_rate, status, error, metrics_json, stages_json, duration_ms, "
           "dates_json, equity_zlib, created_at, updated_at FROM backtest_runs WHERE 1=1")
    args: List[Any] = []
    if strategy_kind:
        sql += " AND strategy_kind = ?"
        args.append(strategy_kind)
    if strategy_id is not None:
        sql += " AND strategy_id = ?"
        args.append(strategy_id)
    if market:
        sql += " AND market = ?"
        args.append(market)
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [int(limit), int(offset)]
    return get_conn().execute(sql, args).fetchall()


def row_to_run_dict(row: sqlite3.Row, unpack_series: bool = False) -> Dict[str, Any]:
    """运行行 → API dict。unpack_series=True 时解压 equity/dates/trades 全量。"""
    out: Dict[str, Any] = {
        "id": row["id"],
        "strategy_name": row["strategy_name"],
        "strategy_kind": row["strategy_kind"],
        "strategy_id": row["strategy_id"],
        "stock_code": row["stock_code"],
        "market": row["market"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "initial_capital": row["initial_capital"],
        "commission_rate": row["commission_rate"],
        "status": row["status"],
        "error": row["error"],
        "stages": json.loads(row["stages_json"]) if row["stages_json"] else [],
        "duration_ms": row["duration_ms"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if row["metrics_json"]:
        out["metrics"] = json.loads(row["metrics_json"])
    if unpack_series:
        out["dates"] = json.loads(row["dates_json"]) if row["dates_json"] else []
        out["equity_curve"] = _unpack_series(row["equity_zlib"]) if row["equity_zlib"] else []
        out["trades"] = json.loads(row["trades_json"]) if row["trades_json"] else []
    else:
        # 列表页净值缩略：降采样 ≤60 点（无时序字段时为空数组）
        out["equity_preview"] = (
            downsample_series(_unpack_series(row["equity_zlib"]), 60)
            if row["equity_zlib"] else []
        )
    return out


# ---------------------------------------------------------------------------
# 参数调优（tuning_tasks / tuning_runs 表）——服务层见 src/services/tuning.py
# ---------------------------------------------------------------------------
def create_tuning_task(fields: Dict[str, Any], combos: List[Dict[str, Any]]) -> int:
    """登记调优任务 + 全部组合行（同一事务），返回任务 id。

    :param fields: 任务列（grid_json/grid_keys_json 等已序列化好的键值）
    :param combos: [{combo_index, is_baseline, params}]，params 为该组完整生效参数
    """
    _ensure_init()
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO tuning_tasks (strategy_kind, strategy_id, strategy_name, market, stock_code, "
            "start_date, end_date, initial_capital, commission_rate, param_grid_json, grid_keys_json, "
            "target_metric, target_metric_desc, status, total_combos, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)",
            (fields["strategy_kind"], fields.get("strategy_id"), fields["strategy_name"],
             fields["market"], fields["stock_code"], fields["start_date"], fields["end_date"],
             fields["initial_capital"], fields["commission_rate"],
             fields["param_grid_json"], fields["grid_keys_json"],
             fields["target_metric"], int(fields.get("target_metric_desc", 1)),
             len(combos), _now(), _now()),
        )
        task_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT INTO tuning_runs (task_id, combo_index, is_baseline, params_json, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'queued', ?, ?)",
            [(task_id, c["combo_index"], int(c.get("is_baseline", 0)),
              json.dumps(c["params"], ensure_ascii=False), _now(), _now()) for c in combos],
        )
    return task_id


def get_tuning_task_row(task_id: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM tuning_tasks WHERE id = ?", (task_id,)).fetchone()


def list_tuning_task_rows(strategy_kind: Optional[str] = None, strategy_id: Optional[int] = None,
                          limit: int = 50, offset: int = 0) -> List[sqlite3.Row]:
    """调优任务列表（新→旧，不含组合）。"""
    _ensure_init()
    sql = "SELECT * FROM tuning_tasks WHERE 1=1"
    args: List[Any] = []
    if strategy_kind:
        sql += " AND strategy_kind = ?"
        args.append(strategy_kind)
    if strategy_id is not None:
        sql += " AND strategy_id = ?"
        args.append(strategy_id)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [int(limit), int(offset)]
    return get_conn().execute(sql, args).fetchall()


def set_tuning_task_running(task_id: int) -> None:
    _ensure_init()
    conn = get_conn()
    conn.execute("UPDATE tuning_tasks SET status='running', updated_at=? WHERE id=? AND status='queued'",
                 (_now(), task_id))
    conn.commit()


def bump_tuning_progress(task_id: int, succeeded: int) -> None:
    """组合落库后推进计数（执行器多线程并发调用，用 SQL 自增避免读改写竞争）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "UPDATE tuning_tasks SET done_combos = done_combos + 1, succeeded_combos = succeeded_combos + ?, "
        "updated_at=? WHERE id=?",
        (1 if succeeded else 0, _now(), task_id),
    )
    conn.commit()


def fail_tuning_task_if_active(task_id: int, error: str) -> None:
    """把活跃调优任务标记 failed（条件更新，迟到结果不覆盖）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute("UPDATE tuning_tasks SET status='failed', error=?, updated_at=? WHERE id=? AND status IN ('queued','running')",
                 (error[:2000], _now(), task_id))
    conn.commit()


def finish_tuning_task_if_active(task_id: int, status: str, best_combo_index: Optional[int],
                                 error: Optional[str], duration_ms: int) -> None:
    """任务终态落库（条件更新；status ∈ succeeded/failed）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "UPDATE tuning_tasks SET status=?, best_combo_index=?, error=?, duration_ms=?, updated_at=? "
        "WHERE id=? AND status IN ('queued','running')",
        (status, best_combo_index, error, int(duration_ms), _now(), task_id),
    )
    conn.commit()


def fail_tuning_runs_if_active(task_id: int, error: str) -> None:
    """把某任务下所有活跃组合行标记 failed（超时放弃/失败收尾用）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "UPDATE tuning_runs SET status='failed', error=?, updated_at=? "
        "WHERE task_id=? AND status IN ('queued','running')",
        (error[:2000], _now(), task_id),
    )
    conn.commit()


def get_tuning_run_row(task_id: int, combo_index: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute(
        "SELECT * FROM tuning_runs WHERE task_id = ? AND combo_index = ?",
        (task_id, combo_index),
    ).fetchone()


def list_tuning_run_rows(task_id: int) -> List[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute(
        "SELECT * FROM tuning_runs WHERE task_id = ? ORDER BY combo_index ASC", (task_id,),
    ).fetchall()


def update_tuning_run_result(task_id: int, combo_index: int, status: str, error: Optional[str] = None,
                             metrics: Optional[Dict[str, Any]] = None,
                             dates: Optional[List[str]] = None, equity: Optional[List[float]] = None,
                             duration_ms: Optional[int] = None) -> None:
    """组合终态落库（succeeded 带指标与降采样净值；failed 带错误文案）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "UPDATE tuning_runs SET status=?, error=?, metrics_json=?, dates_json=?, equity_zlib=?, "
        "duration_ms=?, updated_at=? WHERE task_id=? AND combo_index=?",
        (status, (error or "")[:2000] or None,
         json.dumps(metrics, ensure_ascii=False) if metrics is not None else None,
         json.dumps(dates) if dates is not None else None,
         _pack_series(equity) if equity is not None else None,
         duration_ms, _now(), task_id, combo_index),
    )
    conn.commit()


def row_to_tuning_task_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "strategy_kind": row["strategy_kind"],
        "strategy_id": row["strategy_id"],
        "strategy_name": row["strategy_name"],
        "market": row["market"],
        "stock_code": row["stock_code"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "initial_capital": row["initial_capital"],
        "commission_rate": row["commission_rate"],
        "param_grid": json.loads(row["param_grid_json"] or "{}"),
        "grid_keys": json.loads(row["grid_keys_json"] or "[]"),
        "target_metric": row["target_metric"],
        "target_metric_desc": bool(row["target_metric_desc"]),
        "status": row["status"],
        "total_combos": row["total_combos"],
        "done_combos": row["done_combos"],
        "succeeded_combos": row["succeeded_combos"],
        "best_combo_index": row["best_combo_index"],
        "error": row["error"],
        "duration_ms": row["duration_ms"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_tuning_run_dict(row: sqlite3.Row, unpack_series: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "combo_index": row["combo_index"],
        "is_baseline": bool(row["is_baseline"]),
        "params": json.loads(row["params_json"] or "{}"),
        "status": row["status"],
        "error": row["error"],
        "duration_ms": row["duration_ms"],
    }
    if row["metrics_json"]:
        out["metrics"] = json.loads(row["metrics_json"])
    if unpack_series:
        out["dates"] = json.loads(row["dates_json"]) if row["dates_json"] else []
        out["equity_curve"] = _unpack_series(row["equity_zlib"]) if row["equity_zlib"] else []
    return out


# ---------------------------------------------------------------------------
# 因子库（factors / factor_versions 表）——服务层见 src/services/factor_library.py
# ---------------------------------------------------------------------------
def insert_factor(name: str, market: str, description: str, source: str, tags: str = "") -> int:
    """插入因子，返回新 id。名称唯一由表约束保证（冲突上抛 IntegrityError）。"""
    _ensure_init()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO factors (name, market, description, source, tags, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, market, description, source, tags, _now(), _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_factor_row(factor_id: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM factors WHERE id = ?", (factor_id,)).fetchone()


def get_factor_row_by_name(name: str) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM factors WHERE name = ?", (name,)).fetchone()


def list_factor_rows(market: Optional[str] = None, q: str = "",
                     limit: int = 200, offset: int = 0) -> List[sqlite3.Row]:
    """因子列表（q 对名称/描述/标签 LIKE；按 updated_at 降序）。"""
    _ensure_init()
    sql = "SELECT * FROM factors WHERE 1=1"
    args: List[Any] = []
    if market:
        sql += " AND market = ?"
        args.append(market)
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE ? OR description LIKE ? OR tags LIKE ?)"
        args += [like, like, like]
    sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    args += [int(limit), int(offset)]
    return get_conn().execute(sql, args).fetchall()


def update_factor_row(factor_id: int, fields: Dict[str, Any]) -> bool:
    """更新指定列（白名单键），返回是否有行被更新。updated_at 自动刷新。"""
    _ensure_init()
    allowed = {"name", "market", "description", "source", "tags"}
    sets, args = [], []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        sets.append(f"{key} = ?")
        args.append(value)
    if not sets:
        return False
    sets.append("updated_at = ?")
    args.append(_now())
    args.append(factor_id)
    conn = get_conn()
    cur = conn.execute(f"UPDATE factors SET {', '.join(sets)} WHERE id = ?", args)
    conn.commit()
    return cur.rowcount > 0


def delete_factor_row(factor_id: int) -> bool:
    _ensure_init()
    conn = get_conn()
    cur = conn.execute("DELETE FROM factors WHERE id = ?", (factor_id,))
    conn.commit()
    return cur.rowcount > 0


def insert_factor_version(factor_id: int, name: str, market: str, description: str,
                          source: str, tags: str, note: str = "") -> int:
    """为因子插入一条版本快照（更新/删除前调用），返回版本 id。"""
    _ensure_init()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO factor_versions (factor_id, name, market, description, source, tags, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (factor_id, name, market, description, source, tags, note, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_factor_versions(factor_id: int, limit: int = 50) -> List[sqlite3.Row]:
    """因子版本列表（新→旧；不含 source 大字段）。"""
    _ensure_init()
    return get_conn().execute(
        "SELECT id, factor_id, name, market, description, tags, note, created_at "
        "FROM factor_versions WHERE factor_id = ? ORDER BY id DESC LIMIT ?",
        (factor_id, int(limit)),
    ).fetchall()


def get_factor_version(version_id: int) -> Optional[sqlite3.Row]:
    _ensure_init()
    return get_conn().execute("SELECT * FROM factor_versions WHERE id = ?", (version_id,)).fetchone()


def prune_factor_versions(factor_id: int, keep: int = 20) -> None:
    """只保留最近 keep 个版本（快照含全文，防膨胀）。"""
    _ensure_init()
    conn = get_conn()
    conn.execute(
        "DELETE FROM factor_versions WHERE factor_id = ? AND id NOT IN "
        "(SELECT id FROM factor_versions WHERE factor_id = ? ORDER BY id DESC LIMIT ?)",
        (factor_id, factor_id, int(keep)),
    )
    conn.commit()


def row_to_factor_dict(row: sqlite3.Row, include_source: bool = True) -> Dict[str, Any]:
    """因子行 → API dict。"""
    out = {
        "id": row["id"],
        "name": row["name"],
        "market": row["market"],
        "description": row["description"],
        "tags": row["tags"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_source:
        out["source"] = row["source"]
    return out


# ---------------------------------------------------------------------------
# 压缩/解压助手
# ---------------------------------------------------------------------------
def downsample_series(values: List[float], max_points: int) -> List[float]:
    """等距降采样（保首尾点；点数不足时原样返回）。调优净值对比与列表缩略用。"""
    n = len(values)
    if n <= max_points or n <= 2:
        return list(values)
    step = (n - 1) / (max_points - 1)
    return [values[int(i * step)] for i in range(max_points)]


def _pack_series(values: List[float]) -> str:
    """浮点数组 → zlib+base64 文本（JSON 中转保精度）。"""
    raw = json.dumps(values, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 6)).decode("ascii")


def _unpack_series(packed: str) -> List[float]:
    return json.loads(zlib.decompress(base64.b64decode(packed)).decode("utf-8"))
