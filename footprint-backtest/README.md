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

Tests: `python3 -m unittest test_features`
