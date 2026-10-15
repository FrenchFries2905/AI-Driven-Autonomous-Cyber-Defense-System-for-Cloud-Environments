"""
src/reliability/evidence_log.py

Append-only evidence log for the Evidence Aggregation & Reliability Engine.
Every detection + mitigation event is stored in a local SQLite database
(SQLite: a single-file database built into Python, no server needed).

"Append-only" is enforced by database triggers: any UPDATE or DELETE on the
events table is rejected, so the audit trail cannot be edited after the fact.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.path.join("evidence", "evidence_log.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc   TEXT    NOT NULL,
    source_ip       TEXT,
    predicted_class TEXT    NOT NULL,
    confidence      REAL    NOT NULL,
    risk_level      TEXT    NOT NULL,
    action          TEXT    NOT NULL,
    target          TEXT,
    success         INTEGER NOT NULL,
    mttd_ms         REAL    NOT NULL,
    mttr_ms         REAL    NOT NULL,
    reasoning       TEXT,
    detail          TEXT
);

CREATE TABLE IF NOT EXISTS health_checks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT    NOT NULL,
    ok            INTEGER NOT NULL
);

CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'evidence log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'evidence log is append-only'); END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceLog:
    def __init__(self, db_path: str = DB_PATH):
        folder = os.path.dirname(db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        # check_same_thread=False + a lock: FastAPI may call from worker threads
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def record_event(self, record: dict) -> int:
        """
        Store one detection + mitigation event.
        `record` is the dict built by the orchestrator: the decision from the
        policy engine, the mitigation outcome, mttd_ms, mttr_ms and source_ip.
        Returns the new event id.
        """
        outcome = record.get("mitigation_outcome", {})
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO events
                   (timestamp_utc, source_ip, predicted_class, confidence, risk_level,
                    action, target, success, mttd_ms, mttr_ms, reasoning, detail)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    _now(),
                    record.get("source_ip"),
                    record["predicted_class"],
                    float(record["confidence"]),
                    record["risk_level"],
                    record["action"],
                    outcome.get("target"),
                    1 if outcome.get("success", False) else 0,
                    float(record["mttd_ms"]),
                    float(record["mttr_ms"]),
                    record.get("reasoning"),
                    outcome.get("detail"),
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def record_health_check(self, ok: bool) -> None:
        """Store one service health check (used to estimate uptime)."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO health_checks (timestamp_utc, ok) VALUES (?, ?)",
                (_now(), 1 if ok else 0),
            )
            self._conn.commit()

    def fetch_events(self, limit: int = None, newest_first: bool = True) -> list:
        order = "DESC" if newest_first else "ASC"
        sql = f"SELECT * FROM events ORDER BY id {order}"
        params = ()
        if limit:
            sql += " LIMIT ?"
            params = (int(limit),)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def fetch_health_checks(self) -> list:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM health_checks ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
