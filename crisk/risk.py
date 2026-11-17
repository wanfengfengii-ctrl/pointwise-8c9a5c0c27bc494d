"""Event-before-exit risk contributions for one immutable cohort."""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from fractions import Fraction
from collections import defaultdict

@dataclass(frozen=True)
class RiskFrame:
    cohort_id: str
    time: Fraction
    risk: tuple[tuple[str, Fraction], ...]
    events: tuple[tuple[str, int, Fraction], ...]

def build_risk(cohort):
    frames = []
    observations = cohort.observations
    for time in sorted({x.exit for x in observations if x.event}):
        risk = defaultdict(Fraction)
        events = defaultdict(Fraction)
        for row in observations:
            if row.enter < time <= row.exit:
                risk[row.subject] += row.weight
            if row.exit == time and row.event:
                events[row.subject, row.event] += row.weight
        frames.append(RiskFrame(
            cohort.id, time, tuple(sorted(risk.items())),
            tuple((subject, cause, weight)
                  for (subject, cause), weight in sorted(events.items()))))
    return tuple(frames)

@dataclass(frozen=True)
class RiskSeries:
    """Compact event-time aggregates plus per-subject contribution windows.

    times/cause1/cause2 are aligned with the sorted event times; risk is the
    total weight at risk just before each event time.  subjects groups every
    observation row by exact subject identity; each row carries its weight,
    the half-open window (lo, hi] of event-time indexes it is at risk for,
    and its terminal event cause (0 when censored).
    """
    times: tuple[Fraction, ...]
    risk: tuple[Fraction, ...]
    cause1: tuple[Fraction, ...]
    cause2: tuple[Fraction, ...]
    subjects: tuple[tuple[tuple[str, tuple[tuple[Fraction, int, int, int], ...]], ...], ...]

def sweep(observations):
    """One-pass event-time aggregates and subject-grouped risk windows."""
    rows = list(observations)
    times = tuple(sorted({x.exit for x in rows if x.event}))
    by_enter = sorted(rows, key=lambda x: x.enter)
    by_exit = sorted(rows, key=lambda x: x.exit)
    enters = [x.enter for x in by_enter]
    exits = [x.exit for x in by_exit]
    entered = [Fraction(0)]
    for row in by_enter:
        entered.append(entered[-1] + row.weight)
    exited = [Fraction(0)]
    for row in by_exit:
        exited.append(exited[-1] + row.weight)
    risk = []
    for time in times:
        # enter < exit for every row, so {exit < t} is a subset of {enter < t}.
        risk.append(entered[bisect_left(enters, time)] -
                    exited[bisect_left(exits, time)])
    cause1 = defaultdict(Fraction)
    cause2 = defaultdict(Fraction)
    for row in rows:
        if row.event == 1:
            cause1[row.exit] += row.weight
        elif row.event == 2:
            cause2[row.exit] += row.weight
    grouped = defaultdict(list)
    for row in rows:
        lo = bisect_right(times, row.enter)
        hi = bisect_right(times, row.exit)
        grouped[row.subject].append((row.weight, lo, hi, row.event))
    return RiskSeries(
        times, tuple(risk),
        tuple(cause1[time] for time in times),
        tuple(cause2[time] for time in times),
        tuple((subject, tuple(grouped[subject])) for subject in sorted(grouped)))
