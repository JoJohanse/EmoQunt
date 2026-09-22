# PandaAI(QUBE) 对标优化 Round 2 — W1/W2/W3

> 状态：执行中（2026-09-21 起）。上一轮 P0-P5（pandaai-style-platform-plan.md）已全部落地并推送。
> 本轮对标 live 实探（www.pandaaiquant.com/agent_quant，用户给的 pandaavquant.com 域名不可达，原域名可用）。

## 实探结论（2026-09-21 浏览器实测）

QUBE 导航：对话工作台（+新增会话/会话置顶/更多操作）、策略参数调优（会话内）、策略库、因子库、运行历史、调优任务、仿真盘、技能库、Qube 行情；顶栏 通知/算力/设置/个人中心。风格：暗色优先、绿色强调、圆角卡片、紧凑分组侧栏、大字报价排版。

与 EmoQunt 现状对比后的**本轮范围**（用户指示：技能库不复刻；仿真盘/算力/个人中心/通知为多用户 SaaS 形态，单用户本地平台无意义，明确不做）：

| QUBE 能力 | EmoQunt 现状 | 本轮动作 |
|---|---|---|
| 会话列表（新增/置顶/重命名/删除） | 单会话 localStorage | W2a 复刻 |
| 对话启动卡片（按组的参考策略卡） | 4 条示例问题文本 | W2a 复刻 |
| 模型选择/思考等级/操作权限/策略转写 | 无 | 不做（单模型本地部署；记录决策） |
| 调优任务独立列表页（按策略分组→任务详情） | 任务入口散在策略详情 Tab 与 /tuning/:id | W2b 复刻 /tunings |
| Qube 行情（标的搜索列表 + 大字报价 + 多周期K线） | 首页看板（无独立行情页） | W2b 复刻 /market |
| 首屏行情秒开 | quote_cache 已持久化，但**首次访问**（空缓存）仍冷爬，首屏 8+ 并发请求 | W1 |
| 暗色专业终端观感 | Element Plus 亮色默认 + 紫品牌 | W3 一致性优化（不必一致） |

## W1 行情首访提速（性能，主智能体亲自）

现状：`quote_cache` SWR 已落 SQLite（重启后毫秒），但**空缓存的首次访问**仍然冷（breadth 爬 6s、各 kline 逐个出网），且 HomeView 首屏并发 8+ 请求（kline、每自选 sparkline、sourceHealth、sentiment、calendar、recommend、breadth、sectors）。

1. **启动预热**：FastAPI lifespan 起后台线程，预取 breadth / sectors / 五指数(000300/000001/399001/SP500/NASDAQ) 尾部行情 / 默认自选行情，全部经 quote_cache 落库——**首次访问前缓存已热**。
2. **聚合端点** `GET /api/market/overview`：一次返回 indices + breadth + sectors + 默认自选 quotes（各自走 SWR 缓存），HomeView 首屏改单请求，次级卡片（sentiment/calendar/recommend/sourceHealth）保持独立轮询。
3. 实测：空缓存冷启动 → 首屏可用时间 before/after。

## W2 功能复刻（除技能库）

- **W2a 对话多会话 + 启动卡片**（fixer 子智能体）：chat store 重构为多会话数组（activeId/置顶/重命名/删除，持久化），抽屉加会话列表头；空态启动卡片组（股票策略/A股因子/数据查询，点击填充 prompt）。文案进 chat 词表双语。
- **W2b 调优任务列表 + 行情终端**（fixer 子智能体）：`/tunings`（全量调优任务列表，复用 tuningApi.list，→/tuning/:id）；`/market`（左标的列表：搜索+自选+指数预设；右大字报价头 + K线复用 chart/kline.ts + klineApi，周期日/周/月）。路由/侧栏/收藏/词表双语。

## W3 UI 风格优化（designer 子智能体，最后做避免冲突）

不做全量换肤（保持 Element Plus + 紫品牌），做一致性 pass：设计 token 审计（间距/圆角/字号/阴影）、卡片头部与空态统一、表格密度、暗色模式对比度与图表配色检查（marketColors 规格不动）、新页面（/market、/tunings、chat 会话列表）纳入同一套语言。

## 验收

1. 空 market_cache.db 冷启动，预热完成后首屏 overview 单请求毫秒级；浏览器实测首访无 N+1 突刺。
2. 对话可多会话切换/置顶/重命名/删除，启动卡片可用；/tunings、/market 两页可用且入侧栏。
3. designer pass 后无裸风格漂移（token 消费一致），暗色可用。
4. 回归全绿 + vue-tsc 构建 + 浏览器 E2E。
