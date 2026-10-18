# Late-session momentum: how it works, and why it does NOT fit the FTMO 50K plan

> ## VERDICT FOR THE FTMO FUTURES PRO 50K PLAN (added Oct 18 2026, after testing on 1-minute CL bars 2018-2026)
> **Do not trade this on the FTMO evaluation.** It cannot be implemented inside your rules at a profit:
> 1. **Wrong hours.** Your plan flats at 15:50 ET (FTMO's cutoff is 16:10 ET). The gain sits mostly after that.
>    CL, long on up-days, ticks per contract, 2018-2026 (n=1,041, no costs):
>    | Window (ET) | Gross | t |
>    |---|---|---|
>    | 15:00-15:50 (inside your own deadline) | +0.1 | 0.2 |
>    | 15:50-16:10 (allowed by FTMO, past your deadline) | +1.4 | 3.4 |
>    | 16:10-17:00 (FTMO forbids holding) | +1.0 | 1.4 |
>    | 15:00-17:00 (the original edge) | +2.6 | 2.2 |
> 2. **Wrong instruments.** The strong legs (heating oil, gasoline) are not on FTMO's list. FTMO has CL/MCL
>    and NG only. On crude the edge is ~2.6 ticks gross vs ~2 ticks of spread + fees.
> 3. **Your required stop + target destroy it.** With a stop and a 1:2 target and a flat deadline, the same
>    trades earn -0.1 to +0.3 ticks gross even at ZERO cost, and -2.1 to -2.6 ticks net of costs
>    (t -2.2 to -4.6, 1,041 trades). Stops cut the drift; ~70-80% of trades just time out.
> 4. **Best allowed slot after costs:** 15:50-16:10 is +1.4 ticks gross: -0.1 net at 1.5 ticks of cost,
>    -1.1 net at 2.5 ticks. Zero.
> 5. **Too small to ever verify live.** Per-trade sd ~33 ticks vs mean ~2.6: one year of forward trading gives
>    t ~ 0.9. Paper trading 30 days proves nothing either way.
> The earlier "+$12/trade net on CL, $33 on HO" came from hourly bars, no stops, holding to 16:59 ET,
> and 1 tick + $5 costs. It is real but is not what your FTMO plan allows.
>
> ### Where it still looks real
> Heating oil / gasoline, month-end days, held to 16:59 ET on a normal futures account (not FTMO). Untested
> with stops (needs HO minute data, ~$10). One full HO contract has per-trade sd ~$545 and worst case -$8,271,
> which is incompatible with a $1,000 daily-loss limit unless a stop is used.

## Why it works (the hypotheses, with what is and is not proven)
1. **Hedging demand into the close (published):** Baltussen, Da, Lammers & Martens, *Journal of Financial
   Economics* 142 (2021): across 60+ futures (incl. commodities, 1974-2020) the last half hour is predicted by
   the rest of the day; they link it to gamma-hedging by option market makers and leveraged-fund rebalancing
   (chasing the day's direction late). The effect reverts over the next days, so it only exists intraday.
2. **Month-end flows (our finding, not proven):** since 2018 the effect is concentrated in the last 5 + first 2
   business days of a month (HO +26 ticks, RB +15, CL +4), consistent with index/fund rebalancing. Found after
   looking at the data, so unconfirmed.
3. **Thin liquidity after settlement:** CL trades ~2-4k contracts/hour at 15:00-17:00 ET vs ~20k at 09:00-11:00,
   so flow moves price more and costs more. That is exactly why the gain and the cost are the same size.

## Optional day-to-day routine IF you want to watch it on a SIM account only (no real money, no FTMO)
Times: New York | Buenos Aires until Nov 1 | Buenos Aires from Nov 1
- 15:00 ET | 16:00 | 17:00: is price above where the session started (previous 18:00 ET reopen)? If no, skip.
- 15:00 ET | 16:00 | 17:00: sim buy. Sizing as in your plan: risk $150-200, e.g. at CL $96.70 a 0.30% stop = 5 MCL.
- 15:50 ET | 16:50 | 17:50: your flat deadline: be flat and cancel orders. (Holding to 16:09 ET is allowed by FTMO but past your own rule.)
- Log: date, entry, price at 15:50 / 16:09 / 16:59, month-end yes/no.
Expectation: about zero. The point would be learning, not income. Do not let it touch your FTMO risk budget
(daily -$400, profit cap +$600, ladder, 20-micro cap): all of those stay unchanged.


---

## Original write-up (hourly bars, 2010-2026)
> **Update after the contract-roll question (roll_check.py, roll_split.py):**
> - Not a roll-gap artifact: in 16 years no contract switch ever falls in the 15:00-17:00 ET window
>   (all switches happen at the 18:00-20:00 ET reopen), and every price change is measured inside one
>   contract. Crude keeps the effect after removing every roll/expiry week (+3.5 ticks, t 3.8) and on
>   the 2nd-month contract (+2.9 ticks, t 4.6).
> - **Correction:** the effect was broad in 2010-2017. Since 2018 it is concentrated in the
>   **month-end window** (last 5 business days + first 2 of the next month): TEST HO +26.5 ticks (t 3.0),
>   RB +14.8 (t 2.5), CL +4.2 (t 2.3), BZ +4.0 (t 2.1); rest of the month ~0. Crude expires ~20th,
>   so this is month-end flow, not expiry. The month-end concentration was found AFTER looking at the
>   data, so it is a hypothesis to confirm with forward (paper) trading before risking money.
> - The HO/RB dollar figures below include the pre-2018 broad effect; for current conditions only the
>   month-end days carry the edge.

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
