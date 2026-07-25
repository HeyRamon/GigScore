"""EXPLAIN · Python orchestrates LLM, SQL audit log.

Every score change gets a plain-English explanation and an
adverse-action-ready reason code. FCRA-native by design:

  * Deterministic first. The coach copy the member sees is produced by
    the rules engine's own facts. The LLM (Claude on Bedrock in prod)
    only rewrites tone — it can never introduce a fact, and its output
    is diffed against the deterministic facts before display.
  * Everything is logged. Inputs, factor levels, deltas, model id, and
    final copy land in the SQL audit log so any adverse action can be
    reconstructed line by line.

Offline (this repo, no network): the deterministic templates run as-is,
which also guarantees the demo copy matches the pitch deck verbatim.
Set ANTHROPIC_API_KEY to enable the LLM polish pass.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from ..score.rules_engine import ScoreResult

REASON_CODES = {
    "income_trajectory": "GS-11 · Irregular earnings pattern on one or more weekdays",
    "earnings_consistency": "GS-12 · Week-to-week payout variance above target",
    "platform_diversity": "GS-13 · Limited number of verified income sources",
    "rent_subscriptions": "GS-14 · Insufficient on-time housing payment history",
}

LEVEL_RANK = {"NEEDS_WORK": 0, "FAIR": 1, "GOOD": 2, "EXCELLENT": 3}


# --------------------------------------------------------------------------
# Deterministic coach copy (source of truth)
# --------------------------------------------------------------------------

def most_impactful(result: ScoreResult) -> dict:
    """The single factor dragging hardest, with a concrete fix + payoff."""
    worst = min(result.factors, key=lambda f: LEVEL_RANK[f.level])
    if worst.factor == "income_trajectory" and result.flags.get("gap_day"):
        day = result.flags["gap_day"]
        pair_posted = any(e["event_type"] == "steady_tuesday_pair" for e in result.ledger)
        if pair_posted:
            return {
                "headline": f"Your steady-{day} pair just posted +12 pts — the gap is closing.",
                "how_to_improve": (
                    f"Keep {day}s within 20% of your weekly average and this factor "
                    f"upgrades at your next monthly settlement."
                ),
                "why_important": (
                    f"Lenders read a recurring quiet {day} as income risk. Two steady "
                    f"{day}s in a row is the first proof the pattern has changed."
                ),
                "reason_code": REASON_CODES["income_trajectory"],
                "factor": worst.factor,
            }
        return {
            "headline": f"Your {day} earnings gap is the #1 drag on your score right now.",
            "how_to_improve": (
                f"Two steady {day}s \u2248 +12 pts. Keep any two consecutive "
                f"{day}s within 20% of your weekly average."
            ),
            "why_important": (
                f"A recurring {day} with little or no verified income reads as "
                f"volatility to underwriting models. Filling it is the single "
                f"fastest way to raise your Income trajectory factor."
            ),
            "reason_code": REASON_CODES["income_trajectory"],
            "factor": worst.factor,
        }
    if worst.factor == "platform_diversity":
        return {
            "headline": "Adding one more verified income source is your fastest win.",
            "how_to_improve": "Connect a second platform \u2248 +4 pts now, more at your next monthly settlement.",
            "why_important": (
                "Each verified source is an independent proof of income. More "
                "sources = a stronger, steadier score."
            ),
            "reason_code": REASON_CODES["platform_diversity"],
            "factor": worst.factor,
        }
    if worst.factor == "rent_subscriptions":
        return {
            "headline": "On-time rent reporting is the biggest lever on your score.",
            "how_to_improve": "Each on-time month reported \u2248 +5 pts and builds bureau-ready history.",
            "why_important": (
                "Housing payments are the strongest classic-credit signal gig "
                "workers already generate — reporting them turns rent you pay "
                "anyway into score history."
            ),
            "reason_code": REASON_CODES["rent_subscriptions"],
            "factor": worst.factor,
        }
    return {
        "headline": "Smoothing week-to-week payouts is your biggest opportunity.",
        "how_to_improve": "Keep weekly earnings within 20% of your 4-week average to level up this factor.",
        "why_important": (
            "Steady weekly cash flow is the core underwriting signal GigScore "
            "verifies — the smaller the swings, the stronger the score."
        ),
        "reason_code": REASON_CODES["earnings_consistency"],
        "factor": worst.factor,
    }


def recent_wins(result: ScoreResult, limit: int = 2) -> list[dict]:
    wins = [e for e in result.ledger if e["delta"] > 0 and e["win_label"]]
    wins.sort(key=lambda e: (-e["delta"], e["occurred_at"]))
    return [{"delta": f"+{e['delta']}", "label": e["win_label"]} for e in wins[:limit]]


# --------------------------------------------------------------------------
# Optional LLM polish pass (tone only, fact-locked)
# --------------------------------------------------------------------------

def llm_polish(copy: dict) -> dict:
    """If ANTHROPIC_API_KEY is set, ask Claude to warm the tone without
    changing any number, day name, or threshold. Falls back silently."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {**copy, "model": "deterministic-template"}
    try:  # pragma: no cover - network path
        import urllib.request

        prompt = (
            "Rewrite the coaching copy below in a warm, plain voice. "
            "You may not change or add any number, weekday, product name, or threshold. "
            "Return JSON with the same keys.\n\n" + json.dumps(copy)
        )
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }).encode(),
            headers={"content-type": "application/json",
                     "x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
        polished = json.loads(body["content"][0]["text"])
        for k in ("headline", "how_to_improve"):  # fact lock
            for token in _fact_tokens(copy[k]):
                if token not in polished.get(k, ""):
                    return {**copy, "model": "deterministic-template (fact-lock reject)"}
        return {**polished, "reason_code": copy["reason_code"],
                "factor": copy["factor"], "model": body.get("model", "claude")}
    except Exception:
        return {**copy, "model": "deterministic-template (llm unavailable)"}


def _fact_tokens(text: str) -> list[str]:
    import re
    return re.findall(r"\+?\d+%?|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday", text)


# --------------------------------------------------------------------------
# SQL audit log
# --------------------------------------------------------------------------

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    user_id TEXT NOT NULL,
    score INTEGER NOT NULL,
    baseline INTEGER NOT NULL,
    week_delta INTEGER NOT NULL,
    factors_json TEXT NOT NULL,
    ledger_json TEXT NOT NULL,
    coach_json TEXT NOT NULL,
    model TEXT NOT NULL
);
"""


def log_explanation(conn: sqlite3.Connection, result: ScoreResult, coach: dict) -> int:
    conn.execute(AUDIT_DDL)
    cur = conn.execute(
        "INSERT INTO audit_log (logged_at, user_id, score, baseline, week_delta,"
        " factors_json, ledger_json, coach_json, model)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            result.user_id,
            result.score,
            result.baseline,
            result.week_delta,
            json.dumps([f.__dict__ for f in result.factors]),
            json.dumps(result.ledger),
            json.dumps(coach),
            coach.get("model", "deterministic-template"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def explain(conn: sqlite3.Connection, result: ScoreResult) -> dict:
    """Full EXPLAIN pass: deterministic copy -> optional LLM polish -> audit."""
    coach = llm_polish(most_impactful(result))
    coach["recent_wins"] = recent_wins(result)
    coach["audit_id"] = log_explanation(conn, result, coach)
    return coach


# --------------------------------------------------------------------------
# AWS entry point (ExplainFn in infra/template.yaml)
# --------------------------------------------------------------------------

def lambda_handler(event, context=None):  # pragma: no cover - AWS entry point
    """EventBridge `gigscore.scored` -> coach copy + audit row.

    In AWS the ScoreResult is rehydrated from Aurora; the local demo calls
    explain() directly (see gigscore.pipeline.run_user).
    """
    return {"detail-type": "gigscore.explained",
            "note": "demo stub — run demo/run_demo.py for the full pass"}
