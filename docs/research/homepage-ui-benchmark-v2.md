# 首页导航 / 内容 / 持久化 / Docker 镜像 — 第二轮相似开源项目调研

> 调研日期：2026-08-19（第二轮）。目标：为下轮迭代补充 1) 导航与 UI 交互 2) 首页内容与功能 3) 本地持久化（PG+Redis）4) Docker 镜像 的最新对标与可落地清单。
> 延续首轮 `homepage-ui-benchmark.md`（2026-08-14，覆盖 FreqUI/OpenBB/Ghostfolio/QUANTAXIS/vnpy/管理后台模板/pinia 持久化）；本轮新增四条线并行搜索，补齐量化仪表盘、Vue 导航新范式、Compose 持久化与多阶段镜像。

## 一、调研对象（本轮新增）

| 维度 | 项目 / 来源 | 与 EmoQunt 的相似点 | 值得借鉴 |
|---|---|---|---|
| 量化仪表盘 | Freqtrade / FreqUI（深入 Plot Configurator、多 Bot 聚合、Grafana 替代） | Vue 前端 + Python 后端 + 回测可视化 | 多套绘图配置可切换、钱包 vs 累计收益双曲线、时区/蜡烛配色/通知开关持久化 |
| 量化仪表盘 | QuantConnect / Lean | 策略平台 + Jupyter Docker 镜像 | Lean CLI + VS Code 扩展 + 云端控制台的命令式交互 |
| 量化仪表盘 | NautilusTrader | 回测确定性引擎 | UI 明确 out of scope，社区补位 Web Interface 的分工思路 |
| 量化仪表盘 | vectorbt / vectorbt pro | 因子/信号/组合可复用组件 | Plotly/Dash 自建看板、参数热力图、近 2 万 MACD 组合 30s 扫参 |
| 量化仪表盘 | vnpy / VeighNa、QUANTAXIS | A 股数据/回测分层 | 事件驱动、`portfolio_manager` 子账户、JupyterLab + RESTful + 分布式调度 |
| Vue 导航交互 | shadcn/vue Sidebar、vue-command-palette、Vuetify `v-command-palette`、Nuxt UI | 同技术栈（Vue3） | 可折叠分组 + 收藏/拖拽排序 + Cmd+K 命令面板成标配 |
| Vue 导航交互 | grid-layout-plus / vue-responsive-grid-layout / GridStack.js | SPA 仪表盘 | 卡片拖拽/缩放/响应式、布局 JSON 持久化；OpenBB/Ghostfolio 均为 widget 化可分享仪表盘 |
| Vue 导航交互 | Element Plus Dark Mode 2.2+ | 同组件库 | `dark/css-vars.css` + `html.dark` + 图表主题联动 |
| 持久化 | Ghostfolio / Supabase / Outline / Planka `docker-compose.yml` | `postgres:16-alpine` + `redis:7-alpine` + healthcheck | `healthcheck` + `restart: unless-stopped` + 命名 volume + `depends_on: service_healthy` |
| 持久化 | Redis + FastAPI / Alembic 官方 | FastAPI 缓存层 | `connect_timeout 2-3s` + 熔断器 + `tenacity` 指数退避；单表可 `CREATE TABLE IF NOT EXISTS`，多表切 Alembic/Prisma 版本化 |
| Docker 镜像 | FastAPI 官方 Containers、Docker Building best practices、Python Speed 多阶段 | Python 后端 + Vue3/Vite 前端同构 | `node:20-alpine` 构建 + `python:3.11-slim` 运行双阶段；FastAPI 直托 `frontend/dist`（单镜像零 CORS）vs Nginx 双容器 |

## 二、共性模式 → EmoQunt 下轮落地方案

### 1. 导航与 UI 交互（对标 shadcn/vue、命令面板、网格布局）

