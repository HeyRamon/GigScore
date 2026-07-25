# Scoring

`score = 300 + Σ factor points (max 550) + Σ event ledger, clamped 300–850`

Factor levels re-settle monthly from the canonical ledger; ledger events
move the score in real time between settlements. Every value below is a
row in `data/seed/weights.sql` — the engine never hard-codes a weight.

## Factor points (`factor_levels` + `diversity_weights`)

| Factor | EXCELLENT | GOOD | FAIR | NEEDS WORK |
|---|---:|---:|---:|---:|
| Rent & subscriptions | 140 | 105 | 70 | 30 |
| Earnings consistency | 130 | 90 | 60 | 25 |
| Income trajectory | 190 | 140 | 95 | 50 |
| Platform diversity | 18 × verified sources, cap 5 → max 90 | | | |

Max factor total 550 → range 300–850.

## Level rules (`behavior_thresholds`)

- **Rent & subscriptions** — any missed payment → NEEDS WORK; ≥12
  on-time months → EXCELLENT; ≥6 → GOOD; else FAIR.
- **Earnings consistency** — coefficient of variation of complete-week
  totals: ≤0.08 EXCELLENT · ≤0.22 GOOD · ≤0.40 FAIR · else NEEDS WORK.
- **Platform diversity** — verified sources (gig platforms with payouts,
  plus the linked bank once rent/subscriptions report): 5 EXCELLENT ·
  3–4 GOOD · 2 FAIR · 1 NEEDS WORK.
- **Income trajectory** — a weekday gap (see below) → NEEDS WORK with
  "<Day> gap detected"; otherwise GOOD if the last two weeks out-earn
  the first two, else FAIR.

**Gap detection** — runs only for broad weekday patterns (4+ of Mon–Fri
worked most weeks, so weekend-only drivers are never flagged for days
they don't work). Per-weekday average is taken over *all* complete
weeks, counting an absent day as $0. Any weekday under 20% of the
member's average active day (`day_gap_ratio = 0.80`) is a gap; the worst
one is surfaced.

## Ledger events (`event_rules`)

| Event | Δ | Coach "Recent win" label |
|---|---:|---|
| `rent_reported_on_time` | +5 | Rent reported on time |
| `subscription_reported_on_time` | +2 | Subscription reported on time |
| `consistency_streak_4wk` | +3 | 4-week consistency streak |
| `steady_tuesday_pair` | +12 | Two steady Tuesdays |
| `source_connected` | +4 | New income source connected |
| `rent_payment_missed` | −15 | — |
| `payout_received` | 0 | — (refreshes "Updated … ago") |

The steady pair pays when the member's gap day lands within 20% of their
average active day two weeks running — the exact promise Coach makes:
"Two steady Tuesdays ≈ +12 pts."

## Bands (`score_bands`) and milestones (`milestones`)

300–579 Needs work · 580–669 Fair · 670–739 Good · 740–799 Very good ·
800–850 Excellent.

**680 — Platinum Secured auto-review** (Refundable deposit from $49 ·
reports to all 3 bureaus) · **720 — Quicksilver unsecured pre-approval**
(No deposit · 1.5% cash back on every purchase).

## Worked examples (the demo cohort)

**Maya Reyes — 642 · Fair · ▲ +8.** 12 on-time rent months (140) +
CV≈0.117 GOOD (90) + 3 sources (54) + Tuesday gap NEEDS WORK (50) →
baseline 634. This week: rent on time +5, 4-week streak +3 → **642**,
38 pts to Platinum Secured. Coach: "Your Tuesday earnings gap is the #1
drag on your score right now."

**Priya Shah — 685 · Good · ▲ +15.** Baseline 670 (140 + 90 + 90 + 50 —
the Tuesday gap still holds her trajectory at NEEDS WORK until
settlement). This week her second steady Tuesday posts: +12 pair +3
streak → **685**, crossing **680 → Platinum Secured auto-review
unlocked**. The +12 the deck promises Maya is the +12 Priya just
collected.

**Devon King — 506 · Needs work · ▼ −15.** Weekend-only Uber (no gap
flag by design), volatile weeks (FAIR 60), 2 sources (36), steady
trajectory (95), but July rent reported late: rent factor NEEDS WORK
(30) and a −15 ledger hit → 521 − 15 = **506**.

**Andre Okafor — 678 · Good · ▲ +7.** 8 on-time rent months (105),
CV≈0.127 GOOD (90), trending up (140), 2 sources (36) → 671. Connected
Instacart on Jul 16 (+4) + streak (+3) → **678** — 2 pts from the 680
unlock, and his diversity points rise at the next monthly settlement
when Instacart payouts land.
