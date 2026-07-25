"""Factor level assignment from behavioral metrics.

Takes derived metrics and applies business rules to assign factor levels.
Pure logic — no DB calls or dataclass construction here.
"""

from __future__ import annotations

from scoring_config import (
    RENT_EXCELLENT_MONTHS_KEY,
    RENT_GOOD_MONTHS_KEY,
    CV_EXCELLENT_MAX_KEY,
    CV_GOOD_MAX_KEY,
    CV_FAIR_MAX_KEY,
    DIVERSITY_LEVELS,
    DEFAULT_DIVERSITY_LEVEL,
    get_level_display,
)


def assign_rent_level(
    thresholds: dict, on_time_months: int, missed_rent: bool
) -> tuple[str, str]:
    """
    Assign rent & subscriptions factor level.
    Returns (level_key, why_string).
    """
    if missed_rent:
        return "NEEDS_WORK", "missed payment reported"

    excellent_threshold = thresholds.get(RENT_EXCELLENT_MONTHS_KEY, 12)
    good_threshold = thresholds.get(RENT_GOOD_MONTHS_KEY, 6)

    if on_time_months >= excellent_threshold:
        return "EXCELLENT", f"reported on time, {int(on_time_months)} months"
    elif on_time_months >= good_threshold:
        return "GOOD", f"reported on time, {int(on_time_months)} months"
    else:
        return "FAIR", f"{int(on_time_months)} months of history"


def assign_consistency_level(thresholds: dict, weekly_cv: float) -> tuple[str, str]:
    """
    Assign earnings consistency factor level.
    Returns (level_key, why_string).
    """
    excellent_max = thresholds.get(CV_EXCELLENT_MAX_KEY, 0.15)
    good_max = thresholds.get(CV_GOOD_MAX_KEY, 0.35)
    fair_max = thresholds.get(CV_FAIR_MAX_KEY, 0.60)

    if weekly_cv <= excellent_max:
        return "EXCELLENT", "highly steady weekly payouts"
    elif weekly_cv <= good_max:
        return "GOOD", "steady weekly payouts"
    elif weekly_cv <= fair_max:
        return "FAIR", "weekly payouts vary"
    else:
        return "NEEDS_WORK", "volatile weekly payouts"


def assign_diversity_level(n_sources: int) -> tuple[str, str]:
    """
    Assign platform diversity factor level.
    Returns (level_key, why_string).
    """
    level = DIVERSITY_LEVELS.get(n_sources, DEFAULT_DIVERSITY_LEVEL)
    return level, f"{n_sources} income sources connected"


def assign_trajectory_level(
    gap_day: str | None, weekly_amounts: list[float]
) -> tuple[str, str]:
    """
    Assign income trajectory factor level.
    Returns (level_key, why_string).
    """
    if gap_day:
        return "NEEDS_WORK", f"{gap_day} gap detected"

    # Trend detection: last 2 weeks vs first 2 weeks
    if len(weekly_amounts) >= 4:
        recent_sum = sum(weekly_amounts[-2:])
        early_sum = sum(weekly_amounts[:2])
        if early_sum > 0 and recent_sum > early_sum:
            return "GOOD", "earnings trending up"

    return "FAIR", "earnings holding steady"


def assign_all_factors(
    thresholds: dict, metrics: dict
) -> tuple[list[tuple[str, str, str]], dict]:
    """
    Assign all factor levels from metrics.
    Returns (list of (factor_key, level_key, why_string), flags dict).
    """
    factors = [
        (
            "rent_subscriptions",
            *assign_rent_level(
                thresholds, metrics["on_time_rent_months"], metrics["missed_rent"]
            ),
        ),
        (
            "earnings_consistency",
            *assign_consistency_level(thresholds, metrics["weekly_cv"]),
        ),
        (
            "platform_diversity",
            *assign_diversity_level(metrics["n_sources"]),
        ),
        (
            "income_trajectory",
            *assign_trajectory_level(metrics["gap_day"], metrics["weekly_amounts"]),
        ),
    ]

    flags = {}
    if metrics["gap_day"]:
        flags["gap_day"] = metrics["gap_day"]

    return factors, flags
