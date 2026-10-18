# Bigger-picture oil edges: research and 16-year tests

Data: CL futures daily (front, 2nd, 3rd month) and hourly bars Jun 2010 - Oct 2026 (Databento),
EIA weekly crude stocks (eia.gov), CFTC disaggregated Commitments of Traders 2006-2026 (cftc.gov).
Code: `macro_lab.py` (all families, output `macro_results.txt`), `late_session.py` (robustness).
Method: 2nd-month contract rolled properly; positions use only information known at the prior
close; 0.03% cost per position change; DEV 2010-2017 vs TEST 2018-2026; Holm correction across
all ~25 strategies.

## What professionals use, what the research says, what our test found

| Edge source | Published evidence | Our 16-year test |
|---|---|---|
| Term structure / carry (long when backwardated) | Strong 1985-2004, poor in contango era 2005-2015 (CXO, NMBU thesis) | Sharpe 0.44 long-only-in-backwardation (t 1.8); weak in DEV (0.08), good in TEST (0.60). Regime-dependent, not proven |
| Trend following (time-series momentum) | Positive across a century of futures (Hurst/Ooi/Pedersen), but time-varying | Sharpe 0.1-0.3 on crude alone; long/flat versions slightly beat buy & hold (0.16). Not significant |
| Seasonality (driving season, maintenance) | Commentary, no rigorous evidence | No month significant; Nov weakest (t -1.1). Seasonal rules ~0 |
| Index roll ("Goldman roll", calendar spread days 5-9) | Thesis: 80-110 bp/month in 1995-2012 | +$51/spread/month, t 1.3, but DEV -$3 vs TEST +$98: unstable |
| EIA inventory surprise | Reaction within ~25 min then partial reversal (Li & Geman) | Same-day correlation -0.09 (builds push price down, as expected); no edge in the following days |
| CFTC positioning (managed money) | Weak / unproven as contrarian (Aalto thesis); trend-following behaviour (Sanders et al.) | Contrarian extremes Sharpe -0.12, follow weekly change -0.17. No edge |
| Day-of-week | - | Thursday best (+0.11%/day, t 1.5), not significant |
| **Session timing: 15:00-17:00 New York (after settlement)** | Intraday seasonality literature (momentum into the close) | **Only survivor: Sharpe 0.82, t 3.2, DEV 0.71 / TEST 0.90, 88% of years positive, Holm p 0.03** |

## The late-session drift in detail (`late_session.py`)
- Front month: +1.69 ticks/day gross over 3,893 days (t 2.9); 16 of 17 years positive; both hours
  (15:00 and 16:00 ET) positive.
- 2nd-month contract (no expiry effects; download was cut off, covers 2010-Oct 2020 only):
  +1.11 ticks/day over 2,593 days (t 2.3); 15:00 ET hour strongest again (t 2.3).
- MCL tick data Jul-Oct 2026 (independent instrument): +7.6 ticks/day, t 1.0 (too few days alone).
- **Too thin to trade on its own:** net of 1 tick +0.7 ticks/day front month (~$170/MCL/year), +0.1 on the 2nd month; net of 2 ticks
  it loses. Only workable with near-zero costs (passive limit fills) or as a timing overlay:
  hold existing longs through 15-17 ET, delay new shorts until after 17:00 ET.

## Bottom line
No large, tradable edge appeared in 16 years of the classic oil signals at this level of
simplicity. The one robust pattern (late-session drift) is real-looking but smaller than retail
costs. Carry in backwardation is the next most promising and matches the literature's regime story.
