"""SCORE · Python rules engine, SQL-stored weights.

score = 300 + S(factor points at current level) + S(event ledger deltas)

Factors (max 550 pts total -> 300–850 range):
    Rent & subscriptions   max 140
    Earnings consistency   max 130
    Platform diversity     max  90   (18 per connected source, cap 5)
    Income trajectory      max 190

Levels are recomputed from the canonical ledger on a monthly cadence
("settlement"). Between settlements, micro-events move the score in
real time through the ledger rules in event_rules — those are the
"+5 Rent reported on time / +3 4-week consistency streak" deltas the
member sees in Coach, and the reason the score header can honestly say
"Updated 2 min ago · DoorDash payout received".

All configuration and threshold keys are in scoring_config.py.
Metrics extraction is in metrics.py.
Factor assignment is in factors.py.
This module is pure orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import db
from scoring_config import (
    FACTORS,
    SCORE_MIN,
    SCORE_MAX,
    SCORE_RANGE,
    LEVELS,
    LEDGER_LOOKBACK_WEEKS,
    WEEK_DAYS,
)
from metrics import compute_metrics
from factors import assign_all_factors


@dataclass
class FactorResult:
    """A single factor with its computed level and points."""

    factor: str
    label: str
    level: str
    points: int
    driver: str  # one-line "why" shown under the factor name


@dataclass
class ScoreResult:
    """Complete score computation result."""

    user_id: str
    baseline: int
    ledger: list[dict]
    score: int
    band: str
    factors: list[FactorResult]
    week_delta: int
    next_milestone: dict | None
    gap_to_next: int | None
    unlocked: list[dict] = field(default_factory=list)  # milestones crossed this week
    flags: dict = field(default_factory=dict)
    last_event: dict | None = None


def compute(
    conn,
    user_id: str,
    records: list[dict],
    ledger_events: list[dict],
    as_of: datetime,
) -> ScoreResult:
    """
    Compute the full score for a user.

    Args:
        conn: Database connection (for thresholds, milestone rules, etc.)
        user_id: The user's ID
        records: Canonical ledger (normalized payout/rent/sub records)
        ledger_events: Scored micro-events (with event_type and occurred_at)
        as_of: Reference time for time-based computations (e.g., week cutoffs)

    Returns:
        ScoreResult with score, band, factors, ledger, and metadata.
    """
    # Step 1: Derive behavioral metrics from the ledger
    metrics = compute_metrics(records, as_of)

    # Step 2: Assign factor levels based on metrics
    factor_assignments, flags = assign_all_factors(
        db.thresholds_dict(conn), metrics
    )

    # Step 3: Build factor results and compute baseline
    factors: list[FactorResult] = []
    for factor_key, level_key, why in factor_assignments:
        # Find label and max points from config
        label = next(
            (lbl for fk, lbl, _ in FACTORS if fk == factor_key), factor_key
        )
        points = db.factor_points(conn, factor_key, level_key)
        factors.append(
            FactorResult(
                factor=factor_key,
                label=label,
                level=LEVELS.get(level_key, level_key),
                points=points,
                driver=why,
            )
        )

    baseline = SCORE_MIN + sum(f.points for f in factors)

    # Step 4: Apply ledger events
    ledger = []
    for event in ledger_events:
        delta, win_label = db.event_delta(conn, event["event_type"])
        ledger.append(
            {
                **event,
                "delta": delta,
                "win_label": win_label,
            }
        )

    score = max(SCORE_MIN, min(SCORE_MAX, baseline + sum(e["delta"] for e in ledger)))

    # Step 5: Compute week-over-week delta
    week_ago = as_of - timedelta(days=LEDGER_LOOKBACK_WEEKS * WEEK_DAYS)
    week_delta = sum(
        e["delta"]
        for e in ledger
        if datetime.fromisoformat(e["occurred_at"].replace("Z", "")) >= week_ago
    )

    # Step 6: Milestones
    milestone = db.next_milestone(conn, score)
    unlocked = (
        db.milestones_crossed(conn, score - week_delta, score)
        if week_delta > 0
        else []
    )

    # Step 7: Last event
    payout_records = [r for r in records if r["kind"] == "payout"]
    last_event = (
        max(payout_records, key=lambda r: r["occurred_at"])
        if payout_records
        else None
    )

    return ScoreResult(
        user_id=user_id,
        baseline=baseline,
        ledger=ledger,
        score=score,
        band=db.band_for(conn, score),
        factors=factors,
        week_delta=week_delta,
        next_milestone=milestone,
        gap_to_next=(milestone["threshold"] - score) if milestone else None,
        unlocked=unlocked,
        flags=flags,
        last_event=last_event,
    )
