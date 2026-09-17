"""emoquant.api —— 交易 API（市价单语义）。

所有函数委托给当前线程绑定的策略宿主（见 _runtime.get_host）。仓位契约
（显式化，v2 方案 D1）：size 与 percent 二选一；percent 以总资产为基准、
按可用资金封顶，取整到股。**不强制 A 股整手**——回测使用后复权价，并非
真实可交易价格，整手约束无意义（与旧模板策略 stake=1 的既成口径一致）。
模板策略的 stake=1 口径与本 SDK 不同——同信号下 PnL 不可直接比较。
"""
from __future__ import annotations

from emoquant._runtime import get_host


def buy(size=None, percent=None):
    """市价买入。

    :param size: 买入股数
    :param percent: 以当前总资产为基准的目标买入比例（0-1，按可用资金封顶），如 0.5 = 半仓
    """
    return get_host().buy(size=size, percent=percent)


def sell(size=None, percent=None):
    """市价卖出持仓。

    :param size: 卖出股数（缺省全部平仓）
    :param percent: 卖出当前持仓的比例（0-1]
    """
    return get_host().sell(size=size, percent=percent)


def close_all():
    """市价平掉当前全部持仓。"""
    return get_host().close_all()


def get_position() -> int:
    """当前持仓股数（无持仓返回 0）。"""
    return get_host().get_position()


def order_target_percent(percent: float):
    """调整持仓到总资产的指定比例（0-1）。

    目标高于当前仓位则补买差额（整手取整），低于则卖出差额；无持仓时
    percent<=0 为空操作。
    """
    return get_host().order_target_percent(percent)


def get_cash() -> float:
    """当前可用资金。"""
    return get_host().get_cash()


def get_portfolio_value() -> float:
    """当前总资产（现金 + 持仓市值）。"""
    return get_host().get_portfolio_value()
