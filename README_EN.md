# EmoQunt Quant System

> English | [中文](README.md)

An intelligent quantitative-investment backtesting platform driven by sentiment analysis. It fuses sector-sentiment factors, realistic A-share transaction costs and a CSI 300 benchmark into a one-stop web experience spanning strategy construction, backtesting and performance analysis.

## Features

### Backtesting Engine
- **Realistic A-share transaction costs**: commission (both sides, with a 5 RMB minimum), stamp duty (sell-side only, 0.05%), transfer fee (both sides, 0.001%) and slippage modelling.
- **Benchmark & risk-adjusted returns**: automatically fetches the CSI 300 index, computes Alpha / Beta / Information Ratio, and overlays the benchmark curve on the charts.
- **Sentiment-filtered strategy**: the strategy's moving-average crossover signal can be filtered by historical sentiment snapshots ("most recent snapshot on or before the backtest day" — no look-ahead bias).
- **Trade-level win rate**: the win rate is computed from closed trades (`tradeanalyzer.won/lost`) instead of the incorrect "fraction of profitable days".
- **Performance analyzer**: total/annualized return, Sharpe ratio, max drawdown, Calmar ratio, VaR/CVaR, downside deviation, and more.

### Web Frontend
- **Unified design system**: built on a `base.html` base template + `app.css` design tokens (CSS variables), giving the whole site a consistent navbar, footer and purple-gradient theme.
- **8 pages**: home, backtest (form + result), strategy management, sentiment analysis (with per-stock entry), daily recommendations, error page.
- **Consistent stack**: Bootstrap 5.3 + Font Awesome 6 + Jinja2 template inheritance.
- **Responsive**: working mobile hamburger menu and adaptive cards.

### Other
- **Sentiment analysis**: generates sector-sentiment scores and per-stock trading signals from TrendRadar real-time trending news.
- **Daily recommendations**: combines sentiment with a multi-factor model (price change / volume / sentiment / technical shape) for ranked stock picks.
- **Strategy management**: dynamically creates strategies from JSON config, with template-parameter editing.
- **Test coverage**: pytest covers the cost model, parameter parsing, performance metrics, Alpha/Beta, and the sentiment panel.

## System Architecture

```
EmoQunt/
├── config/                 # Configuration
│   ├── config.yaml         # Main config
│   └── config_loader.py    # Config loader
├── nes_data/               # Sentiment data & snapshots
│   └── sentiment_results/  # Historical sentiment snapshots ({YYYYMMDD}.json)
├── src/                    # Source code
│   ├── Strategy/           # Strategy module
│   │   ├── Strategy.py     # Strategy base + dynamic factory + sentiment filter
│   │   └── strategy_manager.py
│   ├── analysis/           # Factor analysis
│   ├── backtest/           # Backtesting
│   │   └── backtest_manager.py  # AShareCommInfo / PerformanceAnalyzer / BacktestRunner
│   ├── data/               # Data management
│   │   └── data_manager.py      # Stock / get_index_data / sentiment-snapshot loading
│   ├── factor/             # Factor modules
│   │   ├── sentiment.py    # Sentiment factor (LLM scoring)
│   │   ├── technical.py    # Technical factor
│   │   ├── market.py       # Market factor
│   │   └── daily_recommend.py   # Daily recommendations
│   ├── risk/               # Risk management (sizing / stop-loss / VaR)
│   ├── utils/              # Utilities
│   └── visualization.py    # Visualization
├── test/                   # Tests
│   └── test_backtest.py    # Backtest module unit tests
├── web/                    # Web app
│   ├── templates/          # Jinja2 templates (extends base.html)
│   │   ├── base.html       # Base template (navbar/footer/head)
│   │   ├── index.html      # Home
│   │   ├── backtest_form.html / backtest_result.html
│   │   ├── strategies.html
│   │   ├── sentiment_analysis.html / sentiment_result.html
│   │   ├── daily_recommend.html
│   │   └── error.html
│   └── static/
│       ├── css/app.css     # Site-wide design system
│       └── favicon.svg
├── web_app.py              # Entry point (FastAPI)
├── requirements.txt        # Dependencies
└── README.md
```

## Page Previews

### Home
![Home](web/templates/首页.png)

### Strategy Management
![Strategy Management](web/templates/回测策略管理.png)

