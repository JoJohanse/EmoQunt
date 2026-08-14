# 首页导航 / 内容 / 本地持久化 — 相似开源项目调研

> 调研日期：2026-08-14。目标：1) 优化首页导航与 UI 交互；2) 丰富首页内容与功能；3) 本地持久化保存。
> 调研范围：开源量化交易平台、投资组合追踪器、Vue3 管理后台模板、前端持久化方案。

## 一、调研对象

| 项目 | 技术栈 | 与 EmoQunt 的相似点 | 值得借鉴 |
|---|---|---|---|
| [Freqtrade / FreqUI](https://github.com/freqtrade/frequi) | Vue3 + PrimeVue 前端，Python 后端 | Vue3 SPA + Python 后端，回测可视化 | Dashboard 首页聚合多面板（图表 + 指标 + 历史），左侧导航 + 面板灵活组合 |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Python 平台 + Web 工作台 | 投研平台：行情、数据源聚合、AI 助手 | 模块化仪表盘（widget 化）、~100 数据源统一 API、AI agent 深度集成 |
| [Ghostfolio](https://github.com/ghostfolio/ghostfolio) | Web 全栈 | 个人投资追踪 | 自选/持仓（watchlist）+ 净值追踪是核心首屏内容；隐私优先、本地化数据 |
| [QUANTAXIS](https://github.com/yutiansut/QUANTAXIS) | Python + RESTful | A 股回测/数据平台 | RESTful 后端 + 前端可视化分层；多人协作 |
| [Qbot (UFund-Me)]](https://github.com/UFund-Me/Qbot) | Python + Web 看板 | A 股 AI 量化投研平台 | 数据→策略→回测→模拟全闭环在统一看板呈现 |
| [vnpy / VeighNa](https://github.com/vnpy/vnpy) | Python + Qt | 国内最成熟的 Python 量化框架 | 功能分区（数据/回测/实盘各成模块）的信息架构 |
| [vue-element-plus-admin](https://github.com/kailong321200875/vue-element-plus-admin) / [art-design-pro](https://github.com/Daymychen/art-design-pro) / [v3-admin-vite](https://github.com/un-pany/v3-admin-vite) | Vue3 + Element Plus | 同技术栈 | 可折叠侧边栏、分组菜单、面包屑、暗色主题、全局面包屑+标签页 |
| [pinia-plugin-persistedstate](https://github.com/prazdevs/pinia-plugin-persistedstate) | Pinia 插件 | Vue3 状态持久化 | `persist` opt-in、`pick` 选择字段、localStorage 存储；本项目以 ~50 行自研插件复刻，避免新增依赖 |

## 二、提炼出的共性模式 → EmoQunt 落地方案

### 1. 首页导航与 UI 交互（对标 FreqUI / 管理后台模板）

**共性模式**
- 顶部水平导航在 7+ 个功能后开始拥挤；成熟项目统一采用**可折叠侧边栏 + 分组菜单**（总览 / 回测研究 / 数据洞察 / 策略管理）。
- **面包屑** + 当前页标题，用户随时知道自己在哪（v3-admin-vite、art-design-pro 标配）。
- **暗色模式**切换（admin 模板标配；Element Plus 原生支持 `html.dark` + `dark/css-vars.css`）。
- 折叠状态本身要**持久化**，刷新后保持（admin 模板均持久化 UI 偏好）。

**落地**：`AppLayout.vue` 重构为侧边栏布局；折叠状态、暗色主题持久化到 localStorage。

### 2. 丰富首页内容与功能（对标 Ghostfolio / FreqUI / Qbot）

**共性模式**
- **自选股（Watchlist）** 是投资类应用首页的第一公民（Ghostfolio、雪球、富途、FreqUI 的 bot 列表同理）：用户添加标的 → 首屏直接看行情。
- **快捷入口**：首页提供全部功能的快捷卡片（Qbot 看板、OpenBB workspace）。
- **最近活动/历史**：FreqUI 的 trade history、Ghostfolio 的 transaction history —— 回测历史让用户回到首页能看到自己做过什么。
- **大盘概览条**：指数快照（上证/沪深300/深证成指）是 A 股产品首屏标配。

**落地**：首页新增 ① 功能快捷入口；② 自选股面板（增删 + 最新价/涨跌幅，点击切换主图）；③ 最近回测（含核心指标，可一键回填参数）；④ 指数行情条。

### 3. 本地持久化保存（对标 pinia-plugin-persistedstate / admin 模板）

**共性模式**
- 用户数据分两类：**服务端持久化**（策略 JSON、行情缓存——项目已有）与**浏览器本地持久化**（UI 偏好、自选股、对话历史、表单记忆）。
- 本地持久化统一走 Pinia 插件（`persist: true` / `pick` 字段挑选），而不是各组件散落 `localStorage` 调用。
- 刷新后保持：折叠状态、主题、自选股、AI 对话记录、回测表单上次填写值。
- 容错：localStorage 可能抛 quota/序列化异常，必须 try/catch 静默降级。

**落地**：自研 `stores/persist.ts` Pinia 插件（`emoqunt:` 前缀键、opt-in、`pick`、`revive` 钩子）；持久化 chat / ui / watchlist / backtestHistory 四个 store；Jinja2 端回测表单用内联脚本记忆上次输入。

## 三、决策记录

- **不引入 `pinia-plugin-persistedstate` 依赖**：功能需求（opt-in + 字段挑选）用 ~50 行插件即可覆盖，避免为一个轻量功能增加 node_modules 体积与升级面。
- **暗色模式**采用 Element Plus 官方 `html.dark` 方案 + 项目 CSS 变量覆写，改造成本最低。
- **A 股红涨绿跌 / 美股绿涨红跌**：自选股行情按市场区分涨跌配色（与国内主流 App 的美股显示一致）；K 线主图维持现有 A 股配色约定。

## 四、参考链接

- FreqUI: https://github.com/freqtrade/frequi · https://www.freqtrade.io/en/stable/freq-ui/
- OpenBB: https://github.com/OpenBB-finance/OpenBB · https://openbb.co/
- Ghostfolio: https://github.com/ghostfolio/ghostfolio · https://ghostfol.io/en/features
- QUANTAXIS: https://github.com/yutiansut/QUANTAXIS
- Qbot: https://github.com/UFund-Me/Qbot
- vnpy: https://github.com/vnpy/vnpy
- vue-element-plus-admin: https://github.com/kailong321200875/vue-element-plus-admin
- art-design-pro: https://github.com/Daymychen/art-design-pro
- v3-admin-vite: https://github.com/un-pany/v3-admin-vite
- pinia-plugin-persistedstate: https://github.com/prazdevs/pinia-plugin-persistedstate
- awesome-quant: https://github.com/wilsonfreitas/awesome-quant
