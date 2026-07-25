"""Configuration for the demo runner.

All constants, strings, and lookup tables live here so run_demo.py is just logic.
"""

from datetime import datetime

# Demo timestamp - Monday, July 20, 2026, 2:00 PM
AS_OF = datetime(2026, 7, 20, 14, 0)

# Platform display names (source key -> user-facing name)
PLATFORM_NAMES = {
    "doordash": "DoorDash",
    "uber": "Uber",
    "lyft": "Lyft",
    "instacart": "Instacart",
}

# Default source when not recognized
DEFAULT_PLATFORM = "Bank"

# Console formatting
DIVIDER = "─" * 62

# Fields to include in coach output when building state
COACH_FIELDS = (
    "headline",
    "how_to_improve",
    "why_important",
    "reason_code",
    "model",
)

# Time formatting boundaries (in minutes)
TIME_BOUNDARIES = [
    (60, lambda m: f"{m} min ago"),
    (48 * 60, lambda m: f"{m // 60} hr ago"),
]

def format_time_ago(minutes: int) -> str:
    """Convert minutes to a human-readable 'ago' string."""
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} hr ago"
    return f"{minutes // (24 * 60)} days ago"


def platform_display_name(source: str) -> str:
    """Get the user-facing name for a platform source."""
    return PLATFORM_NAMES.get(source, DEFAULT_PLATFORM)
