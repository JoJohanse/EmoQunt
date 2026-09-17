# EmoQunt 平台化改造方案（对标 PandaAI QUBE）— v2

> 状态：**计划稿，未执行**。v2 已合入 Oracle 审核意见（2026-09-17）：修正线程超时不可行点、消除 strategies.json 双真相、明确 SDK 仓位契约与情绪接口、i18n 前置到各期、砍掉公式 DSL 与会话表、分期重排让"AI 生成策略"提前落地。目标：把 EmoQunt 从"参数化回测工具"升级为带策略库、因子库、运行历史、参数调优、AI 生成策略的个人量化研究平台。

## 1. 对标项目调研结论（PandaAI QUBE，浏览器实测）

页面 `pandaaiquant.com/agent_quant`，左侧导航：对话工作台（+会话列表/置顶）、策略库、因子库、运行历史、调优任务、技能库、Qube 行情；顶栏：通知/算力/设置/个人中心。

### 1.1 策略库（`/strategies`）
- 卡片网格：名称、市场标签（股票/期货）、描述、最近回测摘要（总收益·夏普·笔数）、最后更新时间；按市场筛选 + 搜索（名称/代码/公式/备注）+ 排序。
- 新建按市场二分 → 落地详情页。**详情页**四个 Tab：参数设置 / 历史版本 / 回测历史 / 调优历史。
  - 参数设置：日期区间、初始资金、保证金倍率、滑点、手续费倍率、频率；保存/运行回测。
  - 策略代码：Monaco 风格 Python 编辑器 + 实时校验徽章（"校验通过"）。
- **策略代码模型**（实测 001 策略全文）：`panda_backtest.api`（`MarketOrderStyle, buy_open, sell_close`）交易 API；`panda_data`（`get_factor`、`get_future_dominant`、`get_prev_trade_date`）数据 API；`STRATEGY_PARAMS` 参数字典（带中文注释，调优对象）；生命周期 `initialize(context)` / `before_trading(context)` / `handle_data(context, data)`；`context.run_info`/`context.trade_date`/持仓查询。
- **版本机制**：回测历史可"保存为版本"；运行记录提示"该运行历史未生成版本"。

### 1.2 因子库
- "集中管理公式与 Python 因子，并运行完整因子分析"——公式与 Python 两种形态；新建=名称+描述 → 详情页编辑与分析；对话工具提及"按 IC_IR 排名"。

### 1.3 对话工作台（核心）
- 启动卡片六类：期货/股票策略（"AI 生成后自动回测"）、期货/A股因子、数据查询、Quant Skill、常用工具。
- 输入区：模型选择、思考等级、操作权限（自动）、"策略转写"。
- **会话绑定策略上下文**：会话页顶部显示当前策略，点开即策略详情弹窗。
- **实测 AI 调优全流程**：读 STRATEGY_PARAMS → 生成≤63 组候选 → 服务端校验 → 建调优任务（含基准 64 组、目标总收益、不自动应用）→ 最优候选+基准对比+解读+下一步；消息带动作轨迹（"进行了 能力加载、工具调用、思考 等 N 个动作"）。
- 回测结果卡片：10 项指标（含基准收益/索提诺/卡玛，带说明）+ 净值曲线 + 分标的持仓收益表 + 交易时间线（分页）+ 策略日志 + 阶段进度（"8 个阶段 · 用时 28 秒"）；操作：重新运行 / AI 优化 / 保存为版本 / 导出 PDF。

### 1.4 运行历史：按对象（策略/因子）×市场筛选；列：区间、可切换指标、状态、净值缩略、更新时间。
### 1.5 调优任务：策略列表（优化次数）；并发进度（"63/63 已进入终态"）、各组合净值对比（归一化起点=1）、参数组合表（#/参数/指标/**应用此参数**）、基准行标注。
### 1.6 技能库：25+ QuantSkill 目录（风险雷达、可交易性审计、事件因子……），对话斜杠引用。本期非目标。

