from dataclasses import FrozenInstanceError, replace
from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest
from crisk import App
from tests.helpers import MemoryCase, obs

class TestHistory(unittest.TestCase):
    def test_correction_and_reopen(self):
        with tempfile.TemporaryDirectory(prefix="crisk-test-") as directory:
            path = Path(directory) / "history.sqlite"
            with App(path) as app:
                rows = [obs("A", "a", 0, 2, 1), obs("B", "b", 0, 2, 2)]
                app.apply(rows)
                app.freeze("old", [2, 0, 2], (2, 1))
                before = app.analyze("old", "old-report")
                frozen = app.cohort("old")
                app.apply([replace(rows[0], revision=2, event=2)])
                app.freeze("new", [2, 0, 2], (2, 1))
                after = app.analyze("new", "new-report")
                self.assertEqual(after.probabilities, (F(1), F(0), F(0), F(0), F(1), F(0)))
                self.assertNotEqual(after.probabilities, before.probabilities)
                self.assertEqual(app.cohort("old"), frozen)
                self.assertEqual(app.read("old-report"), before)
                app.apply([replace(row, revision=3, event=0) for row in rows])
                app.freeze("zero", [1, 2])
                zero = app.analyze("zero", "zero-report")
                self.assertEqual(zero.probabilities, (F(0),) * 4)
                self.assertEqual(zero.survival, (F(1), F(1)))
            with App(path) as reopened:
                self.assertEqual(reopened.read("old-report"), before)
                self.assertEqual(reopened.read("new-report"), after)
                self.assertEqual(reopened.read("zero-report"), zero)
                self.assertEqual(reopened.cohort("old"), frozen)
                again = reopened.analyze("old", "recomputed")
                self.assertEqual(replace(again, id=before.id), before)

class TestIsolation(MemoryCase):
    def test_input_output_and_bindings(self):
        row = obs("A", "a", 0, 2, 1).record()
        self.app.apply([row])
        row["event"] = 2
        times = [2, 0, 2]
        cohort = self.app.freeze("c", times, (2, 1))
        times[0] = 100
        report = self.app.analyze("c", "r")
        self.assertEqual(report.coordinates, ((F(2), 2), (F(2), 1),
                                              (F(0), 2), (F(0), 1),
                                              (F(2), 2), (F(2), 1)))
        self.assertEqual(report.probabilities[:2], (F(0), F(1)))
        record = report.record()
        record["covariance"][0][0] = "999"
        self.assertEqual(self.app.read("r"), report)
        with self.assertRaises(FrozenInstanceError):
            cohort.times = ()
        with self.assertRaises(TypeError):
            report.covariance[0][0] = F(1)
        self.assertEqual(self.app.freeze("c", [2, 0, 2], (2, 1)), cohort)
        self.assertEqual(self.app.analyze("c", "r"), report)
        with self.assertRaises(ValueError):
            self.app.freeze("c", [3])
        self.app.freeze("other", [3])
        with self.assertRaises(ValueError):
            self.app.analyze("other", "r")
        for bad_times, causes in (([], (1, 2)), ([True], (1, 2)),
                                  ([1], (1, 1)), ([1], (True, 2))):
            with self.assertRaises(ValueError):
                self.app.freeze("bad", bad_times, causes)
        with self.assertRaises(KeyError):
            self.app.cohort("bad")
        self.assertEqual(self.app.archive.ids(), ("r",))