**共性模式**
- 侧边栏已演进为"操作系统化"：可折叠分组 + 收藏/置顶 + 拖拽排序 + 状态记忆（localStorage），辅以顶部 Tabs 标签页（`keep-alive` 多开，类 VS Code / FreqUI）。
- **Cmd+K 命令面板成标配**：`vue-command-palette` 封装模糊搜索 + 分组 + 子面板 + 全局快捷键，解决深层路由跳转慢问题。
- **首页网格化可定制**：`grid-layout-plus` / `vue-responsive-grid-layout` / `GridStack.js` 实现卡片拖拽/缩放/响应式，布局序列化持久化；OpenBB/Ghostfolio 为 widget 式可分享仪表盘。
- 暗色 = CSS Vars + 细节打磨：Element Plus 统一为 `dark/css-vars.css` + `html.dark` 切换，配合图表跟随主题、过渡动画；移动端侧边栏自动转 Drawer + 底部 Tab。

**EmoQunt 现状**：`AppLayout.vue` 已有分组折叠 + 面包屑 + 暗色切换；`HomeView` 三栏（快捷入口/自选股/K线/最近回测）+ 三栏信息已就绪；`stores/persist.ts`（`emoqunt:` 前缀）已覆盖 `ui/watchlist/backtestHistory/chat`。

**下轮增量（按性价比排序）**
1. **命令面板 Cmd+K**（低成本/高收益）：注册回测/因子/自选/策略/个股代码命令，`Ctrl+K` / `/` 唤起。
2. **侧边栏收藏夹 + 标签页**：`⭐ 收藏` 分组（persist）+ 最近访问 5 条 + 顶部 Tabs 带关闭/右键关闭其他；`<768px` 自动收为 Drawer。
3. **通知中心 + 快捷键体系**：趋势雷达/情绪快照/回测完成聚合到右侧 Drawer（`Badge/Drawer`），补充 `g h/b/f/?` 快捷键及 `?` 帮助面板。
4. **可拖拽网格**：`grid-layout-plus` 将首页 4 块卡片改为响应式网格，布局存 `emoqunt:home_grid`，提供重置/紧凑；移动端回退单列。
5. **暗色/移动端抛光**：校验 `dark/css-vars.css` 引入、K 线/eCharts 主题联动、`useDark` 同步系统偏好。

### 2. 首页内容与功能（对标 FreqUI / vectorbt / vnpy）

**共性模式**
- 除 K 线/回测历史外的高频模块：持仓/风险（P&L、回撤、Sharpe、杠杆）、日历（收益日历/财报/情绪快照日历）、热力图（参数敏感度/因子暴露/板块轮动）、钱包/资金曲线、未平仓/委托簿、因子/信号列表、Walk-Forward 校验。
- FreqUI 强调钱包 vs 累计利润双曲线 + Plot Configurator 多套绘图配置；vectorbt 强调组合拆解与交叉验证。
- vnpy `portfolio_manager` 子账户每日盈亏、QUANTAXIS Notebook 串联数据→回测→可视化。

**可复用差距**
- **情绪日历**：`nes_data/sentiment_results/{YYYYMMDD}.json` 的 look-ahead-safe 日历视图（A 股情绪因子特色）。
- **因子暴露热力图 + 持仓/风险四象限**：回撤/波动/胜率/盈亏比。
- **绘图配置器**：K 线叠加情绪分数/均线，多套命名配置持久化（复刻 FreqUI Plot Configurator）。

### 3. 本地持久化（PG + Redis，对标 Ghostfolio/Supabase/Outline）

**共性模式**
- Compose 三件套必备：`healthcheck`（10s/5s/5 次）+ `restart: unless-stopped` + 命名 `volume`；应用服务用 `depends_on: condition: service_healthy` 保证时序，`cap_drop: ALL` + `no-new-privileges` 加固。
- 应用层熔断 > 重试：`connect_timeout 2-3s` + 熔断器（失败后 30s 不再试）+ `tenacity` 指数退避；EmoQunt `db.py` 已实现 30s 熔断与静默降级。
- Schema 迁移分水岭：单表用 `CREATE TABLE IF NOT EXISTS` 足够，多表/演进切 Prisma/Alembic 版本化。
- Redis 序列化：时序/DF 场景 `parquet bytes`（紧凑、保 dtype）优于 JSON/msgpack，配合 `maxmemory-policy allkeys-lru` + 分层 TTL + jitter 防雪崩；纯热缓存默认不挂 volume。

