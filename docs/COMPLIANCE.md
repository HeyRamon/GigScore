# FCRA-native by design

GigScore treats explainability as an input, not a report written after
the fact. Three properties make the pipeline adverse-action-ready:

## 1 · Deterministic facts, reason-coded

Every coach message and every score change carries a machine-stable
reason code produced by the rules engine itself
(`src/gigscore/explain/orchestrator.py`):

| Code | Meaning |
|---|---|
| GS-11 | Irregular earnings pattern on one or more weekdays |
| GS-12 | Week-to-week payout variance above target |
| GS-13 | Limited number of verified income sources |
| GS-14 | Insufficient on-time housing payment history |

The copy a member sees ("Your Tuesday earnings gap is the #1 drag on
your score right now") and the adverse-action reason a lender files are
generated from the same factor result — they cannot drift apart.

## 2 · The LLM can polish, never decide

The optional Claude pass (Bedrock in production) rewrites tone only.
Its output is diffed against the deterministic fact tokens — every
number, weekday name, and product name must survive verbatim
(`_fact_tokens`) — or the polished copy is rejected and the template
ships. Offline, the templates run as-is, which is also why the demo
copy matches the pitch deck word for word. Model id (or
`deterministic-template`) is recorded per explanation.

## 3 · Everything lands in the SQL audit log

One `audit_log` row per score change: timestamp, member, score,
baseline, week delta, full factor levels, the event ledger, the final
coach copy, and the model that produced it. Any score a member ever saw
can be reconstructed line by line — the FCRA §609/§615 file is a
`SELECT`, not an investigation. Because weights live in SQL
(`data/seed/weights.sql`) with the same discipline, the weights that
were live at scoring time are themselves auditable.

## Data handling posture

- **Read-only, consented connections** — payroll-source webhooks and
  Plaid; "Verified and read-only — straight from the payroll source."
  We never see member passwords.
- **Raw payloads are immutable** — INGEST stamps envelopes and never
  mutates `raw`, so every canonical row is traceable to its source
  payload (`ingest_id`).
- **Furnishing path** — milestones graduate members into products that
  report to all 3 bureaus, aligned with CFPB Circular 2023-03 on
  adverse-action specificity and FinRegLab's cash-flow underwriting
  findings (July 2025).

*Hackathon prototype: simulated members and payloads only.*