## 2. EmoQunt 现状盘点（经 Oracle 抽查核实）

### 已有
| 能力 | 现状 | 位置 |
|---|---|---|
| 回测引擎 | backtrader 单标的，A股(hfq)/美股(qfq)，滑点固定 0.0005，双成本模型 | `src/backtest/backtest_manager.py` |
| 指标体系 | 10 项指标（中文键 API 契约）+ 时序 + trades（≤500） | 同上 `_format_metrics_json` |
| 因子分析引擎 | FactorAnalyzer：IC/RankIC/ICIR/分层/单调性 | `src/analysis/factor_analyzer.py` |
| 因子分析服务 | 4 个硬编码因子 × HS300 横截面（universe 硬编码 `get_hs300_stocks()`） | `src/services/factor.py:163` |
| 策略系统 | 仅 1 个模板 `sentiment_ma`；用户策略=JSON 参数集；CRUD+TTL 缓存 | `src/Strategy/`、`src/services/strategies.py` |
| 策略对比 | `/api/strategies/compare`（≤5） | `src/services/backtest.py` |
| Agent | LangGraph ReAct + SSE，7 个只读工具，双语提示词，**按语言缓存** | `src/agent/` |
| 数据层 | 日线多源回退链 + A股分钟线 + HS300 + 情绪快照 + PG/Redis 行情缓存 | `src/data/` |
| 前端 | 7 视图 SPA、K 线组件、回测历史 localStorage（≤20 条） | `frontend/src/` |

### 关键事实（决定改造面）
- 策略解析 seam 集中在 `_run_backtest_core` 598–622 行（`get_user_strategy` → 情绪序列 → `create_user_strategy_class`）；情绪构建与策略类型正交；`_TradeRecorder`/analyzer 与策略类无关——**代码策略天然兼容指标管线**。
- **无 sizer 配置**：模板策略 `self.buy()` 不带 size（默认 `FixedSize(stake=1)`）；`StrategyBase` 的 `min_order_size/max_portfolio_percent` 等风控参数是**死旋钮**（从未参与下单）。
- **`run_backtest_json` 硬编码 `apply_sentiment_filter=False`**（909 行）：SPA/API/agent 路径从不带情绪过滤；情绪仅经闭包注入模板策略。
- Agent prompt 为静态字符串、编译产物按语言缓存（`agent.py:62-84`）——策略上下文不能字面"改系统提示词"。
- 测试：30 个 test 文件（含 `test_strategy.py`、`test_factor_analysis.py`、`test_agent_tools.py`），多于 AGENTS.md 列举的 4 个。

### 缺口
1. 策略=参数集，无代码；2. 无策略库实体（无版本/市场/搜索）；3. 无因子库；4. 无服务端运行历史；5. 无参数调优；6. Agent 只读、无策略上下文绑定；7. 无任务执行器与阶段进度。

## 3. 关键架构决策（v2 修订版）

### D1 策略代码化：双轨制
- **模板策略继续以 `strategies.json` 为唯一真相**：现有 CRUD（`services/strategies.py`）+ TTL 缓存 + 双前端**全部不动**；不迁移、不复制进 SQLite（消除双真相漂移）。SQLite 只存新实体。
- **新增代码策略**（存 SQLite）：Python 源码 + EmoQunt 薄 SDK：
  - `from emoquant.api import buy, sell, close_all, get_position, order_target_percent`——**仓位契约显式化**：`order_target_percent(pct)` 按总资产目标仓位计算股数（A 股向下取整到 100 股），`buy/sell` 带显式 `size` 参数。模板策略 stake=1 的口径差异在文档中写明（信号可比、PnL 口径不同）。
  - `import emoquant.data as eq_data`：`get_price`、`get_factor`（对接因子库）、`get_prev_trade_date`、**`get_sentiment(code, as_of)`**——走 `src/data/sentiment_snapshots.py` 唯一解析器，只暴露当日及之前快照（防未来函数），保住"情绪驱动"立身能力。
  - 生命周期：`initialize(context)` / `handle_data(context, data)`；`STRATEGY_PARAMS` 字典（中文注释）为**初始默认参数**，DB 参数列可覆盖。
