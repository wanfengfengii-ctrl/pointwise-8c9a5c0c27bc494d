"""JSON CLI and a correction/freeze/reopen demonstration."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import sqlite3
from .app import App

def demonstrate(path):
    rows = json.loads((Path(__file__).resolve().parent.parent /
                       "samples" / "joint.json").read_text(encoding="utf-8"))
    with App(path) as app:
        app.apply(rows)
        app.freeze("before", [4, 1, 5, 4], (2, 1))
        before = app.analyze("before", "before-report")
        print(json.dumps(dict(stage="before", result=before.record()), ensure_ascii=False))
        correction = dict(rows[1], revision=2, event=2)
        app.apply([correction])
        app.freeze("after", [4, 1, 5, 4], (2, 1))
        after = app.analyze("after", "after-report")
        print(json.dumps(dict(stage="after", result=after.record()), ensure_ascii=False))
    with App(path) as app:
        old = app.read("before-report")
        again = app.analyze("before", "recomputed")
        assert old == before
        assert again.probabilities == before.probabilities
        assert again.covariance == before.covariance
        assert after.probabilities != before.probabilities
        print(json.dumps(dict(stage="reopened", stable=True, result=old.record()),
                         ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(prog="crisk")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--db")
    for name in ("apply", "freeze", "analyze", "read"):
        command = sub.add_parser(name)
        command.add_argument("--db", required=True)
        if name == "apply":
            command.add_argument("batch")
        elif name == "freeze":
            command.add_argument("cohort_id")
            command.add_argument("times", nargs="+")
            command.add_argument("--causes", nargs=2, type=int, default=[1, 2])
        elif name == "analyze":
            command.add_argument("cohort_id")
            command.add_argument("report_id")
        else:
            command.add_argument("report_id")
    args = parser.parse_args()
    try:
        if args.command == "demo":
            if args.db:
                demonstrate(args.db)
            else:
                with tempfile.TemporaryDirectory(prefix="crisk-") as directory:
                    demonstrate(Path(directory) / "demo.sqlite")
            return 0
        with App(args.db) as app:
            if args.command == "apply":
                rows = json.loads(Path(args.batch).read_text(encoding="utf-8"))
                result = asdict(app.apply(rows))
            elif args.command == "freeze":
                cohort = app.freeze(args.cohort_id, args.times, args.causes)
                result = dict(cohort_id=cohort.id, source_epoch=cohort.source_epoch)
            elif args.command == "analyze":
                result = app.analyze(args.cohort_id, args.report_id).record()
            else:
                result = app.read(args.report_id).record()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, json.JSONDecodeError) as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=False))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
