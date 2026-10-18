# Edge found: late-session momentum in NYMEX energy futures

**Status: statistically real and replicated across markets; economically modest; only worth trading
in full-size contracts (best in heating oil). Not a get-rich edge.**

## The rule (defined in New York time)
1. At **15:00 New York**, look at each market: crude (CL), heating oil (HO), gasoline (RB).
2. If the price is **above where it was at the start of the session** (previous day's 18:00 New York
   reopen, practically: above the previous 17:00 close), **buy 1 contract** (the front month).
3. **Sell at 16:59 New York**, before the daily 17:00 halt. No overnight risk.
4. If the market is down on the day, do nothing.

| | New York | Buenos Aires while US is on summer time (mid-Mar to Nov 1) | Buenos Aires in US winter (Nov 1 to mid-Mar) |
|---|---|---|---|
| Check & buy | 15:00 | **16:00** | **17:00** |
| Sell | 16:59 | **17:59** | **18:59** |

Skip US holidays / early-close days.

## Evidence (16 years, Jun 2010 - Oct 2026, hourly bars; DEV < 2018 <= TEST)
| Market | Gross per trade | t | DEV | TEST |
|---|---|---|---|---|
| CL 15-17 ET | +2.7 ticks ($27) | 3.73 | +3.5 (t 4.4) | +2.1 (t 1.8) |
| CL last hour 16-17 ET | +2.3 ticks | **4.63** | +3.0 | +1.8 (t 2.3) |
| HO 15-17 ET | +10.1 ticks ($43) | 3.47 | t 4.2 | t 2.3 |
| RB 15-17 ET | +6.2 ticks ($26) | 2.98 | t 4.2 | t 1.0 |
| CL 2nd month (2010-2020) | +2.9 ticks | 4.58 | | |
| NG 15-17 ET (replication) | +1.6 ticks ($16) | 2.91 | t 4.0 | t 1.4 |
| Brent on CME (thin) | +0.7 ticks | 0.8 | | |

- Pre-registered on CL before seeing the other markets; then replicated on HO, RB and NG (all four
  NYMEX energy contracts positive; NG's ~$16 gross is roughly its trading cost, so NG is confirmation only).
- The CL last-hour version passes the family-wise bar for ~300 tests run in this search (|t| > 3.77).
- Positive in 16 of 17 years (CL); robust to how "day up" is measured (5 definitions, t 1.9-3.8).
- Not bid/ask bounce: on MCL tick data (Jul-Oct 2026) the move measured at the bid is +9.6 ticks
  vs +10.8 by last trade on up days.
- Matches published research: Baltussen, Da, Lammers & Martens (2021, Journal of Financial Economics),
  "Hedging demand and market intraday momentum" — intraday momentum into the close across 60+ futures.
- The push fades after the 18:00 reopen, so it must be closed before the halt.

## Economics (1 contract, net of 1 tick spread + $5 commissions per round trip)
| | Net per trade | $/year | Sharpe | Max drawdown | Years positive |
|---|---|---|---|---|---|
| HO | +$33 | ~$4,250 | 0.69 (TEST 0.64) | ~$9,800 | 15/17 |
| RB | +$17 | ~$2,230 | 0.49 (TEST 0.10) | ~$11,200 | 14/17 |
| CL | +$12 | ~$1,580 | 0.42 (TEST 0.17) | ~$11,300 | 11/17 |
| Basket (1 each) | | ~$7,700 | 0.64 (TEST 0.40) | ~$25,800 | 16/17 |
With 2-tick spreads: basket ~$5,400/yr, Sharpe 0.45; HO alone still ~$3,700/yr.
Worst single trades: HO -$8,271, CL -$4,795 (crash days). Win rate 52-54%; losing streaks up to 12.

## What it is NOT
- Not for micro crude (MCL): ~2.7 ticks gross vs ~2 ticks of costs leaves ~$0.7 per trade.
- Not improved by filtering for big up days (threshold chosen on DEV did worse on TEST).
- Weakening in CL since 2018; HO remains the strongest leg.

## Risks
Edge decay; liquidity is thin after settlement (CL front ~2k contracts/hour); tail days; broker
day-trade margin cut-offs (positions held to 16:59 NY may require full margin); daylight-saving shifts.

## Code
`hourly_lab.py` (H1 pre-registration), `h1_robust.py`, `hourly_multi.py`, `edge1_portfolio.py`,
`edge1_filter.py`, `h5_reopen.py`, `late_session.py`; every test is logged in `registry.csv`.
