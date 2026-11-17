"""Independent differential and boundary checks for the optimized analyze.

Every case compares the optimized App.analyze against the frozen
analysis_reference.calculate and, for small cohorts, the raw-segment polynomial
oracle from tests.oracle.  Cases are deterministic and disjoint from the
frozen benchmark workloads.  Exits nonzero on any mismatch.
"""
from dataclasses import replace
from fractions import Fraction as F
import random
import sys
from crisk import App, Observation
from analysis_reference import build_risk as reference_risk, calculate as reference
from crisk.risk import build_risk
from tests.oracle import oracle

def obs(subject, segment, enter, exit, event=0, weight=1, revision=1):
    return Observation(subject, segment, revision, weight, enter, exit, event)

def check(name, rows, times, causes=(1, 2), use_oracle=True):
    with App() as app:
        app.apply(rows)
        app.freeze("c", times, causes)
        cohort = app.cohort("c")
        result = app.analyze("c", "r")
        expected = reference(cohort, "r")
        assert result == expected, (name, "frozen reference")
        fields = lambda frames: [(f.time, f.risk, f.events) for f in frames]
        assert fields(build_risk(cohort)) == fields(reference_risk(cohort)), \
            (name, "build_risk")
        if use_oracle:
            independently = oracle(cohort.observations, cohort.times, cohort.causes)
            assert (result.survival, result.probabilities,
                    result.covariance) == independently, (name, "oracle")
    return result

def boundary_cases():
    check("empty", [], [1, -1, 1])
    check("single", [obs("A", "a", 0, 2, 1)], [2, 0, 2])
    # Same instant: both causes, a censoring, and a delayed entry all tied.
    check("ties", [obs("A", "a", 0, 2, 1), obs("B", "b", 0, 2, 2, 2),
                   obs("C", "c", 0, 2), obs("D", "d", 2, 3, 1, 3)],
          [F(3), F(2), F(1), F(2)], (2, 1))
    # Shared identity across a reentry gap differs from split identity only
    # in covariance, never in probabilities.
    rows = [obs("A", "a0", 0, 1, 0, 2), obs("A", "a1", 2, 4, 1, 2),
            obs("B", "b", 0, 1, 2), obs("C", "c", 0, 4, 2),
            obs("D", "d", 1, 4), obs("E", "e", 4, 5, 1, F(3, 2))]
    times, causes = [F(4), F(1), F(5), F(4), F(0)], (2, 1)
    shared = check("reentry", rows, times, causes)
    split = [replace(r, subject=r.subject + "-x") if r.segment == "a1" else r
             for r in rows]
    apart = check("split-identity", split, times, causes)
    assert apart.probabilities == shared.probabilities
    assert apart.covariance != shared.covariance
    # Zero survival factor: risk exhausts at t=1; later events keep the
    # recursion running but defined probabilities stay put.
    check("exhaustion", [obs("A", "a", 0, 1, 1), obs("B", "b", 0, 1, 2),
                         obs("C", "c", 2, 3, 1), obs("D", "d", 2, 4)],
          [0, 1, 2, 3, 4, 4])
    # Fractional weights and uniform rescaling invariance.
    weighted = [obs("A", "a", -1, 1, 1, F(2, 3)), obs("B", "b", 0, 2, 2, 2),
                obs("C", "c", 1, 2, 0, F(3, 2))]
    base = check("fractional", weighted, [2, 0, 1, 2])
    scaled = check("rescaled", [replace(r, weight=r.weight * 7) for r in weighted],
                   [2, 0, 1, 2])
    assert (scaled.probabilities, scaled.covariance) == \
           (base.probabilities, base.covariance)
    # Legal segment split of one subject leaves the report unchanged.
    whole = [obs("A", "a", 0, 3, 1), obs("B", "b", 0, 1, 2), obs("C", "c", 0, 3)]
    pieces = [obs("A", "a0", 0, 1), obs("A", "a1", 1, 3, 1)] + whole[1:]
    assert check("split", pieces, [0, 1, 3, 4]) == \
        check("whole", whole, [0, 1, 3, 4])

def random_histories(cases=24):
    rng = random.Random(20261117)
    for case in range(cases):
        rows = []
        for subject in range(rng.randint(1, 7)):
            who = f"s{subject}"
            weight = F(rng.randint(1, 5), rng.randint(1, 4))
            clock = rng.randint(-2, 1)
            for piece in range(rng.randint(1, 3)):
                leave = clock + rng.randint(1, 3)
                last = piece == rng.randint(0, 2) or leave >= 6
                event = rng.randint(0, 2) if last else 0
                rows.append(obs(who, f"{who}-{piece}", clock, leave, event, weight))
                if event:
                    break
                clock = leave + rng.randint(0, 2)
                if clock >= 6:
                    break
        times = [rng.choice([-1, 0, 1, 2, 3, 4, 5, 6, F(5, 2)])
                 for _ in range(rng.randint(1, 5))]
        for causes in ((1, 2), (2, 1)):
            check(f"random-{case}-{causes}", rows, times, causes)

def medium_cohort():
    rows = []
    for i in range(24):
        who = f"m{i:02d}"
        weight = F(1 + i % 3, 2)
        if i % 4 == 3:
            rows.append(obs(who, who + "a", 0, 2, 0, weight))
            rows.append(obs(who, who + "b", 3, 5 + i % 5, 1 + i % 2, weight))
        else:
            rows.append(obs(who, who, 0, 1 + i % 6, (1 + i % 2) if i % 3 else 0,
                            weight))
    check("medium", rows, [6, 3, 1, 6, F(7, 2)], (2, 1), use_oracle=False)

def main():
    boundary_cases()
    random_histories()
    medium_cohort()
    print("DIFFERENTIAL_CHECKS_OK", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
