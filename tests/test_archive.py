from pathlib import Path
import sqlite3
import tempfile
import unittest
from crisk import App
from tests.helpers import obs

class TestArchive(unittest.TestCase):
    def test_unknown_cohort(self):
        with tempfile.TemporaryDirectory(prefix="crisk-test-") as directory:
            path = Path(directory) / "archive.sqlite"
            with App(path) as app:
                app.freeze("empty", [1])
                old = app.analyze("empty", "old")
            with App(path) as app:
                with self.assertRaises(KeyError):
                    app.analyze("missing", "new")
                with self.assertRaises(KeyError):
                    app.read("missing")
                self.assertEqual(app.archive.ids(), ("old",))
                self.assertEqual(app.read("old"), old)

    def test_publish_failure_retry(self):
        with tempfile.TemporaryDirectory(prefix="crisk-test-") as directory:
            path = Path(directory) / "archive.sqlite"
            with App(path) as app:
                app.apply([obs("A", "a", 0, 2, 1), obs("B", "b", 0, 2, 2)])
                app.freeze("c", [2, 0, 2], (2, 1))
                old = app.analyze("c", "old")
                visited = []
                def interrupt():
                    visited.append(True)
                    self.assertIn("failed", app.archive.ids())
                    other = sqlite3.connect(path)
                    try:
                        self.assertEqual(other.execute(
                            "SELECT id FROM reports ORDER BY id").fetchall(), [("old",)])
                    finally:
                        other.close()
                    raise RuntimeError("before commit")
                with self.assertRaisesRegex(RuntimeError, "before commit"):
                    app.analyze("c", "failed", before_commit=interrupt)
                self.assertEqual(visited, [True])
                self.assertEqual(app.archive.ids(), ("old",))
            with App(path) as app:
                with self.assertRaises(KeyError):
                    app.read("failed")
                self.assertEqual(app.read("old"), old)
                retried = app.analyze("c", "failed")
                self.assertEqual(retried.probabilities, old.probabilities)
                self.assertEqual(retried.covariance, old.covariance)
                self.assertEqual(app.archive.ids(), ("failed", "old"))
                self.assertEqual(app.store.connection.execute(
                    "PRAGMA foreign_key_check").fetchall(), [])
