# 首页导航 / 内容 / 图表交互 / 微交互 / AI 融合 — 第四轮相似开源项目调研

> 调研日期：2026-08-29（第四轮）。目标：延续 1) 优化首页导航与 UI 交互（重点）2) 丰富首页内容与功能。
> 前三轮（`homepage-ui-benchmark.md` 2026-08-14、`-v2.md` 2026-08-19、`-v3.md` 2026-08-22）已覆盖 FreqUI/OpenBB/Ghostfolio/QUANTAXIS/Qbot/vnpy/Lean/NautilusTrader/vectorbt、Vue 管理模板、命令面板/Tabs+侧边栏收藏/暗色模式/情绪日历/首页布局持久化、KLineChart 选型、leek-fund/go-stock/InStock/quant-desktop/StockGoose/chengzuopeng-stock-dashboard/Finviz 热力图、Tremor/shadcn、骨架屏、PG+Redis、Docker；K 线图库选型另见 `kline-chart-benchmark.md`（2026-08-27），其周期/复权/副图/最后价虚线等建议已落地。**本轮换新角度**：Lightweight Charts v5 的交互细节对齐（不重复选型论证）、微型可视化与微交互（uPlot/数字滚动）、投资组合仪表盘内容模型（Wealthfolio）、资讯聚合流（NewsNow）、AI 助手与仪表盘融合（ai-hedge-fund 核实后不适用 + Chat SDK Generative UI）、跨域仪表盘导航范式（Netdata/Uptime Kuma）、首访引导（driver.js）、数据密集列表（TanStack Table）。

## 一、调研对象（本轮新增）

