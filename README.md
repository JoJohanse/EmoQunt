<div align="center">

# 📈 EmoQunt 量化系统

**情感驱动的 A 股 / 美股量化回测平台**

[English](README_EN.md) | 中文

融合行业情绪因子与真实交易成本，提供从策略构建、回测、因子分析到绩效与风险管理的一站式 Web 体验；
配备 **Vue3 现代化 SPA**（`/spa/*`）与 Jinja2 经典版（`/`）双前端。

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-后端-009688?logo=fastapi&logoColor=white)
![backtrader](https://img.shields.io/badge/backtrader-回测引擎-8A2BE2)
![Vue](https://img.shields.io/badge/Vue%203-4FC08D?logo=vuedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![ECharts](https://img.shields.io/badge/ECharts-图表-AA344D)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

## 🖼 页面预览

> 截图由 `conda run -n qdt python docs/screenshots/_capture.py` 在本机源码服务上自动采集，为 2026-08 第四轮迭代后界面。

<table>
  <tr>
    <td colspan="2" align="center">
      <img src="docs/screenshots/spa-home-light.png" alt="SPA 首页看板" width="100%"/><br/>
      <b>SPA 首页看板</b> — 10 张可拖拽卡片：快捷入口 · 指数速览（sparkline）· 市场宽度 · 行情看板 · 行业热力图 · 热门板块 · 快讯来源分组 · 个股推荐 · 自选分布环图 · 数据源心跳 + 情绪日历
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-kline.png" alt="K 线看板" width="100%"/><br/>
      <b>K 线看板</b> — 蜡烛 + MA/BOLL 叠加 + MACD/KDJ/RSI 副图 + 最新价虚线 + 月边界刻度，日/周/月与复权切换
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-backtest-trades.png" alt="回测买卖点标注" width="100%"/><br/>
      <b>回测 K 线 · 买卖点标注</b> — 后端 <code>trades</code> 透传，B/S 箭头 + 加权成本均价线，区间与回测日期精确对齐
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-home-tour.png" alt="首访导览" width="100%"/><br/>
      <b>首访导览</b> — driver.js 七步引导，看过不再弹、可随时重放
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-chat-tool-card.png" alt="AI 工具卡片" width="100%"/><br/>
      <b>AI 工具结果卡片</b> — Generative UI：行情摘要卡片 + 一键"在首页查看主图"
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-home-dark.png" alt="暗色模式" width="100%"/><br/>
      <b>暗色模式</b> — 主题切换后刷新仍保持
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-backtest.png" alt="回测结果" width="100%"/><br/>
      <b>回测结果页</b> — 绩效指标 + 动态收益/回撤/日收益图表 + 风险分析
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-kline-week.png" alt="周线" width="100%"/><br/>
      <b>K 线周线</b> — 服务端聚合，三窗格联动缩放
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-strategies.png" alt="策略列表" width="100%"/><br/>
      <b>策略列表</b>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="docs/screenshots/web-sentiment.png" alt="舆情分析" width="100%"/><br/>
      <b>经典版舆情分析</b>（Jinja2，<code>/sentiment</code>）
    </td>
  </tr>
</table>

---

## ✨ 功能特点

### 🧮 回测引擎
- **双市场成本模型**：A股 `AShareCommInfo`（佣金双边含最低 5 元、印花税**仅卖出** 0.05%、过户费双边 0.001%）与美股 `USStockCommInfo`（对称佣金），按 `market` 参数自动路由；滑点始终启用（费率可配）
- **基准与风险调整收益**：A股自动对比沪深300、美股对比标普500，计算 Alpha / Beta / 信息比率并绘制对比曲线
- **情绪过滤策略**：均线交叉信号可由历史情绪快照过滤（"截至当日最近快照"，避免未来函数）
- **交易级胜率与买卖点**：胜率按已平仓交易计算；逐笔成交透传前端，回测 K 线标注 B/S 买卖点与成本均价线
- **绩效与风险分析**：总/年化收益率、夏普、最大回撤、卡玛比率、VaR/CVaR、下行标准差、压力测试场景

### 🗄 数据层（多源容错）
- **A股回退链**：Tushare Pro（可选，需 `TUSHARE_TOKEN`）→ akshare 新浪源 → 东财源 → baostock，由统一 FetchRunner 驱动，任一环节失败自动降级
- **美股两级回退**：yfinance（主）→ akshare 新浪源
- **数据源健康心跳**：每个取数层的成败被记录（进程内、每源近 7 次），`GET /api/data/source-health` 暴露并在首页渲染为心跳条——"为何某股无数据"一目了然
- **可选 PostgreSQL + Redis 缓存**（`docker-compose.yml` 一键启动）：读序 Redis → PG → CSV → 网络，不可用时静默降级为纯网络模式
- 行情结果缓存至本地 `stock_data/`；情绪快照位于 `nes_data/sentiment_results/{YYYYMMDD}.json`，供情绪日历与回测情绪过滤使用

### 🖥 Vue3 SPA（`/spa/*`）
- **导航**：可折叠分组侧边栏 + 面包屑 + 暗色模式 + 全局命令面板 `Cmd+K` + 顶部标签页 + 侧边栏收藏 + 首访导览（driver.js 七步，可重放）
- **首页看板**：功能快捷入口、指数速览（行内 sparkline，点击切主图）、自选股面板（增删、行内 sparkline、价格滚动与涨跌闪烁、点击切主图）、最近回测（一键重跑参数回填）、热门板块、当日舆情（来源分组过滤）、个股推荐（点击下钻主图）、自选分布环图（市场/涨跌/行业三维）、数据源心跳条、情绪日历；**可拖拽网格布局**持久化，行情 SWR 式轮询刷新
- **动态 ECharts**：回测收益/回撤/日收益曲线；K 线蜡烛图 + 成交量 + 指标叠加 + 吸顶数值面板
- **SPA 独有页面**：策略对比（多策略净值叠加 + 指标表）、因子分析（IC / 分层 / 单调性）
- **浏览器本地持久化**：UI 偏好、自选股、回测历史与表单、AI 对话、收藏/标签页/布局/K 线偏好——刷新全部保持
- **AI 投资助手**：全局抽屉对话，LangGraph ReAct agent，SSE 流式 + Markdown；**工具结果卡片化**（行情/舆情/推荐/回测/信号六类卡片，一键跳转主图）

### 🧾 Jinja2 经典版（`/`）
- `base.html` + `app.css` 设计令牌，Bootstrap 5.3 + Font Awesome 6；8 个页面；回测表单记忆上次输入

---

## 🚀 快速开始

### 1. 环境要求
- Python 3.11+（推荐 conda 环境）+ Node.js 18+（仅 SPA 构建需要）
- 网络访问（akshare 行情、TrendRadar 舆情、LLM API）

### 2. 安装依赖
```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build   # 构建 SPA（未构建时 /spa/* 返回 503）
```

### 3. 配置
```bash
cp .env.example .env    # 填入 LLM API_KEY / LLM_MODEL / LLM_BASE_URL（AI 助手与情绪分析需要）
                        # 可选 TUSHARE_TOKEN 启用 Tushare 首选数据源
```
回测/风险参数在 `config/config.yaml`（环境变量 `QDT_` 前缀可覆盖）。

### 4. 启动
```bash
python web_app.py            # http://127.0.0.1:8000
```
- 经典版前端：http://localhost:8000/
- **Vue3 SPA**：http://localhost:8000/spa/
- SPA 开发模式：`cd frontend && npm run dev` → http://localhost:5173/spa/（`/api` 自动代理）

### 5. 可选：启用数据库缓存层
```bash
docker compose up -d         # PostgreSQL 16 + Redis 7（国内源 docker.m.daocloud.io）
```

### 6. 运行测试
```bash
pytest test/test_backtest.py -v    # 测试文件需显式指定（test/ 下另有手动脚本）
```

---

## 🧭 使用指南

### Vue3 SPA 路由

| 路由 | 功能 |
|------|------|
| `/spa/` | 首页看板：快捷入口、指数速览、自选股、K 线主图、最近回测、板块/舆情/推荐、自选分布、数据源心跳 |
| `/spa/backtest` | 策略回测（表单记忆 + 动态图表 + 买卖点标注 + 风险分析；支持 `?historyId=` 回填） |
| `/spa/strategies` | 策略列表（查看/删除） |
| `/spa/sentiment` | 舆情分析（新闻 + 板块得分） |
| `/spa/daily-recommend` | 每日推荐 |
| `/spa/strategy-compare` | 多策略对比（2~5 个策略净值叠加 + 指标表） |
| `/spa/factor-analysis` | 因子分析（IC / 分层回测 / 单调性） |

### 经典版（Jinja2）路由

| 路由 | 功能 |
|------|------|
| `/` | 首页，功能入口与系统特性 |
| `/backtest` · `/run_backtest` | 回测表单与结果（绩效指标卡 + 收益/回撤/仪表板图表） |
| `/strategies` | 策略列表，创建/编辑/删除自定义策略 |
| `/sentiment` · `/analyze_sentiment` | 舆情分析与个股情绪结果 |
| `/daily_recommend` | 每日推荐（Top3 板块 + 排名股票表） |

### API 接口

<details>
<summary><b>展开 API 列表</b>（两个前端共用同一组 <code>/api/*</code>；数据类接口经线程池执行，不阻塞其它请求）</summary>

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查（含 PG/Redis 缓存层连通性） |
| `/api/strategies` / `list` / `detail/{name}` / `templates` | GET | 策略查询 |
| `/api/strategies/create_new` / `create_from_template` | POST | 创建策略 |
| `/api/strategies/{name}` | PUT / DELETE | 更新 / 删除策略 |
| `/api/backtest/run` | POST | 运行回测，返回 JSON 时序（含逐笔 `trades`，供 ECharts） |
| `/api/strategies/compare` | POST | 多策略对比 |
| `/api/factor/analyze` | POST | 因子 IC / 分层分析 |
| `/api/kline` | GET | K 线 OHLCV（`days` 最近区间或 `start_date/end_date` 区间模式） |
| `/api/sentiment` / `sentiment/data` | GET | 舆情数据 |
| `/api/sentiment/calendar` | GET | 情绪日历 |
| `/api/daily-recommend`（`/refresh`） | GET | 每日推荐 |
| `/api/market/breadth` / `sectors` | GET | 市场宽度 / 行业板块行情 |
| `/api/data/source-health` | GET | 数据源健康心跳（每源近 7 次成败） |
| `/api/agent/chat` | POST | AI 助手（SSE 流式） |
| `/api/agent/chat/sync` | POST | AI 助手（非流式） |

</details>

---

## 🏗 系统架构

<details>
<summary><b>展开目录结构</b></summary>

```
EmoQunt/
├── config/                 # 配置文件（config.yaml + 环境变量 QDT_ 前缀覆盖）
├── docs/
│   ├── research/           # UI 调研与决策记录
│   └── screenshots/        # README 截图与采集脚本
├── frontend/               # Vue3 SPA（Vite + TS + Element Plus + ECharts + Pinia）
│   └── src/
│       ├── views/          # 首页/回测/策略列表/舆情/推荐/策略对比/因子分析
│       ├── stores/         # Pinia 状态（chat/ui/watchlist/backtestHistory/favorites/tabs/homeLayout/klinePrefs + persist 插件）
│       ├── api/            # axios 封装 + SSE 解析 + 类型定义
│       ├── chart/ lib/     # 蜡烛图 option 组装器 / 配色 token / 技术指标纯函数
│       ├── components/     # CommandPalette/AppTabs/SentimentCalendar/ChatPanel/ChatToolCard 等
│       └── layouts/        # 侧边栏（含收藏）+ 面包屑 + 标签页 + 暗色/命令面板布局
├── nes_data/               # 舆情数据与情绪快照（sentiment_results/{YYYYMMDD}.json）
├── src/
│   ├── agent/              # LangGraph ReAct 投资助手
│   ├── Strategy/           # 策略基类 + 动态策略工厂 + 情绪过滤 + 用户策略
│   ├── analysis/           # 因子分析（IC / 分层 / 单调性）
│   ├── backtest/           # 回测引擎 + 绩效分析器 + 成本模型 + 逐笔成交记录
│   ├── data/               # 数据管理：FetchRunner 多源回退链 + db.py(PG/Redis 缓存) + SnapshotStore
│   ├── factor/             # 情绪/技术/市场因子 + 每日推荐
│   ├── risk/               # 风险管理（仓位/止损/VaR/压力测试）
│   ├── services/           # 业务编排薄层（路由适配器与领域模块之间）
│   └── utils/              # 路径/日志/校验/环境变量/序列化/TTL 缓存
├── test/                   # pytest 测试套件
├── web/                    # Jinja2 经典版前端（templates + static）
├── docker-compose.yml      # 可选：PostgreSQL 16 + Redis 7 缓存层
└── web_app.py              # 主入口（FastAPI，双前端 + 统一 /api）
```

</details>

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + Uvicorn + Jinja2（数据类接口线程池化）；可选 `psycopg_pool` 连接池 + 缓存层 |
| SPA 前端 | Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia（自研 localStorage 持久化插件） |
| 经典版前端 | Bootstrap 5.3 + Font Awesome 6 |
| 数据 | akshare / Tushare Pro（可选）/ baostock / yfinance；可选 PostgreSQL 16 + Redis 7 |
| 回测 | backtrader + 自定义双市场成本模型 |
| 分析与可视化 | pandas, numpy, scipy, scikit-learn；ECharts（SPA）、matplotlib / seaborn / plotly（服务端） |
| AI | OpenAI 兼容 LLM + LangChain + LangGraph（ReAct agent） |
| 测试 | pytest（500+ 用例） |

---

## 📝 回测引擎要点

### 交易成本
- **A股**（`AShareCommInfo`）：佣金双边（默认万三，单笔最低 5 元）、印花税**仅卖出** 0.05%、过户费双边 0.001%、滑点 0.05%（始终启用）
- **美股**（`USStockCommInfo`）：对称佣金，无印花税/过户费

### 基准与风险调整收益
- 按市场自动获取基准（A股=沪深300，美股=标普500）
- 计算 Alpha / Beta（协方差法）、信息比率，图表中绘制基准对比曲线

### 情绪过滤
- 扫描 `nes_data/sentiment_results/*.json` 历史快照（统一由 SnapshotStore 解析），构建"快照日期 × 行业"情绪面板
- 回测中某日仅使用"截至该日最近的历史快照"，**避免未来函数**
- 启用情绪过滤时，金叉买入需行业情绪 ≥ −threshold，死叉卖出需 ≤ threshold

---

## ⚠️ 注意事项

- 回测首次获取行情/指数数据需联网（结果会缓存；外部数据源偶发不稳时回退链自动切换）
- 舆情分析需要有效的 LLM API Key
- 首次运行时系统会自动生成 `logs/`、`output/`、`nes_data/` 等目录
- SPA 未构建（`frontend/dist` 不存在）时 `/spa/*` 返回 503 提示
- 回测结果仅供参考，不构成投资建议

## 🤝 贡献指南

请参考 [CONTRIBUTING.md](CONTRIBUTING.md) 文件。

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证。
