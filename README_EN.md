# EmoQunt Quant System

> English | [中文](README.md)

An intelligent quantitative-investment backtesting platform driven by sentiment analysis, supporting **both A-shares and US stocks**. It fuses sector-sentiment factors, realistic transaction costs and benchmark comparisons into a one-stop web experience spanning strategy construction, backtesting, factor analysis and risk management — with **a modern Vue3 SPA** and a classic Jinja2 frontend side by side.

## Features

### Backtesting Engine
- **Dual-market cost models**: A-share `AShareCommInfo` (commission both sides with a 5 RMB minimum, stamp duty sell-side only 0.05%, transfer fee both sides 0.001%) and US `USStockCommInfo` (symmetric commission, no stamp duty), routed automatically by the `market` parameter.
- **Benchmark & risk-adjusted returns**: automatically fetches the CSI 300 (A-shares) or S&P 500 (US) benchmark, computes Alpha / Beta / Information Ratio, and overlays the benchmark curve on the charts.
- **Sentiment-filtered strategy**: moving-average crossover signals can be filtered by historical sentiment snapshots ("most recent snapshot on or before the backtest day" — no look-ahead bias).
- **Trade-level win rate**: computed from closed trades (`tradeanalyzer.won/lost`).
- **Performance & risk analytics**: total/annualized return, Sharpe, max drawdown, Calmar, VaR/CVaR, downside deviation, and stress-test scenarios.

### Data Layer (multi-source failover)
- **A-share fallback chain**: Tushare Pro (optional, needs `TUSHARE_TOKEN`) → akshare Sina → Eastmoney → baostock, degrading automatically on failure.
- **US two-tier fallback**: yfinance (primary) → akshare Sina.
- **Optional PostgreSQL + Redis cache** (one-command `docker-compose.yml` via domestic mirror `docker.m.daocloud.io`, optional `REDIS_PASSWORD`): Redis hot cache + PG persistence, read order Redis → PG → CSV → network; silently degrades to pure network mode when unavailable. PG supports optional `psycopg_pool` connection pool + tiered TTL (today 300s / history 7d ±jitter).
- Market data is cached locally under `stock_data/`; sentiment snapshots live at `nes_data/sentiment_results/{YYYYMMDD}.json` and feed the homepage sentiment calendar via `GET /api/sentiment/calendar` (local-only, threadpooled).
- **Data-source health beats**: every fetch layer records success/failure where the request is actually made (`GET /api/data/source-health`, in-process, last 7 attempts per source), rendered as the homepage heartbeat bar.

### Vue3 SPA (`/spa/*`, modern frontend)
- **Collapsible grouped sidebar navigation** (Overview / Backtest Research / Data Insights / Strategy Management) + breadcrumbs + **dark mode** (Element Plus `html.dark`) + **global command palette `Cmd+K`** + **top tab bar** + **sidebar favorites** + **first-visit tour** (driver.js, 7 steps, shown once with a replay button).
- **Rich homepage**: quick action entries, market index strip (inline sparklines; click to open the main chart), **watchlist panel** (add/remove, inline sparklines, animated price & change flash — red-up/green-down for A-shares, green-up/red-down for US; click to switch the main chart), **recent backtests** (summary + one-click re-run with parameter refill), top sectors / news (**news source filter tabs** + source badges) / recommendations (click to drill into the main chart), **allocation donut** (market / daily change / industry dimensions), **data-source health heartbeat bar**, **sentiment calendar** (driven by `sentiment_results/{YYYYMMDD}.json`) and **draggable grid layout** (persisted as `emoqunt:homeLayout`); quotes refresh via **SWR-style polling** (paused when hidden, exponential backoff on failures).
- **Dynamic ECharts**: zoomable equity/drawdown/daily-return charts; candlestick + volume K-line board with MA/BOLL overlays, MACD/KDJ/RSI sub-panels, last-price line, pinned tooltip panel and month-boundary ticks; **backtest trade markers** (backend `trades` passthrough, B/S arrows + weighted average-cost line, chart range aligned with the backtest dates).
- **SPA-exclusive pages**: strategy comparison (2–5 strategies overlaid with a metrics table) and factor analysis (IC series / quantile cumulative returns / monotonicity).
- **Browser-local persistence** (zero-dependency Pinia plugin, `emoqunt:`-prefixed localStorage): UI preferences (theme/sidebar/tour flag), watchlist, backtest history & last form, AI chat history, favorites/tabs/home layout — all survive a refresh.
- **AI investment assistant**: global drawer chat panel, LangGraph ReAct agent, SSE streaming, Markdown rendering, visible tool calls, and **tool-result cards** (Generative UI: quote/index/sentiment/recommendation/backtest/signal cards with a pending skeleton; one click opens the chart on the homepage or the related page).

