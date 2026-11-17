"""Deterministic long-coverage and shared-subject reentry cohorts."""
from crisk import Observation

def workload(kind, subjects):
    if kind not in ("long", "reentry") or subjects < 8 or subjects % 8:
        raise ValueError("unknown workload or invalid subject count")
    events = subjects // 2
    rows = []
    for i in range(subjects):
        end = i + 1 if i < events else events + 1
        who = f"s{i:04d}"
        event = 1 + i % 2 if i < events else 0
        if kind == "reentry" and end > events // 2 and i < 3 * subjects // 4:
            rows.append(Observation(who, who + "a", 1, 1, 0, events // 4, 0))
            rows.append(Observation(who, who + "b", 1, 1, events // 2, end, event))
        else:
            rows.append(Observation(who, who, 1, 1, 0, end, event))
    return rows, [events, events // 2, events // 4, events]
