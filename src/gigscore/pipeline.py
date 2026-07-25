"""Pipeline wiring — event-driven serverless on AWS, simulated locally.

Production topology (infra/template.yaml):
    API Gateway -> IngestFn -> EventBridge "gigscore" bus
        -> NormalizeFn -> Aurora canonical_ledger
        -> ScoreFn (on payout / rent / connect events, and monthly settle)
        -> ExplainFn -> Aurora audit_log -> CreditWise surface

Local demo: the same four handlers run in-process against
data/events/stream.jsonl and an in-memory SQLite.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .normalize.transforms import transform
from .score import db
from .score.rules_engine import compute, derive_metrics, ScoreResult
from .explain.orchestrator import explain

REPO_ROOT = Path(__file__).resolve().parents[2]
STREAM = REPO_ROOT / "data" / "events" / "stream.jsonl"


# --------------------------------------------------------------------------
# Micro-event detectors (run after each normalized record lands)
# --------------------------------------------------------------------------

def detect_ledger_events(records: list[dict], as_of: datetime) -> list[dict]:
    """Turn canonical records into scoreable micro-events."""
    events: list[dict] = []

    for r in records:
        if r["kind"] == "rent_payment":
            events.append({
                "event_type": "rent_reported_on_time" if r["meta"].get("on_time", True)
                else "rent_payment_missed",
                "occurred_at": r["occurred_at"],
            })
        elif r["kind"] == "subscription_payment" and r["meta"].get("on_time", True):
            events.append({"event_type": "subscription_reported_on_time",
                           "occurred_at": r["occurred_at"]})
        elif r["kind"] == "account_connected":
            events.append({"event_type": "source_connected",
                           "occurred_at": r["occurred_at"]})

    # 4-week consistency streak: four consecutive complete weeks within 20%
    # of the 4-week average awards +3, at most once per 4-week window.
    cutoff_iso = as_of.isocalendar()
    current_wk = (cutoff_iso[0], cutoff_iso[1])
    weekly = defaultdict(float)
    for r in records:
        if r["kind"] == "payout":
            dt = datetime.fromisoformat(r["occurred_at"].replace("Z", ""))
            iso = dt.isocalendar()
            if (iso[0], iso[1]) != current_wk:
                weekly[(iso[0], iso[1])] += r["amount"]
    weeks = sorted(weekly)
    if len(weeks) >= 4:
        last4 = [weekly[w] for w in weeks[-4:]]
        avg = sum(last4) / 4
        if avg and all(abs(v - avg) / avg <= 0.20 for v in last4):
            events.append({"event_type": "consistency_streak_4wk",
                           "occurred_at": _week_end(weeks[-1])})

    # Two steady <gap-day>s: two consecutive weeks where the member's gap
    # day lands within 20% of their average active day awards +12.
    m = derive_metrics(records, as_of)
    if m["gap_days"]:
        wd = m["gap_days"][0]  # worst gap, as surfaced in Coach
        per_week = defaultdict(float)
        for r in records:
            if r["kind"] == "payout":
                dt = datetime.fromisoformat(r["occurred_at"].replace("Z", ""))
                if dt.weekday() == wd:
                    iso = dt.isocalendar()
                    per_week[(iso[0], iso[1])] += r["amount"]
        steady = [wk for wk in weeks
                  if per_week.get(wk, 0.0) >= 0.80 * m["overall_daily_avg"]]
        for a, b in zip(steady, steady[1:]):
            if _next_week(a) == b:
                events.append({"event_type": "steady_tuesday_pair",
                               "occurred_at": _week_end(b)})
                break

    events.sort(key=lambda e: e["occurred_at"])
    return events


def _next_week(wk):
    y, w = wk
    monday = datetime.fromisocalendar(y, w, 1) + timedelta(weeks=1)
    iso = monday.isocalendar()
    return (iso[0], iso[1])


def _week_end(wk) -> str:
    y, w = wk
    return datetime.fromisocalendar(y, w, 7).strftime("%Y-%m-%dT18:00:00Z")


# --------------------------------------------------------------------------
# End-to-end run for one user
# --------------------------------------------------------------------------

def run_user(conn, user: dict, envelopes: list[dict], as_of: datetime,
             window_days: int = 7) -> tuple[ScoreResult, dict]:
    """INGEST envelopes -> NORMALIZE -> SCORE -> EXPLAIN for one member."""
    records = sorted((transform(e) for e in envelopes
                      if e["raw"].get("user_id") == user["user_id"]),
                     key=lambda r: r["occurred_at"])
    ledger_events = [e for e in detect_ledger_events(records, as_of)
                     if datetime.fromisoformat(e["occurred_at"].replace("Z", ""))
                     >= as_of - timedelta(days=window_days)]
    result = compute(conn, user["user_id"], records, ledger_events, as_of)
    coach = explain(conn, result)
    return result, coach


def load_stream(path: Path = STREAM) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --------------------------------------------------------------------------
# AWS entry point (ScoreFn in infra/template.yaml)
# --------------------------------------------------------------------------

def score_handler(event, context=None):  # pragma: no cover - AWS entry point
    """EventBridge `gigscore.canonical` / monthly settle -> ScoreResult.

    In AWS the canonical ledger is read from Aurora via the Data API; the
    demo passes records in the event for parity with the local runner.
    """
    detail = event.get("detail", {})
    conn = db.connect(detail.get("db_path", ":memory:"))
    as_of = datetime.fromisoformat(detail.get("as_of", datetime.now().isoformat()))
    records = detail.get("records", [])
    ledger = detect_ledger_events(records, as_of)
    result = compute(conn, detail.get("user_id", "unknown"), records, ledger, as_of)
    return {"detail-type": "gigscore.scored", "score": result.score,
            "band": result.band, "week_delta": result.week_delta}
