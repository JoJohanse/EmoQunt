"""代码策略加载器：用户源码 → 可执行的 backtrader 策略类。

桥接设计：
- 用户生命周期 ``initialize(context)`` 挂在 bt 的 ``start()``（首根 bar 前），
  ``handle_data(context, data)`` 挂在 ``next()``（每根 bar）；
- ``context`` 即 SDK 宿主（emoquant.api/data 经线程局部绑定找到它）：
  params/run_info/trade_date/data 读属性 + buy/sell/close_all 等交易方法；
- 绑定/解绑 try/finally 包裹，用户异常不会让宿主残留绑定；
- 加载前再跑一遍 ast 校验（纵深防御；保存路径已校验过一次）。

回测引擎的撮合语义：市价单下一根 bar 开盘成交（backtrader 默认
cheat-on-close 关闭），文档与提示词均已写明。
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional

import backtrader as bt
import numpy as np
import pandas as pd

from emoquant._runtime import bind_host, unbind_host
from src.Strategy.code_validator import validate_source

# 情绪快照面板的进程级缓存（TTL 内不重读磁盘）
_sentiment_panel: Optional[pd.DataFrame] = None
_sentiment_panel_at: float = 0.0
_SENTIMENT_TTL_SECONDS = 600.0


def compile_user_namespace(source: str) -> Dict[str, Any]:
    """校验 + exec 用户源码，返回命名空间（含用户函数与常量）。

    预置 pd/np/math/datetime 与 SDK 常用名（buy/sell/close_all/get_position/
    order_target_percent/get_cash/get_portfolio_value/eq_data），用户源码
    不 import 也可用——与提示词示例一致，降低 LLM 生成代码的摩擦。
    """
    errors, _defaults = validate_source(source)
    if errors:
        raise ValueError("；".join(errors))
    ns: Dict[str, Any] = {
        "__name__": "emoquant_user_strategy",
        "pd": pd, "np": np, "math": math,
    }
    try:
        from datetime import date as _date, datetime as _datetime, timedelta as _timedelta

        ns["date"] = _date
        ns["datetime"] = _datetime
        ns["timedelta"] = _timedelta
    except Exception:  # pragma: no cover - 标准库导入不会失败
        pass
    try:
        import emoquant.data as _eq_data
        from emoquant.api import (
            buy as _buy, close_all as _close_all, get_cash as _get_cash,
            get_portfolio_value as _get_portfolio_value, get_position as _get_position,
            order_target_percent as _order_target_percent, sell as _sell,
        )

        ns.update({
            "buy": _buy, "sell": _sell, "close_all": _close_all,
            "get_position": _get_position, "order_target_percent": _order_target_percent,
            "get_cash": _get_cash, "get_portfolio_value": _get_portfolio_value,
            "eq_data": _eq_data,
        })
    except Exception:  # pragma: no cover - SDK 包随仓库分发，导入不会失败
        pass
    exec(compile(source, "<emoquant_strategy>", "exec"), ns)
    return ns


class _RunInfo:
    """context.run_info：本次回测的静态信息。"""

    def __init__(self, info: Dict[str, Any]):
        self.start_date = info.get("start_date")
        self.end_date = info.get("end_date")
        self.stock_code = info.get("stock_code")
        self.market = info.get("market", "zh_a")


class _BarProxy:
    """data 代理：当前 bar 的 OHLCV 浮点值；data[symbol] 兼容返回自身（单标的）。"""

    def __init__(self, strat: bt.Strategy):
        self._strat = strat

    @property
    def open(self) -> float:
        return float(self._strat.data.open[0])

    @property
    def high(self) -> float:
        return float(self._strat.data.high[0])

    @property
    def low(self) -> float:
        return float(self._strat.data.low[0])

    @property
    def close(self) -> float:
        return float(self._strat.data.close[0])

    @property
    def volume(self) -> float:
        return float(self._strat.data.volume[0])

    @property
    def date(self):
        return self._strat.data.datetime.date(0)

    def __getitem__(self, _symbol) -> "_BarProxy":
        """单标的引擎：data[symbol] 返回自身（多标的组合回测为远期扩展）。"""
        return self


class _StrategyContext:
    """SDK 宿主 + 用户 context：一个对象同时承担两个角色。

    ``phase`` 决定 get_price 的防未来函数截断语义（对齐 PandaAI 的预热模式）：
    - ``initialize``（"init"）：end 缺省 = 回测结束日——允许一次性预热全区间
      指标历史（示例模式：全区间 rolling 均线按当日下标取值，rolling 只用 ≤i
      的行，本身无未来函数）；
    - ``handle_data``（"next"）：end 缺省 = 当前交易日——逐 bar 拉数不会看到未来；
    - 显式传入的 end 一律再截断到回测结束日；
    - 情绪快照（get_sentiment）无论阶段都只暴露当前交易日及之前。
    """

    def __init__(self, strat: bt.Strategy, params: Dict[str, Any], run_info: Optional[Dict[str, Any]]):
        self._strat = strat
        self.params = dict(params)
        self.run_info = _RunInfo(run_info or {})
        self.trade_date = None
        self.phase = "init"
        self.data = _BarProxy(strat)

    # ---- 生命周期内部 ----
    def _refresh_trade_date(self) -> None:
        try:
            self.trade_date = self._strat.data.datetime.date(0)
        except Exception:
            pass

    # ---- 交易 API（emoquant.api 委托到这里）----
    def _price(self) -> float:
        return float(self._strat.data.close[0])

    def buy(self, size=None, percent=None):
        """市价买入。percent 以总资产为基准、按可用资金封顶，取整到股；
        不强制 A 股整手——回测用后复权价并非真实可交易价格，整手约束无意义
        （与旧模板策略 stake=1 的既成口径一致）。"""
        if percent is not None:
            price = self._price()
            if price <= 0:
                return None
            budget = min(self.get_cash(), float(self._strat.broker.getvalue()) * float(percent))
            size = budget / price
        if size is None:
            raise ValueError("buy 需要指定 size 或 percent")
        size = int(size)
        if size <= 0:
            return None
        return self._strat.buy(size=size)

    def sell(self, size=None, percent=None):
        held = self.get_position()
        if held <= 0:
            return None
        if size is None and percent is not None:
            size = held * float(percent)
        if size is None:
            size = held
        size = min(int(size), held)
        if size <= 0:
            return None
        return self._strat.sell(size=size)

    def close_all(self):
        if self.get_position() > 0:
            return self._strat.close()
        return None

    def get_position(self) -> int:
        return int(self._strat.position.size or 0)

    def order_target_percent(self, percent):
        pct = float(percent)
        price = self._price()
        if price <= 0:
            return None
        value = float(self._strat.broker.getvalue())
        cur_size = self.get_position()
        target_size = value * pct / price
        if target_size > cur_size:
            # 补买差额按可用资金封顶（目标超出可负担时买到资金上限为止）
            affordable = (self.get_cash() / price) + cur_size
            add = int(min(target_size, affordable) - cur_size)
            if add <= 0:
                return None
            return self._strat.buy(size=add)
        if target_size < cur_size:
            drop = min(int(cur_size - target_size), cur_size)
            if drop <= 0:
                return None
            return self._strat.sell(size=drop)
        return None

    def get_cash(self) -> float:
        return float(self._strat.broker.getcash())

    def get_portfolio_value(self) -> float:
        return float(self._strat.broker.getvalue())

    # ---- 数据 API（emoquant.data 委托到这里）----
    def get_price(self, code=None, start="", end=None, market=None, adjust=None) -> pd.DataFrame:
        from src.data.columns import ZH_TO_EN
        from src.data.data_manager import Stock

        ri = self.run_info
        code = str(code or ri.stock_code)
        market = market or ri.market
        adjust = adjust or ("qfq" if market == "us" else "hfq")
        today = self.trade_date.strftime("%Y-%m-%d") if self.trade_date is not None else None
        run_end = str(ri.end_date) if ri.end_date else None
        # 防未来函数截断（ISO 字符串可直接比较）：
        #   显式 end → min(end, 回测结束日)；缺省 end → init 阶段=回测结束日（预热），next 阶段=当前交易日
        if end:
            effective_end = min(str(end), run_end) if run_end else str(end)
        elif self.phase == "next" and today is not None:
            effective_end = today
        else:
            effective_end = run_end or today
        df = Stock(code, market=market).get_stock_data(
            start_date=str(start or "").replace("-", ""),
            end_date=str(effective_end or "").replace("-", ""),
            adjust=adjust, type="daily",
        )
        if df is None or df.empty:
            return pd.DataFrame()
        if "时间" in df.columns:
            df = df.copy()
            df["时间"] = pd.to_datetime(df["时间"])
            df = df.set_index("时间").sort_index()
        return df.rename(columns={k: v for k, v in ZH_TO_EN.items() if k in df.columns})

    def get_sentiment(self, code=None, as_of=None) -> Optional[dict]:
        ri = self.run_info
        if ri.market == "us":
            return None
        code = str(code or ri.stock_code)
        code = str(code).lstrip("shzSZ")
        as_of = str(as_of) if as_of else (
            self.trade_date.strftime("%Y-%m-%d") if self.trade_date is not None else None
        )
        panel = _load_sentiment_panel()
        if panel is None or panel.empty:
            return None
        from src.data.data_manager import build_stock_sentiment_series

        series, sector = build_stock_sentiment_series(panel, code)
        if series is None or series.empty:
            return None
        prior = series[series.index <= pd.Timestamp(as_of)] if as_of else series
        if prior.empty:
            return None
        return {
            "date": prior.index[-1].strftime("%Y-%m-%d"),
            "score": float(prior.iloc[-1]),
            "sector": sector,
        }


def _load_sentiment_panel() -> Optional[pd.DataFrame]:
    """情绪快照面板（模块级 TTL 缓存；只读，走唯一解析器）。"""
    global _sentiment_panel, _sentiment_panel_at
    now = time.monotonic()
    if _sentiment_panel is not None and now - _sentiment_panel_at < _SENTIMENT_TTL_SECONDS:
        return _sentiment_panel
    try:
        from src.data.data_manager import load_sentiment_snapshots

        _sentiment_panel = load_sentiment_snapshots()
        _sentiment_panel_at = now
    except Exception:
        _sentiment_panel = None
        _sentiment_panel_at = now
    return _sentiment_panel


def build_backtrader_strategy(source: str, params: Optional[Dict[str, Any]] = None,
                              run_info: Optional[Dict[str, Any]] = None) -> type:
    """把代码策略源码物化为 backtrader 策略类。

    :param source: Python 源码（先经 ast 校验）
    :param params: 参数覆盖（DB 参数列为真相，覆盖源码 STRATEGY_PARAMS 默认值）
    :param run_info: {start_date, end_date, stock_code, market} 注入 context.run_info
    :return: bt.Strategy 子类（未 addstrategy，由调用方装配）
    """
    errors, defaults = validate_source(source)
    if errors:
        raise ValueError("；".join(errors))
    merged = dict(defaults)
    merged.update(params or {})
    user_ns = compile_user_namespace(source)
    user_init = user_ns.get("initialize")
    user_next = user_ns.get("handle_data")
    run_info = run_info or {}

    class CodeStrategy(bt.Strategy):
        """源码物化产物：生命周期桥接 + SDK 宿主绑定。"""

        params = tuple(sorted(merged.items()))

        def __init__(self):
            self.ctx = _StrategyContext(self, dict(merged), run_info)

        def start(self):
            self.ctx._refresh_trade_date()
            bind_host(self.ctx)
            try:
                user_init(self.ctx)
            finally:
                unbind_host()

        def next(self):
            self.ctx._refresh_trade_date()
            self.ctx.phase = "next"
            bind_host(self.ctx)
            try:
                user_next(self.ctx, self.ctx.data)
            finally:
                unbind_host()

    return CodeStrategy
