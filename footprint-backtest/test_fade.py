import unittest

import numpy as np
import pandas as pd

import fade_sim


class FadeTests(unittest.TestCase):
    def mk(self, prices):
        ts = pd.Timestamp("2026-10-05 12:00", tz="UTC").value + np.arange(len(prices)) * 10**9 * 30  # 30 s apart
        return pd.DataFrame([dict(bar=pd.Timestamp("2026-10-05", tz="UTC"), k=0, dir=1.0)]), ts, np.array(prices)

    def test_target_first(self):
        ev, ts, px = self.mk([101.0, 100.9, 100.7, 100.0])      # up-spike from open 100; fade short
        r = fade_sim.simulate(ev, ts, px, [100.0], stop_ticks=30, target_frac=1.0, cost_ticks=2)
        self.assertEqual(r.kind.iloc[0], "target"); self.assertAlmostEqual(r.ticks.iloc[0], 100 - 2)

    def test_stop_first(self):
        ev, ts, px = self.mk([101.0, 101.2, 100.0])
        r = fade_sim.simulate(ev, ts, px, [100.0], stop_ticks=15, target_frac=1.0, cost_ticks=2)
        self.assertEqual(r.kind.iloc[0], "stop"); self.assertAlmostEqual(r.ticks.iloc[0], -17)


if __name__ == "__main__":
    unittest.main()
