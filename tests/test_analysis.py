from dataclasses import replace
from fractions import Fraction as F
from itertools import permutations, product
from crisk import App
from crisk.risk import build_risk
from tests.helpers import MemoryCase, obs, joint_rows
from tests.oracle import oracle

class TestAnalysis(MemoryCase):
    def assertOracle(self, report, rows, times, causes=(1, 2)):
        expected = oracle(rows, times, causes)
        self.assertEqual((report.survival, report.probabilities, report.covariance), expected)

    def test_two_causes(self):
        rows = [obs("A", "a", 0, 2, 1), obs("B", "b", 0, 2, 2)]
        report = self.analyze(rows, [2])
        self.assertEqual(report.probabilities, (F(1, 2), F(1, 2)))
        self.assertEqual(report.survival, (F(0),))
        self.assertEqual(report.covariance, ((F(1, 8), F(-1, 8)),
                                             (F(-1, 8), F(1, 8))))
        self.assertOracle(report, rows, [2])

    def test_entry_event_censor_ties(self):
        rows = [obs("A", "a", 0, 2, 1), obs("B", "b", 0, 2, 2, 2),
                obs("C", "c", 0, 2), obs("D", "d", 2, 3, 1, 3)]
        times, causes = [F(3), F(2), F(1), F(2)], (2, 1)
        reference = None
        for order in permutations(rows):
            with App() as app:
                app.apply(order)
                cohort = app.freeze("c", times, causes)
                report = app.analyze("c", "r")
                self.assertEqual(build_risk(cohort)[0].risk,
                                 (("A", F(1)), ("B", F(2)), ("C", F(1))))
                self.assertEqual(report.probabilities,
                                 (F(1, 2), F(1, 2), F(1, 2), F(1, 4),
                                  F(0), F(0), F(1, 2), F(1, 4)))
                self.assertOracle(report, rows, times, causes)
                if reference is None:
                    reference = report
                self.assertEqual(report, reference)
        with App() as app:
            app.apply([obs("A", "a", 0, 2, 1), obs("B", "b", 2, 3)])
            app.freeze("c", [2])
            self.assertEqual(app.analyze("c", "r").probabilities, (F(1), F(0)))

    def test_shared_subject_reentry(self):
        rows = joint_rows()
        times, causes = [F(4), F(1), F(5), F(4), F(0)], (2, 1)
        report = self.analyze(rows, times, causes)
        self.assertEqual(report.probabilities[:6],
                         (F(7, 16), F(3, 8), F(1, 4), F(0), F(7, 16), F(9, 16)))
        self.assertOracle(report, rows, times, causes)
        self.assertEqual(report.coordinates, tuple((t, c) for t in times for c in causes))
        self.assertNotEqual(report.covariance[1][2], 0)
        # Distinct subject identity for the second segment is another valid cohort.
        independent = [replace(row, subject="A-second") if row.segment == "a1" else row
                       for row in rows]
        with App() as app:
            app.apply(independent)
            app.freeze("c", times, causes)
            different = app.analyze("c", "r")
            self.assertEqual(different.probabilities, report.probabilities)
            self.assertNotEqual(different.covariance, report.covariance)

    def test_splitting_zero_exhaustion(self):
        rows = [obs("A", "a", 0, 3, 1), obs("B", "b", 0, 1, 2),
                obs("C", "c", 0, 3)]
        report = self.analyze(rows, [0, 1, 3, 4])
        split = [obs("A", "a0", 0, 1), obs("A", "a1", 1, 3, 1)] + rows[1:]
        for transformed in (split, [replace(row, weight=row.weight * 7) for row in rows]):
            with App() as app:
                app.apply(transformed)
                app.freeze("c", [0, 1, 3, 4])
                other = app.analyze("c", "r")
                self.assertEqual((other.probabilities, other.covariance),
                                 (report.probabilities, report.covariance))
        with App() as app:
            app.freeze("empty", [-1, 10])
            empty = app.analyze("empty", "empty")
            self.assertEqual(empty.probabilities, (F(0),) * 4)
            self.assertEqual(empty.survival, (F(1), F(1)))
            self.assertTrue(all(x == 0 for row in empty.covariance for x in row))
            app.apply([obs("A", "a", 0, 1, 1), obs("B", "b", 1, 2, 2)])
            app.freeze("exhausted", [1, 2])
            exhausted = app.analyze("exhausted", "r")
            self.assertEqual(exhausted.probabilities, (F(1), F(0), F(1), F(0)))
            self.assertOracle(exhausted, app.ledger.current(), [1, 2])

    def test_polynomial_catalog(self):
        for events in product((0, 1, 2), repeat=3):
            rows = [obs("A", "a", -1, 1, events[0], F(2, 3)),
                    obs("B", "b", 0, 2, events[1], 2),
                    obs("C", "c", 1, 2, events[2], F(3, 2))]
            with App() as app:
                app.apply(rows)
                app.freeze("c", [2, 0, 1, 2])
                report = app.analyze("c", "r")
                self.assertOracle(report, rows, [2, 0, 1, 2])