### Classic Jinja2 Frontend (`/`, server-rendered)
- **Unified design system**: `base.html` + `app.css` design tokens, Bootstrap 5.3 + Font Awesome 6.
- **8 pages**: home, backtest (form + result), strategy management (create/edit/delete; read-only in the SPA), sentiment analysis (with per-stock entry), daily recommendations, error page.
- The backtest form **remembers your last input** (localStorage; URL preselection wins).

### Other
- **Sentiment analysis**: sector-sentiment scores and per-stock trading signals from TrendRadar real-time trending news.
- **Daily recommendations**: ranked picks combining sentiment with a multi-factor model (price change / volume / sentiment / technical shape).
- **Strategy management**: dynamic strategy creation from JSON config with template-parameter editing.
- **Test coverage**: pytest covers the cost model, parameter parsing, performance metrics, Alpha/Beta, data sources, strategy management, notification formatting and more (400+ cases).

## System Architecture

```
EmoQunt/
├── config/                 # Configuration (config.yaml + QDT_-prefixed env overrides)
├── docs/
│   ├── research/           # UI research & decision records
│   └── screenshots/        # README screenshots + capture script
├── frontend/               # Vue3 SPA (Vite + TS + Element Plus + ECharts + Pinia)
│   └── src/
│       ├── views/          # Home/Backtest/Strategies/Sentiment/Recommend/Compare/Factor
│       ├── stores/         # Pinia stores (chat/ui/watchlist/backtestHistory/favorites/tabs/homeLayout + persist plugin)
│       ├── api/            # axios wrapper + SSE parsing + type definitions
│       ├── components/     # CommandPalette/AppTabs/SentimentCalendar/ChatPanel, etc.
│       └── layouts/        # Sidebar (with favorites) + breadcrumbs + tabs + dark/command palette layout
├── nes_data/               # Sentiment data & snapshots (sentiment_results/{YYYYMMDD}.json, feeds the homepage calendar & backtest sentiment filter)
├── src/
│   ├── agent/              # LangGraph ReAct investment assistant
│   ├── Strategy/           # Strategy base + dynamic factory + sentiment filter + user strategies
│   ├── analysis/           # Factor analysis (IC / quantiles / monotonicity)
│   ├── backtest/           # Backtest engine + performance analyzer + cost models
│   ├── data/               # Data management: fallback chain + db.py (PG/Redis cache) + column contract
│   ├── factor/             # Sentiment/technical/market factors + daily recommendations
│   ├── risk/               # Risk management (sizing / stop-loss / VaR / stress tests)
│   ├── services/           # Thin service-orchestration layer
│   └── utils/              # Paths / logger / validators / env
├── test/                   # pytest suite
├── web/                    # Classic Jinja2 frontend (templates + static)
├── docker-compose.yml      # Optional: PostgreSQL 16 + Redis 7 cache layer
└── web_app.py              # Entry point (FastAPI, both frontends + unified /api)
```

## Page Previews

> Screenshots are captured locally via `conda run -n qdt python docs/screenshots/_capture.py` against the source stack (`web_app.py` + `db/cache`); all shots are from the 2026-08 round-4 iteration (first-visit tour, AI tool-result cards, backtest trade markers, allocation donut, data-source heartbeats, news source filter).

### SPA Home (light) — 10 draggable cards: quick entries / index strip (sparklines) / market breadth / K-line board / sector heatmap / top sectors / news source filter / recommendations / allocation donut / source heartbeats + sentiment calendar
![SPA Home (light)](docs/screenshots/spa-home-light.png)

