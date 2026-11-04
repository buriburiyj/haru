import subprocess
import sys
import unittest
from pathlib import Path

LIMIT_MB = 150


class MemoryBudgetTest(unittest.TestCase):
    def test_peak_rss_stays_under_150_mb(self):
        probe = Path(__file__).with_name("_mem_probe.py")
        r = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        peak = float(r.stdout.strip().splitlines()[-1])
        print(f"peak RSS: {peak} MB (limit {LIMIT_MB})")
        self.assertLess(peak, LIMIT_MB)


if __name__ == "__main__":
    unittest.main()
