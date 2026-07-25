"""Console rendering for demo output.

Each render function is responsible for one visual element, making the output
easy to test and modify without touching the pipeline logic.
"""

from datetime import datetime
from demo_config import (
    AS_OF,
    DIVIDER,
    format_time_ago,
    platform_display_name,
    COACH_FIELDS,
)


def format_score_header(name: str, score: int, band: str) -> str:
    """Format the member name and score line."""
    return f"{name:<24} GIGSCORE  {score}  ·  {band}"


def format_updated_line(last_event: dict | None) -> str:
    """Format the 'updated X minutes ago' line."""
    if not last_event:
        return f"{'':24} Updated today"

    occurred_at = last_event["occurred_at"]
    dt = datetime.fromisoformat(occurred_at.replace("Z", ""))
    minutes = max(0, int((AS_OF - dt).total_seconds() // 60))
    time_str = format_time_ago(minutes)
    source = platform_display_name(last_event["source"])

    return f"{'':24} Updated {time_str} · {source} payout received"


def format_week_delta(week_delta: int, baseline: int, score: int) -> str:
    """Format the week delta and baseline comparison line."""
    sign = "▲ +" if week_delta >= 0 else "▼ "
    delta_display = f"{week_delta:+d}" if week_delta >= 0 else f"{week_delta}"
    ledger_change = f"{score - baseline:+d}"

    return (
        f"{'':24} {sign}{delta_display} this week"
        f"   (baseline {baseline} {ledger_change} ledger)"
    )


def format_factors(factors: list) -> list[str]:
    """Format all factors as console lines."""
    lines = ["  What's driving it"]
    for factor in factors:
        lines.append(
            f"    {factor.label:<22} {factor.level.upper():<11} {factor.points:>3} pts"
            f"  · {factor.driver}"
        )
    return lines


def format_unlocked(unlocked: list) -> list[str]:
    """Format unlocked milestones."""
    lines = []
    for item in unlocked:
        lines.append(f"  UNLOCKED     {item['threshold']} — {item['product']} 🎉")
    return lines


def format_next_milestone(milestone: dict, gap: int) -> list[str]:
    """Format next milestone section."""
    if not milestone:
        return []
    return [
        f"  NEXT UNLOCK  {gap} pts to {milestone['product']}",
        f"               {milestone['detail']}",
    ]


def format_coach(headline: str, how: str) -> list[str]:
    """Format coach advice."""
    return [
        f"  COACH        {headline}",
        f"               {how}",
    ]


def format_recent_wins(wins: list) -> list[str]:
    """Format recent wins summary."""
    if not wins:
        return []
    wins_str = "   ".join(f"{w['delta']} {w['label']}" for w in wins)
    return [f"  Recent wins  {wins_str}"]


def format_ledger(ledger: list) -> str:
    """Format the ledger events."""
    if not ledger:
        return f"  Ledger       —"
    events_str = ", ".join(f"{e['event_type']} {e['delta']:+d}" for e in ledger)
    return f"  Ledger       {events_str}"


def format_audit(audit_id: int, model: str, reason_code: str) -> str:
    """Format audit trail line."""
    return f"  Audit        row #{audit_id} · {model} · reason {reason_code}"


def render_member(user: dict, result, coach: dict) -> None:
    """Print a complete member scorecard to console."""
    print(DIVIDER)
    print(format_score_header(user["name"], result.score, result.band))
    print(format_updated_line(result.last_event))
    print(format_week_delta(result.week_delta, result.baseline, result.score))
    print()
    print("\n".join(format_factors(result.factors)))
    print()

    if result.unlocked:
        print("\n".join(format_unlocked(result.unlocked)))
        print()

    milestone_lines = format_next_milestone(result.next_milestone, result.gap_to_next)
    if milestone_lines:
        print("\n".join(milestone_lines))
        print()

    print("\n".join(format_coach(coach["headline"], coach["how_to_improve"])))
    print()

    wins_lines = format_recent_wins(coach["recent_wins"])
    if wins_lines:
        print("\n".join(wins_lines))
        print()

    print(format_ledger(result.ledger))
    print(format_audit(coach["audit_id"], coach["model"], coach["reason_code"]))
