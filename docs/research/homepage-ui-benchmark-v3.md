# 首页导航 / 内容 / K 线交互 / 行情面板 — 第三轮相似开源项目调研

> 调研日期：2026-08-22（第三轮）。目标：延续 1) 优化首页导航与 UI 交互（重点）2) 丰富首页内容与功能。
> 前两轮（`homepage-ui-benchmark.md` 2026-08-14、`homepage-ui-benchmark-v2.md` 2026-08-19）已覆盖 FreqUI/OpenBB/Ghostfolio/QUANTAXIS/vnpy/vectorbt、Vue 管理模板、命令面板/网格布局/标签页、PG+Redis 持久化与 Docker 镜像。其中 v2 的 Must 项（命令面板 `CommandPalette.vue`、Tabs+收藏、暗色模式、情绪日历、首页布局持久化）**已全部落地**，本轮换新角度：**专业 K 线图库、国内股票类开源前端（自选股行情面板）、金融看板设计系统、市场热力图、加载态微交互**。

## 一、调研对象（本轮新增）

| 维度 | 项目 / 来源 | 与 EmoQunt 的相似点 | 值得借鉴 |
|---|---|---|---|
| K 线图库 | [KLineChart](https://github.com/klinecharts/KLineChart)（v9.x 稳定 / v10 alpha） | 纯前端金融图表，与现有 ECharts K 线直接对标 | 零依赖 ~45KB gzip；30+ 内置指标（MA/EMA/BOLL/MACD/RSI/KDJ）；副图窗格系统；画线工具（覆盖物）；十字光标+价格/时间轴标签联动；缩放/平移手势；样式深度合并定制 + 主题系统。ECharts 需手写的 tooltip/crosshair/dataZoom 细节它是开箱即用 |
| 国内股票前端 | [leek-fund 韭菜盒子](https://github.com/LeekHub/leek-fund)（VS Code 插件，~13k star） | 自选股列表 + 指数速览 + 新闻，国内用户习惯基准 | **自选股分组管理**（组内增删/置顶/排序，删除非空组二次确认）；**状态栏轮播**（最多 4 只，hover 暂停）；牛熊风向标（涨跌家数分布柱状图+热门主题+北向资金三合一情绪视图）；快讯流（利多🚀/利空🍜标记 + 相关板块提取）；涨跌配色/图标个性化 |
| 国内股票前端 | [go-stock](https://github.com/ArvinLovegood/go-stock)（Wails+Vue3+NaiveUI） | Vue3 前端 + A 股/美股 + AI 分析对话 + 本地存储哲学 | 自选表格**行内迷你 K 线**（hover 预览，标题实时显示最新价/涨跌幅）；K 线周期切换常量（1m~month）+ 复权模式选择；**技术指标选择持久化**（图表偏好跨会话保留）；成本价/止盈/股价三类预警（5 分钟冷却 TTL 防重复推送）；每日盈亏统计面板 |
| 国内股票前端 | [InStock](https://github.com/myhhub/stock) | Python 后端 + 指标计算 + 回测验证闭环 | 股票指标计算、筹码分布、K 线形态识别、多策略选股+回测验证——后端能力清单可对照补齐因子分析维度 |
| 国内股票前端 | [quant-desktop](https://github.com/Leaderxin/quant-desktop) | A 股实时看盘桌面应用 | **可拖拽置顶浮动行情条**：每 3 秒轮播 2 只自选股（名称+最新价+涨跌幅），鼠标悬停暂停——SPA 可做"迷你行情条"吸顶变体 |
| 国内股票前端 | [StockGoose](https://github.com/DJChanahCJD/StockGoose) | 纯前端自选股行情面板 | 浏览器直连公开行情源、无后端无账号、自选/提醒/偏好全存本地——与本项目"浏览器本地持久化"路线互证 |
| A 股看板 | [chengzuopeng/stock-dashboard](https://github.com/chengzuopeng/stock-dashboard)（React+TS） | A 股数据看板：行情/筛选/自选/板块 | 信息架构最接近：Boards(看板)/Heatmap(**行业热力图**)/Rankings(**排行榜**)/Scanner/**Watchlist**/StockDetail 分页；`useLocalStorage` + `usePolling` hooks 封装轮询与本地化；热力图支持行业/板块/自选三维度切换 |
| 市场热力图 | [openalgo-heatmap](https://github.com/marketcalls/openalgo-heatmap)、[Finviz Map](https://finviz.com/map) | Finviz 式市场热力图 | squarified treemap 按市值定面积、按涨跌幅着色（发散色带）、固定行业分区 + 尺寸/颜色双通道编码；A 股可按申万行业聚合 |
| 金融设计系统 | [Tremor](https://github.com/tremorlabs/tremor)（35+ 组件）、shadcn/ui Charts | 数据密集型仪表盘组件规范 | **KPI 卡片模式**：大数字 + Delta 徽章(▲▼+%) + 迷你 Sparkline 三件套；Trackers(日历热力条)；类别条(BadgeList/ProgressBar) —— 可用 Element Plus+ECharts 以 CSS 规范复刻其排版而非引入 React 库 |
| 加载态 UX | NN/g Skeleton Screens 101、onething.design 对比文 | 首页多面板并行加载体验 | 骨架屏优于 spinner（感知等待更短、布局不跳动）：卡片级 `el-skeleton` 占位；spinner 仅用于按钮内联动作；空状态引导添加（HomeView 已有 el-empty）；数据失败静默降级保留上帧 |

## 二、共性模式 → EmoQunt 落地方案

### 1. 首页导航与 UI 交互（重点）

**现状**：侧边栏分组折叠+收藏+面包屑+暗色+Tabs+命令面板均已就绪。

**本轮提炼的增量（按性价比排序）**
1. **K 线主图换装或增强**（最大单点收益）：当前 ECharts 手写 candlestick+tooltip。两条路线：
   - a) 引入 **KLineChart v9.x**（零依赖 40KB，30+ 指标/画线/十字光标开箱即用，样式深度合并对接暗色主题）替换主图；
   - b) 不换库，对齐其交互清单：MA 叠加开关（记忆到 `emoqunt:` 键）、十字光标 OHLC 信息浮层、dataZoom 默认窗口 + 重置按钮。
2. **加载态骨架屏**：HomeView 目前仅 1 处 `v-loading`；为指数速览/自选行情/情绪日历/最近回测四块卡片加 `el-skeleton` 占位（NN/g：感知等待更短且布局无跳动），按钮动作保留 loading 态。
3. **KPI 卡片排版规范化**（Tremor 模式）：指数速览改为"名称 + 大号最新价 + Delta 徽章(▲+x.xx% 红/绿按市场约定)"层级；自选股列表同理统一 Delta 徽章组件。
4. **自选股列表交互升级**（对标 leek-fund/go-stock）：分组（A股/美股/指数）+ 组内置顶/排序；行 hover 显示迷你走势 sparkline 或点击弹出 mini K 线浮层（go-stock 行内 K 线预览模式）；涨跌闪烁动效提示刷新（可选）。
5. **吸顶迷你行情条**（quant-desktop 变体）：从首页向下滚动进入其他页面时，顶部 Tabs 栏右侧显示 1 只自选股的 最新价+涨跌幅 微型胶囊，点击回首页。

### 2. 首页内容与功能

1. **行业/板块热力图卡片**（chengzuopeng/stock-dashboard + Finviz）：squarified treemap，面积=成交额/市值，颜色=涨跌幅发散色带（A 股红涨绿跌）；维度切换（行业/概念/自选）。后端可用 akshare 板块接口聚合，缓存进 `stock_data/`。这是本轮**内容侧最高价值项**。
2. **涨跌家数分布条**（leek-fund 牛熊风向标简化版）：涨停/大涨/上涨/平盘/下跌/大跌/跌停 七档横向堆叠条 + 北向资金净流入数字，一行卡片即可承载"今日市场情绪"，与情绪日历互补（日历=历史回顾，风向标=当日实况）。
3. **涨跌幅排行榜卡片**（stock-dashboard Rankings 页）：首页 Tab 切换"涨幅榜/跌幅榜/成交额榜"，点击行加入自选或切主图。akshare 有现成接口。
4. **快讯/资讯流**（leek-fund 快讯服务）：财联社电报式滚动列表，利多🚀/利空🍜标记 + 关联板块 tag 点击跳转热力图对应板块；轮询间隔 ≥60s 且失败退避（尊重 AGENTS.md 事件循环规则：handler 用 plain def + threadpool）。
5. **价格提醒**（go-stock 预警模型简化版）：自选股设置 上破/下破 阈值，触发后在通知中心 Drawer（v2 清单已有该项）+ Badge 计数；本地 localStorage 存阈值，前端轮询判断即可，无需后端推送。

### 3. 决策建议（供下轮迭代取舍）

| 优先级 | 事项 | 价值 | 工作量 | 备注 |
|---|---|---|---|---|
| Must | K 线交互增强（MA 开关/十字光标浮层/默认 dataZoom）或直接换 KLineChart | 高 | S-M (1-3 天) | 先做 b) 对齐清单，效果不满意再评估 a) 换库 |
| Must | 卡片骨架屏加载态 + KPI Delta 徽章规范化 | 高 | S (1 天) | Element Plus 原生组件，纯前端改造 |
| Should | 行业热力图卡片 | 高 | M (2-4 天) | akshare 板块数据 + ECharts treemap；含后端缓存 |
| Should | 涨跌家数分布条（当日情绪风向标） | 中高 | S (1 天) | akshare 涨跌家数接口 + 堆叠条 |
| Could | 自选股分组 + 行内 sparkline | 中 | S-M (1-2 天) | persist.ts 扩展 group 字段 |
| Could | 涨跌幅排行榜卡片 | 中 | S (1 天) | 依赖 akshare 接口稳定性 |
| Could | 吸顶迷你行情条 | 中低 | S (1 天) | 锦上添花，排在交互打磨末尾 |
| Won't（本轮不做） | 实时 WebSocket 推送/分钟级行情 | 高 | L (>1 周) | 项目定位日线级回测研究，非盯盘工具；轮询日线足够 |
| Won't（本轮不做） | 价格提醒推送通道（钉钉/飞书/TG） | 中 | M | trendradar 已有通知链路，避免功能重叠 |

## 三、决策记录（本轮）

- **K 线先"对齐清单"后"换库"**：ECharts 方案已跑通双市场列名契约与主题，换 KLineChart 收益集中在画线/多指标/手势，但引入新渲染栈与数据格式转换（KLineChart 的 KLineData `{open,high,low,close}` vs 现有中文列 DataFrame）。先以低成本对齐交互清单，若用户仍需画线工具再评估换库。
- **热力图选 ECharts treemap 而非引 d3**：项目已全量依赖 echarts，treemap+squarified 内置支持，无需新依赖。
- **设计系统只借排版规范不引库**：Tremor/shadcn 是 React 生态，仅借鉴 KPI 卡片/Delta 徽章/Trackers 的视觉模式，用现有 Element Plus + CSS 变量实现。
- **加载态遵循 NN/g 结论**：区块级骨架屏、操作级 spinner、空态引导三分法，不做全局遮罩 loading。
- **不做实时盯盘方向**：与既有"日线级回测研究平台"定位冲突，轮询日线 + 本地持久化路线（StockGoose 互证）已够用。

## 四、参考链接

- KLineChart: https://klinecharts.com/ · https://github.com/klinecharts/KLineChart （生产用 v9.x）
- leek-fund: https://github.com/LeekHub/leek-fund · https://leek.fund/docs
- go-stock: https://github.com/ArvinLovegood/go-stock
- InStock: https://github.com/myhhub/stock
- quant-desktop: https://github.com/Leaderxin/quant-desktop
- StockGoose: https://github.com/DJChanahCJD/StockGoose
- chengzuopeng/stock-dashboard: https://github.com/chengzuopeng/stock-dashboard
- openalgo-heatmap: https://github.com/marketcalls/openalgo-heatmap · Finviz Map: https://finviz.com/map
- Tremor: https://tremor.so/ · https://github.com/tremorlabs/tremor · shadcn/ui Charts: https://ui.shadcn.com/charts
- 骨架屏: NN/g https://www.nngroup.com/articles/skeleton-screens/ · https://www.onething.design/post/skeleton-screens-vs-loading-spinners
- fupanhezi-admin（复盘工具，备查）: https://github.com/franktrue/fupanhezi-admin
