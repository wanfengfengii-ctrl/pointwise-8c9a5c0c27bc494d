"""Paired end-to-end timing; separate fresh-process target allocation measurement."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter
import tracemalloc
from crisk import App
from crisk.model import dumps
from analysis_reference import calculate as reference
from analysis_workloads import workload

def fingerprint(report):
    return hashlib.sha256(dumps(report.record()).encode("utf-8")).hexdigest()

def one(directory, name, kind, subjects, implementation, measure_peak=False):
    path = Path(directory) / (name + ".sqlite")
    with App(path) as app:
        rows, times = workload(kind, subjects)
        app.apply(rows)
        app.freeze("c", times, (2, 1))
        del rows, times
        gc.collect()
        if measure_peak:
            tracemalloc.start()
        started = perf_counter()
        if implementation == "reference":
            report = app.archive.publish(reference(app.cohort("c"), "r"))
        else:
            report = app.analyze("c", "r")
        elapsed = perf_counter() - started
        peak = tracemalloc.get_traced_memory()[1] if measure_peak else None
        if measure_peak:
            tracemalloc.stop()
        # External checks do not contribute to the measured window.
        assert app.read("r") == report, "stored report differs"
        assert app.archive.ids() == ("r",), "unexpected publication"
        return dict(seconds=elapsed, peak_bytes=peak, digest=fingerprint(report), record=report.record())

def worker(args):
    with tempfile.TemporaryDirectory(prefix="crisk-analysis-bench-") as directory:
        if args.phase == "peak":
            return one(directory, "peak", args.kind, args.subjects, "target", True)
        order = ("reference", "target") if args.round % 2 == 0 else ("target", "reference")
        result = {}
        for name in order:
            result[name] = one(directory, name, args.kind, args.subjects, name)
        assert result["reference"]["record"] == result["target"]["record"], "report mismatch"
        return result

def child(kind, subjects, round_number, phase):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "_worker",
               "--kind", kind, "--subjects", str(subjects),
               "--round", str(round_number), "--phase", phase]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)

def benchmark(mode, kind, subjects):
    rounds = []
    for index in range(3):
        pair = child(kind, subjects, index, "pair")
        if mode == "target":
            peak = child(kind, subjects, index, "peak")
            assert peak["record"] == pair["reference"]["record"], "peak-run report mismatch"
            assert peak["peak_bytes"] <= 32 * 1024 * 1024, "allocation cap exceeded"
            pair["target"]["peak_bytes"] = peak["peak_bytes"]
        pair["reference"].pop("record")
        pair["target"].pop("record")
        rounds.append(pair)
        print(json.dumps(dict(stage="round", kind=kind, subjects=subjects,
                              round=index, measurements=pair)), flush=True)
    reference_time = statistics.median(r["reference"]["seconds"] for r in rounds)
    target_time = statistics.median(r["target"]["seconds"] for r in rounds)
    summary = dict(stage="summary", mode=mode, kind=kind, subjects=subjects,
                   reference_seconds=reference_time, target_seconds=target_time,
                   speed_ratio=target_time / reference_time,
                   target_peaks=[r["target"]["peak_bytes"] for r in rounds])
    print(json.dumps(summary), flush=True)
    if mode == "target":
        assert target_time <= reference_time / 8, "speed ratio exceeded"
    return summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("baseline", "target", "_worker"))
    parser.add_argument("--kind", choices=("long", "reentry"), required=True)
    parser.add_argument("--subjects", type=int, choices=(64, 256), required=True)
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--phase", choices=("pair", "peak"), default="pair")
    args = parser.parse_args()
    if args.mode == "_worker":
        print(json.dumps(worker(args)))
    else:
        benchmark(args.mode, args.kind, args.subjects)

if __name__ == "__main__":
    main()