### First-visit tour — driver.js, 7 steps (shown once, replayable from the layout toolbar)
![First-visit tour](docs/screenshots/spa-home-tour.png)

### SPA K-line board — candles + MA/BOLL overlays + last-price line + MACD/KDJ/RSI sub-panels + period/adjust switching + month-boundary ticks
![SPA K-line board](docs/screenshots/spa-kline.png)

### SPA K-line (weekly) — server-side aggregation, three linked panes
![SPA K-line weekly](docs/screenshots/spa-kline-week.png)

### SPA Home (dark mode) — persists across reloads
![SPA Home (dark)](docs/screenshots/spa-home-dark.png)

### SPA Backtest Result — metrics + backtest K-line trade markers + dynamic equity/drawdown/return charts + risk panel
![SPA Backtest Result](docs/screenshots/spa-backtest.png)

### Backtest K-line trade markers — B/S arrows with market-aware colors + weighted average-cost line, aligned with the backtest date range
![Backtest trade markers](docs/screenshots/spa-backtest-trades.png)

### AI tool-result card — Generative UI: quote card with one-click "open on homepage"
![AI tool-result card](docs/screenshots/spa-chat-tool-card.png)

### SPA Strategy List
![SPA Strategy List](docs/screenshots/spa-strategies.png)

### Classic Sentiment Analysis (Jinja2, `/sentiment`)
![Sentiment Analysis](docs/screenshots/web-sentiment.png)

## Quick Start

### Requirements
- Python 3.11+ (conda recommended) + Node.js 18+ (only for building the SPA)
- Network access (akshare market data, TrendRadar news, LLM API)

### Install Dependencies
```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build   # build the SPA (otherwise /spa/* returns 503)
```

### Configuration
1. Copy `.env.example` → `.env` and fill in the LLM `API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` (needed by the AI assistant and sentiment analysis); optionally set `TUSHARE_TOKEN` to enable the primary Tushare data tier.
2. Edit `config/config.yaml` to tune backtest/risk parameters.

### Start the Service
```bash
python web_app.py            # http://127.0.0.1:8000
```
- Classic frontend: http://localhost:8000/
- **Vue3 SPA**: http://localhost:8000/spa/
- SPA dev mode: `cd frontend && npm run dev`, then open http://localhost:5173/spa/ (`/api` is proxied to port 8000)

### Optional: enable the database cache layer
```bash
docker compose up -d         # PostgreSQL 16 + Redis 7 (via domestic mirror docker.m.daocloud.io); connection params in .env
# Pip also defaults to a domestic mirror; override with --build-arg PIP_INDEX_URL if needed
```

### Run Tests
```bash
pytest test/test_backtest.py -v
```

## Pages

**Vue3 SPA (`/spa/*`)**

| Route | Purpose |
|-------|---------|
| `/spa/` | Home dashboard: quick actions, index strip, watchlist, K-line board, recent backtests, sectors/news/recommendations |
| `/spa/backtest` | Backtest (form memory + dynamic charts + risk analysis; supports `?historyId=` refill) |
| `/spa/strategies` | Strategy list (view/delete) |
| `/spa/sentiment` | Sentiment analysis (news + sector scores) |
| `/spa/daily-recommend` | Daily recommendations |
| `/spa/strategy-compare` | Strategy comparison (2–5 equity curves + metrics table) |
| `/spa/factor-analysis` | Factor analysis (IC / quantile backtests / monotonicity) |

**Classic (Jinja2)**

| Route | Purpose |
|-------|---------|
| `/` | Home — feature entries and system highlights |
| `/backtest` | Backtest form (supports `?strategy_name=` preselection; remembers last input) |
| `/run_backtest` | Backtest result (metric cards + equity/drawdown/dashboard charts) |
| `/strategies` | Strategy list — create/edit/delete custom strategies |
| `/sentiment` | Sentiment analysis (trending news + sector scores + per-stock entry) |
| `/analyze_sentiment` | Per-stock sentiment result (signal, scores, distribution chart) |
| `/daily_recommend` | Daily recommendations (Top-3 sectors + ranked stock table) |