| 维度 | 项目 / 来源 | 与 EmoQunt 的相似点 | 值得借鉴 |
|---|---|---|---|
| 图表交互范式 | [TradingView Lightweight Charts v5.2](https://tradingview.github.io/lightweight-charts/docs)（tradingview/lightweight-charts，约 17.1k star，2026-08-21 仍在推送，2026-08 查证；Apache-2.0 但要求保留 TradingView 署名+链接） | 交互细节标杆，用于对齐现有 ECharts K 线（不换库，选型已在 kline-chart-benchmark 收口） | ① crosshair 默认 **Magnet 吸附模式**（吸附最近数据点，另有 `doNotSnapToHiddenSeriesIndices`）；② **PriceLine 价格线**（`price/color/lineStyle/axisLabelVisible/title/axisLabelColor`——每条线可带标题与轴上标签，天然适合成本线/止盈止损线）；③ 时间轴 `tickMarkFormatter` 自定义刻度、`fixLeftEdge/fixRightEdge` 防越界滚动、`rightBarStaysOnScroll`；④ v5 新增 **enableConflation 数据抽稀**（<0.5px 自动合并多点，`conflationThresholdFactor` 官方注明适用 sparkline）；⑤ v4→v5 中 markers（B/S 箭头）与 watermark 均拆为按需 plugin。核实发现：**其 API 无 "favorites toolbar"**（那是 Advanced Charts 交易终端能力），社区另有 68 件画线工具插件包 |
| 图表交互范式 | [trading-vue-js](https://github.com/tvjsx/trading-vue-js)（tvjsx，约 2.3k star，2026-08 查证） | Vue 原生金融图表（备选核实项） | **核实结论：不可用**。README 标题明确 `[Not Maintained]`（"was a hackable charting lib"），最后推送 2024-06；Vue3 适配停留在 [issue #227](https://github.com/tvjsx/trading-vue-js/issues/227)（"did not work"），npm 的 VUE3 版标注 "future release" 未发布。仅借鉴其概念：**一个 overlay = 一个 .vue 组件**的声明式扩展、DataStructure 的 onchart/offchart（主图叠加/副图）分层 |
| 微型可视化 | [uPlot](https://github.com/leeoniya/uPlot)（leeoniya，约 10.5k star，MIT，2026-08 查证） | 自选股行内 sparkline / 回测历史迷你净值 | ~50KB min（README 标题声明），基准：16.6 万点冷启动 25ms；官方对比表 mousemove 10s 事件处理 218 vs ECharts 1943、内存 21MB vs 17MB；特性：多系列 toggle、**多图 cursor sync**、High/Low bands；Non-features 明确：无动画、无堆叠、无内置拖动平移（走 zoom-wheel/zoom-touch 插件）；README 列有 Vue 封装（Sergey Kalinichev） |
| 微交互 | [@vueuse/core `useTransition`](https://vueuse.org/core/useTransition/)（数字滚动）、MDN/`requestAnimationFrame` | 涨跌数字滚动、涨跌闪烁刷新反馈 | `useTransition`：数值过渡（duration/easing/`TransitionPresets` 25 种缓动/delay/onFinished），官方标注 export size 1.02KB（tree-shaking 后按需 ~2KB）。但项目未依赖 vueuse——为单函数引整包不划算，**自研 ~40 行 rAF tween composable** 等价；涨跌闪烁用 CSS animation 类切换（`up-flash/down-flash` + setTimeout 移除），零依赖 |
| 投资组合面板 | [Wealthfolio](https://github.com/wealthfolio/wealthfolio)（约 8.8k star，AGPL-3.0，2026-08-28 仍在推送，2026-08 查证；Tauri+Rust+SQLite / React+Radix+shadcn+Recharts+React Query；v3.6 起从投资追踪扩展为个人财务：净值/支出/目标/FIRE 模拟） | 本地优先、隐私优先的个人投资仪表盘（与 Ghostfolio 同类，找增量） | `src/pages` 一手结构：dashboard/（accounts-summary、balance、overview、goals-chart）；**holdings/ 持仓表 + 7 维配置图**（account-allocation/资产类别/composition/国家/货币/行业 6 张环图 + 现金挂件）；income/ 收益历史曲线；activity/ 交易活动表 + 分步 CSV 导入向导；**onboarding/ 三步首用向导**（step1-3）。对 EmoQunt 的增量为"配置环图组 + 活动流 + 分步向导" |
| 资讯聚合流 | [NewsNow](https://github.com/ourongxing/newsnow)（ourongxing，约 21.5k star，MIT，2026-08 查证；Unjs/Nuxt 系，PWA） | 中文财经快讯源聚合的 IA 与刷新策略范本 | README 特性：**30 分钟默认缓存**（登录用户可强制刷新）、**自适应抓取间隔（最少 2 分钟）防 IP ban**、GitHub OAuth 同步、MCP server；`server/sources` 一手含 **cls 财联社 / wallstreetcn 华尔街见闻 / jin10 金十 / gelonghui 格隆汇 / fastbull / mktnews / xueqiu 雪球** 等中文源（另有 weibo/zhihu 等 50+）；前端 hooks：`useRefetch/useRelativeTime/useSync/useDark`，`components/column/{card,index,dnd}` 卡片列+拖拽。**注意**：README 声明新版本封闭开发中、不再接受贡献；其源多为平台爬虫接口，**不宜直接复用其抓取代码**（合规/稳定性），只借鉴 IA 与节奏 |
| AI × 仪表盘 | [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)（约 51k star，MIT，2026-08 查证） | 多 agent 投资助手（备选核实项） | **核实结论：web UI 已从 main 移除**。README 仍描述 Web Application（截图 2025-06，多投资者 agent 决策看板），但当前 main 为纯 Python 包 `hedge_fund/`（signals/backtesting/brokers/**Textual TUI**），项目正按 VISION.md 重构为"可回测的 alpha 模型"。仅借鉴产品概念：多 agent（价值/成长/情绪/技术 + Risk Manager + Portfolio Manager）并行给出信号与置信度；UI 借鉴改由 Chat SDK 承担 |
| AI × 仪表盘 | [vercel/chatbot（Chat SDK）](https://github.com/vercel/chatbot)（约 20.9k star，2026-08 查证；License 标记 NOASSERTION，使用前需核对许可文本）+ [AI SDK Generative UI 文档](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces) | 流式聊天 + 结构化数据卡片（EmoQunt 已有 SSE agent 聊天侧栏） | **Generative UI 模式**（官方文档一手）：消息为 `UIMessage.parts` 结构化分片（`text` / `tool-${toolName}`，状态机 `input-available → output-available / output-error`），**tool 结果映射为 UI 组件卡片**——官方示例就是 `stockTool` 股价卡片（还有 weather 卡片）；官方 Getting Started 含 Vue.js (Nuxt) 适配。此模式可平移到自研 SSE 协议 |
| 跨域导航范式 | [Netdata](https://github.com/netdata/netdata)（约 80.3k star，GPL-3.0，2026-08 查证；**UI 为闭源免费 NCUL1 许可——只能借鉴模式，不能搬实现**） | 数据密集仪表盘的"概览→下钻"导航 | Getting Started 一手：每个 dashboard 分区开头自动放 **Overview charts 汇总图**；**Nodes Tab 统一视图**再进单节点下钻；Expanded Chart View 的 drill-down 用 **metric weights 推荐相关指标**（官方博客）；FAQ 明示对新手"start small：目录+搜索"。→ EmoQunt 首页即概览层，每张卡片补"下钻到功能页并预选标的"入口 |
| 跨域导航范式 | [Uptime Kuma](https://github.com/louislam/uptime-kuma)（约 90.7k star，MIT，2026-08-29 当天仍在推送，2026-08 查证；**Vue3+Vite+WebSocket SPA**——README Motivation 一手声明） | 同为 Vue3 单页应用的自托管监控 | 卡片化监控列表 + **心跳条（beat bar）**：每个监控项一行 0/1 心跳格子，一屏看出历史健康；**空状态引导添加第一个 monitor**；首次进入 setup 向导。心跳条可迁移为"数据源健康"或回测历史的迷你结果条 |
| 首访引导 | [driver.js](https://driverjs.com/)（kamranahmedse，官网标注 26.3k+ star、月下载 4.3M，2026-08 查证） | SPA 首页首访引导/新功能发现 | 官网一手：~5KB、零依赖 vanilla JS、MIT 且无需署名；三种模式 **Tours（多步导览）/ Highlights（单点高亮）/ Hints（非阻塞提示点）**；遮罩颜色可配、防误关、退出确认、进度与 hooks；官方声明适配 Vue。对比 [shepherd.js](https://shepherdjs.dev/)：依赖 Floating UI 定位、**AGPL-3.0 商用需购买许可**——driver.js 完胜 |
| 数据密集列表 | [TanStack Table v8 `@tanstack/vue-table`](https://tanstack.com/table/latest/docs/framework/vue/vue-table)（TanStack/table 约 28.4k star，MIT，2026-08 查证） | 自选股/排行榜表格化（备选核实项） | Vue 适配器一手：`useVueTable` + `FlexRender`；功能覆盖排序/列固定/列显隐/过滤/分组/行选择/**虚拟滚动**（官方 Vue 示例齐全）。**核实结论：当前收益有限**——EmoQunt 自选股 ≤30 只，无虚拟滚动需求，排序/固定列 el-table 原生即可；仅当排行榜要做数千行虚拟列表时再评估 |
| 刷新策略 | [MDN `Cache-Control: stale-while-revalidate`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control)（RFC 5861） | 行情轮询"保留上帧数据"的权威语义 | MDN 一手：后台 revalidate 期间**继续复用旧响应**，"effectively hiding the latency penalty of revalidation"——即先展示旧数据、后台取新、到货后静默替换。配合自研 `usePolling`（间隔+指数退避+`visibilitychange` 暂停），不引 TanStack Query |

## 二、共性模式 → EmoQunt 落地方案

### 1. 首页导航与 UI 交互（重点）

**现状**：侧边栏分组折叠+收藏+面包屑、暗色模式、顶部 Tabs、全局命令面板（Cmd+K）均已落地；首页 8 个可拖拽卡片（快捷入口/指数速览/市场宽度/行情看板=K 线主图+右栏自选股+最近回测/行业热力图/热门板块/当日舆情/个股推荐，顺序持久化）+ 情绪日历就绪；K 线主图已支持周期/复权切换、MA/BOLL 叠加、MACD/KDJ/RSI 副图、最后价虚线、千分位、dataZoom 手势（`HomeView.vue` 约 1650 行，骨架屏已覆盖各卡片）；本地持久化 store：ui/watchlist/backtestHistory/chat/favorites/homeLayout/tabs。另有一处代码盘点的交互缺口：**指数速览卡片不可点击**（`INDEX_PRESETS` 带 `kind=index` 却未接入 `activeKey`，自选股行则已可点击切换主图）。

**本轮提炼的增量（按性价比排序）**
1. **K 线买卖点价格线/标记**（对标 Lightweight Charts PriceLine + SeriesMarkers，同时是 kline-chart-benchmark 的 P0-5 遗留）：后端 `run_backtest_json` 透传 `trades`，前端在 K 线上以 `markPoint`（B/S，箭头朝向按买卖）+ 成本价 `markLine`（带标签，对标 PriceLineOptions 的 `title`/`axisLabelVisible`）呈现——回测研究与 K 线主图首次打通。ECharts 完全等价可做，无需换库。
2. **十字光标 magnet 吸附**：Lightweight Charts 的默认体验是 crosshair 吸附到最近 K 线数据点；ECharts `axisPointer` 天然按类目轴吸附，补齐的是**吸附时的浮层定位**：tooltip 固定在图顶部（TradingView 式数值面板，kline-benchmark P0-2 遗留）而非跟随鼠标，消除遮挡。
3. **时间轴刻度本地化 + 边界固定**：对标 `tickMarkFormatter` 与 `fixLeftEdge/fixRightEdge`——K 线 X 轴按"月初/季初"加权刻度（中文日期），dataZoom 禁止拖出数据边界（`minValueSpan` 已有，补左右边界锁定）。
4. **首访导览 driver.js**：首次进入 `/spa` 首页时对四卡片+指数速览做一次 5 步导览（Tours 模式），完成标记存 `ui` store（`emoqunt:` 键，复用 persist.ts）；后续迭代发新功能（如热力图/情绪日历）时对老用户单点 Hints。dynamic import 懒加载，5KB 不进主 chunk。空状态联动：自选股/最近回测 `el-empty` 增加"去添加/去回测"动作按钮（Uptime Kuma 空态模式）。
5. **卡片下钻入口**（Netdata 模式）：热力图/情绪日历/最近回测/自选股卡片标题行加"查看详情 →"，跳转对应路由并预选标的（板块→因子分析、回测→结果页、个股→主图）。首页定位为"概览层"，与 Netdata"Overview charts + 下钻"同构。第一落点可顺手补上现状缺口：让指数速览卡片可点击，将主图切到对应指数（复用现有 `kind=index` 数据链）。
6. **数字滚动 + 涨跌闪烁微交互**：自研 `useCountUp` composable（rAF tween ~40 行，参照 `useTransition` 语义，不引 vueuse 整包）用于指数速览/自选股价最新值滚动；自选股刷新到新价时按涨跌方向触发一次 CSS 闪烁类（`up-flash`/`down-flash`），与 v3 的 Delta 徽章体系叠加。

### 2. 首页内容与功能

1. **聊天工具结果卡片化（Generative UI 落地，本轮差异化最高项）**：现状 `ChatPanel.vue` 的工具调用只渲染"参数/结果" `<pre>` 纯文本。借鉴 AI SDK 的 parts 状态机：SSE 事件流插入结构化 data 事件（`{type:'tool_result', tool, state, payload}`），前端按 tool 名映射组件——`kline` → 内嵌 mini ECharts K 线卡（复用 `useECharts`）+ "在首页打开"按钮；`sentiment` → 情绪分数卡 + 情绪日历跳转；`recommend` → 推荐列表卡。流式中 `input-available` 先渲染"查询中"骨架，`output-available` 替换为卡片，`output-error` 显示错误（与 MDN SWR 同思想：先保留占位/旧态，后台到达后静默替换）。
2. **资产配置环图组**（Wealthfolio holdings 增量）：自选股按 行业/市场/情绪得分 三维环形图切换，数据直接复用热力图已拉的板块聚合接口（`/api/market/sectors`），零新增后端成本；Wealthfolio 的"持仓表+多维环图"布局可缩为一张卡片（环图 + 右侧图例 TopN）。
3. **快讯/资讯流卡片**（NewsNow IA）：来源分组 tab（财联社电报/情绪快报两源起步）+ 列表卡片（标题 + 相对时间 + 来源徽标），刷新走"30 分钟后端缓存 + 自适应间隔（失败指数退避）"，handler 用 plain def + threadpool（AGENTS.md 事件循环规则）。**数据源走自有情绪快照/akshare 资讯接口或极简 RSS，不自建爬虫**；与 trendradar 不重叠（trendradar=主动通知链路，资讯流=首页被动展示）。首版可用现有 `sentiment.news_list`（情绪页已有舆情列表，HomeView 已渲染）升格为独立卡片+分组。
4. **数据源健康心跳条**（Uptime Kuma 模式）：一行小卡片，Tushare/akshare/baostock/新浪 各一列 7 格心跳（绿=近 7 次取数成功，红=失败），数据来自后端现有数据链的取数结果计数（可先由 `/api/health` 扩展）；帮助用户理解"为何某股无数据"，也是排查 akshare 抖动的可视化入口。
5. **自选股行内 sparkline**（v3 建议的选型补全）：≤10 只自选直接用 ECharts 微实例或**纯 SVG 折线（~1KB，零依赖）**；若未来列表规模与刷新频率上量再引 uPlot（47KB，含 cursor sync）。回测历史卡片同样可加迷你净值 sparkline（数据已在 backtestHistory store）。

### 3. 决策建议（供下轮迭代取舍）

| 优先级 | 事项 | 价值 | 工作量 | 备注 |
|---|---|---|---|---|
| Must | 聊天工具结果卡片化（Generative UI 模式，SSE 结构化 data 事件） | 高 | M (3-5 天) | 改造 `chat store` + `ChatPanel.vue`；先支持 kline/sentiment 两类卡片 |
| Must | K 线买卖点价格线/标记（后端 `trades` 透传 + markPoint/markLine） | 高 | M (2-3 天) | kline-benchmark P0-5 遗留 + 本轮 PriceLine 对标 |
| Must | driver.js 首访导览 + 空态动作按钮 | 中高 | S (1-2 天) | ~5KB 懒加载；完成标记入 `ui` store |
| Should | 十字光标固定数值面板 + 时间轴刻度本地化 + 边界锁定 | 中高 | S (1-2 天) | 纯 ECharts 配置项改造 |
| Should | 首页卡片下钻入口（概览→详情） | 中高 | S (1-2 天) | router.push + query 预选 |
| Should | 自选股/回测历史 sparkline（SVG 起步，uPlot 备选） | 中 | S-M (1-2 天) | SVG 零依赖优先 |
| Should | 资产配置环图组（行业/市场/情绪三维） | 中 | S-M (1-2 天) | 复用 `/api/market/sectors` |
| Could | 数字滚动 useCountUp + 涨跌闪烁 | 中 | S (1 天) | 自研 ~40 行，不引 vueuse |
| Could | 快讯流卡片（NewsNow IA，自有数据源） | 中 | M (3-5 天) | 首版升格 `sentiment.news_list`；不建爬虫 |
| Could | usePolling（SWR 式轮询 + 退避 + 页面不可见暂停） | 中低 | S (1 天) | 统一自选股/指数速览刷新路径 |
| Could | 数据源健康心跳条 | 中低 | S-M (1-2 天) | 依赖 `/api/health` 扩展 |
| Won't（本轮不做） | 引入 trading-vue-js | — | — | README `[Not Maintained]`（最后推送 2024-06），Vue3 适配未发布（issue #227 未解决） |
| Won't（本轮不做） | 借鉴 ai-hedge-fund web UI | — | — | web 前端已从 main 移除（现为 Python 包 + Textual TUI），仅存于历史版本 |
| Won't（本轮不做） | 引入 TanStack Table | — | — | 列表规模 ≤30 行，el-table/自定义行足够；虚拟滚动无需求，headless 表格包装成本 > 收益 |
| Won't（本轮不做） | 引入 @vueuse/core（仅为 useTransition）/ shepherd.js | — | — | 前者单函数不值得整包；后者 AGPL-3.0 商用受限且依赖 Floating UI |
| Won't（本轮不做） | 实时推送/分钟级行情/爬虫型资讯源 | 高 | L (>1 周) | 延续 v3 定位约束：日线级回测研究平台；资讯流不自建抓取，避免合规风险 |

> 工作量：S ≤2 天，M 3-5 天，L >1 周（仅估算，不含联调）。

## 三、决策记录（本轮）

- **Lightweight Charts 只做"交互对标"不做换库**：v3 与 kline-chart-benchmark 已确立"继续 ECharts 增量、KLineChart 专业页另议"；本轮核实其 v5 文档后确认 PriceLine/markers/tickMarkFormatter/conflation 均能在 ECharts 用 markLine/markPoint/axisLabel/数据抽稀等价实现，换库论据进一步减弱。另核实其 **API 无 favorites toolbar**（属 Advanced Charts），修正任务假设；Apache-2.0 的**强制署名要求**（NOTICE + tradingview.com 链接）也是不引入的加分理由。
- **trading-vue-js 判死**：README 自述 `[Not Maintained]` + 最后推送 2024-06 + Vue3 分支 issue 未解决，三重证据；仅吸收"overlay=组件、onchart/offchart 分层"的概念进 ECharts 副图组织。
- **AI 融合主线从 ai-hedge-fund 换为 Chat SDK**：核实发现 ai-hedge-fund main 分支已移除 web 前端（README 与目录结构不一致，项目重构期），如实降级为"产品概念参考"；Chat SDK 的 Generative UI parts 状态机（input-available/output-available/output-error + tool 结果映射组件）与 EmoQunt 现有 SSE 聊天 + toolCalls 折叠面板完美衔接，且官方支持 Vue 生态，是本轮"聊天内嵌图表卡片"的直接蓝本。
- **资讯流"借 IA 不借源"**：NewsNow 的 30min 缓存/自适应间隔/相对时间/来源分组值得照搬，但其数据源为平台爬虫接口且有合规与失效风险（README 亦声明进入封闭开发）；EmoQunt 用自有情绪快照与既有接口起步。
- **微交互全部零依赖自研**：useCountUp（rAF tween）、CSS 闪烁类、SVG sparkline 均为小实现；uPlot 仅在列表规模/刷新频率上量后作为备选（README 体积与性能基准已存档备查）。
- **引导选 driver.js**：MIT + ~5KB + 零依赖 + Vue 适配（官网一手），对比 shepherd.js 的 Floating UI 依赖与 AGPL-3.0 商用限制完胜；与 persist.ts 联动做"看过不再弹"，与空状态联动做发现式引导。
- **TanStack Table 与 Netdata/Uptime Kuma 的边界**：前者经核实当前收益不足列 Won't（保留结论备查）；后两者 UI 分别闭源（NCUL1）/技术栈同源，只提炼"概览→下钻、心跳条、空态引导"三个可移植模式，不碰实现代码。
- **SWR 落在自研 usePolling**：MDN/RFC 5861 语义确认"旧响应 + 后台 revalidate"即目标行为；TanStack Query 功能过剩，沿用 v1 以来的"最小自研"持久化/数据层哲学。

## 四、参考链接

- Lightweight Charts：文档 https://tradingview.github.io/lightweight-charts/docs · CrosshairOptions（Magnet 默认）https://tradingview.github.io/lightweight-charts/docs/api/interfaces/CrosshairOptions · PriceLineOptions https://tradingview.github.io/lightweight-charts/docs/api/interfaces/PriceLineOptions · TimeScaleOptions（conflation）https://tradingview.github.io/lightweight-charts/docs/api/interfaces/TimeScaleOptions · v4→v5 迁移（markers/watermark 插件化）https://tradingview.github.io/lightweight-charts/docs/migrations/from-v4-to-v5 · GitHub https://github.com/tradingview/lightweight-charts · star 佐证 https://www.star-history.com/tradingview/lightweight-charts
- trading-vue-js：https://github.com/tvjsx/trading-vue-js（README `[Not Maintained]`）· Vue3 状态 issue https://github.com/tvjsx/trading-vue-js/issues/227
- uPlot：https://github.com/leeoniya/uPlot（~50KB 声明与性能基准表）
- useTransition：https://vueuse.org/core/useTransition/
- Wealthfolio：https://github.com/wealthfolio/wealthfolio · 官网 https://wealthfolio.app/
- NewsNow：https://github.com/ourongxing/newsnow
- ai-hedge-fund：https://github.com/virattt/ai-hedge-fund（README 与 main 目录结构，app/ 已移除）
- Chat SDK / AI SDK Generative UI：https://github.com/vercel/chatbot · https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces
- Netdata：https://github.com/netdata/netdata · Getting Started（Overview charts/Nodes Tab）https://learn.netdata.cloud/docs/getting-started · Expanded Chart View 博客 https://www.netdata.cloud/blog/charts-expanded-view/
- Uptime Kuma：https://github.com/louislam/uptime-kuma（Motivation：Vue3+Vite+WebSocket SPA）
- driver.js：https://driverjs.com/ · shepherd.js：https://shepherdjs.dev/
- TanStack Table Vue：https://tanstack.com/table/latest/docs/framework/vue/vue-table
- stale-while-revalidate：MDN https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control · RFC 5861
- 本仓库现状锚点：`frontend/src/views/HomeView.vue` · `frontend/src/components/ChatPanel.vue`（toolCalls 纯文本渲染，待卡片化）· `frontend/src/components/CommandPalette.vue` · `frontend/src/stores/persist.ts`（ui/watchlist/backtestHistory/chat/favorites/homeLayout/tabs）· `frontend/src/composables/useECharts.ts` · `web_app.py`（`/api/agent/chat` SSE、`/api/backtest/run`）

## 五、落地记录（2026-08-29 当轮执行）

| MoSCoW 事项 | 状态 | 实现要点 |
|---|---|---|
| Must · 聊天工具结果卡片化 | ✅ 已落地 | SSE 新增 `tool_start` 事件（agent.py + web_app.py 透传），`stores/chat.ts` 实现 tool_start→tool 状态机并在流结束标记未回填调用为 failed；新增 `ChatToolCard.vue` + `chat/toolCards.ts`，支持 quote/sentiment/recommend/backtest/signal 五类卡片（含 pending 骨架、失败态、"在首页查看主图/去对应页"动作），未知工具回退原始折叠面板；结果截断 800→4000（仅影响前端展示副本） |
| Must · K 线买卖点价格线/标记 | ✅ 已落地 | 后端新增 `_TradeRecorder`（backtrader Analyzer，notify_order 捕获含滑点的真实成交价），`run_backtest_json` 透传 `trades`（封顶 500）；`BacktestView.vue` 新增"回测 K 线 · 买卖点标注"卡片：`markPoint` B/S 箭头（按市场约定配色）+ 买入加权成本均价 `markLine`，K 线取数复权口径与回测核心一致（A股 hfq / 美股 qfq）。实测 000001·test·2024H1 返回 6 笔成交 |
| Must · driver.js 首访导览 + 空态动作 | ✅ 已落地 | `useHomeTour.ts` 动态 import driver.js v1.8（独立 chunk ~26KB/7.5KB gzip，css 同步懒加载），7 步导览按元素存在性过滤（widget 可拖拽重排）；完成/关闭标记 `ui.tourDone` 持久化，布局工具栏"新手引导"可重放；自选/最近回测 `el-empty` 增加"输入代码添加/去运行回测"动作按钮 |
| Should · 固定数值面板 + 刻度本地化 + 边界锁定 | ✅ 已落地 | K 线 tooltip 吸顶并水平钳制（TradingView 式数值面板，消除遮挡）；时间轴按月边界加权刻度、1 月显示年份（对标 tickMarkFormatter）；边界锁定经核实由 ECharts `min/max='dataMin/dataMax'` 天然保证，无需额外配置 |
| Should · 卡片下钻入口 | ✅ 已落地 | 指数速览卡片可点击 → 主图切到对应指数（复用 `kind=index` 数据链）；个股推荐行点击 → 未跟踪则先加入自选再切主图（`ensureTracked`）；热力图/当日舆情卡片头新增"板块情绪 →/舆情分析 →"链接 |
| Should · 自选股行内 sparkline | ✅ 已落地 | 新增 `MiniSparkline.vue`（纯 SVG ~1KB 零依赖）；行情拉取从 2 根升为 30 根日线一次取齐最新价/涨跌/走势；自选行与指数速览行内展示，颜色按区间涨跌+市场约定 |
| Should · 资产配置环图组 | ✅ 已落地（缩维） | 新增"自选分布"widget（homeLayout 新增 `allocation`，旧用户 revive 自动补齐）：市场/当日涨跌/行业 三维环图切换；行业映射复用 `/api/sentiment` 板块成分股（零新增后端），无匹配归"其他"，Top8 截断 |
| Could · 数字滚动 + 涨跌闪烁 | ✅ 已落地 | `AnimNumber.vue`（自研 ~30 行 rAF tween，未引 vueuse）；价格变化按方向触发 0.9s 闪烁（`flashMap`），叠加既有 Delta 徽章 |
| Could · 快讯流卡片升格 | ✅ 已落地 | 当日舆情卡片升级：来源分组过滤（≥2 个来源时显示 radio tab）+ 来源徽标（按来源名哈希固定配色）+ 展示条数 6→10；数据仍来自情绪快照 `news_list`（零新增后端）。与原计划的差异：news `date` 仅有 `YYYY-MM-DD` 粒度（无时刻），故不做"相对时间"而保留日期展示 |
| Could · usePolling（SWR 式轮询） | ✅ 已落地 | `usePolling.ts`：60s 基础间隔 + 页面不可见暂停/恢复即刷 + 失败指数退避（上限 32×）；统一自选+指数行情刷新路径；数据源心跳另挂 5 分钟轮询 |
| Could · 数据源健康心跳条 | ✅ 已落地 | 新增 `src/data/source_health.py`（进程内 deque、线程安全、每源 7 条），在 `data_manager.py` 个股/指数（A股+美股）取数链的每层数据源真实发起处打点（未启用的源无记录）；`/api/data/source-health`（plain def）暴露；首页"数据源心跳"widget（Uptime Kuma beat bar：绿=成功/红=失败/灰=无记录 + 最近一次时间），5 分钟轮询。实测：指数取数显示 tushare 红（无 index_daily 权限）→ sina 绿（回退成功），正是该卡片要诊断的场景 |

**附带修正**：自选/行情/主图选中键从 `code|market` 升级为 `code|market|kind`（第三段区分上证指数/平安银行二义代码），顺带修复了行情缓存对二义代码的潜在覆盖；`watchlist.has/add/remove` 按 kind 区分，允许同时跟踪同代码的指数与个股；旧 2 段式 `lastKey` 在加载时归一化。

**验证**：`pytest test/test_backtest.py` 31 通过、`test/test_agent_tools.py` 12 通过；`npm run build`（vue-tsc -b + vite）通过；`run_backtest_json.trades` 实跑冒烟通过；服务器启动冒烟（`/spa/` 200、`/api/kline kind=index` 200、`/api/data/source-health` 心跳实时反映"tushare 失败 → sina 回退成功"）。
