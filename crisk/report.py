"""Weighted Aalen-Johansen and exact subject-direction propagation.

The forward recursion is evaluated once for the point values, and each
requested probability coordinate gets one reverse adjoint sweep over the
event timeline.  Because the derivative of any output with respect to a
subject multiplier is linear in that subject's per-time contributions, the
adjoint coefficients (A for risk weight, B for event weight) turn each
subject gradient into a windowed sum over its own rows; gradients are merged
per subject before the covariance outer product.  All arithmetic stays in
exact Fractions, so results equal the frozen reference bit for bit.
"""
from bisect import bisect_right
from fractions import Fraction as F
from .model import Report, identifier
from .risk import sweep

def _adjoints(series, outputs):
    """Reverse-mode coefficients per requested output.

    outputs is an iterable of (cause, steps) pairs, where cause is 1 or 2 and
    steps is the number of event times covered by the request.  Returns a dict
    mapping each output to (prefix, B1, B2): prefix is the running sum of the
    risk-coefficient array A over event-time indexes, and B1/B2 hold the
    per-event-time coefficients of the cause-1/cause-2 event weights.
    """
    times, risk, cause1, cause2 = (series.times, series.risk,
                                  series.cause1, series.cause2)
    events = len(times)
    zero, one = F(0), F(1)
    survival = [one]
    counts = {1: [zero], 2: [zero]}
    for index in range(events):
        total = risk[index]
        d1, d2 = cause1[index], cause2[index]
        if total <= 0 or d1 + d2 > total:
            raise ValueError("invalid risk contributions")
        previous = survival[-1]
        counts[1].append(counts[1][-1] + previous * d1 / total)
        counts[2].append(counts[2][-1] + previous * d2 / total)
        survival.append(previous * (total - d1 - d2) / total)
    adjoints = {}
    for cause, steps in outputs:
        if (cause, steps) in adjoints:
            continue
        lam_survival, lam1, lam2 = zero, zero, zero
        if cause == 1:
            lam1 = one
        else:
            lam2 = one
        A = [zero] * (events + 1)
        B1 = [zero] * (events + 1)
        B2 = [zero] * (events + 1)
        for step in range(steps, 0, -1):
            total = risk[step - 1]
            d1, d2 = cause1[step - 1], cause2[step - 1]
            share = survival[step - 1] / total
            B1[step] = (lam1 - lam_survival) * share
            B2[step] = (lam2 - lam_survival) * share
            A[step] = share * (lam_survival * (d1 + d2) -
                               lam1 * d1 - lam2 * d2) / total
            lam_survival = (lam_survival * (total - d1 - d2) +
                            lam1 * d1 + lam2 * d2) / total
        prefix = [zero]
        for step in range(1, steps + 1):
            prefix.append(prefix[-1] + A[step])
        prefix.extend([prefix[-1]] * (events - steps))
        adjoints[(cause, steps)] = (prefix, B1, B2)
    return survival, counts, adjoints

def calculate(cohort, report_id):
    identifier(report_id)
    series = sweep(cohort.observations)
    times = series.times
    zero = F(0)
    requests = [bisect_right(times, time) for time in cohort.times]
    outputs = [(cause, steps) for steps in requests for cause in cohort.causes]
    survival, counts, adjoints = _adjoints(series, outputs)
    size = len(outputs)
    covariance = [[zero] * size for _ in range(size)]
    for _, rows in series.subjects:
        gradient = []
        for (cause, steps) in outputs:
            prefix, B1, B2 = adjoints[(cause, steps)]
            total = zero
            for weight, lo, hi, event in rows:
                total += weight * (prefix[hi] - prefix[lo])
                if event == 1:
                    total += weight * B1[hi]
                elif event == 2:
                    total += weight * B2[hi]
            gradient.append(total)
        for i in range(size):
            if gradient[i]:
                row = covariance[i]
                for j in range(size):
                    row[j] += gradient[i] * gradient[j]
    return Report(
        report_id, cohort.id, cohort.source_epoch,
        tuple((t, cause) for t in cohort.times for cause in cohort.causes),
        tuple(survival[steps] for steps in requests),
        tuple(counts[cause][steps] for (cause, steps) in outputs),
        tuple(tuple(row) for row in covariance))