## API

Both frontends share the same `/api/*` endpoints (data-heavy handlers run in a threadpool, so slow data sources never block other requests).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (includes PG/Redis cache connectivity) |
| `/api/strategies` / `list` / `detail/{name}` / `templates` | GET | Strategy queries |
| `/api/strategies/create_new` / `create_from_template` | POST | Create strategies |
| `/api/strategies/{name}` | PUT / DELETE | Update / delete a strategy |
| `/api/backtest/run` | POST | Run a backtest, returns JSON time series (for ECharts) |
| `/api/strategies/compare` | POST | Compare multiple strategies |
| `/api/factor/analyze` | POST | Factor IC / quantile analysis |
| `/api/kline` | GET | K-line OHLCV (`stock_code` / `market` / `days`) |
| `/api/sentiment` / `sentiment/data` | GET | Sentiment data |
| `/api/sentiment/calendar` | GET | Sentiment calendar (scans local `sentiment_results/*.json` for the homepage calendar) |
| `/api/daily-recommend` (`/refresh`) | GET | Daily recommendations (force refresh) |
| `/api/agent/chat` | POST | AI assistant (SSE streaming) |
| `/api/agent/chat/sync` | POST | AI assistant (non-streaming) |

## Backtesting Engine Highlights

### Transaction Costs
- **A-shares** (`AShareCommInfo`): commission both sides (default 3 bps, 5 RMB minimum per trade), stamp duty **sell-side only** 0.05%, transfer fee both sides 0.001%, configurable slippage (default 0.05%).
- **US stocks** (`USStockCommInfo`): symmetric commission, no stamp duty or transfer fee.

### Benchmark & Risk-Adjusted Returns
- Fetches the benchmark automatically by market (A-share = CSI 300, US = S&P 500).
- Computes Alpha / Beta (covariance method) and the Information Ratio; draws the benchmark curve on the charts.

### Sentiment Filter
- Scans `nes_data/sentiment_results/*.json` snapshots and builds a "snapshot-date × sector" sentiment panel.
- On a given backtest day, only the most recent historical snapshot on or before that day is used — **no look-ahead bias**.
- When `use_sentiment_filter=True`, a golden-cross buy requires sector sentiment ≥ −threshold, and a death-cross sell requires ≤ threshold.

## Tech Stack

- **Backend**: FastAPI + Uvicorn + Jinja2; data-heavy handlers threadpooled; optional `psycopg_pool` pool + cache layer
- **SPA frontend**: Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia (with a homegrown localStorage persistence plugin, including a draggable home grid with persisted layout)
- **Classic frontend**: Bootstrap 5.3 + Font Awesome 6
- **Data**: akshare / Tushare Pro (optional) / baostock / yfinance; optional PostgreSQL 16 + Redis 7 cache
- **Backtesting**: backtrader + custom dual-market cost models
- **Analysis**: pandas, numpy, scipy, scikit-learn
- **Visualization**: ECharts (SPA), matplotlib / seaborn / plotly (server-side)
- **AI**: OpenAI-compatible LLM + LangChain + LangGraph (ReAct agent)
- **Testing**: pytest

## Configuration

The config file is at `config/config.yaml` (overridable via `QDT_`-prefixed env vars), including:
- `backtest`: initial capital, commission rate, slippage toggle and rate
- `risk_management`: max daily loss, max drawdown, leverage, position/sector exposure limits
- `data` / `strategy` / `factor` and other module parameters

## Strategy Management

You can create custom strategies via the web UI or by editing `src/Strategy/user_strategies/strategies.json` directly, configuring parameters on the `sentiment_ma` (sentiment moving-average) template.

## Notes

- The first backtest fetch of market/index data requires network access (results are cached; the fallback chain switches sources automatically when one is flaky).
- Sentiment analysis needs a valid LLM API key.
- On first run the system auto-creates `logs/`, `output/`, `nes_data/`, etc.
- If the SPA is not built (`frontend/dist` missing), `/spa/*` returns a 503 hint.
- Backtest results are for reference only and do not constitute investment advice.

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under [MIT](LICENSE).
