"""Public end-to-end API; one App owns one SQLite connection."""
from .storage import Store
from .ledger import Ledger
from .cohort import Cohorts
from .archive import Archive
from .report import calculate

class App:
    def __init__(self, path=":memory:"):
        self.store = Store(path)
        self.ledger = Ledger(self.store)
        self.cohorts = Cohorts(self.store, self.ledger)
        self.archive = Archive(self.store)

    def apply(self, batch):
        return self.ledger.apply(batch)

    def freeze(self, cohort_id, times, causes=(1, 2)):
        return self.cohorts.freeze(cohort_id, times, causes)

    def cohort(self, cohort_id):
        return self.cohorts.get(cohort_id)

    def analyze(self, cohort_id, report_id, *, before_commit=None):
        cohort = self.cohorts.get(cohort_id)
        return self.archive.publish(calculate(cohort, report_id), before_commit)

    def read(self, report_id):
        return self.archive.read(report_id)

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
