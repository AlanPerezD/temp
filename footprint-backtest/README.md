# Footprint backtest data (WTI crude, CME L2 + trades)

Raw trades + top-10 book from Databento (GLBX.MDP3), converted to Parquet, then footprint
features for an AI to explore and a Nautilus backtest.

## Setup
1. `pip install -r requirements.txt`
2. Put your key in `.env` (copy `.env.example`; git-ignored) or `export DATABENTO_API_KEY=...`
   (new accounts get free credit: https://databento.com/portal/keys).
3. Optional MCP: `pip install databento-mcp`, then add `mcp-config.example.json` to your
   Claude config. Review its code first; it runs locally with your key. Use it for cost
   estimates and small samples only; bulk data goes through `fetch_data.py`.

## Get data
```
python3 fetch_data.py --start 2026-10-05 --end 2026-10-07            # estimate only
python3 fetch_data.py --start 2026-10-05 --end 2026-10-07 --download # fetch (aborts if > $1)
```
Writes `data/trades_*.parquet` and `data/mbp-10_*.parquet` (git-ignored). Start with 1-3 days.

## Build footprint features
```
python3 features.py data/trades_CL_v_0_2026-10-05_2026-10-07.parquet --freq 1min
```
Produces `*_levels.parquet` (bar x price: bid/ask volume), `*_bars.parquet` (OHLC, delta, POC,
diagonal imbalances) and `*_bars.jsonl` (one bar per line with the full ladder, for the AI).
`features.book_imbalance(mbp)` gives top-10 book imbalance from the mbp-10 file.

## Nautilus backtest
```
python3 fetch_data.py --start ... --end ... --schemas definition --download   # contract specs (free)
python3 build_catalog.py        # DBN/Parquet -> data/catalog_cl (trades + 10-level book + instrument)
python3 run_backtest.py --imb-thr 0.3 --delta-thr 20 --hold-s 120
```
`rule_strategy.py` is the file the AI edits (`signal()` or the config thresholds). The runner
fills market orders against the replayed 10-level book and charges $2.50 per contract per fill.
Verified on 2026-10-12/13 CL (CLX6): 4.4M book updates replay in ~3 min; the default rule
loses money (65 trades, -$2,195), which is expected for an untuned baseline.

Notes: pull one contract per range (build_catalog stops if the range spans a roll; CLX6 expires
2026-10-20). Fills are against the visible book only (no queue position for limit orders).

Tests: `python3 -m unittest test_features`
