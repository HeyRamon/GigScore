"""NORMALIZE · Python transforms data, AWS Lambda organizes.

Every platform speaks a different dialect. This phase turns raw ingest
envelopes into one canonical record shape so the rules engine never has
to know what a "dasher_payout" is.

Canonical record:
    {user_id, kind, source, amount, occurred_at, meta}
kinds: payout | rent_payment | subscription_payment | account_connected
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


# --- per-source adapters ----------------------------------------------------

def _uber(raw: dict) -> dict:
    return {
        "kind": "payout",
        "amount": round(raw["net_fare_total"], 2),
        "occurred_at": raw["deposit_time"],
        "meta": {"trips": raw.get("trip_count")},
    }


def _doordash(raw: dict) -> dict:
    return {
        "kind": "payout",
        "amount": round(raw["dasher_payout"]["amount_cents"] / 100, 2),
        "occurred_at": raw["dasher_payout"]["paid_at"],
        "meta": {"deliveries": raw["dasher_payout"].get("delivery_count")},
    }


def _lyft(raw: dict) -> dict:
    return {
        "kind": "payout",
        "amount": round(raw["earnings"]["total"], 2),
        "occurred_at": raw["earnings"]["settled_at"],
        "meta": {"rides": raw["earnings"].get("ride_count")},
    }


def _instacart(raw: dict) -> dict:
    return {
        "kind": "payout",
        "amount": round(raw["batch_earnings_usd"], 2),
        "occurred_at": raw["paid_at"],
        "meta": {"batches": raw.get("batch_count")},
    }


def _plaid(raw: dict) -> dict:
    """Plaid transaction webhooks carry rent + recurring subscriptions."""
    category = raw.get("personal_finance_category", {}).get("primary", "")
    kind = "rent_payment" if category == "RENT_AND_UTILITIES" else "subscription_payment"
    return {
        "kind": kind,
        "amount": round(abs(raw["amount"]), 2),
        "occurred_at": raw["date"],
        "meta": {"merchant": raw.get("merchant_name"), "on_time": raw.get("on_time", True)},
    }


ADAPTERS = {
    "uber": _uber,
    "doordash": _doordash,
    "lyft": _lyft,
    "instacart": _instacart,
    "plaid": _plaid,
}


def transform(envelope: dict) -> dict:
    """Ingest envelope -> canonical record."""
    source = envelope["source"]
    raw = envelope["raw"]
    if raw.get("event") == "account_connected":
        record = {"kind": "account_connected", "amount": 0.0,
                  "occurred_at": raw["connected_at"], "meta": {}}
    else:
        record = ADAPTERS[source](raw)
    record.update({
        "user_id": raw["user_id"],
        "source": source,
        "ingest_id": envelope["ingest_id"],
    })
    return record


def lambda_handler(event, context=None):  # pragma: no cover - AWS entry point
    """EventBridge rule target. Writes canonical rows to the ledger table."""
    envelope = event["detail"] if "detail" in event else event
    record = transform(envelope)
    # Production: INSERT INTO canonical_ledger ... (Aurora). Demo returns it.
    return record


def normalize_stream(stream_path: Path) -> list[dict]:
    """Batch helper for the local demo: whole stream -> canonical ledger."""
    records = []
    with stream_path.open() as fh:
        for line in fh:
            if line.strip():
                records.append(transform(json.loads(line)))
    records.sort(key=lambda r: r["occurred_at"])
    return records
