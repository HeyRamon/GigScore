# Architecture

Event-driven serverless on AWS — the pitch's four phases, one module each.

```
              INGEST                NORMALIZE               SCORE                    EXPLAIN
platform ──▶ API Gateway ──▶ EventBridge "gigscore" bus ─────────────────────────────────────▶
webhooks      IngestFn        │                                                    CreditWise
              (HMAC verify,   ├──▶ NormalizeFn ──▶ Aurora canonical_ledger          surface
               stamp, emit)   ├──▶ ScoreFn  ◀──── SQL-stored weights (weights.sql)
                              └──▶ ExplainFn ──▶ Aurora audit_log
```

## Phase by phase

**INGEST — Python webhook listeners, AWS Lambda triggers.**
`src/gigscore/ingest/webhook_listener.py`. One route per platform
(`/webhooks/uber`, `/doordash`, `/lyft`, `/instacart`, `/plaid`), HMAC
signature verification per source secret, then `stamp()` wraps the raw
payload into an envelope `{ingest_id, ingested_at, source, raw}` — raw is
never mutated, so any downstream decision can be replayed from the
envelope. Locally the same handler runs as a tiny HTTP listener on :8080;
in AWS it is `IngestFn` publishing `gigscore.raw` to the bus.

**NORMALIZE — Python transforms data, AWS Lambda organizes.**
`src/gigscore/normalize/transforms.py`. One adapter per source maps
whatever the platform calls money and time (`net_fare_total` /
`dasher_payout.amount_cents` / `earnings.total` / `batch_earnings_usd` /
Plaid `amount`) into one canonical row:

```
{user_id, kind, source, amount, occurred_at, meta}
kind ∈ payout | rent_payment | subscription_payment | account_connected
```

Plaid transactions with `personal_finance_category.primary ==
RENT_AND_UTILITIES` become `rent_payment`; other recurring merchants
become `subscription_payment`. Canonical rows land in
`canonical_ledger` (Aurora in prod, in-memory list in the demo) and are
re-emitted as `gigscore.canonical`.

**SCORE — Python rules engine, SQL-stored weights.**
`src/gigscore/score/rules_engine.py` + `data/seed/weights.sql`. The
engine derives behavioral metrics from complete ISO weeks only (the
in-progress week never counts), assigns a level per factor, and sums:

```
score = 300 + Σ factor points + Σ event ledger, clamped 300–850
```

Every number is a SQL row — `factor_levels`, `event_rules`,
`score_bands`, `milestones`, `behavior_thresholds` — so risk can retune
weights with an UPDATE, not a deploy, and every historical score can be
recomputed against the weights that were live at the time. Micro-events
(`pipeline.detect_ledger_events`) move the score between monthly
settlements: that is why the header can honestly say "Updated 2 min ago
· DoorDash payout received" and the Coach tab can show "+5 Rent reported
on time".

Gap detection: for members working a broad weekday pattern (4+ of
Mon–Fri most weeks), any weekday averaging under 20% of their average
active day — counting absent days as $0 — is a gap ("Tuesday gap
detected"). Filling it two consecutive weeks fires the +12
`steady_tuesday_pair` event; the factor level itself upgrades at the
next monthly settlement.

**EXPLAIN — Python orchestrates LLM, SQL audit log.**
`src/gigscore/explain/orchestrator.py`. Deterministic templates own the
facts and the FCRA reason code (GS-11…GS-14). If `ANTHROPIC_API_KEY` is
set, Claude (Bedrock in prod) may rewrite tone only — the output is
diffed against fact tokens (numbers, weekdays) and rejected on any
mismatch. Every explanation writes one `audit_log` row: inputs, factor
levels, ledger, final copy, model id.

## Local demo = production, minus AWS

`demo/run_demo.py` runs the same four handlers in-process over
`data/events/stream.jsonl` with SQLite standing in for Aurora.
`infra/template.yaml` is the SAM sketch of the deployed topology.
`app/index.html` renders the exported state; serving `app/` over HTTP
makes it re-fetch `state.json` on load, so pipeline changes show up on
the phone with one `--export`.