- **加载器** `src/Strategy/code_loader.py`：`exec` 编译 → 必备函数校验 → 动态生成 `bt.Strategy` 子类（桥接 `__init__/next/notify_order`）。回测核心在 598–622 行 seam 处按 `strategy_kind`（template|code）分支，情绪序列构建照旧复用。
- **安全边界（定位"防呆不防恶"，文档如实声明）**：`ast` 白名单校验（禁危险 import/`open/eval/exec/__import__`，SDK 白名单导入；**禁 dunder 链与 `getattr`**——防 `().__class__` 绕过）；保存时试编译；超时采用**"放弃等待 + 标记 failed + 线程泄漏"**的务实策略（Python 线程不可强杀；真隔离走 `multiprocessing` 为远期选项，注意 Windows spawn）。风险说明：LLM 生成代码 + 外部内容提示注入是比恶意用户更现实的输入面。

### D2 持久化：SQLite 只存新实体（零新依赖）
- `src/store/db.py`（标准库 `sqlite3`，WAL），库文件路径经 `src/utils/paths.py` 新增 helper（如 `get_data_dir()/emoqunt.db`），入 `.gitignore`。
- 表：`strategies`（仅 code 类：id/名称/市场/描述/源码/**参数列（真相，覆盖源码 STRATEGY_PARAMS 默认值）**/标签/时间戳）、`strategy_versions`（更新即快照+备注+回滚）、`factors`（Python 因子）、`factor_versions`、`backtest_runs`（`strategy_name + strategy_kind` 弱引用、参数、指标 JSON、equity 时序 zlib+base64（drawdown/daily_returns 可派生）、trades、状态、阶段耗时）、`tuning_tasks`+`tuning_runs`。**`chat_sessions`/`chat_messages` 不建**（SPA localStorage 已有）。
- **每线程独立连接** + `busy_timeout`；执行器内串行落库。
- **重启恢复**：启动时把遗留 `running` 任务批量标记 `failed`（进程内执行器无持久队列）。
- 新环境变量 `QDT_TASK_WORKERS`/`QDT_BACKTEST_TIMEOUT` 同步 `.env.example`；文档写明备份建议（DB 是代码策略唯一真相，丢库=丢策略）。
- **name vs id 边界**：v2 路由用 id（code 策略）；旧 `/api/backtest/run` 只认 template name——两条链路并行不混用。

### D3 异步任务执行器 + 阶段进度
- `src/services/task_runner.py`：`ThreadPoolExecutor(max_workers=QDT_TASK_WORKERS, default 2)` + 状态机（queued/running/succeeded/failed/cancelled）。
- **阶段化以可选 `progress_cb` 参数穿透现有 `_run_backtest_core`**（不复制流水线）：校验→取数→策略加载→回测→指标→持久化，耗时记入 `backtest_runs.stages`；旧同步 `run_backtest_json` 行为不变（`test/test_backtest.py` 特征测试护航）。
- 前端 SSE（复用 agent SSE 模式）或轮询 `GET /api/runs/{id}` 展示进度。

### D4 参数调优
- `POST /api/tuning/tasks`：策略 id + 参数网格（笛卡尔积上限 64 组含基准）+ 目标指标 + 回测参数；执行器并发跑（=工作线程数），逐组落库。
- 结果：组合表（参数/指标，基准行标注）+ 归一化净值对比（每组**降采样**存储）。
- `apply`：**只 UPDATE DB 参数列，永不改源码**（源码 STRATEGY_PARAMS 仅初始默认）——消灭 ast 重写丢注释与"改源码后漂移"两个问题域。模板策略的 apply 走既有 `update_strategy` 写 strategies.json。

