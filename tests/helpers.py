from fractions import Fraction as F
from crisk import App, Observation
import unittest

def obs(subject, segment, enter, exit, event=0, weight=1, revision=1):
    return Observation(subject, segment, revision, weight, enter, exit, event)

def joint_rows():
    return [obs("A", "a0", 0, 1, 0, 2),
            obs("A", "a1", 2, 4, 1, 2),
            obs("B", "b", 0, 1, 2),
            obs("C", "c", 0, 4, 2),
            obs("D", "d", 1, 4),
            obs("E", "e", 4, 5, 1, F(3, 2))]

class MemoryCase(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.addCleanup(self.app.close)

    def analyze(self, rows, times, causes=(1, 2)):
        self.app.apply(rows)
        self.app.freeze("cohort", times, causes)
        return self.app.analyze("cohort", "report")
