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
- **Optional PostgreSQL + Redis cache** (one-command `docker-compose.yml`): Redis hot cache + PG persistence, read order Redis → PG → CSV → network; silently degrades to pure network mode when unavailable.
- Market data is cached locally under `stock_data/`.

### Vue3 SPA (`/spa/*`, modern frontend)
- **Collapsible grouped sidebar navigation** (Overview / Backtest Research / Data Insights / Strategy Management) + breadcrumbs + **dark mode** (Element Plus `html.dark`).
- **Rich homepage**: quick action entries, market index strip, **watchlist panel** (add/remove, live price & change — red-up/green-down for A-shares, green-up/red-down for US; click to switch the main chart), **recent backtests** (summary + one-click re-run with parameter refill), top sectors / news / recommendations.
- **Dynamic ECharts**: zoomable equity/drawdown/daily-return charts; candlestick + volume K-line board.
- **SPA-exclusive pages**: strategy comparison (2–5 strategies overlaid with a metrics table) and factor analysis (IC series / quantile cumulative returns / monotonicity).
- **Browser-local persistence** (zero-dependency Pinia plugin, `emoqunt:`-prefixed localStorage): UI preferences (theme/sidebar), watchlist, backtest history & last form, AI chat history — all survive a refresh.
- **AI investment assistant**: global drawer chat panel, LangGraph ReAct agent, SSE streaming, Markdown rendering, visible tool calls.

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
│       ├── stores/         # Pinia stores (chat/ui/watchlist/backtestHistory + persist plugin)
│       ├── api/            # axios wrapper + SSE parsing + type definitions
│       └── layouts/        # Sidebar + breadcrumb + dark-mode layout
├── nes_data/               # Sentiment data & snapshots (sentiment_results/{YYYYMMDD}.json)
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

### SPA Home (light) — sidebar nav / index strip / watchlist / K-line board
![SPA Home (light)](docs/screenshots/spa-home-light.png)

### SPA Home (dark mode) — persists across reloads
![SPA Home (dark)](docs/screenshots/spa-home-dark.png)

### SPA Backtest Result — dynamic equity/drawdown/return charts + metric cards + risk panel
![SPA Backtest Result](docs/screenshots/spa-backtest.png)

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
docker compose up -d         # PostgreSQL 16 + Redis 7; connection params in .env
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

- **Backend**: FastAPI + Uvicorn + Jinja2; data-heavy handlers threadpooled
- **SPA frontend**: Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia (with a homegrown localStorage persistence plugin)
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