**EmoQunt 现状**：`docker-compose.yml` 已有 `postgres:16-alpine` + `redis:7-alpine`、`pg_isready`/`redis-cli ping` healthcheck、`pgdata` 卷、`maxmemory 256mb allkeys-lru`；`src/data/db.py` 已实现 `Redis→PG→CSV→网络` 读序、`parquet bytes`、`connect_timeout=3s` + 30s 熔断、幂等建表；`/api/health` 暴露 `postgres/redis` 布尔值。

**下轮 3 条建议**
1. **轻量迁移骨架**：保留幂等建表，新增 `alembic` 最小骨架（仅 `stock_daily` 的 `market/adjust/is_index` 演进）与 `python -m src.data.db init` 并存。
2. **缓存分层**：TTL 从统一 86400s 改为"当日未收盘 300s + 历史 7d + ±10% jitter"，键从"精确起止窗口"改为 `stock:{market}:{adjust}:{code}` 全量 + 应用层切片；评估 `zstd` 压缩 parquet。
3. **连接池化与 Compose 加固**：`psycopg` 单例换 `psycopg_pool.ConnectionPool` 并在 `web_app.py lifespan` 统一开关；`cache` 加 `REDIS_PASSWORD` + 带密码的 healthcheck，预留 `app` 服务的 `depends_on: service_healthy`。

### 4. Docker 镜像（对标 FastAPI 官方 + 多阶段最佳实践）

**共性模式**
- **双阶段为主流**：`node:20-alpine AS frontend` 负责 `npm ci && npm run build`，`python:3.11-slim AS runtime` 负责运行；需编译（`numpy/backtrader`）时再拆 `builder` 阶段用 `build-essential`，产物 `COPY --from=builder` 到 runtime（镜像 ~1.2GB → ~200MB）。
- 基础镜像：`python:3.11-slim-bookworm` + `node:20-alpine`；含 `torch/transformers` 重依赖时忌 `alpine` 跑 Python（musl 缺 glibc）。
- 前端托管二选一：a) 单镜像 FastAPI 直托（`StaticFiles` 挂 `/assets` + `/spa/*` fallback，零 CORS、部署最简）；b) 双容器 Nginx 托管（`/api` 反代）。单体内网选 a)，需 CDN/强缓存再选 b)。EmoQunt 已实现 a) 应延续。
- 缓存与体积：`COPY requirements.txt` → `pip install --no-cache-dir` 置于 `COPY .` 之前命中 BuildKit 缓存；`.dockerignore` 必配 `node_modules/.git/stock_data/logs/output/nes_data/sentiment_results/__pycache__/.env`。
- 启动与健康：`CMD ["uvicorn","web_app:app","--host","0.0.0.0","--port","8000"]` 用 exec 形态；`HEALTHCHECK CMD curl -f http://localhost:8000/api/health`；`compose` 加 `depends_on: service_healthy`。

**可落地镜像草案**
```dockerfile
FROM node:20-alpine AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=web /app/frontend/dist ./frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn","web_app:app","--host","0.0.0.0","--port","8000"]
```
`compose.yml` 扩展：新增 `app: build: . / ports: 8000:8000 / env_file: .env / depends_on: db/cache(healthy)`，保留现有 `db/cache` 的 healthcheck 与 `pgdata` 卷，可选挂 `stock_data:/app/stock_data`。

## 三、下轮迭代可落地清单（MoSCoW + 工作量）

| 优先级 | 事项 | 价值 | 工作量 | 备注 |
|---|---|---|---|---|
| Must（下一迭代） | 全局命令面板 Cmd+K | 高 | S (1-2 天) | `vue-command-palette`，搜股票/策略/回测/路由 |
| Must | 标签页 Tabs + 侧边栏收藏 | 高 | S (1-2 天) | 复用 `persist.ts`，`keep-alive` |
| Should | 可拖拽网格仪表盘 | 高 | M (3-5 天) | `grid-layout-plus`，布局持久化 `emoqunt:home_grid` |
| Should | 情绪日历（快照日历） | 中高 | M (2-3 天) | 基于 `sentiment_results/{YYYYMMDD}.json`，look-ahead-safe |
| Should | PG 连接池化 + compose 加固 | 中 | S (1 天) | `psycopg_pool` + `lifespan` 统一开关 |
| Could | 缓存分层（TTL 分层 + 键收敛） | 中 | S-M (1-2 天) | 当日 300s / 历史 7d + jitter |
| Could | 通知中心抽屉 | 中 | S (1-2 天) | 聚合回测完成/拉取失败/情绪更新 |
| Could | 绘图配置器（多套 K 线叠加） | 中 | M (3 天) | 复刻 FreqUI Plot Configurator |
| Could | 因子热力图 / 风险四象限 | 中 | M (2-3 天) | 因子暴露 + 回撤/波动/胜率/盈亏比 |
| Won't（本轮不做） | 完整 Docker 镜像 + compose app 服务 | 高 | M (2-3 天) | 按"最后做"要求排至四项目标收口阶段；草案已就绪 |

