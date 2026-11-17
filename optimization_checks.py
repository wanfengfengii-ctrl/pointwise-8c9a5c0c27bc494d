"""Original regressions plus independent small-cohort and joint-resource checks."""
from dataclasses import replace
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from crisk import App, Observation
from analysis_reference import calculate as reference
from analysis_workloads import workload
from tests.oracle import oracle

def small_checks():
    cases = [workload(kind, 8) for kind in ("long", "reentry")]
    cases.append(([Observation("A", "a", 1, 1, 0, 1, 1),
                   Observation("B", "b", 1, 2, 1, 2, 2)], [2, 1, 0, 2]))
    cases.append(([], [1, -1, 1]))
    for number, (rows, times) in enumerate(cases):
        for causes in ((1, 2), (2, 1)):
            with App() as app:
                app.apply(rows)
                cohort = app.freeze("c", times, causes)
                result = app.analyze("c", "r")
                expected = reference(cohort, "r")
                assert result == expected, (number, causes, "frozen reference")
                independently = oracle(cohort.observations, cohort.times, cohort.causes)
                assert (result.survival, result.probabilities, result.covariance) == independently
                if number == 1:
                    assert all(value > 0 for value in result.survival)
                    split_identity = [replace(r, subject=r.subject + "-late")
                                      if r.segment.endswith("b") else r for r in rows]
                    with App() as other:
                        other.apply(split_identity)
                        other.freeze("other", times, causes)
                        separate = other.analyze("other", "separate")
                        assert separate.probabilities == result.probabilities
                        assert separate.covariance != result.covariance
                if rows:
                    changed = replace(rows[0], revision=2, weight=rows[0].weight * 3)
                    # A whole-subject revision preserves valid histories.
                    subject_rows = [replace(r, revision=2, weight=changed.weight)
                                    for r in rows if r.subject == changed.subject]
                    app.apply(subject_rows)
                    assert app.read("r") == result
                    assert app.analyze("c", "again") == replace(result, id="again")
                def fail():
                    raise RuntimeError("joint check")
                try:
                    app.analyze("c", "retry", before_commit=fail)
                except RuntimeError as error:
                    assert str(error) == "joint check"
                else:
                    raise AssertionError("publication callback did not fail")
                assert "retry" not in app.archive.ids()
                assert app.analyze("c", "retry") == replace(result, id="retry")
    print("INDEPENDENT_JOINT_CHECKS_OK", flush=True)

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("baseline", "target"):
        raise SystemExit("usage: optimization_checks.py baseline|target")
    root = Path(__file__).resolve().parent
    completed = subprocess.run([sys.executable, "-B", "-m", "unittest",
                                "discover", "-s", "tests", "-v"], cwd=root)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    small_checks()
    if sys.argv[1] == "target":
        from bench_analysis import benchmark
        for kind in ("long", "reentry"):
            small = benchmark("target", kind, 64)
            large = benchmark("target", kind, 256)
            growth = large["target_seconds"] / small["target_seconds"]
            print(json.dumps(dict(stage="growth", kind=kind, ratio=growth)), flush=True)
            assert growth <= 6, "fourfold-size growth exceeded"
    print("BASELINE_BUSINESS_OK" if sys.argv[1] == "baseline" else "OPTIMIZED_ANALYSIS_OK")

if __name__ == "__main__":
    main()
