-- ============================================================
-- GigScore · SQL-stored weights (SCORE phase source of truth)
-- Loaded into SQLite locally; Aurora/RDS Postgres in production.
-- Score = 300 + Σ(factor points at current level) + Σ(event ledger)
-- Max factor points sum to 550  ->  score range 300–850.
-- ============================================================

DROP TABLE IF EXISTS factor_levels;
CREATE TABLE factor_levels (
    factor      TEXT NOT NULL,          -- machine name
    label       TEXT NOT NULL,          -- UI label ("What's driving it")
    level       TEXT NOT NULL,          -- EXCELLENT / GOOD / FAIR / NEEDS_WORK
    points      INTEGER NOT NULL,
    sort_order  INTEGER NOT NULL,
    PRIMARY KEY (factor, level)
);

-- Rent & subscriptions ------------------------------- max 140
INSERT INTO factor_levels VALUES ('rent_subscriptions','Rent & subscriptions','EXCELLENT',140,1);
INSERT INTO factor_levels VALUES ('rent_subscriptions','Rent & subscriptions','GOOD',105,1);
INSERT INTO factor_levels VALUES ('rent_subscriptions','Rent & subscriptions','FAIR',70,1);
INSERT INTO factor_levels VALUES ('rent_subscriptions','Rent & subscriptions','NEEDS_WORK',30,1);

-- Earnings consistency ------------------------------- max 130
INSERT INTO factor_levels VALUES ('earnings_consistency','Earnings consistency','EXCELLENT',130,2);
INSERT INTO factor_levels VALUES ('earnings_consistency','Earnings consistency','GOOD',90,2);
INSERT INTO factor_levels VALUES ('earnings_consistency','Earnings consistency','FAIR',60,2);
INSERT INTO factor_levels VALUES ('earnings_consistency','Earnings consistency','NEEDS_WORK',25,2);

-- Platform diversity (18 pts per connected source, cap 5) -- max 90
DROP TABLE IF EXISTS diversity_weights;
CREATE TABLE diversity_weights (
    points_per_source INTEGER NOT NULL,
    max_sources       INTEGER NOT NULL
);
INSERT INTO diversity_weights VALUES (18, 5);

-- Level thresholds used only for the diversity UI badge
INSERT INTO factor_levels VALUES ('platform_diversity','Platform diversity','EXCELLENT',90,3);
INSERT INTO factor_levels VALUES ('platform_diversity','Platform diversity','GOOD',54,3);
INSERT INTO factor_levels VALUES ('platform_diversity','Platform diversity','FAIR',36,3);
INSERT INTO factor_levels VALUES ('platform_diversity','Platform diversity','NEEDS_WORK',18,3);

-- Income trajectory ---------------------------------- max 190
INSERT INTO factor_levels VALUES ('income_trajectory','Income trajectory','EXCELLENT',190,4);
INSERT INTO factor_levels VALUES ('income_trajectory','Income trajectory','GOOD',140,4);
INSERT INTO factor_levels VALUES ('income_trajectory','Income trajectory','FAIR',95,4);
INSERT INTO factor_levels VALUES ('income_trajectory','Income trajectory','NEEDS_WORK',50,4);

-- ============================================================
-- Event ledger rules (micro-deltas between monthly recomputes)
-- These are the "+5 / +3 / +12" numbers shown in Coach.
-- ============================================================
DROP TABLE IF EXISTS event_rules;
CREATE TABLE event_rules (
    event_type  TEXT PRIMARY KEY,
    delta       INTEGER NOT NULL,
    win_label   TEXT                    -- "Recent wins" copy; NULL = not surfaced
);
INSERT INTO event_rules VALUES ('rent_reported_on_time',        +5, 'Rent reported on time');
INSERT INTO event_rules VALUES ('subscription_reported_on_time',+2, 'Subscription reported on time');
INSERT INTO event_rules VALUES ('consistency_streak_4wk',       +3, '4-week consistency streak');
INSERT INTO event_rules VALUES ('steady_tuesday_pair',         +12, 'Two steady Tuesdays');
INSERT INTO event_rules VALUES ('source_connected',             +4, 'New income source connected');
INSERT INTO event_rules VALUES ('rent_payment_missed',         -15, NULL);
INSERT INTO event_rules VALUES ('payout_received',               0, NULL);  -- recalc trigger only

-- ============================================================
-- Score bands (300–850)
-- ============================================================
DROP TABLE IF EXISTS score_bands;
CREATE TABLE score_bands (
    band  TEXT NOT NULL,
    lo    INTEGER NOT NULL,
    hi    INTEGER NOT NULL
);
INSERT INTO score_bands VALUES ('Needs work', 300, 579);
INSERT INTO score_bands VALUES ('Fair',       580, 669);
INSERT INTO score_bands VALUES ('Good',       670, 739);
INSERT INTO score_bands VALUES ('Very good',  740, 799);
INSERT INTO score_bands VALUES ('Excellent',  800, 850);

-- ============================================================
-- Graduation milestones (Coach "Next milestone" card)
-- ============================================================
DROP TABLE IF EXISTS milestones;
CREATE TABLE milestones (
    threshold  INTEGER PRIMARY KEY,
    product    TEXT NOT NULL,
    detail     TEXT NOT NULL
);
INSERT INTO milestones VALUES (680, 'Platinum Secured auto-review',
    'Refundable deposit from $49 · reports to all 3 bureaus');
INSERT INTO milestones VALUES (720, 'Quicksilver unsecured pre-approval',
    'No deposit · 1.5% cash back on every purchase');

-- ============================================================
-- Behavioral thresholds (NORMALIZE -> SCORE handoff)
-- ============================================================
DROP TABLE IF EXISTS behavior_thresholds;
CREATE TABLE behavior_thresholds (name TEXT PRIMARY KEY, value REAL NOT NULL);
INSERT INTO behavior_thresholds VALUES ('cv_excellent_max',      0.08); -- weekly payout coefficient of variation
INSERT INTO behavior_thresholds VALUES ('cv_good_max',           0.22);
INSERT INTO behavior_thresholds VALUES ('cv_fair_max',           0.40);
INSERT INTO behavior_thresholds VALUES ('day_gap_ratio',         0.80); -- day is a "gap" if < 80% of daily average
INSERT INTO behavior_thresholds VALUES ('rent_excellent_months', 12);
INSERT INTO behavior_thresholds VALUES ('rent_good_months',      6);
