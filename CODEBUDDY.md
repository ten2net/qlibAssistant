# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Project Overview

A quantitative stock-selection pipeline for A-share CSI300, built on [Microsoft Qlib](https://github.com/microsoft/qlib). It trains 20 models nightly (5 algorithms × 5 rolling lookback windows), filters them by IC metrics, and outputs an ensemble score sheet. Results are served via a VitePress static site backed by GitHub Pages.

## Common Commands

### Python environment
```bash
pip install -r requirements.txt
```

### Tests
Run the full suite with coverage (used by CI/SonarQube):
```bash
pytest --cov=. --cov-report=xml
```

Run a single test file:
```bash
pytest tests/test_utils.py
```

### Data
Update local Qlib data (downloads from `chenditc/investment_data` releases):
```bash
cd ./roll && python ./roll.py data update
```

### Models
Decompress the latest bundled models from `model_pkl/` into `~/.qlibAssistant/mlruns`:
```bash
cd ./roll && python ./roll.py model decompress_mlruns
```

Generate predictions for the latest trade date:
```bash
cd ./roll && python ./roll.py model selection
```

Review historical predictions:
```bash
cd ./roll && python ./roll.py model review
```

Run backtest on historical top-k selections:
```bash
cd ./roll && python ./roll.py model backtest
```

### Training
Train a single model manually:
```bash
cd ./roll && python ./roll.py \
  --pfx_name="EXP" \
  --model_name="LightGBM" \
  --dataset_name="Alpha158" \
  --stock_pool="csi300" \
  --rolling_type="custom" \
  train start_custom
```

Run the CI-style batch training (20 model combinations sequentially):
```bash
cd ./roll && python ../script/run.py
```

### Page (VitePress)
Install deps, generate pages from `qlib_score_csv`, and build:
```bash
cd page && npm ci && npm run docs:build
```

Local dev (also regenerates pages):
```bash
cd page && npm run docs:dev
```

## High-Level Architecture

### Entry point and CLI structure
- `roll/roll.py` is the single CLI entry point. It uses Python `fire.Fire(RollingTrader)` to expose subcommands.
- `RollingTrader` loads `roll/config.yaml`, merges it with CLI kwargs (CLI > YAML > defaults), and binds parameters as instance attributes.
- Three submodules are attached lazily:
  - `self.data` → `DataCLI` (data management, no Qlib init)
  - `self.train` → `TrainCLI` (lazy property, triggers `qlib.init` on first access)
  - `self.model` → `ModelCLI` (lazy property, triggers `qlib.init` on first access)
- This lazy initialization is intentional: pure data operations should not pay the cost of initializing Qlib.

### Training and model storage
- `TrainCLI` uses Qlib's `RollingGen` to produce time-segmented tasks. `my_enhanced_handler_mod` patches `fit_start_time` / `fit_end_time` into handler kwargs after the default rolling logic.
- Training runs inside a `multiprocessing.Process` with `start_method="spawn"` (`run_train_blocking` in `traincli.py`). This isolates Qlib/numpy memory growth and avoids macOS fork safety issues.
- Models are stored as MLflow experiments under `~/.qlibAssistant/mlruns`. Each experiment name follows the pattern: `<pfx>_<ModelClass>_<Dataset>_<Pool>_<rolling>_step<N>_<sfx>_<timestamp>`.
- `model_backup.py` compresses `~/.qlibAssistant/mlruns` into `model_pkl/mlruns_YYYY-MM-DD.tar.gz` (and decompresses back). CI commits these tarballs to `main` and uploads them to GitHub Releases.
- `script/run.py` is the batch trainer used by CI; it iterates over the Cartesian product of `[XGBoost, Linear, DoubleEnsemble, LightGBM, CatBoost]` and rolling windows 1–5 years.

### Model selection and ensemble
- `ModelCLI.get_model_list()` filters experiments by `model_filter` regexes and recorders by required artifacts (`params.pkl`, `sig_analysis`) plus `rec_filter` thresholds (IC, ICIR, Rank IC, Rank ICIR).
- Surviving models are weighted by normalized `Rank ICIR` (`self.rid_weight`).
- `ModelCLI.selection()` calls `analysis()` (predict on the latest date), collects per-model scores, and computes a weighted average (`avg_score`) and positive-ratio (`pos_ratio`) per instrument.
- `filter_ret_df()` applies volatility/momentum filters (STD5/20/60 and ROC10/20/60 thresholds) to produce the `xxx_filter_ret` sheet.
- Output CSVs are written to `~/.qlibAssistant/analysis/selection_YYYYMMDD_HH_MM_SS/`.

### Prediction target
The label being predicted is: `Ref($close, -2)/Ref($close, -1) - 1`. This means: given T-day close data, predict the expected return of buying at T+1 close and selling at T+2 close.

### Review and backtest
- `model_review.py` (`ModelReviewHelper`) implements post-hoc review (`review`) and backtest (`backtest`).
- Review compares predicted scores against realized next-day returns, computing top-k win rates and average returns per selection bucket.
- Backtest simulates daily rebalanced top-k portfolios against CSI300, computes turnover, net returns after fees, and equity curves. Results land in `backtest_csv/` and `review_csv/`.

### Page generation
- `page/script/gen_page.py` scans `qlib_score_csv/` and `backtest_csv/` to generate VitePress Markdown pages under `page/docs/`.
- It also syncs `backtest_csv/*.csv` into `docs/public/backtest_csv/` and generates `nav_curve.md` with `<NavCurveChart>` components (rendered by Lightweight Charts).
- `GEN_PAGE_LIMIT` environment variable caps the number of score directories rendered (CI sets it to `25`).

### GitHub Actions pipeline
1. `train.yml` — scheduled daily at 12:05 UTC (20:05 CST). Downloads data, trains models if needed, compresses `mlruns`, commits tarballs to `main`, and creates a GitHub Release.
2. `analysis.yml` — triggered after Train succeeds. Decompresses models, runs `model selection`, pushes resulting CSVs to the `qlib_score` branch.
3. `review.yml` — triggered after Analysis succeeds. Runs `model review` and `model backtest`, pushes `review_csv/` and `backtest_csv/` to the `qlib_score` branch.
4. `deploy_page.yml` — triggered after Review succeeds (or on `page/**` / `qlib_score_csv/**` pushes). Builds the VitePress site from `main` + data from `qlib_score` branch, deploys to `gh-pages`.
5. `build.yml` — on PR/push to `main`, runs `pytest --cov=. --cov-report=xml` and SonarQube scan.

### Testing conventions
- Tests live in `tests/` and import from `roll/` via `sys.path.insert(0, roll_dir)`.
- Several tests require a prior `qlib.init(...)` (see `test_train.py` and `test_model.py` for the session-scoped fixture pattern).
- `loguru` output is not captured by standard `caplog`; use the `caplog_loguru` fixture pattern from `test_data.py` when asserting log content.

### Important paths and conventions
- Local data: `~/.qlib/qlib_data/cn_data/`
- Model experiments: `~/.qlibAssistant/mlruns/`
- Analysis output: `~/.qlibAssistant/analysis/`
- Bundled models in repo: `model_pkl/`
- Score/review/backtest CSVs in repo: `qlib_score_csv/`, `review_csv/`, `backtest_csv/` (all gitignored on `main`; persisted on the `qlib_score` branch)
- `fix_mlflow_paths()` in `utils.py` repairs absolute home-directory paths inside `meta.yaml` files when moving `mlruns` across machines.
