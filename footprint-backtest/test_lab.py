import unittest

import numpy as np
import pandas as pd

import strategy_lab as lab


def mkt(prices, start="2026-10-05 12:00:00"):
    t0 = pd.Timestamp(start, tz="UTC")
    tr = pd.DataFrame({"ts_event": [t0 + pd.Timedelta(seconds=10 * i) for i in range(len(prices))],
                       "price": prices, "size": 1, "side": "B"})
    return lab.Mkt(tr)


class LabTests(unittest.TestCase):
    def test_simulate_target_then_stop(self):
        m = mkt([100.0, 100.4, 100.7, 101.0])
        self.assertAlmostEqual(lab.simulate(m, 0, 1, stop=30, target=60, cost=2), 58)
        m = mkt([100.0, 99.6, 100.9])
        self.assertAlmostEqual(lab.simulate(m, 0, 1, stop=30, target=60, cost=2), -32)

    def test_vwap_fade_enters_against_extension(self):
        prices = [100.0] * 400 + [101.5] * 3 + [101.0] * 50  # 150 ticks above vwap ~100.0
        m = mkt(prices, start="2026-10-05 12:30:00")  # 09:30 BA
        ent = lab.ev_vwap_fade(m, 120)
        self.assertEqual(len(ent), 1); self.assertEqual(ent[0][1], -1)

    def test_orb_breaks_premarket_range(self):
        pre = list(np.linspace(100.0, 100.2, 60))
        t0 = pd.Timestamp("2026-10-05 11:00:00", tz="UTC")  # 08:00 BA
        px = pre + [100.1] * 540 + [100.3, 100.4]  # 600 ticks * 10s -> past 09:30 BA, then breaks high
        tr = pd.DataFrame({"ts_event": [t0 + pd.Timedelta(seconds=10 * i) for i in range(len(px))],
                           "price": px, "size": 1, "side": "B"})
        ent = lab.ev_orb(lab.Mkt(tr))
        self.assertEqual(len(ent), 1); self.assertEqual(ent[0][1], 1)


if __name__ == "__main__":
    unittest.main()
