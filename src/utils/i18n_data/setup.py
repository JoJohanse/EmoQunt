"""安装引导页文案目录：自检项（``src/services/system.py``）+ 页面外壳（``setup.html``）。

自检项的 key 约定（``<id>`` 即 ``system.py`` 各检查项 dict 里的 ASCII ``id`` 字段，
如 ``python`` / ``env_file`` / ``llm_api_key`` / ``frontend_dist`` / ``pg_cache``）：

    setup.check.<id>.name             检查项名称（label，与状态无关）
    setup.check.<id>.detail.<status>  当前值（detail）——按 status 区分文案
    setup.check.<id>.hint.<status>    修复建议（hint）——按 status 区分文案

status ∈ {ok, warn, fail, skip}（见 system.py 模块 docstring）。**同一检查项在不同
状态下的 detail/hint 文案不同**（如 ``llm_api_key`` 的 ok 是「已配置」、warn 是
「未配置或仍为占位值」；``pg_cache`` 的 skip 是「已显式关闭」），因此按状态分键。

setup.html 的推荐写法（缺失键由 default 兜底，因此动态文案——版本号、路径、
「N 份快照」、连接失败详情等——会原样回落到 system.py 产出的中文/值）：

    {{ t('setup.check.' ~ c.id ~ '.name', c.label) }}
    {{ t('setup.check.' ~ c.id ~ '.detail.' ~ c.status, c.detail) }}
    {{ t('setup.check.' ~ c.id ~ '.hint.' ~ c.status, c.hint) }}

zh 值必须与 system.py 中的字符串逐字一致（本 Agent 未改动任何 zh 文案）。

页面外壳部分（``setup.`` 前缀中除 ``setup.check.*`` 外的键）覆盖：页头、自检结果
表头与状态徽章、四步安装引导、常用命令表、环境变量表与安全说明。其中**含受信任
行内 HTML（``<code>`` / ``<a>`` / ``<span>``）的条目由模板以 ``| safe`` 渲染**，
这些 HTML 全部来自本目录的静态文案（不含任何用户/运行期数据）；``setup.check.*``
的 name/detail/hint 一律**不**用 safe——detail 可能含路径与异常文本。
"""

