import unittest

import pandas as pd

import range_study as rs


def trades(prices):
    t0 = pd.Timestamp("2026-10-05 12:00:00", tz="UTC")
    return pd.DataFrame({"ts_event": [t0 + pd.Timedelta(seconds=10 * i) for i in range(len(prices))],
                         "price": prices, "size": 1, "side": "B"})


class RangeTests(unittest.TestCase):
    def test_setup_and_target(self):
        # open 100, rally to 100.90 (90 ticks), pull back 25 ticks, then fall to 100.0
        p = [100.0, 100.3, 100.6, 100.9, 100.75, 100.65, 100.5, 100.3, 100.0, 99.9]
        ev, ts, px = rs.setups(trades(p), range_ticks=80, pullback_ticks=20, delay_s=0)
        self.assertEqual(len(ev), 1); self.assertEqual(ev.iloc[0].dir, 1)
        s = rs.run(ev, ts, px, stop_ticks=30, target_ticks=50, cost_ticks=2)
        self.assertEqual(s.kind.iloc[0], "target"); self.assertAlmostEqual(s.ticks.iloc[0], 48)

    def test_narrow_candle_ignored(self):
        ev, _, _ = rs.setups(trades([100.0, 100.2, 100.1, 100.0]), range_ticks=80)
        self.assertTrue(ev.empty)


if __name__ == "__main__":
    unittest.main()
