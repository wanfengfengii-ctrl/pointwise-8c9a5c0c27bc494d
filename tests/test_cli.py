import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class TestCLI(unittest.TestCase):
    def run_cli(self, *args, code=0):
        completed = subprocess.run([sys.executable, "-B", "-m", "crisk", *map(str, args)],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, code, completed.stderr + completed.stdout)
        return completed.stdout

    def test_roundtrip(self):
        sample = Path(__file__).resolve().parent.parent / "samples" / "joint.json"
        with tempfile.TemporaryDirectory(prefix="crisk-cli-") as directory:
            path = Path(directory) / "analysis.sqlite"
            receipt = json.loads(self.run_cli("apply", "--db", path, sample))
            self.assertEqual(receipt["epoch"], 1)
            self.run_cli("freeze", "--db", path, "c", "4", "1", "5",
                         "--causes", "2", "1")
            result = json.loads(self.run_cli("analyze", "--db", path, "c", "r"))
            self.assertEqual(result["probabilities"], ["7/16", "3/8", "1/4", "0", "7/16", "9/16"])
            self.assertEqual(json.loads(self.run_cli("read", "--db", path, "r")), result)
            self.assertIn("error", json.loads(self.run_cli("read", "--db", path, "unknown", code=2)))

    def test_demo(self):
        rows = [json.loads(line) for line in self.run_cli("demo").splitlines()]
        self.assertEqual([row["stage"] for row in rows], ["before", "after", "reopened"])
        self.assertTrue(rows[2]["stable"])
        self.assertEqual(rows[0]["result"], rows[2]["result"])
        self.assertNotEqual(rows[0]["result"]["probabilities"], rows[1]["result"]["probabilities"])
