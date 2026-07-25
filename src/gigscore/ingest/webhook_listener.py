"""INGEST · Python webhook listeners, AWS Lambda triggers.

Gig platforms (Uber, DoorDash, Lyft, Instacart) and Plaid push signed
webhooks the moment a payout lands or a rent transaction posts. Each
raw payload is verified, stamped, and dropped onto the event bus
untouched — normalization happens downstream.

Local demo:  `python -m gigscore.ingest.webhook_listener` starts a
             stdlib HTTP listener on :8080 that appends verified
             payloads to data/events/stream.jsonl.
Production:  API Gateway -> `lambda_handler` -> EventBridge bus
             (see infra/template.yaml).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STREAM = REPO_ROOT / "data" / "events" / "stream.jsonl"
SIGNING_SECRET = os.environ.get("GIGSCORE_WEBHOOK_SECRET", "demo-secret")

SUPPORTED_SOURCES = {"uber", "doordash", "lyft", "instacart", "plaid"}


def verify_signature(raw_body: bytes, signature: str) -> bool:
    expected = hmac.new(SIGNING_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def stamp(payload: dict, source: str) -> dict:
    """Wrap a raw platform payload in the GigScore ingest envelope."""
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    return {
        "ingest_id": str(uuid.uuid4()),
        "ingested_at": payload.get("_demo_time") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "raw": {k: v for k, v in payload.items() if not k.startswith("_")},
    }


def lambda_handler(event, context=None):  # pragma: no cover - AWS entry point
    """API Gateway proxy -> EventBridge. One payload in, one envelope out."""
    import boto3  # available in the Lambda runtime

    body = event.get("body", "").encode()
    source = (event.get("pathParameters") or {}).get("source", "")
    sig = (event.get("headers") or {}).get("x-gigscore-signature", "")
    if not verify_signature(body, sig):
        return {"statusCode": 401, "body": "bad signature"}

    envelope = stamp(json.loads(body), source)
    boto3.client("events").put_events(
        Entries=[{
            "Source": f"gigscore.ingest.{source}",
            "DetailType": "raw_payload",
            "Detail": json.dumps(envelope),
            "EventBusName": os.environ.get("GIGSCORE_BUS", "gigscore"),
        }]
    )
    return {"statusCode": 202, "body": envelope["ingest_id"]}


class _Listener(BaseHTTPRequestHandler):
    """Local stand-in for API Gateway. POST /webhooks/<source>."""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        source = self.path.rstrip("/").split("/")[-1]
        sig = self.headers.get("x-gigscore-signature", "")
        if not verify_signature(raw, sig):
            self.send_response(401); self.end_headers(); return
        envelope = stamp(json.loads(raw), source)
        STREAM.parent.mkdir(parents=True, exist_ok=True)
        with STREAM.open("a") as fh:
            fh.write(json.dumps(envelope) + "\n")
        self.send_response(202)
        self.end_headers()
        self.wfile.write(envelope["ingest_id"].encode())

    def log_message(self, *args):  # keep demo output clean
        pass


def main():  # pragma: no cover
    print("GigScore ingest listener on http://127.0.0.1:8080/webhooks/<source>")
    HTTPServer(("127.0.0.1", 8080), _Listener).serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
