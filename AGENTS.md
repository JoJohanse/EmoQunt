# AGENTS.md

Guidance for OpenCode agents working in this repo. EmoQunt is a sentiment-driven A-share/US-stock backtesting platform: FastAPI backend + backtrader, with **two coexisting frontends** (Jinja2 templates served at `/`, and a Vue3 SPA served at `/spa/*`). Internal legacy name is "Qdt_test" (appears in `config.yaml`, FastAPI title, `CONTRIBUTING.md`).

## Commands

### Backend / Python
- Run dev server: `python web_app.py` (uvicorn on `127.0.0.1:8000`, single entrypoint)
- Run tests (pick files explicitly — `test/` also contains scratch scripts):
  - `pytest test/test_backtest.py -v`
  - `pytest test/test_trendradar_notify.py -v`
- **No** `pyproject.toml`, `pytest.ini`, `conftest.py`, or Python linter/formatter config exists. CONTRIBUTING.md asks for PEP 8 + Google-style docstrings, but nothing enforces it.
- Python 3.11+ in conda env named **`qdt`** (per `.vscode/settings.json` and `test_backtest.py` docstring).
- Heavy deps: `torch`, `transformers`, `modelscope` are in `requirements.txt` (used by LLM/model layer) — installs are large.

### Frontend (Vue3 SPA, `frontend/`)
- Dev server: `npm run dev` (Vite on `:5173`, proxies `/api` → `127.0.0.1:8000`)
- Build (served by FastAPI in prod): `npm run build` — runs `vue-tsc -b && vite build`, so **type errors fail the build**
- Type-check only: `npm run type-check`
- Build output `frontend/dist/` is auto-served by `web_app.py` at `/assets` + `/spa/*` fallback; if unbuilt, `/spa/*` returns 503.

## Architecture & wiring (non-obvious)

- **Path resolution**: `PROJECT_ROOT` is computed in `src/utils/paths.py` (`parents[2]`). All directory helpers (`get_logs_dir`, `get_output_dir`, `get_config_dir`, `get_stock_data_dir`, `get_web_dir`, `get_frontend_dist_dir`) live there. Never hardcode paths — use these.
- **Env loading order matters**: `src/utils/env.py` loads `.env` idempotently at import time. Entry points and `config/config_loader.py` call `load_env()` at module top *before* any `os.environ.get`. Replicate this pattern in new entry points.
- **Config**: `config/config.yaml` is loaded by the `ConfigLoader` singleton (`get_config()` in `config/config_loader.py`). Env vars with prefix **`QDT_`** override keys (e.g. `QDT_DATA_STORAGE_PATH`). Separate `sentiment_config.yaml` / `scoring_config.yaml` are overridable via `QDT_SENTIMENT_CONFIG_PATH` / `QDT_SCORING_CONFIG_PATH`.
- **Two backtest entrypoints** in `src/backtest/backtest_manager.py`:
  - `run_backtest_with_charts` → returns chart image URLs; used by the Jinja2 `POST /run_backtest`.
  - `run_backtest_json` → returns JSON time series; used by the Vue3 `POST /api/backtest/run`.
- **Two cost models**: `AShareCommInfo` (asymmetric — stamp duty sell-only 0.05%, min commission 5 RMB, transfer fee both sides) and `USStockCommInfo` (symmetric, no stamp duty). Routed by `market` param: `zh_a` (default, CSI300/000300 benchmark) vs `us` (S&P500/SP500).
- **Strategy system**: built-in backtrader strategies are registered in `global_strategy_manager` (`src/Strategy/Strategy.py`). User strategies are JSON in `src/Strategy/user_strategies/strategies.json` based on the `sentiment_ma` template, materialized into classes via `create_user_strategy_class`. Parameter parsing: `extract_param_value` accepts **both** `value` (user-saved) and `default` (template) keys, with `value` winning.
- **Strategy list cache**: `web_app.py` keeps a 5-min in-process cache (`_strategy_cache`). After any strategy mutation (create/update/delete), call `clear_strategy_cache()` — already done in the API handlers; preserve it when adding new mutation paths.
- **`nes_data/trendradar/main.py` is NOT a normal importable module** (no proper package layout). `trendradar.py` *is* importable as `from nes_data.trendradar.trendradar import ...`. Tests load `main.py` via `importlib.util.spec_from_file_location`. Don't `import nes_data.trendradar.main`.
- **Sentiment filter is look-ahead-safe**: backtests use only the snapshot dated on or before the backtest day, from `nes_data/sentiment_results/{YYYYMMDD}.json`. Don't introduce future-snapshot access.
- **Both frontends consume the same `/api/*` endpoints.** Jinja2 routes render server-side (`web/templates/`, `base.html` inheritance, `web/static/css/app.css` design tokens); the Vue3 SPA (`frontend/src/`) calls `/api` via axios and is mounted under `/spa/*`.

## Testing quirks

- No `conftest.py` / `pytest.ini`. `test_backtest.py` manually inserts the project root into `sys.path`; `test_trendradar_notify.py` manually adds `nes_data/trendradar/` to `sys.path`. Keep that when adding tests.
- `test/test_trendradar_notify.py` are **characterization / golden-master tests**: on failure, update the expected value to match current output — do **not** change production `nes_data/trendradar/main.py` to satisfy them.
- `test/test_ak.py` and `test/check_cuda.py` are **manual scratch scripts** (no `test_*` functions). Don't treat them as the test suite.
- `TestSentimentSnapshots` in `test_backtest.py` `pytest.skip`s when no local sentiment snapshots exist, and asserts a specific mapping (e.g. `600938` 中国海油 → `石油行业`). It depends on real snapshot data under `nes_data/sentiment_results/`.

## Runtime / env

- Copy `.env.example` → `.env` (gitignored). Sentiment analysis needs `API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` (OpenAI-compatible; default points at Xiaomi MiMo). `ZHI_TU_API_TOKEN` is referenced for the 智兔 data API.
- First backtest fetch of market/index data needs network access (akshare); results cache to `stock_data/` (subdirs `zh_a/`, `us/`, `stock_cache/`).
- `logs/`, `output/`, `nes_data/sentiment_results/`, `nes_data/trendradar/output/`, `stock_data/zh_a/`, `stock_data/stock_cache/` are gitignored runtime dirs auto-created on first run.

## Workflow

- Branch from `main`; PRs need at least one maintainer approval (per `CONTRIBUTING.md`).
- Codebase is bilingual: Chinese docstrings/comments/log messages + Chinese UI; English identifiers. Match the surrounding style.
