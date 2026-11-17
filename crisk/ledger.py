"""Revision acceptance and validation of the complete effective history."""
import json
from collections import defaultdict
from .model import Observation, Receipt, dumps

def validate_history(observations):
    groups = defaultdict(list)
    for row in observations:
        groups[row.subject].append(row)
    for rows in groups.values():
        rows.sort(key=lambda x: (x.enter, x.exit, x.segment))
        if len({x.weight for x in rows}) != 1:
            raise ValueError("subject weights differ")
        for previous, following in zip(rows, rows[1:]):
            if previous.exit > following.enter:
                raise ValueError("overlapping observation segments")
            if previous.event:
                raise ValueError("observation after terminal event")

class Ledger:
    def __init__(self, store):
        self.store = store

    def current(self):
        return tuple(Observation.from_record(json.loads(payload))
                     for (payload,) in self.store.connection.execute(
                         "SELECT payload FROM current ORDER BY segment"))

    @property
    def epoch(self):
        return self.store.connection.execute(
            "SELECT value FROM metadata WHERE key='epoch'").fetchone()[0]

    def apply(self, batch):
        rows = tuple(x if isinstance(x, Observation) else Observation.from_record(x)
                     for x in batch)
        if len({x.segment for x in rows}) != len(rows):
            raise ValueError("duplicate segment in batch")
        with self.store.transaction() as db:
            effective = {x.segment: x for x in self.current()}
            changed = []
            for row in rows:
                payload = dumps(row.record())
                known = db.execute("SELECT payload FROM history WHERE segment=? AND revision=?",
                                   (row.segment, row.revision)).fetchone()
                if known and known[0] != payload:
                    raise ValueError("revision conflict")
                old = effective.get(row.segment)
                if old is not None and row.revision <= old.revision:
                    continue
                effective[row.segment] = row
                changed.append(row)
            validate_history(effective.values())
            for row in changed:
                payload = dumps(row.record())
                db.execute("INSERT INTO history VALUES (?,?,?)",
                           (row.segment, row.revision, payload))
                db.execute("INSERT OR REPLACE INTO current VALUES (?,?)",
                           (row.segment, payload))
            if changed:
                db.execute("UPDATE metadata SET value=value+1 WHERE key='epoch'")
            receipt = Receipt(self.epoch, tuple(sorted(x.segment for x in changed)))
        return receipt
