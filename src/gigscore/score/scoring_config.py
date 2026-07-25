"""Scoring configuration and thresholds.

All magic numbers, factor definitions, and business rules live here.
The rules_engine imports this and applies the logic.
"""

# Factor definitions (order, label, max points)
FACTORS = [
    ("rent_subscriptions", "Rent & subscriptions", 140),
    ("earnings_consistency", "Earnings consistency", 130),
    ("platform_diversity", "Platform diversity", 90),
    ("income_trajectory", "Income trajectory", 190),
]

# Score bounds
SCORE_MIN = 300
SCORE_MAX = 850
SCORE_RANGE = SCORE_MAX - SCORE_MIN

# Factor level display names
LEVELS = {
    "EXCELLENT": "Excellent",
    "GOOD": "Good",
    "FAIR": "Fair",
    "NEEDS_WORK": "Needs work",
}

# Database threshold keys (kept for DB compatibility)
RENT_EXCELLENT_MONTHS_KEY = "rent_excellent_months"
RENT_GOOD_MONTHS_KEY = "rent_good_months"
CV_EXCELLENT_MAX_KEY = "cv_excellent_max"
CV_GOOD_MAX_KEY = "cv_good_max"
CV_FAIR_MAX_KEY = "cv_fair_max"

# Platform diversity points per source (before capping at 90 total)
DIVERSITY_POINTS_PER_SOURCE = 18
DIVERSITY_SOURCE_CAP = 5

# Platform diversity level thresholds
DIVERSITY_LEVELS = {
    5: "EXCELLENT",
    3: "GOOD",
    2: "FAIR",
}
DEFAULT_DIVERSITY_LEVEL = "NEEDS_WORK"

# Income trajectory gap detection
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
GAP_DETECTION_MIN_BREADTH = 4  # min working days Mon–Fri to scan for gaps
GAP_DETECTION_MIN_WEEKS = 1  # min weeks to compute weekday averages
GAP_THRESHOLD_RATIO = 0.20  # gap day < 20% of overall_daily_avg

# Week analysis
MIN_WEEKLY_SAMPLES = 2  # min samples for coefficient of variation

# Ledger event types and their point deltas
# (moved to DB in production, but these are the event types the system recognizes)
EVENT_TYPES = {
    "rent_reported_on_time",
    "subscription_reported_on_time",
    "consistency_streak_4wk",
    "steady_tuesday_pair",
    "source_connected",
    "rent_payment_missed",
}

# Time windows
WEEK_DAYS = 7
LEDGER_LOOKBACK_WEEKS = 1  # for computing week_delta


def get_factor_label(factor_key: str) -> str | None:
    """Get the display label for a factor key."""
    for key, label, _ in FACTORS:
        if key == factor_key:
            return label
    return None


def get_factor_max_points(factor_key: str) -> int | None:
    """Get the max points for a factor."""
    for key, _, max_pts in FACTORS:
        if key == factor_key:
            return max_pts
    return None


def get_level_display(level_key: str) -> str:
    """Get the UI display name for a level."""
    return LEVELS.get(level_key, level_key)
