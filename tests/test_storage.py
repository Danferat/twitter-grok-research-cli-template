import tempfile
import unittest
from pathlib import Path

from twitter_research.storage import latest_run_path, save_run


class StorageTests(unittest.TestCase):
    def test_save_run_writes_json_and_latest_finds_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)

            first = save_run({"query": "first"}, runs_dir=runs_dir, timestamp="2026-04-29T10:00:00Z")
            second = save_run({"query": "second"}, runs_dir=runs_dir, timestamp="2026-04-29T11:00:00Z")

            self.assertTrue(first.exists())
            self.assertEqual(latest_run_path(runs_dir), second)


if __name__ == "__main__":
    unittest.main()
