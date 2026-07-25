"""Generate the deterministic demo dataset.

Writes:
    data/users.json           member profiles + connected-account states
    data/events/stream.jsonl  ingest envelopes (what the webhooks delivered)
    data/events/samples/      one pretty-printed raw payload per source

No randomness — every dollar is scheduled, so the pipeline output is
reproducible and the numbers in the pitch deck fall out exactly:
Maya lands on 642 (Fair), +8 this week, 38 pts to Platinum Secured.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gigscore.ingest.webhook_listener import stamp  # noqa: E402

DATA = REPO_ROOT / "data"
AS_OF = datetime(2026, 7, 20, 14, 0)  # Monday · demo "now"

WD = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
PAYOUT_TIME = {"uber": "11:30", "doordash": "21:45", "lyft": "20:15", "instacart": "19:05"}


def day(year: int, week: int, weekday: int, hhmm: str) -> str:
    d = datetime.fromisocalendar(year, week, weekday + 1)
    return d.strftime(f"%Y-%m-%dT{hhmm}:00Z")


def payout_raw(source: str, user_id: str, amount: float, when: str, n: int) -> dict:
    amount = round(amount, 2)
    if source == "uber":
        return {"user_id": user_id, "net_fare_total": amount, "deposit_time": when,
                "trip_count": n, "_demo_time": when}
    if source == "doordash":
        return {"user_id": user_id, "_demo_time": when,
                "dasher_payout": {"amount_cents": int(round(amount * 100)),
                                  "paid_at": when, "delivery_count": n}}
    if source == "lyft":
        return {"user_id": user_id, "_demo_time": when,
                "earnings": {"total": amount, "settled_at": when, "ride_count": n}}
    if source == "instacart":
        return {"user_id": user_id, "batch_earnings_usd": amount, "paid_at": when,
                "batch_count": n, "_demo_time": when}
    raise ValueError(source)


def plaid_raw(user_id: str, amount: float, date: str, merchant: str,
              category: str, on_time: bool = True) -> dict:
    return {"user_id": user_id, "amount": -abs(round(amount, 2)), "date": date,
            "merchant_name": merchant, "on_time": on_time,
            "personal_finance_category": {"primary": category}, "_demo_time": date}


def weekly_payouts(user_id: str, template: dict, weeks: list[int], mults: list[float],
                   year: int = 2026) -> list[dict]:
    """template: {'Mon': {'uber': 92, 'doordash': 71}, ...} · one envelope per deposit."""
    out = []
    for wk, mult in zip(weeks, mults):
        for dname, per_source in template.items():
            for source, base in per_source.items():
                when = day(year, wk, WD[dname], PAYOUT_TIME[source])
                out.append(stamp(payout_raw(source, user_id, base * mult, when,
                                            max(1, int(base // 18))), source))
    return out


def monthly_plaid(user_id: str, months: list[str], dom: int, amount: float,
                  merchant: str, category: str, missed: set[str] = frozenset()) -> list[dict]:
    out = []
    for ym in months:
        y, m = map(int, ym.split("-"))
        date = f"{y:04d}-{m:02d}-{dom:02d}T09:00:00Z"
        out.append(stamp(plaid_raw(user_id, amount, date, merchant, category,
                                   on_time=ym not in missed), "plaid"))
    return out


def months_back(last: str, n: int) -> list[str]:
    y, m = map(int, last.split("-"))
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def build() -> tuple[list[dict], list[dict]]:
    env: list[dict] = []

    # ---------------- Maya Reyes · the deck persona -----------------------
    maya = "usr_maya"
    maya_template = {
        "Mon": {"uber": 92, "doordash": 71},
        "Tue": {"uber": 15},                       # <- the Tuesday gap
        "Wed": {"uber": 88, "doordash": 69},
        "Thu": {"uber": 90, "doordash": 74},
        "Fri": {"uber": 95, "doordash": 88},
        "Sat": {"doordash": 96},
        "Sun": {"doordash": 58},
    }
    env += weekly_payouts(maya, maya_template, weeks=list(range(22, 30)),
                          mults=[1.00, 0.82, 1.15, 0.90, 1.12, 0.85, 1.08, 1.00])
    # Rent: $1,240 on the 15th, 12 straight on-time months (Aug '25 – Jul '26)
    env += monthly_plaid(maya, months_back("2026-07", 12), 15, 1240,
                         "Lakeview Property Mgmt", "RENT_AND_UTILITIES")
    # Subscriptions on the 8th (outside the last-7-day window on purpose)
    env += monthly_plaid(maya, months_back("2026-07", 3), 8, 15.49, "Netflix", "ENTERTAINMENT")
    env += monthly_plaid(maya, months_back("2026-07", 3), 8, 11.99, "Spotify", "ENTERTAINMENT")
    # This morning's deposit — the "Updated 2 min ago · DoorDash payout received"
    env.append(stamp(payout_raw("doordash", maya, 68.40,
                                "2026-07-20T13:58:00Z", 4), "doordash"))

    # ---------------- Priya Shah · fixes her Tuesday gap, crosses 680 -----
    priya = "usr_priya"
    priya_template = {
        "Mon": {"uber": 118, "lyft": 60},
        "Wed": {"doordash": 95, "instacart": 88},
        "Thu": {"uber": 110, "lyft": 70},
        "Fri": {"doordash": 125, "instacart": 92},
        "Sat": {"uber": 160, "lyft": 95},
        "Sun": {"doordash": 98, "instacart": 69},
    }
    env += weekly_payouts(priya, priya_template, weeks=list(range(20, 30)),
                          mults=[1.00, 0.85, 1.12, 0.92, 1.10, 0.88, 1.06, 0.95, 1.05, 1.07])
    # The fix: two consecutive steady Tuesdays (weeks 28 & 29)
    env.append(stamp(payout_raw("uber", priya, 165.00, day(2026, 28, WD["Tue"], "11:30"), 9), "uber"))
    env.append(stamp(payout_raw("uber", priya, 172.00, day(2026, 29, WD["Tue"], "11:30"), 9), "uber"))
    env += monthly_plaid(priya, months_back("2026-07", 12), 3, 1580,
                         "Wicker Park Lofts", "RENT_AND_UTILITIES")

    # ---------------- Devon King · misses July rent -----------------------
    devon = "usr_devon"
    devon_template = {
        "Thu": {"uber": 105},
        "Fri": {"uber": 190},
        "Sat": {"uber": 240},
        "Sun": {"uber": 150},
    }
    env += weekly_payouts(devon, devon_template, weeks=list(range(22, 30)),
                          mults=[1.30, 0.60, 1.45, 0.75, 1.35, 0.65, 1.00, 0.90])
    env += monthly_plaid(devon, months_back("2026-07", 7), 14, 1120,
                         "Southport Realty", "RENT_AND_UTILITIES",
                         missed={"2026-07"})  # July 14 reported late -> -15

    # ---------------- Andre Okafor · connects a new source ----------------
    andre = "usr_andre"
    andre_template = {
        "Mon": {"doordash": 96},
        "Wed": {"doordash": 104},
        "Fri": {"doordash": 132},
        "Sat": {"doordash": 148},
    }
    env += weekly_payouts(andre, andre_template, weeks=list(range(22, 30)),
                          mults=[1.00, 0.82, 1.18, 0.90, 1.10, 0.85, 1.15, 1.00])
    env += monthly_plaid(andre, months_back("2026-07", 8), 3, 990,
                         "Bronzeville Flats", "RENT_AND_UTILITIES")
    env.append(stamp({"user_id": andre, "event": "account_connected",
                      "connected_at": "2026-07-16T10:12:00Z",
                      "_demo_time": "2026-07-16T10:12:00Z"}, "instacart"))

    env.sort(key=lambda e: e["raw"].get("deposit_time")
             or e["raw"].get("dasher_payout", {}).get("paid_at")
             or e["raw"].get("earnings", {}).get("settled_at")
             or e["raw"].get("paid_at") or e["raw"].get("date")
             or e["raw"].get("connected_at"))

    users = [
        {
            "user_id": maya, "name": "Maya Reyes", "age": 27, "city": "Chicago",
            "blurb": "Rideshare + delivery + weekend tutoring",
            "accounts": [
                {"key": "uber", "name": "Uber", "sub": "Rideshare · since 2022", "connected": True},
                {"key": "doordash", "name": "DoorDash", "sub": "Delivery · since 2023", "connected": True},
                {"key": "lyft", "name": "Lyft", "sub": "Rideshare", "connected": False},
                {"key": "instacart", "name": "Instacart", "sub": "Delivery", "connected": False},
                {"key": "chase", "name": "Chase ····4417", "sub": "Bank & rent — via Plaid", "connected": True},
            ],
        },
        {
            "user_id": priya, "name": "Priya Shah", "age": 31, "city": "Chicago",
            "blurb": "Four platforms, seven days a week",
            "accounts": [
                {"key": "uber", "name": "Uber", "sub": "Rideshare · since 2021", "connected": True},
                {"key": "doordash", "name": "DoorDash", "sub": "Delivery · since 2022", "connected": True},
                {"key": "lyft", "name": "Lyft", "sub": "Rideshare · since 2023", "connected": True},
                {"key": "instacart", "name": "Instacart", "sub": "Delivery · since 2024", "connected": True},
                {"key": "chase", "name": "Chase ····9052", "sub": "Bank & rent — via Plaid", "connected": True},
            ],
        },
        {
            "user_id": devon, "name": "Devon King", "age": 24, "city": "Chicago",
            "blurb": "Weekend rideshare, rebuilding after a rough month",
            "accounts": [
                {"key": "uber", "name": "Uber", "sub": "Rideshare · since 2024", "connected": True},
                {"key": "doordash", "name": "DoorDash", "sub": "Delivery", "connected": False},
                {"key": "lyft", "name": "Lyft", "sub": "Rideshare", "connected": False},
                {"key": "instacart", "name": "Instacart", "sub": "Delivery", "connected": False},
                {"key": "chase", "name": "Chase ····2210", "sub": "Bank & rent — via Plaid", "connected": True},
            ],
        },
        {
            "user_id": andre, "name": "Andre Okafor", "age": 35, "city": "Chicago",
            "blurb": "Evening delivery, just added a second platform",
            "accounts": [
                {"key": "uber", "name": "Uber", "sub": "Rideshare", "connected": False},
                {"key": "doordash", "name": "DoorDash", "sub": "Delivery · since 2020", "connected": True},
                {"key": "lyft", "name": "Lyft", "sub": "Rideshare", "connected": False},
                {"key": "instacart", "name": "Instacart", "sub": "Delivery · connected Jul 16", "connected": True},
                {"key": "chase", "name": "Chase ····7731", "sub": "Bank & rent — via Plaid", "connected": True},
            ],
        },
    ]
    return users, env


def main():
    users, env = build()
    DATA.mkdir(exist_ok=True)
    (DATA / "users.json").write_text(json.dumps(users, indent=2) + "\n")
    stream = DATA / "events" / "stream.jsonl"
    stream.parent.mkdir(parents=True, exist_ok=True)
    with stream.open("w") as fh:
        for e in env:
            fh.write(json.dumps(e) + "\n")

    samples = DATA / "events" / "samples"
    samples.mkdir(exist_ok=True)
    seen = set()
    for e in env:
        if e["source"] not in seen:
            seen.add(e["source"])
            (samples / f"{e['source']}_payload.json").write_text(json.dumps(e, indent=2) + "\n")

    print(f"wrote {len(env)} ingest envelopes for {len(users)} members -> {stream}")


if __name__ == "__main__":
    main()
