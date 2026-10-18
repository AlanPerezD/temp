import unittest

import numpy as np

import ftmo_fit as ff


class SimTests(unittest.TestCase):
    def test_target_stop_time_and_same_minute_conservatism(self):
        # entry 100.00; stop 20t = 99.80; target 40t = 100.40
        r, k = ff.simulate([100.0, 100.1], [100.2, 100.45], [99.95, 100.0], [100.1, 100.4], 20, 40)
        self.assertEqual((r, k), (40, "target"))
        r, k = ff.simulate([100.0, 99.9], [100.1, 100.0], [99.9, 99.79], [99.9, 99.8], 20, 40)
        self.assertEqual(k, "stop"); self.assertEqual(r, -21)   # 20 ticks + 1 tick slippage
        r, k = ff.simulate([100.0], [100.5], [99.7], [100.2], 20, 40)   # both inside one minute
        self.assertEqual(k, "stop")
        r, k = ff.simulate([100.0, 100.1], [100.1, 100.15], [99.95, 100.05], [100.1, 100.12], 20, 40)
        self.assertEqual(k, "time"); self.assertAlmostEqual(r, 12)


if __name__ == "__main__":
    unittest.main()
