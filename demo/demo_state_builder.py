"""Build the app/state.json representation from pipeline results.

Keeps the data transformation separate from rendering and orchestration.
"""

from datetime import datetime
from demo_config import AS_OF, platform_display_name, COACH_FIELDS


def calculate_time_ago(iso_timestamp: str) -> str:
    """Convert ISO timestamp to 'X ago' format."""
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", ""))
    minutes = max(0, int((AS_OF - dt).total_seconds() // 60))

    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} hr ago"
    return f"{minutes // (24 * 60)} days ago"


def build_updated_line(last_event: dict | None) -> str:
    """Format the 'Updated X ago · Platform payout received' line."""
    if not last_event:
        return "Updated today"

    time_ago = calculate_time_ago(last_event["occurred_at"])
    source = platform_display_name(last_event["source"])
    return f"Updated {time_ago} · {source} payout received"


def build_factor_dict(factor) -> dict:
    """Convert a factor object to a state-compatible dictionary."""
    return {
        "label": factor.label,
        "status": factor.level,  # level from rules_engine maps to status UI
        "driver": factor.driver,
        "points": factor.points,
    }


def build_coach_dict(coach: dict) -> dict:
    """Extract only the fields needed for the app state."""
    return {key: coach[key] for key in COACH_FIELDS if key in coach}


def build_member_state(user: dict, result, coach: dict) -> dict:
    """Convert pipeline result into app/state.json member record."""
    connected_accounts = [a for a in user["accounts"] if a["connected"]]

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "score": result.score,
        "band": result.band,
        "baseline": result.baseline,
        "week_delta": result.week_delta,
        "updated_line": build_updated_line(result.last_event),
        "factors": [build_factor_dict(f) for f in result.factors],
        "next_milestone": result.next_milestone,
        "gap_to_next": result.gap_to_next,
        "unlocked": result.unlocked,
        "coach": build_coach_dict(coach),
        "recent_wins": coach["recent_wins"],
        "ledger": [
            {
                "event_type": e["event_type"],
                "delta": e["delta"],
                "occurred_at": e["occurred_at"],
            }
            for e in result.ledger
        ],
        "accounts": user["accounts"],
        "sources_connected": len(connected_accounts),
        "sources_total": len(user["accounts"]),
    }


def build_state_payload(members: list[dict]) -> dict:
    """Build the complete state.json payload."""
    return {
        "schema_version": 1,
        "as_of": "2026-07-20T14:00:00Z",
        "members": members,
    }
