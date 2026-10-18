# Strategy: range fade (saved for later)

**Idea (from the trader's labeled charts):** only act on a violent 5-minute candle, then enter
against it after it starts to pull back from its extreme, aiming back toward the candle's origin.

## Rules as implemented (`range_study.py`, `strategy_lab.ev_fade_pullback`)
1. MCL (CL.v.0-style continuous), entries only 08:00-13:00 Buenos Aires; trades may run to the 18:00 close.
2. Setup: the forming 5-min candle's range (running high - running low) reaches R ticks
   (R = 60-100; 80 matched 14 of his 15 take/skip choices; skips were 44-64 ticks).
3. Spike direction = side of the open where the extreme is.
4. Entry: first trade where price has pulled back P = 20 ticks from the extreme, still inside
   the candle; enter +1 s later against the spike.
5. Exit: stop 30-45 ticks, target 60-90 ticks (his typical targets 55-110), else the 18:00 BA close.
6. Costs: 2 ticks round trip ($2/MCL); 1 tick = $1/MCL.

## Results (3 months, Jul 15 - Oct 15 2026, 3.24M trades)
- R=80, P=20, stop 30 / target 90: 39 trades, win 33%, avg +8 ticks (+$8/MCL), total ~ +312 ticks. t ~ 0.8.
- Strategy lab (`strategy_lab.py`, 54 combos; dev Jul-Aug, test Sep-Oct): dev-selected R=60 stop 30 / tgt 60:
  dev avg +8.0t (n=36), TEST avg +5.3t (n=41), win 41%, t=+0.8.
- Sensitive to R and the stop/target; no combination reaches t>2 after trying 54.

## Status: NOT proven. Do not trade real money on it. Edge, if any, is small (a few $ per trade).

## Known gaps / next
- Trader's real edge is likely in entry timing and the exhaustion read (footprint cues), not in this
  mechanical pullback. Needs more labeled charts and out-of-sample prediction of his take/skip calls.
- Continuation (with-the-move) variants and "wait then fade" are in the lab; nothing significant yet.
- Labeled decisions: `labels.csv` (21 charts).
