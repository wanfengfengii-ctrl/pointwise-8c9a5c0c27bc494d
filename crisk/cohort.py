"""Freeze complete copies of effective observations and ordered requests."""
import json
from .model import (Cohort, identifier, rational, dumps,
                    cohort_record, cohort_from_record)

class Cohorts:
    def __init__(self, store, ledger):
        self.store, self.ledger = store, ledger

    def get(self, cohort_id):
        identifier(cohort_id)
        row = self.store.connection.execute(
            "SELECT payload FROM cohorts WHERE id=?", (cohort_id,)).fetchone()
        if row is None:
            raise KeyError(cohort_id)
        return cohort_from_record(json.loads(row[0]))

    def freeze(self, cohort_id, times, causes=(1, 2)):
        identifier(cohort_id)
        times = tuple(rational(t) for t in times)
        causes = tuple(causes)
        if not times:
            raise ValueError("at least one request time required")
        if (len(causes) != 2 or any(type(c) is not int for c in causes)
                or set(causes) != {1, 2}):
            raise ValueError("causes must be a permutation of (1, 2)")
        with self.store.transaction() as db:
            cohort = Cohort(cohort_id, self.ledger.epoch,
                            self.ledger.current(), times, causes)
            payload = dumps(cohort_record(cohort))
            old = db.execute("SELECT payload FROM cohorts WHERE id=?",
                             (cohort_id,)).fetchone()
            if old is not None and old[0] != payload:
                raise ValueError("cohort ID already bound")
            if old is None:
                db.execute("INSERT INTO cohorts VALUES (?,?)", (cohort_id, payload))
        return cohort
