"""Atomic result publication and independent immutable reads."""
import json
from .model import identifier, dumps, report_from_record

class Archive:
    def __init__(self, store):
        self.store = store

    def ids(self):
        return tuple(row[0] for row in self.store.connection.execute(
            "SELECT id FROM reports ORDER BY id"))

    def read(self, report_id):
        identifier(report_id)
        row = self.store.connection.execute(
            "SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        return report_from_record(json.loads(row[0]))

    def publish(self, report, before_commit=None):
        if before_commit is not None and not callable(before_commit):
            raise ValueError("before_commit must be callable")
        payload = dumps(report.record())
        with self.store.transaction() as db:
            old = db.execute("SELECT payload FROM reports WHERE id=?",
                             (report.id,)).fetchone()
            if old is not None and old[0] != payload:
                raise ValueError("report ID already bound")
            if old is None:
                db.execute("INSERT INTO reports VALUES (?,?,?)",
                           (report.id, report.cohort_id, payload))
                if before_commit is not None:
                    before_commit()
        return self.read(report.id)