MESSAGES = {
    # =======================================================================
    # 页面外壳（web/templates/setup.html）
    # =======================================================================
    # ---- 页头与横幅 ----
    "setup.title": {"zh": "安装引导 · 环境自检", "en": "Setup Guide · Environment Check"},
    "setup.generatedAt": {"zh": "检测时间：", "en": "Checked at: "},
    "setup.intro": {
        "zh": "初次使用请按下方步骤完成安装，再回到这里确认全部通过",
        "en": "First time here? Follow the steps below, then come back to confirm everything passes",
    },
    "setup.recheck": {"zh": "重新检测", "en": "Re-check"},
    # 含受信任行内 HTML（状态徽章）
    "setup.bannerNeedsSetup": {
        "zh": "存在需要处理的检查项（见下表 <span class=\"badge bg-danger\">失败</span> / "
              "<span class=\"badge bg-warning text-dark\">警告</span>），按「修复建议」处理后重新检测。",
        "en": "Some checks need attention (see the <span class=\"badge bg-danger\">Failed</span> / "
              "<span class=\"badge bg-warning text-dark\">Warning</span> badges below). "
              "Follow the repair hints, then re-check.",
    },
    # 含受信任行内 HTML（<a>）
    "setup.bannerOk": {
        "zh": "环境自检全部通过，可以直接 <a href=\"/backtest\">开始回测</a>。",
        "en": "All checks passed. You can go straight to "
              "<a href=\"/backtest\">running a backtest</a>.",
    },

    # ---- 自检结果表 ----
    "setup.checkResultsTitle": {"zh": "环境自检结果", "en": "Environment Check Results"},
    "setup.col.status": {"zh": "状态", "en": "Status"},
    "setup.col.check": {"zh": "检查项", "en": "Check"},
    "setup.col.value": {"zh": "当前值", "en": "Current Value"},
    "setup.col.hint": {"zh": "说明 / 修复建议", "en": "Notes / How to Fix"},
    # 自检项状态徽章（status ∈ ok/warn/fail/skip）
    "setup.status.ok": {"zh": "正常", "en": "Passed"},
    "setup.status.warn": {"zh": "警告", "en": "Warning"},
    "setup.status.fail": {"zh": "失败", "en": "Failed"},
    "setup.status.skip": {"zh": "可选", "en": "Skipped"},

    # ---- 分步安装引导（含受信任行内 HTML：<code> / <a>）----
    "setup.stepsTitle": {"zh": "初次安装步骤", "en": "First-Time Setup Steps"},
    "setup.step1Title": {"zh": "准备环境与依赖", "en": "Prepare Environment and Dependencies"},
    "setup.step1Desc": {
        "zh": "Python 3.11+（推荐 conda 环境 <code>qdt</code>），安装依赖：",
        "en": "Python 3.11+ (the <code>qdt</code> conda environment is recommended). "
              "Install the dependencies:",
    },
    "setup.step2Title": {"zh": "配置 .env", "en": "Configure .env"},
    "setup.step2Desc": {
        "zh": "复制模板并填入 LLM API Key（舆情分析/AI 助手用）：",
        "en": "Copy the template and fill in your LLM API key "
              "(used by sentiment analysis and the AI assistant):",
    },
    # pre 代码块内的注释行
    "setup.step2CodeEdit": {
        "zh": "# 编辑 .env 填入 API_KEY=sk-...",
        "en": "# Edit .env and set API_KEY=sk-...",
    },
    "setup.step2Note": {
        "zh": "不配置 Key 时回测功能完全可用，仅舆情类功能不可用。",
        "en": "Without a key, backtesting works fully; only sentiment features are unavailable.",
    },
    "setup.step3Title": {"zh": "自检并启动", "en": "Self-Check and Start"},
    "setup.step3Desc": {
        "zh": "先自检确认无失败项，再启动服务：",
        "en": "Run the self-check first to confirm there are no failures, then start the server:",
    },
    "setup.step3Note": {
        "zh": "启动后访问 <a href=\"/\">http://127.0.0.1:8000</a>。",
        "en": "Once started, open <a href=\"/\">http://127.0.0.1:8000</a>.",
    },
    "setup.step4Title": {"zh": "可选增强", "en": "Optional Enhancements"},
    "setup.step4Item1": {
        "zh": "构建 Vue3 SPA：<code>cd frontend && npm install && npm run build</code>",
        "en": "Build the Vue3 SPA: <code>cd frontend && npm install && npm run build</code>",
    },
    "setup.step4Item2": {
        "zh": "本地缓存层：<code>docker compose up -d</code>（PostgreSQL + Redis）",
        "en": "Local cache layer: <code>docker compose up -d</code> (PostgreSQL + Redis)",
    },
    "setup.step4Item3": {
        "zh": "Tushare 数据主源：.env 中设置 <code>TUSHARE_TOKEN</code>",
        "en": "Tushare as the primary data source: set <code>TUSHARE_TOKEN</code> in .env",
    },

    # ---- 常用命令说明（说明列全部含受信任行内 HTML，统一 | safe 渲染）----
    "setup.commandsTitle": {"zh": "常用命令说明", "en": "Common Commands"},
    "setup.col.command": {"zh": "命令", "en": "Command"},
    "setup.col.desc": {"zh": "说明", "en": "Description"},
    "setup.cmd.webApp": {
        "zh": "启动 Web 服务（默认 <code>127.0.0.1:8000</code>，仅本机访问）",
        "en": "Start the web server (defaults to <code>127.0.0.1:8000</code>, local access only)",
    },
    "setup.cmd.checkEnv": {
        "zh": "安装自检（Python / .env / Key / 前端构建 / 缓存层），存在失败项时退出码为 1",
        "en": "Environment self-check (Python / .env / keys / frontend build / cache layer); "
              "exits with code 1 if any check fails",
    },
    "setup.cmd.host": {
        "zh": "监听所有网卡（局域网可访问）。<span class=\"text-danger\">注意暴露风险</span>，"
              "也可用环境变量 <code>QDT_WEB_HOST</code> / <code>QDT_WEB_PORT</code> 持久覆盖",
        "en": "Listen on all interfaces (reachable from the LAN). "
              "<span class=\"text-danger\">Exposure risk</span>: the API has no built-in "
              "authentication; you can also set <code>QDT_WEB_HOST</code> / "
              "<code>QDT_WEB_PORT</code> for a persistent override",
    },
    "setup.cmd.pytest": {
        "zh": "运行回测模块测试（其它套件：<code>test_us_data_sources</code> / "
              "<code>test_ashare_data_sources</code> / <code>test_trendradar_notify</code>）",
        "en": "Run the backtest module tests (other suites: <code>test_us_data_sources</code> / "
              "<code>test_ashare_data_sources</code> / <code>test_trendradar_notify</code>)",
    },
    "setup.cmd.build": {
        "zh": "构建 Vue3 SPA 到 <code>frontend/dist/</code>（构建后 <code>/spa/*</code> 可用；"
              "类型错误会中断构建）",
        "en": "Build the Vue3 SPA into <code>frontend/dist/</code> (afterwards <code>/spa/*</code> "
              "is available; type errors fail the build)",
    },
    "setup.cmd.dev": {
        "zh": "SPA 开发服务器（<code>http://localhost:5173/spa/</code>，"
              "自动代理 <code>/api</code> 到后端）",
        "en": "SPA dev server (<code>http://localhost:5173/spa/</code>, "
              "proxies <code>/api</code> to the backend)",
    },
    "setup.cmd.docker": {
        "zh": "启动本地数据缓存层（PostgreSQL 16 + Redis 7，端口仅绑定 127.0.0.1）",
        "en": "Start the local data cache layer (PostgreSQL 16 + Redis 7, "
              "ports bound to 127.0.0.1 only)",
    },
    "setup.cmd.healthcheck": {
        "zh": "检查数据缓存层连通性（也可访问 <code>/api/health</code>）",
        "en": "Check data cache layer connectivity (or visit <code>/api/health</code>)",
    },

    # ---- 关键环境变量表 ----
    "setup.envTitle": {"zh": "关键环境变量（.env）", "en": "Key Environment Variables (.env)"},
    "setup.col.variable": {"zh": "变量", "en": "Variable"},
    "setup.col.required": {"zh": "必填", "en": "Required"},
    "setup.required.recommended": {"zh": "推荐", "en": "Recommended"},
    "setup.required.optional": {"zh": "可选", "en": "Optional"},
    "setup.env.apiKeyDesc": {
        "zh": "舆情分析的 OpenAI 兼容 LLM 配置",
        "en": "OpenAI-compatible LLM configuration for sentiment analysis",
    },
    "setup.env.agentKeyDesc": {
        "zh": "AI 投资助手独立配置，留空回退上方 API_KEY / LLM_BASE_URL",
        "en": "Separate configuration for the AI investment assistant; leave it empty to fall back "
              "to API_KEY / LLM_BASE_URL above",
    },
    "setup.env.tushareDesc": {
        "zh": "Tushare Pro token，配置后成为 A 股数据主源（免费源自动兜底）",
        "en": "Tushare Pro token; once set it becomes the primary A-share data source "
              "(the free sources remain as an automatic fallback)",
    },
    "setup.env.dbDesc": {
        "zh": "docker compose 启动的本地缓存层连接参数",
        "en": "Connection settings for the local cache layer started by docker compose",
    },
    "setup.env.redisPasswordDesc": {
        "zh": "设置后 Redis 启用 requirepass，应用自动携带密码",
        "en": "When set, Redis enables requirepass and the app sends the password automatically",
    },
    "setup.env.cacheToggleDesc": {
        "zh": "设为 <code>false</code> 关闭对应缓存层（自动降级到 CSV + 网络数据源）",
        "en": "Set to <code>false</code> to disable that cache layer "
              "(the app degrades to CSV plus network data sources)",
    },
    "setup.env.webHostDesc": {
        "zh": "覆盖服务监听地址/端口（等价于 <code>--host</code> / <code>--port</code>）",
        "en": "Override the server host/port (equivalent to <code>--host</code> / <code>--port</code>)",
    },
    "setup.envFooter": {
        "zh": "完整清单见 <code>.env.example</code>；<code>.env</code> 已被 .gitignore 忽略，"
              "请勿提交真实密钥。",
        "en": "See <code>.env.example</code> for the full list. <code>.env</code> is gitignored, "
              "so never commit real keys.",
    },

    # ---- 安全说明（四条均含受信任行内 HTML）----
    "setup.securityTitle": {"zh": "安全说明", "en": "Security Notes"},
    "setup.security.bullet1": {
        "zh": "服务默认只监听 <code>127.0.0.1</code>（仅本机访问）。需要局域网访问时用 "
              "<code>--host 0.0.0.0</code> 显式开启，并自行确保网络可信——本项目接口"
              "<strong>没有内置鉴权</strong>。",
        "en": "The server listens on <code>127.0.0.1</code> by default (local access only). "
              "If you need LAN access, enable it explicitly with <code>--host 0.0.0.0</code> and "
              "make sure the network is trusted: this project's API has "
              "<strong>no built-in authentication</strong>.",
    },
    "setup.security.bullet2": {
        "zh": "所有 API Key 只保存在本地 <code>.env</code>（已 gitignore），"
              "不会出现在前端页面或接口响应中。",
        "en": "All API keys are stored only in the local <code>.env</code> (gitignored) and never "
              "appear in pages or API responses.",
    },
    "setup.security.bullet3": {
        "zh": "docker compose 的 PostgreSQL / Redis 端口仅绑定 <code>127.0.0.1</code>，"
              "不会暴露到局域网；Redis 可通过 <code>REDIS_PASSWORD</code> 启用密码。",
        "en": "The docker compose PostgreSQL / Redis ports bind to <code>127.0.0.1</code> only and "
              "are not exposed to the LAN; Redis can require a password via "
              "<code>REDIS_PASSWORD</code>.",
    },
    "setup.security.bullet4": {
        "zh": "全站响应带 <code>X-Content-Type-Options</code> / <code>X-Frame-Options</code> / "
              "<code>Referrer-Policy</code> 安全头；接口 500 错误不回显内部异常细节。",
        "en": "All responses carry the <code>X-Content-Type-Options</code> / "
              "<code>X-Frame-Options</code> / <code>Referrer-Policy</code> security headers; "
              "API 500 errors never echo internal exception details.",
    },

    # =======================================================================
    # 环境自检项（src/services/system.py）
    # =======================================================================
    # ---- Python 版本 ----
    "setup.check.python.name": {"zh": "Python 版本", "en": "Python version"},
    "setup.check.python.hint.ok": {
        "zh": "需要 Python 3.11+（推荐 conda 环境 qdt）",
        "en": "Python 3.11+ is required (the qdt conda environment is recommended)",
    },
    "setup.check.python.hint.fail": {
        "zh": "需要 Python 3.11+（推荐 conda 环境 qdt）",
        "en": "Python 3.11+ is required (the qdt conda environment is recommended)",
    },

    # ---- .env 配置文件 ----
    "setup.check.env_file.name": {"zh": ".env 配置文件", "en": ".env configuration file"},
    "setup.check.env_file.detail.fail": {"zh": "未找到 .env", "en": ".env not found"},
    "setup.check.env_file.hint.fail": {
        "zh": "复制模板：copy .env.example .env（Linux/Mac: cp .env.example .env），再填入 API_KEY 等真实值",
        "en": "Copy the template: copy .env.example .env (Linux/macOS: cp .env.example .env), "
              "then fill in real values such as API_KEY",
    },

    # ---- LLM API Key ----
    "setup.check.llm_api_key.name": {
        "zh": "LLM API Key（舆情分析）", "en": "LLM API Key (sentiment analysis)",
    },
    "setup.check.llm_api_key.detail.ok": {"zh": "已配置", "en": "Configured"},
    "setup.check.llm_api_key.detail.warn": {
        "zh": "未配置或仍为占位值", "en": "Not configured, or still a placeholder value",
    },
    "setup.check.llm_api_key.hint.warn": {
        "zh": "在 .env 中设置 API_KEY / LLM_BASE_URL / LLM_MODEL（OpenAI 兼容接口）；"
              "不配置则舆情分析不可用，回测功能不受影响",
        "en": "Set API_KEY / LLM_BASE_URL / LLM_MODEL in .env (OpenAI-compatible endpoint). "
              "Without it sentiment analysis is unavailable; backtesting is unaffected",
    },

    # ---- AI 助手 Key ----
    "setup.check.agent_api_key.name": {"zh": "AI 助手 Key", "en": "AI Assistant Key"},
    "setup.check.agent_api_key.detail.ok": {
        "zh": "AGENT_API_KEY 或回退 API_KEY 已配置",
        "en": "AGENT_API_KEY, or the API_KEY fallback, is configured",
    },
    "setup.check.agent_api_key.detail.warn": {"zh": "未配置", "en": "Not configured"},
    "setup.check.agent_api_key.hint.warn": {
        "zh": "AI 投资助手需要 AGENT_API_KEY（留空则回退 API_KEY）",
        "en": "The AI investment assistant needs AGENT_API_KEY (it falls back to API_KEY when empty)",
    },

    # ---- Tushare Pro Token ----
    "setup.check.tushare_token.name": {"zh": "Tushare Pro Token", "en": "Tushare Pro Token"},
    "setup.check.tushare_token.detail.ok": {
        "zh": "已配置（A 股数据主源）", "en": "Configured (primary A-share data source)",
    },
    "setup.check.tushare_token.detail.skip": {
        "zh": "可选，未配置", "en": "Optional, not configured",
    },
    "setup.check.tushare_token.hint.skip": {
        "zh": "注册 tushare.pro 获取 token 后在 .env 中设置 TUSHARE_TOKEN，"
              "A 股数据链升级为 Tushare → akshare → baostock；不配置则免费源完全可用",
        "en": "Register at tushare.pro, get a token, and set TUSHARE_TOKEN in .env to upgrade the "
              "A-share data chain to Tushare → akshare → baostock. The free sources work fine without it",
    },

    # ---- Vue3 SPA 构建产物 ----
    "setup.check.frontend_dist.name": {
        "zh": "Vue3 SPA 构建产物", "en": "Vue3 SPA build output",
    },
    "setup.check.frontend_dist.detail.warn": {
        "zh": "frontend/dist 未构建", "en": "frontend/dist has not been built",
    },
    "setup.check.frontend_dist.hint.warn": {
        "zh": "在 frontend/ 目录执行 npm install && npm run build；"
              "不构建则 /spa/* 返回 503，Jinja2 前端（/）不受影响",
        "en": "Run npm install && npm run build in frontend/. Without a build, /spa/* returns 503 "
              "while the Jinja2 frontend (/) keeps working",
    },

    # ---- 历史情绪快照 ----
    "setup.check.sentiment_snapshots.name": {
        "zh": "历史情绪快照", "en": "Historical sentiment snapshots",
    },
    "setup.check.sentiment_snapshots.detail.warn": {
        "zh": "nes_data/sentiment_results/ 为空", "en": "nes_data/sentiment_results/ is empty",
    },
    "setup.check.sentiment_snapshots.hint.warn": {
        "zh": "运行一次舆情分析可生成快照；没有快照时情绪过滤策略退化为普通均线策略",
        "en": "Run a sentiment analysis once to generate a snapshot. Without snapshots, "
              "sentiment-filtered strategies degrade to plain moving-average strategies",
    },

    # ---- 运行目录可写 ----
    "setup.check.dirs_writable.name": {
        "zh": "运行目录可写", "en": "Runtime directories writable",
    },
    "setup.check.dirs_writable.detail.ok": {
        "zh": "logs/、output/ 均可写", "en": "logs/ and output/ are both writable",
    },
    "setup.check.dirs_writable.hint.fail": {
        "zh": "检查目录权限：logs/ 与 output/ 必须可写（图表与日志输出）",
        "en": "Check directory permissions: logs/ and output/ must be writable "
              "(chart and log output)",
    },

    # ---- PostgreSQL 缓存 ----
    "setup.check.pg_cache.name": {"zh": "PostgreSQL 缓存", "en": "PostgreSQL cache"},
    "setup.check.pg_cache.detail.ok": {"zh": "已连接", "en": "Connected"},
    "setup.check.pg_cache.detail.warn": {"zh": "未连接", "en": "Not connected"},
    "setup.check.pg_cache.detail.skip": {
        "zh": "未启用（QDT_DB_CACHE_ENABLED=false）", "en": "Disabled (QDT_DB_CACHE_ENABLED=false)",
    },
    "setup.check.pg_cache.hint.warn": {
        "zh": "可选：docker compose up -d 启动后自动接入；未启动时自动降级到 CSV + 网络数据源",
        "en": "Optional: it attaches automatically after docker compose up -d; without it the app "
              "degrades to CSV plus network data sources",
    },
    "setup.check.pg_cache.hint.skip": {"zh": "已显式关闭", "en": "Explicitly disabled"},

    # ---- Redis 热缓存 ----
    "setup.check.redis_cache.name": {"zh": "Redis 热缓存", "en": "Redis hot cache"},
    "setup.check.redis_cache.detail.ok": {"zh": "已连接", "en": "Connected"},
    "setup.check.redis_cache.detail.warn": {"zh": "未连接", "en": "Not connected"},
    "setup.check.redis_cache.detail.skip": {
        "zh": "未启用（QDT_REDIS_CACHE_ENABLED=false）",
        "en": "Disabled (QDT_REDIS_CACHE_ENABLED=false)",
    },
    "setup.check.redis_cache.hint.warn": {
        "zh": "可选：docker compose up -d 启动后自动接入；未启动时自动降级",
        "en": "Optional: it attaches automatically after docker compose up -d; "
              "without it the app degrades gracefully",
    },
    "setup.check.redis_cache.hint.skip": {"zh": "已显式关闭", "en": "Explicitly disabled"},
}
