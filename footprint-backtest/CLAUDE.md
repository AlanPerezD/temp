# footprint-backtest: oil / futures edge research and the FTMO 50K plan

This folder is a separate project from the lead-generation work in the repo root. Work here for trading research.

## Who and what
- User trades micro futures (MCL, MNQ, ...) on an FTMO Futures Pro 50K evaluation: $3,000 end-of-day trailing drawdown,
  $1,000 daily-loss limit, flat and orders cancelled by 16:10 ET, max 50 micros. Own plan: $150-200 risk per trade,
  -$400 daily stop, +$600 profit cap, flat by 15:50 ET, 20-micro cap, real stop and target on every trade, min 1:2.
  (The full risk plan is a claude.ai doc the user owns, not in this repo.)
- User is in Buenos Aires (UTC-3, no DST). New York = Buenos Aires minus 1 h until Sun Nov 1 2026 (US DST ends), then minus 2 h.
- Wants autonomy and plain-language reports. Report negative results honestly; never present an unproven edge as proven.

## Rules for any claim of an "edge"
Net of realistic costs (MCL ~2.5 ticks round trip, $1/tick), positive in DEV (<2018) and TEST (2018+), and significant
after correcting for everything tried (`registry.csv` counts every test; `registry.bonferroni_t()` gives the bar, ~3.8).
Size the edge in R (dollars per $200 of risk): a $3-5 per-trade edge cannot pass a $3,000 target in reasonable time.

## Safety
- Repo is PUBLIC. Never commit market data (`data/` is git-ignored, Databento terms) or API keys. Key goes in env
  `DATABENTO_API_KEY` or `footprint-backtest/.env` (git-ignored). The key pasted in the old cloud chat must be revoked.
- Data is paid per download: fetch scripts estimate first and abort above `--max-cost`. Ask before any single pull > ~$5.
- `python rebuild_data.py --tier nq|oil|mcl` shows the plan and cost before buying anything.
- Tests (no data needed): `python -m unittest discover -p "test_*.py"`.

## Map
- Data: `fetch_data.py`, `fetch_chunks.py`, `rebuild_data.py`, `session.py` (Buenos Aires session helpers)
- Footprint / MCL ticks: `features.py`, `render_events.py`, `spike_study.py`, `live_study.py`, `range_study.py`, `fade_sim.py`,
  `strategy_lab.py`, Nautilus: `build_catalog.py`, `rule_strategy.py`, `run_backtest.py`
- Edge search: `edge_lab.py`, `research_lab.py`, `macro_lab.py`, `energy_lab.py`, `ml_lab.py`, `hourly_lab.py`, `h1_robust.py`,
  `hourly_multi.py`, `roll_check.py`, `roll_split.py`, `registry.py`
- FTMO fit: `ftmo_fit.py` (oil version), `index_close_lab.py`, `index_ftmo_sim.py` (Nasdaq version), `edge1_portfolio.py`
- Results and write-ups: `strategies/` (start with `strategies/README.md`)

## Findings so far
- Footprint/spike rules (fade, follow, range, VWAP, ORB ...): about break-even after costs on MCL tick data (67 days).
  The user's discretionary take/skip calls are in `strategies/labels.csv` (21 charts); their filter = candle range >= ~80 ticks.
- Macro oil edges over 16 years (carry, trend, seasonality, COT, EIA, roll, ML): nothing significant after costs.
- Late-session momentum into the 17:00 ET close: real for heating oil / gasoline / crude (replicated, month-end concentrated)
  but cannot be traded inside FTMO rules (`strategies/EDGE_late_session_momentum.md`).
- FTMO adaptation: MNQ, 15:00-15:49 ET, 2 MNQ, stop 40 pt / target 80 pt: ~+$3.7 per trade, t about 1, ~11 months to $3,000
  (`strategies/FTMO_ADAPTATION_nasdaq_close_momentum.md`). A small add-on, not a way to pass faster.
