"""Shared DB helper — loads the SQL-stored weights into SQLite.

Local demo uses SQLite (stdlib). In production the same DDL runs on
Aurora Serverless / RDS Postgres; the rules engine only ever reads.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WEIGHTS_SQL = REPO_ROOT / "data" / "seed" / "weights.sql"


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection and (re)apply the weights seed."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(WEIGHTS_SQL.read_text())
    return conn


def factor_points(conn: sqlite3.Connection, factor: str, level: str) -> int:
    row = conn.execute(
        "SELECT points FROM factor_levels WHERE factor=? AND level=?",
        (factor, level),
    ).fetchone()
    if row is None:
        raise KeyError(f"No weight for {factor}/{level}")
    return int(row["points"])


def diversity_points(conn: sqlite3.Connection, n_sources: int) -> int:
    row = conn.execute("SELECT points_per_source, max_sources FROM diversity_weights").fetchone()
    return int(row["points_per_source"]) * min(n_sources, int(row["max_sources"]))


def event_delta(conn: sqlite3.Connection, event_type: str) -> tuple[int, str | None]:
    row = conn.execute(
        "SELECT delta, win_label FROM event_rules WHERE event_type=?", (event_type,)
    ).fetchone()
    if row is None:
        return 0, None
    return int(row["delta"]), row["win_label"]


def band_for(conn: sqlite3.Connection, score: int) -> str:
    row = conn.execute(
        "SELECT band FROM score_bands WHERE ? BETWEEN lo AND hi", (score,)
    ).fetchone()
    return row["band"] if row else "Unscored"


def next_milestone(conn: sqlite3.Connection, score: int):
    row = conn.execute(
        "SELECT threshold, product, detail FROM milestones "
        "WHERE threshold > ? ORDER BY threshold LIMIT 1",
        (score,),
    ).fetchone()
    return dict(row) if row else None


def milestones_crossed(conn: sqlite3.Connection, prev_score: int, score: int) -> list[dict]:
    """Milestones unlocked when the score moved prev_score -> score."""
    rows = conn.execute(
        "SELECT threshold, product, detail FROM milestones "
        "WHERE threshold > ? AND threshold <= ? ORDER BY threshold",
        (prev_score, score),
    ).fetchall()
    return [dict(r) for r in rows]


def threshold(conn: sqlite3.Connection, name: str) -> float:
    row = conn.execute("SELECT value FROM behavior_thresholds WHERE name=?", (name,)).fetchone()
    return float(row["value"])
