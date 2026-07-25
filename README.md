# GigScore

**A scoring tool that tries to turn gig earnings into something lenders can use.**

Capital One Launchpad · July 2026  
By Bryan Tillman Jr., Radia Soumah, Sophia Bolkovatz, Diego Flores, Ramon Vazquez & Feyza Gurler — Team 4 the Win

---

## The actual problem

Maya is 27 years old in Chicago. She works Uber in the mornings ($1,650/month), DoorDash evenings ($1,400/month), tutoring on weekends (~$750/month). Totals around $3,800 a month across three platforms. She applied for a $12,000 used-car loan and got rejected. The denial letter said "Unable to verify income."

She's not the only one this happens to. The stats are real:
- Gig workers' income swings month-to-month more than salaried workers. That makes lenders nervous.
- A meaningful chunk of gig workers are people of color, and they already face higher barriers to credit.
- Roughly 32M adults in the US don't fit traditional credit models because their income doesn't show up on W-2s or tax returns.

The problem isn't that Maya doesn't make enough money. It's that there's no clean way to *prove* it to a lending algorithm built for steady paychecks.

## What we're trying to do

**1. Tap verified sources** — Instead of asking Maya for bank statements or tax returns, we pull data directly from the platforms she uses: Uber, DoorDash, Lyft, her bank (via Plaid). Read-only, straight from the source.

**2. Live updates, not monthly snapshots** — The score updates when payouts hit, not on a billing cycle. Maya sees "Updated 2 min ago · DoorDash payout received." She understands what's moving the needle because we show her the actual events driving the score.

**3. Tell her what to do** — Every score comes with the single thing that would help most ("You need one more consistent Tuesday to hit +12"). If she hits milestones (680 score → eligible for Platinum Secured card), we tell her that too. The goal is graduation into actual Capital One products.

## How it works (in theory)

The pipeline has four steps:

| Phase | What it does | Constraints |
|---|---|---|
| **INGEST** | Listen for webhooks from Uber, DoorDash, Lyft, Instacart, etc | Requires platform agreements. We have test data; production is TBD |
| **NORMALIZE** | Convert each platform's event format into one standard row | One adapter per source. Lyft's schema isn't the same as Uber's. Plaid sometimes sends duplicates |
| **SCORE** | Apply rules to the ledger (rent on time = +5, streak = +3, etc.) with weights in SQL | Rules are deterministic but weights are guesses based on limited data |
| **EXPLAIN** | Generate human-readable reasons for score changes | We template most of it; Claude can polish if needed |

Each phase is a separate service. When one finishes, it publishes an event that triggers the next phase. So the flow right now is as follows: a webhook arrives → INGEST reads it → publishes "done" → NORMALIZE picks up the result → publishes "done" → SCORE runs → publishes "done" → EXPLAIN runs. All the data gets saved as it moves through the pipeline.

## The test cohort (numbers we asserted, not validated at scale)

We built four fake members with deterministic event streams. Their scores move from specific things:

| Member | Starting | This week | Final | Notes |
|---|---|---|---|---|
| **Maya Reyes** | 634 | rent on time +5, 4 Tuesdays in a row +3 | 642 | Fictional. Stays in "Fair" band |
| **Priya Shah** | 670 | two good Tuesdays +12, streak +3 | 685 | Crosses 680 threshold. Gets Platinum auto-review notice |
| **Devon King** | 521 | rent late −15 | 506 | Dropped. Coaching shifts to "get rent reported" |
| **Andre Okafor** | 671 | new income source +4, streak +3 | 678 | Close to 680. Two points away |

Every score in that table is asserted in our test file. We haven't validated any of this against real gig workers—that requires actual partnership agreements and data access we don't have yet.

## Scoring

`score = 300 + factor points + ledger events, clamped 300–850`

The factors we're using:

| Factor | Points if strong | If weak |
|---|---|---|
| Rent & subscriptions on-time history | 140 | 30 |
| Earnings consistency (variance month-to-month) | 130 | 25 |
| Income trajectory (trending up vs. flat/down) | 190 | 50 |
| # of verified income sources (max 5) | 18 per source, capped at 90 | 0 |

Events (real-time ledger):
- Rent paid on time: +5
- Subscription paid on time: +2
- 4 consistent weeks: +3
- Two steady week-days in a row (addressed a gap pattern): +12
- New income source verified: +4
- Rent missed: −15

Score bands:
- 300–579: Needs work
- 580–669: Fair
- 670–739: Good
- 740–799: Very good
- 800–850: Excellent

**IN PROGRESS**
- Are these weights correlated with default risk? We don't know yet.
- The +12 for "two steady Tuesdays"—is that too generous? Does it actually predict anything? We guessed.
- What happens when a gig worker has a slow week? Does the score tank? Should it?

More in `docs/SCORING.md`.

## What we built

```
app/               A demo phone UI (styled like CreditWise) showing one member's score
data/seed/         weights.sql and the scoring bands
data/events/       A synthetic event stream (321 events, zero randomness)
demo/              Python script that runs the full pipeline on our four fake members
src/gigscore/      The actual pipeline code (ingest, normalize, score, explain)
tests/             Tests that verify our four members' scores match the deck numbers
```

Run `python demo/run_demo.py` and you get the cohort scorecard. Run it with `--export` and it updates the app's state file.

**Requires:** Python 3.10+ · no external dependencies · doesn't need the network.

## What we're not sure will actually work

1. **Platform partnerships** — We assume Uber, DoorDash, etc. will give us reliable webhooks. They haven't signed anything yet.

2. **Plaid reliability** — Plaid is how we pull rent and subscription data from bank accounts. It's not always accurate or timely.

3. **Score stability** — Our weights are basically educated guesses. Real gig workers probably have patterns we haven't thought of (seasonal work, contract shifts, side hustles that aren't on the big platforms).

4. **Regulatory** — FCRA has opinions about how credit scores work. We have reason codes and an audit trail. We're not lawyers. This needs real compliance review.

5. **Actual lending impact** — Would a score of 685 actually reduce defaults? We don't have that data. We're assuming that consistency and verified income matter, but the underwriting test is real data.

## The ask (what we actually need)

To move from "working demo" to "real product," we need:

- **Data partnership with at least one gig platform** to pull real (anonymized, aggregated) event streams and test our scoring model against actual defaults. This is the riskiest part.
- **One team for one year.** Regulatory compliance, real platform integration, underwriting validation, then beta with a small cohort.
- **A lending partner** — someone willing to originate a few hundred micro-loans to gig workers and see if our score predicts default better than FICO.

We're not going to know if this works until we try it with real people and real money at stake. The demo proves the mechanics. Real validation is harder.

## Impact (if it works)

There are about 6.8M platform-dependent gig drivers in the US. If we can score even 1% and graduate them into Capital One products at better rates than they're currently getting (many are stuck with 21%+ APR), that's meaningful.

---

*DEMO PROJECT only. The cohort members are fictional. All payloads are synthetic. We styled the app like CreditWise for pitch clarity. This is a proof of concept, not a shipping product.*
