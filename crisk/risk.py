"""Event-before-exit risk contributions for one immutable cohort."""
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
