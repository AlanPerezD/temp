# The edge, adapted to the FTMO Futures Pro 50K plan: Nasdaq close momentum (MNQ)

**What it is.** The same effect as the oil edge (the market keeps moving in the day's direction into the
close; Baltussen, Da, Lammers & Martens, JFE 2021, 60+ futures), moved to the market that fits FTMO's rules:
Nasdaq futures, micro MNQ. NQ's stock-market close is 16:00 ET, inside FTMO's 16:10 ET cutoff.

**Honest size of it.** Real but tiny: about **+$3.7 per trade** at the position size your risk plan allows,
t-stat about 1 (not statistically proven). Treat it as a small tilt, not a strategy that carries the account.

## The rule (one trade per day, manual orders)
1. **At 15:00 ET** look at NQ. Compare the price to the **start of the current Globex session (6:00 pm ET the previous evening)**.
   Above it = LONG. Below it = SHORT. Exactly equal = no trade.
2. **Order:** 2 MNQ, entered with a bracket: stop **40 index points** away, target **80 points** away
   (1:2). Risk = 2 x 40 x $2 = **$160** (inside your $150-200 range; stop and target sent with the entry).
3. **At 15:49 ET: flatten and cancel any working orders** (your own 15:50 deadline, 20 minutes before FTMO's 16:10).
4. Log it (below). Nothing else.

| | New York | Buenos Aires until Sun Nov 1 | Buenos Aires from Mon Nov 2 |
|---|---|---|---|
| Check direction, place bracket | 15:00 | 16:00 | 17:00 |
| Flat, orders cancelled | 15:49 | 16:49 | 17:49 |

## How it fits each of your rules
| Your rule | This trade |
|---|---|
| Micros only, symbol starts with M (MNQ), $ per point checked | MNQ = $2 per point ($0.50 per tick). Check "tick value / units" before sending |
| Stop and target on every order, min 1:2 | 40 / 80 points = 1:2 |
| Risk $150-200 per trade | $160 (2 MNQ). If NQ is far from 30,800 recompute: contracts = $200 / (stop points x $2), rounded down |
| Flat by your deadline 15:50 ET, FTMO 16:10 | Out at 15:49 ET |
| One position per lane; equity indices are one lane | This uses the equity-index lane: do not hold ES/MES/YM at the same time |
| Daily stop -$400, 3 losers in a row, 5 trades/day | Max one trade a day; worst case about -$164. Three straight losing days still leaves you far from -$400 on any day |
| Daily profit cap +$600 | Best day in 8.6 years of backtest: +$317 |
| Consistency (best day <= 50% of profit) | Not an issue: each day is small |
| Drawdown ladder | Applies unchanged. Backtest max drawdown was -$6,558 over 8.6 years: expect to hit the -$1,000 / -$1,500 steps in bad stretches |
| No new positions within 2% of the CME price limit | Still your check each morning |
| Partner / copying rule | This is a systematic rule from my research, placed by you. Ask FTMO support whether rule-based entries are fine; also whether bracket orders you place manually are fine (they are manual) |
| Automation | Not needed: two actions a day. Do not script it unless FTMO confirms automated entry is allowed |

## Backtest (NQ 1-minute bars, 2,156 sessions, 2018-2026, costs $1.40 per MNQ round trip incl. spread)
2 MNQ, stop 40 pt / target 80 pt, in 15:00, out 15:49 ET:
- Average **+$3.72 per trade**, sd $140, worst -$164, best +$317, win rate 47%.
- 2018-2022: +$2.7/trade (t 0.7). 2023-2026: +$5.1/trade (t 1.0).
- Outcomes: ~8% hit the target, ~20-30% hit the stop, the rest closed at 15:49.
- Total +$8,012 over 8.6 years = ~$940/year. Max drawdown -$6,558. Longest losing streak 11.
- Wider stops (60-80 pt, 1 MNQ) earn about the same per trade or less. Tighter stops lose (the Nasdaq moves
  3-7 points in a minute, so a small stop is just noise).

## What this means for passing the $3,000 evaluation
Bootstrapping those real trades, one trade a day, with the $3,000 end-of-day trailing drawdown:
| | Pass before trailing limit | Fail | Undecided after 2 years | Median days to pass |
|---|---|---|---|---|
| With the edge (+$3.72/trade) | **51%** | 34% | 15% | ~238 trading days (~11 months) |
| Edge half as big | 41% | 44% | 15% | ~237 |
| No edge at all (same volatility) | 31% | 55% | 15% | ~241 |
At $139 a month that is roughly $1,500 in fees for a ~50% chance, if the edge is real. The edge is only
~1 standard error from zero in the recent years, so plan for the middle row, not the top one.
**It speeds nothing up: the plan's own pacing (40-50% win rate at 1:2, 2-3 trades a day with $200 risk) is
roughly 5-10x faster. This trade is a small add-on, not a way to pass sooner.**

## Honest limits
- Not statistically proven (t about 1 in 2018-2026). Hourly bars over 16 years show the same direction
  (NQ +5 ticks gross, t 1.7; ES +1.5, t 2.0; YM nothing), and the late-oil version fails FTMO's rules.
- The last-30-minutes version (entry 15:30) loses money in 2023-2026 with the same stops, so the edge is not the
  textbook "last half hour": the 15:00 entry is better, but that choice came after looking at both.
- Costs matter: $1.40 per MNQ round trip assumed. With 1 extra tick of slippage the edge falls by about $1 per MNQ.
- Stops fill 1 tick worse in the test; gap risk in a news minute (Fed days) can be worse.
- Sizing is fixed by your plan. Do not add contracts: 20 MNQ would swing $2,500 a trade.

## Daily log (copy into your journal)
date | NQ price at 15:00 ET | Globex session-open price | direction | entry | exit (time and price) | result in $ | stop/target/time

After 30 logged trades the average will be noisy (sd about $140 means the average alone swings by about
$25). Judge it only after 150+ trades; the decision rule: keep running only if the average stays above $0
and you are inside the drawdown ladder.

## Code
`index_close_lab.py` (pre-registered hourly test on ES/NQ/YM), `index_ftmo_sim.py` (stop/target on 1-minute
bars), `ftmo_fit.py` (why the oil version does not fit). Every test is in `registry.csv`.
