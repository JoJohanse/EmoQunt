"""
i18n 文案目录包（按域拆分）

本包只放「数据」不放逻辑：每个模块导出 ``MESSAGES``（``{key: {"zh": ..., "en": ...}}``），
由 ``src/utils/i18n.py`` 统一合并为扁平目录。zh 值必须与改造前的界面文案逐字一致。

``MESSAGE_MODULES`` 是合并顺序（后者覆盖同键条目）；本包不 import 任何东西，
避免与 i18n.py 形成循环导入。
"""

# i18n.py 合并的目录模块（顺序即覆盖优先级）
MESSAGE_MODULES = (
    "common",      # 导航/品牌/页脚/页面标题/通用文案（i18n 基础设施，本 Agent 所有）
    "setup",       # 安装引导自检项（本 Agent 所有）
    "validators",  # 输入校验消息（本 Agent 所有）
    "backtest",    # 回测指标键与回测页文案（backtest_form/result 模板 Agent）
    "strategies",  # 策略列表页文案（strategies.html 模板 Agent）
    "sentiment",   # 舆情分析页文案（sentiment 模板 Agent）
    "recommend",   # 每日推荐页文案（daily_recommend.html 模板 Agent）
    "charts",      # matplotlib 图表标签（可视化 Agent）
    "agent",       # Agent 工具错误/提示文案（src/agent/tools.py）
    "library",     # 策略库/运行历史文案（code_validator、v2 服务与路由）
    "tuning",      # 参数调优文案（src/services/tuning.py）
)
