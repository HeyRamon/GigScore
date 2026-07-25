"""Behavioral metrics from canonical ledger.

Derives weekly consistency, daily averages, gap detection, rent/sub history
from the normalized ledger records. No scoring logic here — just data extraction.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

from scoring_config import (
    WEEKDAY_NAMES,
    MIN_WEEKLY_SAMPLES,
    GAP_DETECTION_MIN_BREADTH,
    GAP_DETECTION_MIN_WEEKS,
    GAP_THRESHOLD_RATIO,
)


def _week_key(d: datetime) -> str:
    """ISO week key: YYYY-Www."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_start(d: datetime) -> datetime:
    """Start of the ISO week containing date d."""
    iso = d.isocalendar()
    return datetime.fromisocalendar(iso[0], iso[1], 1)


def extract_records_by_kind(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by their kind."""
    by_kind = defaultdict(list)
    for record in records:
        by_kind[record["kind"]].append(record)
    return dict(by_kind)


def compute_weekly_amounts(payouts: list[dict], as_of: datetime) -> dict[str, float]:
    """Sum payouts by ISO week (complete weeks only, before as_of)."""
    cutoff = _week_start(as_of)
    complete = [
        p
        for p in payouts
        if datetime.fromisoformat(p["occurred_at"].replace("Z", "")) < cutoff
    ]

    weekly = defaultdict(float)
    for payout in complete:
        dt = datetime.fromisoformat(payout["occurred_at"].replace("Z", ""))
        weekly[_week_key(dt)] += payout["amount"]

    return dict(weekly)


def compute_consistency(weekly_amounts: dict[str, float]) -> float:
    """Coefficient of variation of weekly payouts."""
    amounts = list(weekly_amounts.values())
    if len(amounts) < MIN_WEEKLY_SAMPLES or not amounts:
        return 1.0
    mean = statistics.mean(amounts)
    if mean == 0:
        return 1.0
    return statistics.pstdev(amounts) / mean


def compute_daily_breakdown(
    payouts: list[dict], as_of: datetime
) -> tuple[dict[tuple[int, str], float], float, dict[int, float]]:
    """
    Return (daily totals, overall daily avg, weekday averages).
    daily: (weekday_0to6, week_key) -> amount
    overall_daily_avg: mean of all non-zero days
    weekday_avgs: weekday_0to6 -> average across all weeks
    """
    cutoff = _week_start(as_of)
    complete = [
        p
        for p in payouts
        if datetime.fromisoformat(p["occurred_at"].replace("Z", "")) < cutoff
    ]

    daily = defaultdict(float)
    for payout in complete:
        dt = datetime.fromisoformat(payout["occurred_at"].replace("Z", ""))
        daily[(dt.weekday(), _week_key(dt))] += payout["amount"]

    active_days = set(daily.keys())
    overall_daily_avg = sum(daily.values()) / len(active_days) if active_days else 0.0

    # Per-weekday average across all weeks
    weeks = sorted(set(week for _, week in active_days))
    n_weeks = len(weeks)
    weekday_avgs = {}

    for wd in range(7):
        vals = [daily.get((wd, w), 0.0) for w in weeks]
        present = sum(1 for w in weeks if (wd, w) in daily)
        if present:
            weekday_avgs[wd] = sum(vals) / n_weeks if n_weeks else 0.0

    return daily, overall_daily_avg, weekday_avgs


def detect_gap_days(
    weekday_avgs: dict[int, float],
    overall_daily_avg: float,
    n_weeks: int,
) -> tuple[list[int], str | None]:
    """
    Detect days earning < gap_threshold_ratio of overall_daily_avg.
    Returns (sorted gap_day indices, worst gap day name or None).
    """
    if not overall_daily_avg or n_weeks < GAP_DETECTION_MIN_WEEKS:
        return [], None

    # Only scan Mon–Fri if member works 4+ of them most weeks
    breadth = sum(1 for wd in range(5) if wd in weekday_avgs)
    if breadth < GAP_DETECTION_MIN_BREADTH:
        return [], None

    gap_days = [
        wd
        for wd in range(5)
        if weekday_avgs.get(wd, 0) < GAP_THRESHOLD_RATIO * overall_daily_avg
    ]
    gap_days.sort(key=lambda wd: weekday_avgs.get(wd, 0))

    gap_day_name = WEEKDAY_NAMES[gap_days[0]] if gap_days else None
    return gap_days, gap_day_name


def compute_rent_history(rent_records: list[dict]) -> tuple[int, bool]:
    """Count on-time rent months and detect any missed payments."""
    on_time_months = sum(
        1 for r in rent_records if r.get("meta", {}).get("on_time", True)
    )
    missed = any(not r.get("meta", {}).get("on_time", True) for r in rent_records)
    return on_time_months, missed


def compute_metrics(records: list[dict], as_of: datetime) -> dict:
    """Extract all behavioral metrics from the canonical ledger."""
    by_kind = extract_records_by_kind(records)

    payouts = by_kind.get("payout", [])
    rents = by_kind.get("rent_payment", [])
    subs = by_kind.get("subscription_payment", [])

    # Sources: gig platforms + bank if rent/subs reported through it
    sources = sorted(
        {p["source"] for p in payouts}
        | ({"plaid"} if (rents or subs) else set())
    )

    weekly = compute_weekly_amounts(payouts, as_of)
    consistency = compute_consistency(weekly)
    daily, overall_daily_avg, weekday_avgs = compute_daily_breakdown(payouts, as_of)

    n_weeks = len(set(week for _, week in daily.keys()))
    gap_days, gap_day_name = detect_gap_days(
        weekday_avgs, overall_daily_avg, n_weeks
    )

    on_time_rent_months, missed_rent = compute_rent_history(rents)
    n_sub_merchants = len({s.get("meta", {}).get("merchant") for s in subs})

    return {
        "sources": sources,
        "n_sources": len(sources),
        "weekly_cv": consistency,
        "weekly_amounts": list(weekly.values()),
        "weekday_avgs": weekday_avgs,
        "overall_daily_avg": overall_daily_avg,
        "gap_days": gap_days,
        "gap_day": gap_day_name,
        "on_time_rent_months": on_time_rent_months,
        "missed_rent": missed_rent,
        "n_sub_merchants": n_sub_merchants,
    }
