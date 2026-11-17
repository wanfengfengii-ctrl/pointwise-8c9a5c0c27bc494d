"""SQLite v1: exact JSON snapshots, single-worker transactions."""
from contextlib import contextmanager
import sqlite3

class Store:
    def __init__(self, path):
        self.connection = sqlite3.connect(str(path), isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA temp_store=MEMORY")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.connection.close()
            raise ValueError("unsupported archive version")
        try:
            with self.transaction() as db:
                db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
                db.execute("INSERT OR IGNORE INTO metadata VALUES ('epoch', 0)")
                db.execute("CREATE TABLE IF NOT EXISTS history (segment TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(segment, revision))")
                db.execute("CREATE TABLE IF NOT EXISTS current (segment TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS cohorts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, cohort_id TEXT NOT NULL REFERENCES cohorts(id), payload TEXT NOT NULL)")
                db.execute("PRAGMA user_version=1")
        except BaseException:
            self.connection.close()
            raise

    @contextmanager
    def transaction(self):
        db = self.connection
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise

    def close(self):
        self.connection.close()
