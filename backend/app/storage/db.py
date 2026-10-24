"""SQLite persistence for the learner profile & progress (criterion #14)."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager

from ..config import settings


@contextmanager
def _conn():
    con = sqlite3.connect(settings.db_path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS learners (
                name TEXT PRIMARY KEY,
                profile TEXT,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student TEXT,
                topic TEXT,
                score REAL,
                strong TEXT,
                weak TEXT,
                misconceptions TEXT,
                next_topic TEXT,
                created_at REAL
            );
            """
        )


def save_profile(profile) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO learners (name, profile, updated_at) VALUES (?,?,?)",
            (profile.name, profile.model_dump_json(), time.time()),
        )


def record_result(report) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO history
               (student, topic, score, strong, weak, misconceptions, next_topic, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "Student",
                report.topic,
                report.score,
                json.dumps(report.strong_areas),
                json.dumps(report.weak_areas),
                json.dumps(report.misconceptions),
                report.next_topic,
                time.time(),
            ),
        )


def get_history(student: str = "Student", limit: int = 20) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM history WHERE student=? ORDER BY created_at DESC LIMIT ?",
            (student, limit),
        ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "topic": r["topic"],
                "score": r["score"],
                "strong": json.loads(r["strong"] or "[]"),
                "weak": json.loads(r["weak"] or "[]"),
                "next_topic": r["next_topic"],
                "created_at": r["created_at"],
            }
        )
    return out