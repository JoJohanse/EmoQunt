"""emoquant 运行时绑定：把 SDK 函数接到"当前正在跑的策略宿主"。

线程局部（threading.local）：执行器并发跑多个回测时，各线程各自绑定自己的
宿主，互不串扰。绑定/解绑由 code_loader 在调用用户 initialize/handle_data
前后用 try/finally 管理；SDK 函数只允许在这两个生命周期内调用。
"""
from __future__ import annotations

import threading

_state = threading.local()


def bind_host(host) -> None:
    """绑定当前线程的策略宿主（code_loader 专用）。"""
    _state.host = host


def unbind_host() -> None:
    """解绑当前线程的策略宿主。"""
    _state.host = None


def get_host():
    """取当前线程的策略宿主。

    :raises RuntimeError: 不在策略生命周期内调用（如模块导入期）时抛出
    """
    host = getattr(_state, "host", None)
    if host is None:
        raise RuntimeError(
            "emoquant API 只能在策略的 initialize/handle_data 内调用"
        )
    return host
