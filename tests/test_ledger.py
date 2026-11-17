from dataclasses import replace
from fractions import Fraction
from crisk import Observation
from tests.helpers import MemoryCase, obs

class TestLedger(MemoryCase):
    def test_invalid_subject_history(self):
        original = obs("A", "a", 0, 2)
        self.app.apply([original])
        self.app.freeze("c", [2])
        report = self.app.analyze("c", "r")
        before, epoch = self.app.ledger.current(), self.app.ledger.epoch
        invalid = [
            [obs("A", "b", 1, 3)],
            [replace(original, revision=2, event=1), obs("A", "b", 2, 3)],
            [obs("A", "b", 2, 3, weight=2)],
        ]
        for batch in invalid:
            with self.assertRaises(ValueError):
                self.app.apply(batch + [obs("X", "x", 0, 1)])
            self.assertEqual(self.app.ledger.current(), before)
            self.assertEqual(self.app.ledger.epoch, epoch)
            self.assertEqual(self.app.read("r"), report)
        self.assertEqual(self.app.store.connection.execute(
            "SELECT count(*) FROM history").fetchone()[0], 1)

    def test_revision_conflict(self):
        initial = obs("A", "a", 0, 2)
        receipt = self.app.apply([initial])
        self.assertEqual(receipt.changed, ("a",))
        newest = replace(initial, revision=3, event=1)
        self.app.apply([newest])
        epoch = self.app.ledger.epoch
        for conflict in (replace(newest, event=2), replace(initial, event=2)):
            with self.assertRaises(ValueError):
                self.app.apply([obs("B", "b", 0, 2), conflict])
            self.assertEqual(self.app.ledger.current(), (newest,))
            self.assertEqual(self.app.ledger.epoch, epoch)
        for replay in (newest, replace(initial, revision=2, event=2), initial):
            result = self.app.apply([replay])
            self.assertEqual(result.changed, ())
            self.assertEqual(result.epoch, epoch)
            self.assertEqual(self.app.ledger.current(), (newest,))
        # Valid final histories are checked after all replacements, not row by row.
        self.app.apply([replace(newest, revision=4, event=0), obs("A", "a2", 2, 3, 2)])
        self.assertEqual(len(self.app.ledger.current()), 2)

    def test_fields_and_atomic_input(self):
        good = obs("A", "a", 0, 1).record()
        bad_fields = [
            dict(good, weight=0), dict(good, weight=True), dict(good, weight=0.5),
            dict(good, weight="1/0"), dict(good, enter="1"), dict(good, exit=False),
            dict(good, revision=True), dict(good, revision=0),
            dict(good, event=True), dict(good, event=3), dict(good, subject=""),
            dict(good, extra=1)
        ]
        for row in bad_fields:
            with self.assertRaises(ValueError):
                self.app.apply([good, row])
            self.assertEqual(self.app.ledger.current(), ())
        with self.assertRaises(ValueError):
            self.app.apply([good, good])
        self.assertEqual(Observation("A", "a", 1, "2/3", -2, "1/2", 0).weight,
                         Fraction(2, 3))