> 工作量：S ≤2 天，M 3-5 天，L >1 周（仅估算，不含联调）。

## 四、决策记录（本轮新增）

- **命令面板优先于网格**：命令面板以最小依赖解决 SPA 深层路由跳转效率问题，验证成本最低，故排 Must。
- **网格选 `grid-layout-plus`**：Vue3 原生、API 与 `react-grid-layout` 一致、社区活跃度高于 `GridStack.js` 的 Vue 封装；移动端回退单列可控。
- **镜像仍选 FastAPI 直托**：与现有 `web_app.py` 的 `/assets` + `/spa/*` fallback 一致，单镜像零 CORS 最简部署；Nginx 分离仅在需 CDN 时再引入。
- **持久化不引入 Prisma**：当前仅 `stock_daily` 单表，Alembic 最小骨架足够，避免 ORM 迁移成本。

## 五、参考链接

- FreqUI / freqtrade: https://github.com/freqtrade/frequi · https://www.freqtrade.io/en/stable/freq-ui/ · Grafana Dashboard 14632
- QuantConnect Lean: https://github.com/QuantConnect/Lean · https://www.lean.io/
- NautilusTrader: https://nautilustrader.io/ · https://pypi.org/project/nautilus_trader/ · https://github.com/Black101081/Nautilus-Web-Interface
- vectorbt: https://vectorbt.dev/ · https://vectorbt.pro/
- vnpy: https://github.com/vnpy/vnpy · https://www.vnpy.com/docs/
- QUANTAXIS: https://github.com/yutiansut/QUANTAXIS · https://yutiansut.github.io/QUANTAXIS/
- Element Plus Dark Mode: https://element-plus.org/en-US/guide/dark-mode
- shadcn/vue Sidebar: https://www.shadcn-vue.com/docs/components/sidebar
- vue-command-palette: https://github.com/xiaoluoboding/vue-command-palette · https://vue-command-palette.vercel.app/
- Vuetify Command: https://vuetifyjs.com/en/components/command-palettes/
- grid-layout-plus: https://grid-layout-plus.netlify.app/ · vue-responsive-grid-layout: https://github.com/gwinnem/vue-responsive-grid-layout · GridStack: https://blog.prototypr.io/grid-layout-editor-for-vue-js-a-research-project-for-pariksha-io-e3445025d21e
- OpenBB Dashboards: https://docs.openbb.co/workspace/analysts/dashboards · Ghostfolio Changelog: https://ghostfol.io/en/about/changelog
- Docker Compose Services: https://docs.docker.com/compose/compose-file/05-services/
- Ghostfolio docker-compose: https://github.com/ghostfolio/ghostfolio/blob/main/docker/docker-compose.yml
- Supabase Self-hosting: https://supabase.com/docs/guides/self-hosting/docker
- Outline Docker: https://docs.getoutline.com/s/hosting/doc/docker-7pfeLP5a8t
- Redis + FastAPI: https://redis.io/docs/latest/integrate/fastapi/
- Alembic: https://alembic.sqlalchemy.org/
- Docker Building best practices: https://docs.docker.com/build/building/best-practices/
- FastAPI Containers: https://fastapi.tiangolo.com/deployment/docker/
- Python Speed Multi-stage: https://pythonspeed.com/articles/multi-stage-docker-python/
- Slimmer FastAPI Docker: https://davidmuraya.com/blog/slimmer-fastapi-docker-images-multistage-builds/
