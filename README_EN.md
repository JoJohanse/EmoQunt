<div align="center">

# 📈 EmoQunt

**Sentiment-driven A-share / US-stock quantitative backtesting platform**

中文 | [English](README_EN.md)

A one-stop web experience for strategy building, backtesting, factor analysis and performance/risk
management — with industry sentiment factors and realistic trading costs. Ships with a modern
**Vue3 SPA** (`/spa/*`) and a classic Jinja2 frontend (`/`).

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![backtrader](https://img.shields.io/badge/backtrader-engine-8A2BE2)
![Vue](https://img.shields.io/badge/Vue%203-4FC08D?logo=vuedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![ECharts](https://img.shields.io/badge/ECharts-charts-AA344D)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

## 🖼 Screenshots

> Captured automatically via `conda run -n qdt python docs/screenshots/_capture.py` against the local source stack; all shots are from the 2026-08 round-4 iteration.

<table>
  <tr>
    <td colspan="2" align="center">
      <img src="docs/screenshots/spa-home-light.png" alt="SPA home dashboard" width="100%"/><br/>
      <b>SPA home dashboard</b> — 10 draggable cards: quick entries · index strip (sparklines) · market breadth · K-line board · sector heatmap · top sectors · news source filter · recommendations · allocation donut · data-source heartbeats + sentiment calendar
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-kline.png" alt="K-line board" width="100%"/><br/>
      <b>K-line board</b> — candles + MA/BOLL overlays + MACD/KDJ/RSI sub-panels + last-price line + month-boundary ticks, day/week/month &amp; adjust switching
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-backtest-trades.png" alt="Backtest trade markers" width="100%"/><br/>
      <b>Backtest K-line trade markers</b> — backend <code>trades</code> passthrough, B/S arrows + weighted average-cost line, aligned with the backtest date range
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-home-tour.png" alt="First-visit tour" width="100%"/><br/>
      <b>First-visit tour</b> — driver.js, 7 steps; shown once, replayable
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-chat-tool-card.png" alt="AI tool card" width="100%"/><br/>
      <b>AI tool-result card</b> — Generative UI: quote card with one-click "open on homepage"
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-home-dark.png" alt="Dark mode" width="100%"/><br/>
      <b>Dark mode</b> — persists across reloads
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-backtest.png" alt="Backtest result" width="100%"/><br/>
      <b>Backtest result</b> — metric cards + dynamic equity/drawdown/return charts + risk panel
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-kline-week.png" alt="Weekly K-line" width="100%"/><br/>
      <b>Weekly K-line</b> — server-side aggregation, three linked panes
    </td>
    <td width="50%" valign="top">
      <img src="docs/screenshots/spa-strategies.png" alt="Strategy list" width="100%"/><br/>
      <b>Strategy list</b>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="docs/screenshots/web-sentiment.png" alt="Sentiment analysis" width="100%"/><br/>
      <b>Classic sentiment analysis</b> (Jinja2, <code>/sentiment</code>)
    </td>
  </tr>
</table>

---

## ✨ Features

### 🧮 Backtesting engine
- **Dual-market cost models**: A-share `AShareCommInfo` (two-sided commission with 5 RMB minimum, sell-side-only 0.05% stamp duty, 0.001% transfer fee) vs US `USStockCommInfo` (symmetric commission); slippage always on (rate configurable)
- **Benchmark & risk-adjusted returns**: CSI 300 (A-share) / S&P 500 (US) benchmarks with Alpha / Beta / Information Ratio and overlay curves
- **Sentiment-filtered strategies**: crossover signals filtered by historical sentiment snapshots ("latest snapshot on or before the day" — look-ahead safe)
- **Trade-level win rate & trade markers**: per-fill `trades` passed to the SPA, rendered as B/S arrows plus an average-cost line on the backtest K-line
- **Performance & risk analytics**: total/annualized return, Sharpe, max drawdown, Calmar, VaR/CVaR, downside deviation, stress-test scenarios

### 🗄 Data layer (multi-source failover)
- **A-share fallback chain**: Tushare Pro (optional, needs `TUSHARE_TOKEN`) → akshare Sina → Eastmoney → baostock, driven by a unified FetchRunner with automatic degradation
- **US two-tier fallback**: yfinance (primary) → akshare Sina
- **Data-source health beats**: every fetch layer records success/failure (in-process, last 7 per source) exposed at `GET /api/data/source-health` and rendered as a homepage heartbeat bar
- **Optional PostgreSQL + Redis cache** (one-command `docker-compose.yml`): read order Redis → PG → CSV → network; silently degrades to pure network mode
- Market data cached under `stock_data/`; sentiment snapshots at `nes_data/sentiment_results/{YYYYMMDD}.json` feed the homepage calendar and the backtest sentiment filter

### 🖥 Vue3 SPA (`/spa/*`)
- **Navigation**: collapsible grouped sidebar + breadcrumbs + dark mode + global command palette `Cmd+K` + top tab bar + sidebar favorites + first-visit tour (driver.js, replayable)
- **Home dashboard**: quick entries, index strip (inline sparklines; click to open the chart), watchlist panel (add/remove, inline sparklines, animated price & change flash; click to switch chart), recent backtests (one-click re-run with parameter refill), top sectors, news with source filter tabs, recommendations (click to drill into the chart), allocation donut (market / daily change / industry), data-source heartbeat bar, sentiment calendar; **draggable grid layout** persisted; SWR-style polling for quotes
- **Dynamic ECharts**: equity/drawdown/daily-return curves; candlestick K-line + volume + indicator overlays + pinned tooltip panel
- **SPA-exclusive pages**: strategy comparison (overlaid equity + metrics table), factor analysis (IC / quantile returns / monotonicity)
- **Browser-local persistence**: UI prefs, watchlist, backtest history & form, AI chat, favorites/tabs/layout/K-line preferences — all survive a refresh
- **AI investment assistant**: global drawer chat, LangGraph ReAct agent, SSE streaming + Markdown; **tool-result cards** (quote/sentiment/recommendation/backtest/signal, one click opens the chart)

### 🧾 Classic Jinja2 frontend (`/`)
- `base.html` + `app.css` design tokens, Bootstrap 5.3 + Font Awesome 6; 8 pages; the backtest form remembers your last input

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.11+ (conda recommended) + Node.js 18+ (only for building the SPA)
- Network access (akshare quotes, TrendRadar news, LLM API)

### 2. Install
```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build   # build the SPA (/spa/* returns 503 without it)
```

### 3. Configure
```bash
cp .env.example .env    # fill in LLM API_KEY / LLM_MODEL / LLM_BASE_URL (AI assistant & sentiment)
                        # optional TUSHARE_TOKEN enables the primary Tushare data tier
```
Backtest/risk parameters live in `config/config.yaml` (overridable via `QDT_`-prefixed env vars).

### 4. Run
```bash
python web_app.py            # http://127.0.0.1:8000
```
- Classic frontend: http://localhost:8000/
- **Vue3 SPA**: http://localhost:8000/spa/
- SPA dev mode: `cd frontend && npm run dev` → http://localhost:5173/spa/ (`/api` proxied)

### 5. Optional: database cache layer
```bash
docker compose up -d         # PostgreSQL 16 + Redis 7 (via domestic mirror docker.m.daocloud.io)
```

### 6. Tests
```bash
pytest test/test_backtest.py -v    # pick test files explicitly (test/ also contains manual scripts)
```

---

## 🧭 Usage

### Vue3 SPA routes

| Route | Purpose |
|-------|---------|
| `/spa/` | Home dashboard: quick entries, index strip, watchlist, K-line board, recent backtests, sectors/news/recommendations, allocation donut, source heartbeats |
| `/spa/backtest` | Backtest (form memory + dynamic charts + trade markers + risk analysis; supports `?historyId=` refill) |
| `/spa/strategies` | Strategy list (view/delete) |
| `/spa/sentiment` | Sentiment analysis (news + sector scores) |
| `/spa/daily-recommend` | Daily recommendations |
| `/spa/strategy-compare` | Strategy comparison (2–5 equity curves + metrics table) |
| `/spa/factor-analysis` | Factor analysis (IC / quantile backtests / monotonicity) |

### Classic (Jinja2) routes

| Route | Purpose |
|-------|---------|
| `/` | Home — feature entries and system highlights |
| `/backtest` · `/run_backtest` | Backtest form and result (metric cards + equity/drawdown/dashboard charts) |
| `/strategies` | Strategy list — create/edit/delete custom strategies |
| `/sentiment` · `/analyze_sentiment` | Sentiment analysis and per-stock sentiment result |
| `/daily_recommend` | Daily recommendations (Top-3 sectors + ranked stock table) |

### API

<details>
<summary><b>Expand API list</b> (both frontends share the same <code>/api/*</code> endpoints; data-heavy handlers run in a threadpool)</summary>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (includes PG/Redis cache connectivity) |
| `/api/strategies` / `list` / `detail/{name}` / `templates` | GET | Strategy queries |
| `/api/strategies/create_new` / `create_from_template` | POST | Create strategies |
| `/api/strategies/{name}` | PUT / DELETE | Update / delete a strategy |
| `/api/backtest/run` | POST | Run a backtest, returns JSON time series (incl. per-fill `trades`) |
| `/api/strategies/compare` | POST | Compare multiple strategies |
| `/api/factor/analyze` | POST | Factor IC / quantile analysis |
| `/api/kline` | GET | K-line OHLCV (`days` for recent window, or `start_date/end_date` range mode) |
| `/api/sentiment` / `sentiment/data` | GET | Sentiment data |
| `/api/sentiment/calendar` | GET | Sentiment calendar |
| `/api/daily-recommend` (`/refresh`) | GET | Daily recommendations |
| `/api/market/breadth` / `sectors` | GET | Market breadth / sector board |
| `/api/data/source-health` | GET | Data-source health beats (last 7 attempts per source) |
| `/api/agent/chat` | POST | AI assistant (SSE streaming) |
| `/api/agent/chat/sync` | POST | AI assistant (non-streaming) |

</details>

---

## 🏗 Architecture

<details>
<summary><b>Expand directory tree</b></summary>

```
EmoQunt/
├── config/                 # Configuration (config.yaml + QDT_-prefixed env overrides)
├── docs/
│   ├── research/           # UI research & decision records
│   └── screenshots/        # README screenshots + capture script
├── frontend/               # Vue3 SPA (Vite + TS + Element Plus + ECharts + Pinia)
│   └── src/
│       ├── views/          # Home/Backtest/Strategies/Sentiment/Recommend/Compare/Factor
│       ├── stores/         # Pinia stores (chat/ui/watchlist/backtestHistory/favorites/tabs/homeLayout/klinePrefs + persist plugin)
│       ├── api/            # axios wrapper + SSE parsing + type definitions
│       ├── chart/ lib/     # Candlestick option assembler / color tokens / indicator pure functions
│       ├── components/     # CommandPalette/AppTabs/SentimentCalendar/ChatPanel/ChatToolCard, etc.
│       └── layouts/        # Sidebar (with favorites) + breadcrumbs + tabs + dark/command palette layout
├── nes_data/               # Sentiment data & snapshots (sentiment_results/{YYYYMMDD}.json)
├── src/
│   ├── agent/              # LangGraph ReAct investment assistant
│   ├── Strategy/           # Strategy base + dynamic factory + sentiment filter + user strategies
│   ├── analysis/           # Factor analysis (IC / quantiles / monotonicity)
│   ├── backtest/           # Backtest engine + performance analyzer + cost models + trade recorder
│   ├── data/               # Data management: FetchRunner fallback chain + db.py (PG/Redis cache) + SnapshotStore
│   ├── factor/             # Sentiment/technical/market factors + daily recommendations
│   ├── risk/               # Risk management (sizing / stop-loss / VaR / stress tests)
│   ├── services/           # Thin service-orchestration layer
│   └── utils/              # Paths / logger / validators / env / serialization / TTL cache
├── test/                   # pytest suite
├── web/                    # Classic Jinja2 frontend (templates + static)
├── docker-compose.yml      # Optional: PostgreSQL 16 + Redis 7 cache layer
└── web_app.py              # Entry point (FastAPI, both frontends + unified /api)
```

</details>

### Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn + Jinja2 (threadpooled data handlers); optional `psycopg_pool` + cache layer |
| SPA frontend | Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia (zero-dependency localStorage persist plugin) |
| Classic frontend | Bootstrap 5.3 + Font Awesome 6 |
| Data | akshare / Tushare Pro (optional) / baostock / yfinance; optional PostgreSQL 16 + Redis 7 |
| Backtesting | backtrader + custom dual-market cost models |
| Analysis & viz | pandas, numpy, scipy, scikit-learn; ECharts (SPA), matplotlib / seaborn / plotly (server) |
| AI | OpenAI-compatible LLM + LangChain + LangGraph (ReAct agent) |
| Testing | pytest (500+ cases) |

---

## 📝 Backtesting engine highlights

### Transaction costs
- **A-shares** (`AShareCommInfo`): commission both sides (default 3 bps, 5 RMB minimum per trade), stamp duty **sell-side only** 0.05%, transfer fee both sides 0.001%, slippage 0.05% (always on)
- **US stocks** (`USStockCommInfo`): symmetric commission, no stamp duty or transfer fee

### Benchmark & risk-adjusted returns
- Fetches the benchmark automatically by market (A-share = CSI 300, US = S&P 500)
- Computes Alpha / Beta (covariance method) and the Information Ratio; draws the benchmark curve on the charts

### Sentiment filter
- Scans `nes_data/sentiment_results/*.json` historical snapshots (parsed by the single SnapshotStore) into a "snapshot date × industry" sentiment panel
- Each backtest day uses only the latest snapshot **on or before that day** — look-ahead safe
- When enabled, golden-cross buys require sector sentiment ≥ −threshold and death-cross sells ≤ threshold

---

## ⚠️ Notes

- First backtest data fetch needs network access (results are cached; the fallback chain switches automatically when a source misbehaves)
- Sentiment analysis needs a valid LLM API key
- `logs/`, `output/`, `nes_data/` directories are auto-created on first run
- `/spa/*` returns a 503 hint when the SPA is not built (`frontend/dist` missing)
- Backtest results are for reference only and do not constitute investment advice

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

Released under the [MIT](LICENSE) license.