### D5 因子库：P3 只做 Python 因子（公式 DSL 推迟）
- factor 实体（见 D2）；**Python 因子**：`def compute(df: DataFrame) -> pd.Series` 签名（单标的 OHLCV 中文列契约），同 D1 校验器。
- 分析直接喂现有 `FactorAnalyzer`。**市场字段本期限定 zh_a**（universe 硬编码 HS300，us 显式报错文案）。
- 范围：因子本期只做研究（横截面 IC/分层），不接入单标的回测引擎。Formula DSL 推迟（AI 写 Python 比自造 DSL 可靠；DSL 是解析器+窗口语义+错误文案+双语一整个子系统，单用户收益极低）。

### D6 Agent 从只读升级为"能建策略"
- 新增工具（全部走服务层）：`get_strategy`、`create_strategy`（创建前走 D1 校验）、`update_strategy`（自动存版本）、`run_backtest`（增强：支持 code 策略；**短回测保持工具内同步**——同步工具在 ToolNode executor 线程跑不阻塞事件循环）、`list_backtest_runs`/`get_run`、`create_tuning_task`/`get_tuning_status`、`list_factors`/`create_factor`/`analyze_factor`。分钟级调优走"提交 → 卡片 → `get_tuning_status` 稍后查询"，提示词引导。
- **策略上下文注入**：不改静态系统提示词（会击穿语言缓存）——每请求追加一条 context 消息（`strategy_id` → 服务端生成策略摘要消息），或改用 `create_react_agent` 的 callable prompt。
- **提示词**（双语）追加：SDK 完整参考 + `sentiment_ma` 等价代码策略 few-shot + 生成规范（STRATEGY_PARAMS 中文注释、防未来函数、仓位用 `order_target_percent`、风控默认值）。
- 前端卡片（复用 ChatToolCard Generative-UI）：策略代码卡片（CodeMirror 只读+跳转）、回测结果卡片、调优结果卡片。SSE 协议不变。
- 操作权限：本期全自动，预留工具分级字段。

### D7 前端（SPA；**Jinja2 端只读消费、编辑仅 SPA**）
- 新路由：`/strategy-library`（卡片网格）、`/strategy-library/:id`（参数/代码/版本/回测历史/调优历史 Tabs）、`/factor-library`+详情（把现 FactorAnalysisView 的 IC/分层图迁来复用）、`/runs`、`/tuning/:taskId`。旧 `/backtest`、`/strategies` 保留兼容。
- **代码编辑器：CodeMirror 6**（`@codemirror/lang-python`，懒加载 chunk）；保存前 `POST /api/strategies/{id}/validate` 显示校验状态。
- 回测历史落服务端，BacktestView 加历史侧栏；localStorage 降级为表单记忆。
- **仓库规则**：新文案每期随做随入 `locales/` 双语词表（AGENTS.md 硬规则，不攒到末期）；策略列表 v2 缓存复用 `src/utils/ttl_cache.py`（谁写谁失效，禁止手动 clear）；图表配色走 `lib/marketColors.ts`；数据重 HTTP handler 不阻塞事件循环（新增路由遵守 web_app.py 现有模式）。

## 4. 分期实施（v2 重排：AI 生成策略价值前移）

