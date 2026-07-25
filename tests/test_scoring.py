"""Deck-fidelity tests — every number the pitch shows must fall out of the
pipeline, not be hard-coded. Run:  python -m unittest discover tests -v
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gigscore.pipeline import run_user, load_stream          # noqa: E402
from gigscore.score import db                                 # noqa: E402

AS_OF = datetime(2026, 7, 20, 14, 0)


def _run_all():
    users = json.loads((REPO_ROOT / "data" / "users.json").read_text())
    envelopes = load_stream(REPO_ROOT / "data" / "events" / "stream.jsonl")
    conn = db.connect(":memory:")
    out = {}
    for user in users:
        result, coach = run_user(conn, user, envelopes, AS_OF)
        out[user["user_id"]] = (user, result, coach)
    return out


RUNS = _run_all()


class TestMayaMatchesTheDeck(unittest.TestCase):
    """Slide 1/4/6/7 — the hero phone."""

    def setUp(self):
        self.user, self.result, self.coach = RUNS["usr_maya"]

    def test_score_band_and_week_delta(self):
        self.assertEqual(self.result.score, 642)
        self.assertEqual(self.result.band, "Fair")
        self.assertEqual(self.result.week_delta, 8)          # ▲ +8 this week
        self.assertEqual(self.result.baseline, 634)

    def test_updated_line_is_a_fresh_doordash_payout(self):
        self.assertEqual(self.result.last_event["source"], "doordash")
        dt = datetime.fromisoformat(
            self.result.last_event["occurred_at"].replace("Z", ""))
        self.assertEqual((AS_OF - dt).total_seconds() // 60, 2)  # 2 min ago

    def test_whats_driving_it_rows(self):
        got = {f.label: (f.level, f.driver) for f in self.result.factors}
        self.assertEqual(got["Rent & subscriptions"],
                         ("EXCELLENT", "reported on time, 12 months"))
        self.assertEqual(got["Earnings consistency"],
                         ("GOOD", "steady weekly payouts"))
        self.assertEqual(got["Platform diversity"],
                         ("GOOD", "3 income sources connected"))
        self.assertEqual(got["Income trajectory"],
                         ("NEEDS_WORK", "Tuesday gap detected"))

    def test_next_unlock_is_38_pts_to_platinum_secured(self):
        self.assertEqual(self.result.gap_to_next, 38)
        self.assertEqual(self.result.next_milestone["threshold"], 680)
        self.assertEqual(self.result.next_milestone["product"],
                         "Platinum Secured auto-review")
        self.assertEqual(self.result.next_milestone["detail"],
                         "Refundable deposit from $49 · reports to all 3 bureaus")

    def test_coach_copy_verbatim(self):
        self.assertEqual(
            self.coach["headline"],
            "Your Tuesday earnings gap is the #1 drag on your score right now.")
        self.assertEqual(
            self.coach["how_to_improve"],
            "Two steady Tuesdays \u2248 +12 pts. Keep any two consecutive "
            "Tuesdays within 20% of your weekly average.")

    def test_recent_wins_order_and_labels(self):
        self.assertEqual(self.coach["recent_wins"],
                         [{"delta": "+5", "label": "Rent reported on time"},
                          {"delta": "+3", "label": "4-week consistency streak"}])

    def test_connect_tab_matches_mock(self):
        acct = {a["name"]: (a["sub"], a["connected"]) for a in self.user["accounts"]}
        self.assertEqual(acct["Uber"], ("Rideshare · since 2022", True))
        self.assertEqual(acct["DoorDash"], ("Delivery · since 2023", True))
        self.assertEqual(acct["Lyft"], ("Rideshare", False))
        self.assertEqual(acct["Instacart"], ("Delivery", False))
        self.assertEqual(acct["Chase ····4417"], ("Bank & rent — via Plaid", True))
        self.assertEqual(sum(a["connected"] for a in self.user["accounts"]), 3)  # 3 of 5


class TestCohortEventsMoveScores(unittest.TestCase):
    """Small test dataset: each member's score moves from a specific event."""

    def test_priya_steady_tuesday_pair_crosses_680(self):
        _, result, coach = RUNS["usr_priya"]
        self.assertEqual(result.baseline, 670)
        deltas = {e["event_type"]: e["delta"] for e in result.ledger}
        self.assertEqual(deltas["steady_tuesday_pair"], 12)   # the fix pays +12
        self.assertEqual(deltas["consistency_streak_4wk"], 3)
        self.assertEqual(result.score, 685)
        self.assertEqual(result.band, "Good")
        self.assertEqual([u["threshold"] for u in result.unlocked], [680])
        self.assertIn("steady-Tuesday pair just posted +12", coach["headline"])

    def test_devon_missed_rent_costs_15(self):
        _, result, coach = RUNS["usr_devon"]
        deltas = {e["event_type"]: e["delta"] for e in result.ledger}
        self.assertEqual(deltas["rent_payment_missed"], -15)
        self.assertEqual(result.score, result.baseline - 15)
        self.assertEqual(result.score, 506)
        self.assertEqual(result.band, "Needs work")
        self.assertEqual(coach["reason_code"].split(" ")[0], "GS-14")

    def test_andre_new_source_pays_4_and_sits_2_from_unlock(self):
        _, result, _ = RUNS["usr_andre"]
        deltas = {e["event_type"]: e["delta"] for e in result.ledger}
        self.assertEqual(deltas["source_connected"], 4)
        self.assertEqual(result.score, 678)
        self.assertEqual(result.gap_to_next, 2)               # cliffhanger

    def test_scores_are_deterministic(self):
        again = _run_all()
        for uid, (_, result, _) in RUNS.items():
            self.assertEqual(again[uid][1].score, result.score)
            self.assertEqual(again[uid][1].week_delta, result.week_delta)


class TestSqlStoredWeights(unittest.TestCase):
    """SCORE phase: weights live in SQL, never in Python."""

    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_score_range_is_300_to_850(self):
        total_max = (db.factor_points(self.conn, "rent_subscriptions", "EXCELLENT")
                     + db.factor_points(self.conn, "earnings_consistency", "EXCELLENT")
                     + db.diversity_points(self.conn, 5)
                     + db.factor_points(self.conn, "income_trajectory", "EXCELLENT"))
        self.assertEqual(300 + total_max, 850)

    def test_event_rules_match_the_deck(self):
        self.assertEqual(db.event_delta(self.conn, "rent_reported_on_time"),
                         (5, "Rent reported on time"))
        self.assertEqual(db.event_delta(self.conn, "consistency_streak_4wk"),
                         (3, "4-week consistency streak"))
        self.assertEqual(db.event_delta(self.conn, "steady_tuesday_pair")[0], 12)
        self.assertEqual(db.event_delta(self.conn, "source_connected")[0], 4)
        self.assertEqual(db.event_delta(self.conn, "rent_payment_missed")[0], -15)

    def test_bands(self):
        self.assertEqual(db.band_for(self.conn, 642), "Fair")
        self.assertEqual(db.band_for(self.conn, 685), "Good")
        self.assertEqual(db.band_for(self.conn, 506), "Needs work")


if __name__ == "__main__":
    unittest.main(verbosity=2)
