"""Weighted Aalen-Johansen and exact subject-direction propagation."""
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction as F
from .model import Report, identifier
from .risk import build_risk

@dataclass(frozen=True)
class Direction:
    value: F
    derivative: F = F(0)

    def __add__(self, other):
        return Direction(self.value + other.value, self.derivative + other.derivative)

    def __sub__(self, other):
        return Direction(self.value - other.value, self.derivative - other.derivative)

    def __mul__(self, other):
        return Direction(self.value * other.value,
                         self.derivative * other.value + self.value * other.derivative)

    def __truediv__(self, other):
        return Direction(self.value / other.value,
                         (self.derivative * other.value - self.value * other.derivative)
                         / (other.value * other.value))

def _evaluate(cohort, frames, subject):
    survival = Direction(F(1))
    cumulative = {1: Direction(F(0)), 2: Direction(F(0))}
    timeline = []
    for frame in frames:
        if frame.cohort_id != cohort.id:
            raise ValueError("risk frame belongs to another cohort")
        risk = sum((Direction(weight, weight if who == subject else F(0))
                    for who, weight in frame.risk), Direction(F(0)))
        counts = {1: Direction(F(0)), 2: Direction(F(0))}
        for who, cause, weight in frame.events:
            counts[cause] = counts[cause] + Direction(
                weight, weight if who == subject else F(0))
        if risk.value <= 0 or counts[1].value + counts[2].value > risk.value:
            raise ValueError("invalid risk contributions")
        for cause in (1, 2):
            cumulative[cause] = cumulative[cause] + survival * (counts[cause] / risk)
        survival = survival * (Direction(F(1)) - (counts[1] + counts[2]) / risk)
        timeline.append((survival, cumulative[1], cumulative[2]))
    event_times = [frame.time for frame in frames]
    probabilities, survivals = [], []
    initial = (Direction(F(1)), Direction(F(0)), Direction(F(0)))
    for time in cohort.times:
        index = bisect_right(event_times, time) - 1
        state = initial if index < 0 else timeline[index]
        survivals.append(state[0])
        probabilities.extend(state[cause] for cause in cohort.causes)
    return tuple(survivals), tuple(probabilities)

def calculate(cohort, report_id):
    identifier(report_id)
    frames = build_risk(cohort)
    survivals, probabilities = _evaluate(cohort, frames, None)
    subjects = sorted({row.subject for row in cohort.observations})
    size = len(probabilities)
    covariance = [[F(0) for _ in range(size)] for _ in range(size)]
    for subject in subjects:
        _, values = _evaluate(cohort, frames, subject)
        gradient = [x.derivative for x in values]
        for i in range(size):
            for j in range(size):
                covariance[i][j] += gradient[i] * gradient[j]
    return Report(
        report_id, cohort.id, cohort.source_epoch,
        tuple((t, cause) for t in cohort.times for cause in cohort.causes),
        tuple(x.value for x in survivals), tuple(x.value for x in probabilities),
        tuple(tuple(row) for row in covariance))