### Backtest Result
![Backtest Result](web/templates/回测结果.png)

### Daily Recommendations
![Daily Recommendations](web/templates/每日推荐.png)

### Sentiment Analysis
![Sentiment Analysis](web/templates/舆情分析.png)

## Quick Start

### Requirements
- Python 3.11+ (a conda environment is recommended)
- Network access (akshare market data, TrendRadar news, LLM API)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configuration
1. Copy and edit environment variables (e.g. LLM API key)
2. Edit `config/config.yaml` to tune backtest/risk parameters

### Start the Service

```bash
python web_app.py
```

Open http://localhost:8000

### Run Tests

```bash
pytest test/test_backtest.py -v
```

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Home — feature entries and system highlights |
| `/backtest` | Backtest form (supports `?strategy_name=` preselection) |
| `/run_backtest` | Backtest result (metric cards + equity/drawdown/dashboard charts) |
| `/strategies` | Strategy list — create/edit/delete custom strategies |
| `/sentiment` | Sentiment analysis (trending news + sector scores + per-stock entry) |
| `/analyze_sentiment` | Per-stock sentiment result (signal, scores, distribution chart) |
| `/daily_recommend` | Daily recommendations (Top-3 sectors + ranked stock table) |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/strategies` | GET | List strategies |
| `/api/strategies/detail/{name}` | GET | Strategy detail |
| `/api/strategies/create_new` | POST | Create a custom strategy |
| `/api/strategies/create_from_template` | POST | Create a strategy from a template |
| `/api/strategies/templates` | GET | List strategy templates |
| `/api/strategies/{name}` | PUT | Update a strategy |
| `/api/strategies/{name}` | DELETE | Delete a strategy |
| `/api/sentiment` | GET | Sentiment analysis result |

## Backtesting Engine Highlights

### A-share Transaction Costs
Backtesting enables the `AShareCommInfo` cost model by default — far more realistic than backtrader's default symmetric commission:
- Commission: both sides, default 3 bps, 5 RMB minimum per trade
- Stamp duty: **sell-side only**, 0.05%
- Transfer fee: both sides, 0.001%
- Slippage: configurable (default 0.05%)

### Benchmark & Risk-Adjusted Returns
- Automatically fetches the CSI 300 (000300) daily series as the benchmark
- Computes Alpha / Beta (covariance method) and the Information Ratio
- Plots the benchmark curve on the equity chart and dashboard

### Sentiment Filter
- Scans `nes_data/sentiment_results/*.json` snapshots and builds a "snapshot-date × sector" sentiment panel
- Locates the backtest stock's sector via `StockSectorMapper`
- On a given backtest day, only the most recent historical snapshot on or before that day is used — **no look-ahead bias**
- When `use_sentiment_filter=True`, a golden-cross buy requires sector sentiment ≥ −threshold, and a death-cross sell requires ≤ threshold

## Tech Stack

- **Backend**: FastAPI + Uvicorn + Jinja2
- **Frontend**: Bootstrap 5.3 + Font Awesome 6 (shared `base.html` + `app.css` design system)
- **Data**: akshare (A-share market data and indices)
- **Backtesting**: backtrader + custom A-share cost model
- **Analysis**: pandas, numpy, scipy, scikit-learn
- **Visualization**: matplotlib, seaborn, plotly
- **Sentiment**: OpenAI-compatible LLM (SiliconFlow/Qwen) + LangChain
- **Testing**: pytest

## Configuration

The config file is at `config/config.yaml`, including:
- `backtest`: initial capital, commission rate, slippage toggle and rate
- `risk_management`: max daily loss, max drawdown, leverage, position/sector exposure limits
- `data` / `strategy` / `factor` and other module parameters

## Strategy Management

You can create custom strategies via the web UI or by editing `src/Strategy/user_strategies/strategies.json` directly, configuring parameters on the `sentiment_ma` (sentiment moving-average) template.

## Notes

- The first backtest fetch of market/index data requires network access (results are cached under `stock_data/`)
- Sentiment analysis needs a valid LLM API key (configure in `config/config.yaml` or environment variables)
- On first run the system auto-creates `logs/`, `output/`, `nes_data/`, etc.
- Cache files live under `nes_data/` and can be cleared manually as needed
- Backtest results are for reference only and do not constitute investment advice

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under [MIT](LICENSE).
