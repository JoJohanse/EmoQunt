"""策略域文案目录：策略列表页（web/templates/strategies.html）。

页面静态文案与内联脚本提示都在这里；策略名/描述/参数名/参数值/参数类型等
**后端数据保持中文原样**（strategies.json 里持久化的是中文标签），不收录进目录。
策略 CRUD 的接口错误文案不走本文件，而是走 ``i18n_data/errors.py`` 的 ``tr_error`` 映射。

约定：
- zh 值必须与改造前的界面文案逐字一致（zh 语言下界面零变化）；
- ``js.`` 前缀条目由 web_app 注入 ``window.__I18N__``，内联脚本用
  ``tt('js.strategies.xxx', '中文兜底')`` 读取；
- ``js.strategies.deleteConfirm`` 含 ``{name}`` 占位符——tt() 不支持参数，
  脚本侧以 ``.replace('{name}', name)`` 完成插值。
"""

MESSAGES = {
    # ---- 页面头部 ----
    "strategies.heading": {"zh": "策略列表", "en": "Strategy List"},
    "strategies.subtitle": {
        "zh": "查看、创建与管理所有回测策略",
        "en": "View, create, and manage all backtest strategies",
    },
    "strategies.newStrategy": {"zh": "新建策略", "en": "New strategy"},

    # ---- 策略卡片 ----
    "strategies.badgeUser": {"zh": "自定义", "en": "Custom"},
    "strategies.badgeSystem": {"zh": "系统", "en": "System"},
    "strategies.edit": {"zh": "编辑", "en": "Edit"},
    "strategies.delete": {"zh": "删除", "en": "Delete"},
    "strategies.view": {"zh": "查看", "en": "View"},
    "strategies.noDescription": {"zh": "暂无描述", "en": "No description"},
    "strategies.parameterConfig": {"zh": "参数配置", "en": "Parameters"},
    "strategies.paramName": {"zh": "参数名", "en": "Parameter"},
    "strategies.value": {"zh": "值", "en": "Value"},
    "strategies.type": {"zh": "类型", "en": "Type"},
    "strategies.noExtraParams": {
        "zh": "此策略无额外参数",
        "en": "This strategy has no extra parameters",
    },
    "strategies.useForBacktest": {
        "zh": "使用此策略回测",
        "en": "Backtest with this strategy",
    },
    # 含受信任的直引号（原始模板为字面 "），模板需以 | safe 渲染，否则被转义为 &#34;
    "strategies.empty": {
        "zh": "暂无可用策略，点击右上角\"新建策略\"创建",
        "en": "No strategies available yet. Click \"New strategy\" in the top right to create one.",
    },

    # ---- 新建/编辑模态框 ----
    "strategies.strategyName": {"zh": "策略名称", "en": "Strategy name"},
    "strategies.strategyTemplate": {"zh": "策略模板", "en": "Strategy template"},
    "strategies.selectTemplate": {"zh": "请选择策略模板", "en": "Select a strategy template"},
    "strategies.strategyDescription": {"zh": "策略描述", "en": "Strategy description"},
    "strategies.defaultValue": {"zh": "默认值", "en": "Default"},
    "strategies.range": {"zh": "范围", "en": "Range"},
    "strategies.cancel": {"zh": "取消", "en": "Cancel"},
    "strategies.createFromTemplate": {"zh": "使用模板创建", "en": "Create from template"},
    "strategies.createCustom": {"zh": "自定义创建", "en": "Create custom"},

    # ---- 内联脚本文案（js. 前缀，供 tt() 读取）----
    "js.strategies.loadTemplatesFailed": {
        "zh": "加载策略模板失败:",
        "en": "Failed to load strategy templates:",
    },
    "js.strategies.newStrategy": {"zh": "新建策略", "en": "New strategy"},
    "js.strategies.editTitle": {"zh": "编辑策略", "en": "Edit strategy"},
    "js.strategies.viewTitle": {"zh": "查看策略", "en": "View strategy"},
    "js.strategies.cancel": {"zh": "取消", "en": "Cancel"},
    "js.strategies.createFromTemplate": {"zh": "使用模板创建", "en": "Create from template"},
    "js.strategies.createCustom": {"zh": "自定义创建", "en": "Create custom"},
    "js.strategies.saveChanges": {"zh": "保存修改", "en": "Save changes"},
    "js.strategies.close": {"zh": "关闭", "en": "Close"},
    "js.strategies.yes": {"zh": "是", "en": "Yes"},
    "js.strategies.no": {"zh": "否", "en": "No"},
    "js.strategies.loadingDetail": {
        "zh": "正在加载策略信息...",
        "en": "Loading strategy details...",
    },
    "js.strategies.creating": {"zh": "正在创建策略...", "en": "Creating strategy..."},
    "js.strategies.saving": {"zh": "正在保存策略...", "en": "Saving strategy..."},
    "js.strategies.deleting": {"zh": "正在删除策略...", "en": "Deleting strategy..."},
    "js.strategies.nameRequired": {
        "zh": "策略名称不能为空",
        "en": "Strategy name cannot be empty",
    },
    "js.strategies.templateRequired": {
        "zh": "请选择策略模板",
        "en": "Please select a strategy template",
    },
    "js.strategies.paramsRequired": {
        "zh": "请配置参数",
        "en": "Please configure the parameters",
    },
    # {name}：策略名（tt() 不支持插值，脚本侧用 .replace('{name}', name)）
    "js.strategies.deleteConfirm": {
        "zh": "确定要删除策略 \"{name}\" 吗？此操作不可恢复。",
        "en": "Delete strategy \"{name}\"? This action cannot be undone.",
    },
    "js.strategies.deleteSuccess": {
        "zh": "策略删除成功",
        "en": "Strategy deleted successfully",
    },
    "js.strategies.createFailed": {"zh": "创建失败", "en": "Creation failed"},
    "js.strategies.saveFailed": {"zh": "保存失败", "en": "Save failed"},
    "js.strategies.deleteFailed": {"zh": "删除失败", "en": "Delete failed"},
    "js.strategies.fetchFailed": {
        "zh": "获取策略信息失败",
        "en": "Failed to fetch strategy details",
    },
}
