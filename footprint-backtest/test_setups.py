import unittest

import pandas as pd

import setups


def make_trades():
    """Bar 1 (12:00): heavy buying at 70.10-70.12 then drops; bar 2: rally back, break, spike."""
    t0 = pd.Timestamp("2026-10-05 12:00:00", tz="UTC")
    rows = []
    for s in range(-60, 55):  # quiet history so the quantile has data
        rows.append((s, 70.00 + 0.01 * (s % 3), 1, "B" if s % 2 else "A"))
    rows += [(56, 70.10, 40, "B"), (57, 70.11, 40, "B"), (58, 70.12, 40, "B"), (59, 70.05, 5, "A")]
    rows += [(65, 70.09, 1, "B"), (70, 70.12, 1, "B"),    # touch the zone
             (80, 70.14, 1, "B"),                          # break (zone high 70.12 + 2 ticks)
             (90, 70.25, 1, "B"), (150, 70.20, 1, "B")]   # explosive: +11 ticks within 60s
    return pd.DataFrame({
        "ts_event": [t0 + pd.Timedelta(seconds=s) for s, *_ in rows],
        "price": [r[1] for r in rows], "size": [r[2] for r in rows], "side": [r[3] for r in rows]})


class SetupTests(unittest.TestCase):
    def test_zone_touch_break_explode(self):
        p = setups.Params(lookback=1, vol_q=0.0, share=0.5)
        tr = make_trades()
        zones = setups.find_zones(tr, p)
        hi = zones[zones.side == "high"]
        self.assertEqual(len(hi), 1)
        self.assertAlmostEqual(hi.iloc[0]["lo"], 70.10)
        self.assertAlmostEqual(hi.iloc[0]["hi"], 70.12)
        res = setups.study(tr, hi, p)
        r = res.iloc[0]
        self.assertTrue(r.touched and r.broke and r.exploded)
        self.assertGreater(r.break_mfe, 10)
        self.assertIn("exploded 1", setups.summarize(res))


if __name__ == "__main__":
    unittest.main()
