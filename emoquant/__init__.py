"""emoquant —— EmoQunt 策略 SDK。

代码策略通过本包与回测引擎交互（对标 PandaAI 的 panda_backtest/panda_data）：

    from emoquant.api import buy, sell, close_all, order_target_percent
    import emoquant.data as eq_data

STRATEGY_PARAMS 字典是策略的可调参数（带中文注释，作为参数调优对象）；
initialize(context) 在回测开始时调用一次，handle_data(context, data) 每个
交易日调用一次。

安全边界："防呆不防恶"——ast 校验器封堵危险调用/导入/dunder 链，但本平台
定位为本地单用户工具，不提供容器级隔离。
"""