| 期 | 内容 | 验收标准 |
|---|---|---|
| **P0 地基（压缩）** | 只建 `strategies(code)`/`backtest_runs` 两表 + store 层 + task_runner（含重启清扫）+ 阶段化 progress_cb | 旧接口特征测试全绿；一次回测落库完整 runs 与阶段耗时 |
| **P1 代码策略+AI 最小闭环** | SDK（含 `get_sentiment`/`order_target_percent`）+ code_loader + ast 校验；策略 CRUD v2+版本；策略库/详情页（CodeMirror）；**立即加 `create_strategy`/`update_strategy`/`run_backtest(code)` 三个 agent 写工具** | 对话"建一个双均线策略并回测"全链路走通；内置示例策略可编辑→校验→回测→出指标；**验收口径：与模板策略信号一致，指标差异可归因于仓位口径**；测试：ast 校验器（含绕过样例）/loader/建表幂等/agent 写工具走服务层 |
| **P2 运行历史+调优** | /runs 页；调优任务 API+页（网格、并发、净值对比、apply 只写 DB） | 63 组调优可创建/查看/应用；/runs 可筛选；重启后遗留 running 被标 failed |
| **P3 因子库** | 因子实体+CRUD+Python 执行器（zh_a 限定）；因子详情分析页复用 FactorAnalyzer | 新建动量 Python 因子→IC/分层出图；恶意代码被校验拦截 |
| **P4 Agent 完整版** | 策略上下文注入（context 消息方案）、调优工具链、三类卡片、提示词 SDK 参考+few-shot | 对话完成"读参数→生成候选→建调优→报告最优"流程；卡片渲染正确 |
| **P5 打磨** | i18n 审计（各期已随做随入）、README/AGENTS.md 更新、截图 | 双语无硬编码中文；文档与实现一致 |

## 5. 风险与应对（v2 修订）

| 风险 | 应对 |
|---|---|
| `exec` 用户代码 | ast 白名单**含 dunder/getattr 封堵**+试编译+"放弃等待"超时；定位"防呆不防恶"文档声明；容器沙箱远期 |
| backtrader 并发资源（64 组调优） | 并发=2~4 可配；走 CSV/PG 缓存链；单组"放弃等待"超时；重启清扫 |
| 回测取数慢 | 强制走既有缓存链；P2 起可预热 |
| 破坏既有契约 | 旧路由/中文指标键/响应形状不动；新能力 `/api/v2/*`；模板策略 truths 不迁移 |
| SQLite 并发 | WAL+每线程连接+busy_timeout+执行器串行落库；单用户量级足够 |
| 双键（name/id）混用 | v2=id、旧链路=template name，方案与代码注释双重写明 |
| 仓位口径混淆 | SDK 显式仓位契约 + 文档写明与模板 stake=1 的差异 |
| i18n 债务 | 每期随做随入词表，P5 只做审计 |

## 6. 明确非目标
期货/期权与保证金模型；多标的组合回测（横截面因子暂不进回测）；实盘对接、计费、多用户；行情终端；技能库（QuantSkill 目录）；Formula DSL（推迟）；服务端会话存储。

## 7. 依赖
后端零新重依赖（sqlite3 标准库）；前端新增 CodeMirror 6 三件套（懒加载）。不动 torch 等 requirements 重依赖。

## 附：v1→v2 变更记录（Oracle 审核合入）
1. 线程硬超时改为"放弃等待+标 failed"（Python 线程不可强杀）；multiprocessing 列远期。
2. 砍掉 strategies.json 迁移——模板策略继续以 JSON 为唯一真相，SQLite 只存新实体。
3. SDK 仓位契约显式化（`order_target_percent`），点破现有风控参数为死旋钮、模板 stake=1 口径；P1 验收改为"信号一致+差异可归因"。
4. Agent 策略上下文改为每请求 context 消息（防击穿语言缓存）；短回测同步、调优异步+轮询工具。
5. SDK 增加 `get_sentiment`（唯一解析器+防未来函数），点破 `apply_sentiment_filter=False` 现状。
6. i18n 从 P5 前置到每期。
7. 调优 apply 改为 DB 参数列为真相、不改源码。
8. 补 SQLite 工程细节（每线程连接/重启清扫/paths helper/.gitignore/.env.example/备份）。
9. 阶段化以 progress_cb 穿透而非复制流水线。
10. 分期重排：P1 即接入最小 agent 写工具，AI 生成策略第二期可演示。
11. 因子市场字段限定 zh_a；公式 DSL 推迟；会话表砍掉；版本管理降级为快照+回滚。
12. 补测试策略（ast 绕过样例/状态机/建表幂等/apply 写回/agent 工具）与 name-id 边界、compare 是否落 runs（定：**compare 不落 runs**，保持无状态）。
