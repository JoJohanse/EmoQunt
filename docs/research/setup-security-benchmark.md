# 首次安装引导 / 命令说明 / 安全性提升 — 开源项目调研

> 调研日期：2026-08-14。目标：1) 增加初次安装引导（first-run setup wizard / 安装检查）与命令说明；2) 安全性提升；3) 更新 README。
> 调研范围：本地部署的量化/投研平台（Freqtrade、OpenBB、Ghostfolio、QUANTAXIS、vnpy）、智能家居本地部署（Home Assistant）、工具链环境自检命令（flutter doctor、npm doctor、Django check、Home Assistant check_config）、Web 安全权威来源（OWASP、MDN、Redis 官方文档、Docker 官方文档、12-factor）。
> 说明：所有论断均核对官方文档/官方 GitHub 仓库；本文档为「现状调研 → 共性模式 → EmoQunt 落地方案」基准，不替代 PRD。

## 一、调研对象

| 项目 | 类型 | 与 EmoQunt 的相似点 | 值得借鉴 |
|---|---|---|---|
| [Freqtrade](https://github.com/freqtrade/freqtrade) | Python 量化交易平台 | Python 后端 + Web UI，本地部署 | `new-config` 交互式配置向导（只问关键问题）；quickstart 的安装→配置→验证结构；`list-*` 环境诊断命令 |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Python 投研平台 | 数据源聚合 + FastAPI 服务（`openbb-api` 即 uvicorn 起 127.0.0.1:6900） | pip 安装后即用的极简 quickstart；`obb` CLI / `openbb` CLI 分层 |
| [Ghostfolio](https://github.com/ghostfolio/ghostfolio) | Web 投资追踪（自托管） | Docker Compose（PostgreSQL + Redis）+ Web 全栈，前端与后端同仓库 | `.env.example → .env` 起步；首个注册用户自动成为 ADMIN；容器启动自动跑迁移 |
| [QUANTAXIS](https://github.com/yutiansut/QUANTAXIS) | Python A 股量化框架 | A 股数据 + 回测 | 安装后的「版本 + 能力」验证脚本（`QA.__version__` + `has_qars_support()`） |
| [vnpy / VeighNa](https://github.com/vnpy/vnpy) | Python 量化框架 | 国内量化、本地部署 | 平台化安装脚本（install.bat/sh）；安装后需注册外部模拟账号（SimNow）→ 属于「安装后引导」 |
| [Home Assistant](https://www.home-assistant.io/) | 本地部署智能家居 | 纯本地 Web 服务 | 浏览器端 5 步 onboarding 向导（建账号→位置→分享设置）；`hass --script check_config` 配置自检 |
| Flutter / npm / Django | 工具链 | 无 | `flutter doctor`（✓/✗ 分项输出 + 修复建议）、`npm doctor`、`manage.py check --deploy` 环境自检先例 |
| OWASP / MDN / Redis / Docker / 12-factor | 安全权威来源 | 无 | CSRF、安全响应头、错误脱敏、端口绑定、Redis 认证、配置外置的一手依据 |

## 二、板块 A：初次安装引导与命令说明

### A1. 交互式配置向导与首次运行体验

**共性模式**

- **Freqtrade `new-config`**：`freqtrade new-config` 是官方推荐的配置向导，文档定位为「Creates a new configuration file, asking some questions which are important selections for a configuration」，且明确「Only vital questions are asked」——只问：是否 dry-run、Stake currency、Stake amount、max_open_trades、Timeframe、Display currency、Exchange、是否启用 Telegram，生成的文件写入 `-c/--config` 指定路径（默认 `userdir/config.json`）。[freqtrade utils 文档](https://www.freqtrade.io/en/stable/utils/#new-config)
- **Freqtrade quickstart**：官方安装指南结构为 **Requirements → Installation（脚本安装 setup.sh/setup.ps1、手动 venv、Conda 三种方式）→ "You are ready" → Troubleshooting**。安装完成的验证不是跑版本号，而是两条初始化命令：`freqtrade create-userdir --userdir user_data` 与 `freqtrade new-config --config user_data/config.json` —— 即「装完立刻生成用户目录 + 配置」。[freqtrade installation](https://www.freqtrade.io/en/stable/installation/)
- **OpenBB**：quickstart 极简——`pip install openbb` 后直接给一段可跑代码（`obb.equity.price.historical("AAPL")`）；完整安装 `pip install "openbb[all]"` 后用 `openbb-api` 一条命令起 FastAPI 服务（uvicorn，`127.0.0.1:6900`），再引导用户到 OpenBB Workspace 里「Connect backend」填入 URL 并测试连通。[OpenBB README](https://github.com/OpenBB-finance/OpenBB)
- **Ghostfolio**：安装 = `docker compose up -d` + 打开 `http://localhost:3333` + 「Create a new user via Get Started」——文档明确 **第一个注册用户自动获得 ADMIN 角色**；不预置演示数据；数据库迁移由容器启动时自动执行。[Ghostfolio README](https://github.com/ghostfolio/ghostfolio)
- **Home Assistant**：浏览器端 5 步 onboarding——① 打开安装地址（看到 "Preparing Home Assistant"）② 创建账号（owner/admin，丢失不可找回）③ 输入家庭位置（推导时区/单位）④ 数据分享设置 ⑤ 完成进入主界面。是「本地部署 Web 服务 + 浏览器向导」的完整范例。[HA onboarding](https://www.home-assistant.io/getting-started/onboarding/)
- **vnpy**：安装脚本（Windows `install.bat` / Ubuntu `install.sh`）之外，安装后还需要**外部前置引导**：注册 SimNow CTP 模拟账号 → 拿 broker code 和行情/交易地址 → 登录 VeighNa Station 启动 VeighNa Trader。[vnpy README](https://github.com/vnpy/vnpy)

**EmoQunt 落地**
- 新增 `python web_app.py --doctor`（或 `python web_app.py --setup`）子命令 + 首页/SPA 首次启动检测横幅，双保险。
- 参考 freqtrade：向导**只问关键问题**。EmoQunt 的「配置」实质是环境（`.env`），引导项应限于：复制 `.env.example → .env`、`TUSHARE_TOKEN` 可选、数据源连通性测试（akshare/yfinance 一条链路探测）、启动验证（访问 `http://127.0.0.1:8000/`）。
- 参考 Home Assistant：首次启动检测到「无 `.env` 或关键依赖缺失」时，在 Jinja2 首页顶部渲染一个安装检查卡片（分项 ✓/✗ + 修复指引），SPA 端 `/spa/` 同源提示；不阻塞正常使用。
- README 验证节：`python web_app.py` 后给出「打开 http://127.0.0.1:8000/ 应看到回测表单」的验收描述（对标 freqtrade 的 "You are ready"）。

### A2. 环境自检命令（doctor 形态）

**共性模式**
- freqtrade **没有** doctor 命令（用户提到的 `list-timescales` 实际名为 `list-timeframes`）；其环境诊断靠一组 `list-*` 子命令：`list-strategies` / `list-hyperoptloss` / `list-freqaimodels` 官方定位为发现「environment problems with loading」对应模块，另有 `test-pairlist` 校验选股逻辑。[freqtrade utils 文档](https://www.freqtrade.io/en/stable/utils/)
- 真正的 `doctor` 形态来自工具链：**flutter doctor**——「Show information about the installed tooling」，按检查项分行输出 ✓（正常）/ !（警告）/ ✗（问题），每项附修复建议，末尾提示 `flutter doctor --verbose` 查看更多细节，是「分项 ✓/✗ + 修复建议」的范式。[flutter CLI 参考](https://docs.flutter.dev/reference/flutter-cli)
- **npm doctor**：命令定位「Check the health of your npm environment」，分项检查 registry 连通性、npm/node 版本、git 是否在 PATH、缓存/全局目录读写权限、包校验和，「if there are any recommended changes, it will display them」。[npm doctor](https://docs.npmjs.com/cli/v10/commands/npm-doctor)
- **Django check**：基于 system check framework，「inspect the entire Django project for common problems」，支持 `--deploy`（激活仅生产环境相关的额外检查）与 `--fail-level`（设定失败退出级别）。[Django admin 参考](https://docs.djangoproject.com/en/5.0/ref/django-admin/#check)
- **Home Assistant check_config**：`hass --script check_config` 定位「Script to perform a check of the current configuration」，用于「Test any changes to your configuration.yaml file before launching」，支持 `--json` 与 `--fail-on-warnings`（有警告即非零退出）。[HA check_config](https://www.home-assistant.io/docs/tools/check_config/)

**共性输出形态总结**：① 每条检查一行，用 ✓ / ! / ✗ 前缀表示 正常/警告/问题；② 问题项附带**修复建议**（命令或配置示例）；③ 支持 `--verbose` 展开细节；④ 可选 `--fail-on-warnings` 让 CI 可用；⑤ 退出码非零表示「不满足运行条件」。

**EmoQunt 落地**
- 新增 `python web_app.py --doctor`，输出按上述五条形态实现，检查项（分项 ✓/✗ + 修复建议）：
  1. Python 版本 ≥ 3.11（当前实现用 sys.version_info 判定）；
  2. 依赖完整性（import 探测核心模块：fastapi、uvicorn、backtrader、akshare、yfinance、tushare[可选]）；
  3. `.env` 存在性 + 必填键（`API_KEY`/`LLM_MODEL`/`LLM_BASE_URL`），缺失时提示「复制 .env.example 并填写」；
  4. 网络/数据源连通性（探测 akshare 一个轻量接口或数据缓存目录可写性，**不做重请求**）；
  5. 目录可写（logs/、stock_data/、output/，用 paths.py 的 helper 取路径）；
  6. 前端产物存在性（frontend/dist/ 是否存在——缺失时 `/spa/*` 会 503，提示 `npm run build`）；
  7. 与 `check_config` 对齐：支持 `--json` 输出。
- 引导命令说明：`--doctor` 的完整输出与各检查项写入 README「故障排查」节（对标 freqtrade 的 Troubleshooting 节）。

### A3. README「快速开始」结构共性

**共性模式**
- 五个环节高度一致：**环境要求 → 安装 → 配置 → 启动 → 验证**。
  - freqtrade：Requirements → Installation（三选一）→ Configuration（new-config）→ "You are ready"（验证=初始化命令）→ Troubleshooting。
  - Ghostfolio：前置要求（Docker 知识/已装 Docker）→ clone + 复制 `.env.example` 并填写 → compose up → 打开浏览器创建账号（验证）。
  - OpenBB：`pip install openbb` → 一段可跑代码 → 起服务 → 连接 Workspace（验证=Test successful）。
  - vnpy：安装脚本 → 注册外部账号（SimNow）→ 启动 Station/Trader（验证=界面出现）。
- 配置环节普遍用 **`.env.example → .env` + 环境变量注入**（Ghostfolio 明确写「Copy the file .env.example to .env and populate it with your data」）。
- 专门的**命令参考文档页**是标配：freqtrade 有 Commands/utils 文档页、OpenBB 有 docs.openbb.co（platform/cli 分开）、Flutter CLI 参考、npm CLI 文档、Django admin 参考、HA tools 页。

**EmoQunt 落地**
- README 快速开始重排为「环境要求（Python 3.11+、conda env `qdt`）→ 安装（pip install -r requirements.txt、前端 npm install + build）→ 配置（cp .env.example .env）→ 启动（python web_app.py）→ 验证（打开首页 + 可选 --doctor）」五节，与现有 AGENTS.md 内容保持一致。
- 新增「命令参考」小节或文档链接：`--doctor`、`--setup`、现有入口 `python web_app.py`，对齐 freqtrade/OpenBB 的 commands 文档惯例。

## 三、板块 B：面向本地部署 Web 服务的安全实践

### B1. uvicorn 监听地址与反向代理

**一手依据**
- uvicorn 的 `--host` **默认就是 `127.0.0.1`**（`--port` 默认 8000）——官方默认只绑 loopback。[uvicorn settings 文档](https://www.uvicorn.org/settings/)
- 显式绑 `0.0.0.0` 意味着所有网卡可达（含局域网）；Docker Compose 文档明确：ports 的 `host_ip`「If it is not set, it binds to all network interfaces (`0.0.0.0`)」。[Docker Compose 05-services ports](https://docs.docker.com/compose/compose-file/05-services/)
- uvicorn 官方建议对外服务走反向代理：「Using Nginx as a proxy in front of your Uvicorn processes ... is recommended for additional resilience」，推荐 UNIX domain socket；信任代理头时警告「Only trust clients you can actually trust!」。[uvicorn deployment 文档](https://www.uvicorn.org/deployment/)

**EmoQunt 落地**
- `web_app.py` 维持默认 `127.0.0.1:8000`（当前已是），README 明确写出「仅本机访问；如需局域网/公网访问请置于 Nginx/Caddy 反代之后，不要直接绑 0.0.0.0」。
- 检查项：`--doctor` 若检测到通过 `--host 0.0.0.0` 启动（env 或启动参数），打印警告与反代建议。

### B2. Docker Compose 端口绑定与 Redis 认证

**一手依据**
- Compose ports 长语法支持 `host_ip`，即 `127.0.0.1:5432:5432` 短写法的等价形式；不写 host_ip 时**默认绑到 0.0.0.0（所有网卡）**——本机依赖服务（PostgreSQL/Redis）就会暴露给局域网。
- Redis 官方安全文档：Redis「is designed to be accessed by trusted clients inside trusted environments」，直连互联网不是好主意；应 `bind 127.0.0.1` 只允许 loopback；并明确后果：「a single `FLUSHALL` command can be used by an external attacker to delete the whole data set」。Redis 3.2 起引入 **protected mode**（默认配置绑所有接口且无密码时，仅回 loopback 请求）作为兜底；认证层用 `requirepass`（配合 AUTH 命令）「provide a layer of redundancy」。[Redis security 文档](https://redis.io/docs/latest/operate/oss_and_stack/management/security/)
- 未授权访问的历史风险：官方文档还记录了配置可控导致的**写盘逃逸**问题（CONFIG 命令可改工作目录与 dump 文件名 → 写任意路径 RDB 文件，可能被利用执行任意代码，antirez 本人 2015 年发文承认），是无密码 Redis 公网暴露演变成挖矿/勒索蠕虫（如 RedisWannaMine 等）的技术根因。[antirez blog](http://antirez.com/news/96)

**EmoQunt 落地**
- docker-compose 中 PostgreSQL/Redis 端口统一改为 `127.0.0.1:5432:5432` / `127.0.0.1:6379:6379` 形式（或长语法 `host_ip: 127.0.0.1`），并在 compose 注释与 README 说明理由：服务仅供本机应用消费，不暴露局域网。
- 若 Redis 需持久化对外暴露（如未来 SPA 直连），设置 `requirepass` 并从 env 注入（compose `command: redis-server --requirepass ${REDIS_PASSWORD}` 或 config 挂载），密码放 `.env`，绝不硬编码。
- `--doctor` 增加一项：检测到 Redis 可连接但无密码时给出警告（`requirepass` 建议）。

### B3. 安全响应头中间件

**一手依据**
- **X-Content-Type-Options: nosniff**：告诉浏览器尊重声明的 `Content-Type` 不做 MIME 嗅探；对 script/style 响应类型不匹配直接 block，防止「上传的 text/plain 内容被当 HTML 执行」的 XSS 变体；安全测试工具普遍要求该头存在。[MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options)
- **X-Frame-Options: DENY / SAMEORIGIN**：防点击劫持（clickjacking）与跨站泄漏；不设置时其他站点可 iframe 嵌入本页；注意仅 HTTP 响应头生效（`<meta>` 内无效），更完整的替代是 CSP `frame-ancestors`。[MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options)
- **Referrer-Policy**：控制 `Referer` 携带多少信息；`unsafe-url` 会「leak potentially-private information from HTTPS resource URLs to insecure origins」（URL 中的 token/session 参数会外泄）；浏览器默认值即 `strict-origin-when-cross-origin`（跨域只带 origin，HTTPS→HTTP 不发）。[MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy)
- **Permissions-Policy**：按 allowlist 允许/禁用文档与 iframe 的浏览器能力（camera、microphone、geolocation、payment…），如 `microphone=(), geolocation=()` 全部禁用。[MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy)
- **CSP 与内联脚本的冲突**：OWASP CSP cheat sheet 明确「CSP by default disables any JavaScript code placed inline in the HTML source」，内联事件处理器（`onclick="..."`）同样被禁，需改 `addEventListener`；`'unsafe-inline'` 会放行内联脚本但也大幅削弱 CSP。因此对带内联脚本/样式的页面，官方建议先用 **`Content-Security-Policy-Report-Only` 观察模式**——「often used as a precursor to utilizing CSP in blocking mode」。[OWASP CSP cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)

**EmoQunt 落地**
- FastAPI 加一个 `SecurityHeadersMiddleware`（Starlette `BaseHTTPMiddleware` 或 `@app.middleware`），对全部响应追加：`X-Content-Type-Options: nosniff`、`X-Frame-Options: SAMEORIGIN`、`Referrer-Policy: strict-origin-when-cross-origin`、`Permissions-Policy: camera=(), microphone=(), geolocation=()`。
- CSP：**先 report-only 观察再收紧**——原因是本项目两套前端都存在内联脚本：Jinja2 模板（backtest_form.html 的内联脚本、base.html 的少量内联）、SPA 构建产物（Vite 产物默认外链，但 Element Plus 图标/样式与潜在的 style 注入可能触发违规）。落地为：默认 `Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'self'`，观察 `report-to`/日志一段时间后再决定是否收紧或保持宽松（记录到文档，不盲目阻断 Bootstrap/Font Awesome/Vue 的正常渲染）。

### B4. API 错误信息脱敏

**一手依据**
- OWASP Improper Error Handling：「detailed internal error messages such as stack traces, database dumps, and error codes are displayed to the user (hacker). These details reveal implementation details that should never be revealed.」应返回「a specifically designed result that is helpful to the user without revealing unnecessary internal details」，同时策略要区分「what information is going to be reported back to the user, and what information is going to be logged」。[OWASP Improper Error Handling](https://owasp.org/www-community/Improper_Error_Handling)
- 对 Python/FastAPI 而言，`str(exception)` 常含绝对路径（`E:\coding\EmoQunt\src\...`）、依赖版本、SQL 片段等内部信息，属于「implementation details that should never be revealed」；500 响应应返回泛化信息（如请求 ID），完整 traceback 只进日志。

**EmoQunt 落地**
- 新增全局异常处理器：`Exception` → 500 响应体只含通用文案（中文提示 + 请求 ID，日志中记录完整 traceback 与该 ID 关联）。
- 排查现有 handler 中所有把 `str(e)`/`repr(e)` 塞进响应的位置（kline/sentiment/recommend/analyze 等数据型 handler），统一改为：日志记录细节、响应返回可操作的提示（如「数据源不可用，请稍后重试」）。
- `--doctor` 或测试中用「触发一次 500 断言响应体不含 `E:\`、`traceback`、`site-packages` 字样」做回归验证。

### B5. GET 请求产生副作用与 CSRF

**一手依据**
- OWASP CSRF Prevention Cheat Sheet 直接规定：「Do not use GET requests for state changing operations」「Safe HTTP methods should not be used for state-changing requests」「All state changes require POST, PUT, PATCH, or DELETE」；并特别警示：「If any state-changing operation in the application is reachable via a GET request, SameSite=Lax will not stop it」——即浏览器在跨站顶级导航等场景仍会带 Cookie 发 GET，依赖 SameSite 兜底是不够的。[OWASP CSRF cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)

**EmoQunt 落地**
- 审计并整改「GET 触发副作用」的端点：刷新数据缓存类接口（如 GET `/refresh_cache` 之类）改 POST；查询类保持 GET 但确保纯读。
- 本项目暂未引入 Cookie 会话（无登录态，API 无 Cookie），CSRF 面有限；但写入类操作（策略增删改、回测运行）统一走 POST + JSON body，作为长期约定写入文档与 code review 清单。

### B6. .env 与密钥管理惯例

**一手依据**
- 12-factor Config 原则：config 是「everything that is likely to vary between deploys」，要求「strict separation of config from code」；判断标准是「whether the codebase could be made open source at any moment, without compromising any credentials」。配置文件的弊端是「it's easy to mistakenly check in a config file to the repo」；而环境变量「there is little chance of them being checked into the code repo accidentally」。[12-factor config](https://12factor.net/config)
- 社区通例：`.env`（真实密钥）进 `.gitignore`；`.env.example`（占位符/空值 + 注释说明每项含义）提交进仓库——Ghostfolio README 的安装第一步即「Copy the file .env.example to .env and populate it with your data」。

**EmoQunt 落地**
- 保持现有 `.env`（gitignored）+ `.env.example`（已入库，确认不含真实密钥）双文件模式；README 配置节明确「所有密钥只放 `.env`，经 `QDT_` 前缀环境变量覆盖 config.yaml」。
- `--doctor` 检查 `.env` 中 `API_KEY` 等是否仍为示例占位值（与 `.env.example` 比对），命中则警告「尚未配置，AI 相关功能不可用」。
- 提交前检查约定写入 CONTRIBUTING/README：新密钥只加 `.env.example` 占位，不落真实值。

## 四、决策记录

- **引导形态**：采用「CLI 自检命令（`--doctor`）+ 首页检测横幅」双通道，不引入独立安装向导页面——与 EmoQunt 现有轻量单体架构匹配，且 Home Assistant 证明「浏览器内分项引导」对本地 Web 服务有效。
- **doctor 输出**：严格对齐 flutter/npm doctor 形态（✓/! /✗ 分项 + 修复建议 + `--verbose`/`--json` 选项），检查项清单见 A2。
- **CSP 先 report-only**：两套前端均含内联脚本（Jinja2 模板内联 JS、SPA 构建产物），直接上 blocking 模式会破坏 Bootstrap/Font Awesome/Vue 渲染，按 OWASP 建议先观察再收紧。
- **不引入 CSRF Token 体系**：当前无 Cookie 会话、写操作均为 POST JSON，CSRF 面小；以「GET 禁副作用 + 写操作 POST」约定为主，避免为不存在会话的架构增加复杂度。
- **.env 双文件模式**维持现状并文档化，新增 doctor 的占位值检测。

## 五、参考链接

- Freqtrade utils（new-config / list-* 命令）: https://www.freqtrade.io/en/stable/utils/
- Freqtrade 安装指南: https://www.freqtrade.io/en/stable/installation/
- OpenBB 仓库 README: https://github.com/OpenBB-finance/OpenBB · CLI: https://github.com/OpenBB-finance/OpenBB/blob/develop/cli/README.md · 文档: https://docs.openbb.co/
- Ghostfolio 仓库 README: https://github.com/ghostfolio/ghostfolio · 官网: https://ghostfol.io/
- QUANTAXIS 仓库 README: https://github.com/yutiansut/QUANTAXIS
- vnpy 仓库 README: https://github.com/vnpy/vnpy
- Home Assistant onboarding: https://www.home-assistant.io/getting-started/onboarding/ · check_config: https://www.home-assistant.io/docs/tools/check_config/
- flutter CLI（doctor）: https://docs.flutter.dev/reference/flutter-cli
- npm doctor: https://docs.npmjs.com/cli/v10/commands/npm-doctor
- Django check: https://docs.djangoproject.com/en/5.0/ref/django-admin/#check
- uvicorn settings（host 默认值）: https://www.uvicorn.org/settings/ · deployment（反代）: https://www.uvicorn.org/deployment/
- Docker Compose ports（host_ip）: https://docs.docker.com/compose/compose-file/05-services/
- Redis 安全文档: https://redis.io/docs/latest/operate/oss_and_stack/management/security/ · 写盘逃逸问题: http://antirez.com/news/96
- OWASP CSP cheat sheet: https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html
- OWASP CSRF cheat sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- OWASP Improper Error Handling: https://owasp.org/www-community/Improper_Error_Handling
- MDN X-Content-Type-Options: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options
- MDN X-Frame-Options: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options
- MDN Referrer-Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy
- MDN Permissions-Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy
- 12-factor config: https://12factor.net/config
