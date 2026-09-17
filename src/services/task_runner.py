"""进程内任务执行器：ThreadPoolExecutor + 超时看门狗。

单用户本地语义（docs/plans/pandaai-style-platform-plan.md D3）：
- 无持久队列：重启即丢，配合 store.db.init_db() 的启动清扫把遗留
  queued/running 批量标 failed；
- 超时 = "放弃等待 + 标记 failed"：Python 线程不可从外部强杀，看门狗
  触发后工作线程会继续运行至自然结束（线程泄漏是文档明示的务实取舍）；
  终态写入走条件 UPDATE，迟到的完成结果不会覆盖 failed；
- 真隔离（multiprocessing 子进程）为远期选项，注意 Windows spawn 语义。
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional

from src.utils.env import get_env_int

logger = logging.getLogger(__name__)

_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()
_watchdogs: Dict[int, threading.Timer] = {}
_watchdogs_lock = threading.Lock()


def _worker_count() -> int:
    return max(1, min(get_env_int("QDT_TASK_WORKERS", 2), 8))


def get_executor() -> ThreadPoolExecutor:
    """懒建全局执行器（幂等）。"""
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=_worker_count(), thread_name_prefix="qdt-task"
                )
                logger.info("任务执行器已启动（workers=%d）", _worker_count())
    return _executor


def submit_task(task_id: int, work: Callable[[], None], timeout_seconds: float,
                on_abandon: Optional[Callable[[int], None]] = None) -> None:
    """提交任务并在超时后"放弃等待"（把活跃任务标 failed，见模块 docstring）。

    :param task_id: 业务任务 id（backtest_runs.id 或 tuning_tasks.id）
    :param work: 无参工作函数（自身负责状态流转与结果落库）
    :param timeout_seconds: 放弃等待的秒数；<=0 视为不设看门狗
    :param on_abandon: 超时回调（接收 task_id）；缺省为回测运行的放弃逻辑，
        其他任务类型（如调优）传入自己的标记函数
    """
    get_executor().submit(work)
    if timeout_seconds and timeout_seconds > 0:
        timer = threading.Timer(timeout_seconds, on_abandon or _abandon_run, args=(task_id,))
        timer.daemon = True
        with _watchdogs_lock:
            _watchdogs[(id(on_abandon or _abandon_run), task_id)] = timer
        timer.start()


def _abandon_run(task_id: int) -> None:
    """看门狗触发（回测运行）：工作线程尚未结束则把运行标记 failed（条件更新防覆盖）。"""
    try:
        from src.store import db as store

        row = store.get_run_row(task_id)
        if row is None or row["status"] not in ("queued", "running"):
            return
        store.fail_run_if_active(
            task_id, "回测超时，已放弃等待（后台线程将继续运行至自然结束，结果不采纳）"
        )
        logger.warning("任务 %s 超时，已放弃等待", task_id)
    except Exception:
        logger.exception("超时看门狗执行失败 task_id=%s", task_id)
    finally:
        _pop_watchdog(_abandon_run, task_id)


def _pop_watchdog(on_abandon: Callable[[int], None], task_id: int) -> None:
    with _watchdogs_lock:
        _watchdogs.pop((id(on_abandon), task_id), None)


def shutdown_executor(wait: bool = False) -> None:
    """关闭执行器（lifespan 退出用；wait=False 不等在途任务）。"""
    global _executor
    with _watchdogs_lock:
        for timer in _watchdogs.values():
            timer.cancel()
        _watchdogs.clear()
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None