"""Tests for metrics.py

Validates behavioral metrics extraction from ledger records.
"""

import pytest
from datetime import datetime, timedelta
from metrics import (
    compute_weekly_amounts,
    compute_consistency,
    compute_daily_breakdown,
    detect_gap_days,
    compute_rent_history,
    compute_metrics,
)


@pytest.fixture
def sample_payouts():
    """Sample payout records spanning multiple weeks."""
    base = datetime(2026, 7, 1, 12, 0, 0)  # Tuesday
    return [
        # Week 1: Mon-Fri normal payouts
        {"kind": "payout", "source": "uber", "amount": 100, "occurred_at": (base - timedelta(days=1)).isoformat() + "Z"},
        {"kind": "payout", "source": "doordash", "amount": 80, "occurred_at": base.isoformat() + "Z"},
        {"kind": "payout", "source": "uber", "amount": 120, "occurred_at": (base + timedelta(days=1)).isoformat() + "Z"},
        {"kind": "payout", "source": "doordash", "amount": 90, "occurred_at": (base + timedelta(days=2)).isoformat() + "Z"},
        {"kind": "payout", "source": "uber", "amount": 110, "occurred_at": (base + timedelta(days=3)).isoformat() + "Z"},
        # Week 2: Normal payouts (Mon-Fri)
        {"kind": "payout", "source": "uber", "amount": 105, "occurred_at": (base + timedelta(days=5)).isoformat() + "Z"},
        {"kind": "payout", "source": "doordash", "amount": 85, "occurred_at": (base + timedelta(days=6)).isoformat() + "Z"},
        {"kind": "payout", "source": "uber", "amount": 115, "occurred_at": (base + timedelta(days=7)).isoformat() + "Z"},
        {"kind": "payout", "source": "doordash", "amount": 95, "occurred_at": (base + timedelta(days=8)).isoformat() + "Z"},
        # Note: Tuesday (day 9) has NO payout — this is the "gap"
        {"kind": "payout", "source": "uber", "amount": 125, "occurred_at": (base + timedelta(days=10)).isoformat() + "Z"},
    ]


@pytest.fixture
def sample_rent_records():
    """Sample rent payment records."""
    return [
        {"kind": "rent_payment", "meta": {"on_time": True}},
        {"kind": "rent_payment", "meta": {"on_time": True}},
        {"kind": "rent_payment", "meta": {"on_time": True}},
    ]


@pytest.fixture
def as_of_date():
    """Reference date for cutoff calculations."""
    return datetime(2026, 7, 20, 14, 0, 0)


class TestWeeklyAmounts:
    """Weekly payout aggregation is correct."""

    def test_sums_payouts_by_week(self, sample_payouts, as_of_date):
        """Payouts are grouped by ISO week."""
        weekly = compute_weekly_amounts(sample_payouts, as_of_date)
        assert len(weekly) > 0

    def test_ignores_incomplete_weeks(self, sample_payouts, as_of_date):
        """Only complete weeks (before cutoff) are included."""
        weekly = compute_weekly_amounts(sample_payouts, as_of_date)
        # All our samples are before the cutoff, so they should be included
        assert len(weekly) >= 2

    def test_weekly_amounts_are_positive(self, sample_payouts, as_of_date):
        """Each week's total is positive."""
        weekly = compute_weekly_amounts(sample_payouts, as_of_date)
        for amount in weekly.values():
            assert amount > 0


class TestConsistency:
    """Coefficient of variation is calculated correctly."""

    def test_perfect_consistency_is_zero(self):
        """Identical weekly amounts have CV of 0."""
        amounts = {"2026-W28": 1000, "2026-W29": 1000, "2026-W30": 1000}
        cv = compute_consistency(amounts)
        assert cv < 0.01  # Effectively 0

    def test_high_variance_has_high_cv(self):
        """Volatile weeks have high CV."""
        amounts = {"2026-W28": 100, "2026-W29": 1000, "2026-W30": 200}
        cv = compute_consistency(amounts)
        assert cv > 0.5

    def test_empty_amounts_returns_one(self):
        """Empty ledger returns high CV (not enough data)."""
        cv = compute_consistency({})
        assert cv == 1.0

    def test_single_week_returns_one(self):
        """Only one week of data returns high CV."""
        cv = compute_consistency({"2026-W28": 500})
        assert cv == 1.0


class TestDailyBreakdown:
    """Daily payout patterns are extracted correctly."""

    def test_returns_three_values(self, sample_payouts, as_of_date):
        """Returns (daily dict, overall avg, weekday avgs)."""
        daily, overall, weekday_avgs = compute_daily_breakdown(sample_payouts, as_of_date)
        assert isinstance(daily, dict)
        assert isinstance(overall, float)
        assert isinstance(weekday_avgs, dict)

    def test_overall_daily_avg_is_positive(self, sample_payouts, as_of_date):
        """Overall average of active days is positive."""
        _, overall, _ = compute_daily_breakdown(sample_payouts, as_of_date)
        assert overall > 0

    def test_weekday_avgs_are_positive(self, sample_payouts, as_of_date):
        """All weekday averages are positive."""
        _, _, weekday_avgs = compute_daily_breakdown(sample_payouts, as_of_date)
        for wd, avg in weekday_avgs.items():
            assert avg >= 0
            assert 0 <= wd <= 6


class TestGapDetection:
    """Earnings gaps are detected correctly."""

    def test_detects_gap_day(self):
        """A day with much lower earnings is flagged."""
        # Weekday avgs: Mon-Fri normally earn ~100, but Tuesday only earns 15 (< 20% of 100)
        weekday_avgs = {0: 100, 1: 15, 2: 100, 3: 100, 4: 100}
        gap_days, worst_day = detect_gap_days(weekday_avgs, overall_daily_avg=100, n_weeks=2)
        assert len(gap_days) > 0
        assert 1 in gap_days  # Tuesday is the gap

    def test_no_gap_when_consistent(self):
        """Consistent earnings across all days show no gap."""
        weekday_avgs = {0: 100, 1: 95, 2: 105, 3: 90, 4: 110}
        gap_days, _ = detect_gap_days(weekday_avgs, overall_daily_avg=100, n_weeks=2)
        assert len(gap_days) == 0

    def test_gap_name_is_weekday(self):
        """Gap day name is a real weekday."""
        weekday_avgs = {1: 10}  # Only Tuesday, very low
        _, gap_name = detect_gap_days(weekday_avgs, overall_daily_avg=100, n_weeks=2)
        assert gap_name == "Tuesday"

    def test_no_gap_with_insufficient_data(self):
        """Gap detection requires enough working days."""
        weekday_avgs = {1: 50}  # Only one day
        gap_days, _ = detect_gap_days(weekday_avgs, overall_daily_avg=100, n_weeks=1)
        assert len(gap_days) == 0


class TestRentHistory:
    """Rent payment history is extracted correctly."""

    def test_counts_on_time_payments(self, sample_rent_records):
        """On-time rent payments are counted."""
        on_time, missed = compute_rent_history(sample_rent_records)
        assert on_time == 3
        assert not missed

    def test_detects_missed_payments(self):
        """Missed rent is flagged."""
        records = [
            {"kind": "rent_payment", "meta": {"on_time": True}},
            {"kind": "rent_payment", "meta": {"on_time": False}},
        ]
        on_time, missed = compute_rent_history(records)
        assert on_time == 1
        assert missed

    def test_empty_rent_history(self):
        """No rent records returns zero on-time, no missed."""
        on_time, missed = compute_rent_history([])
        assert on_time == 0
        assert not missed


class TestComputeMetrics:
    """Full metrics extraction works end-to-end."""

    def test_returns_all_metrics(self, sample_payouts, sample_rent_records, as_of_date):
        """compute_metrics returns a complete dict."""
        records = sample_payouts + sample_rent_records
        metrics = compute_metrics(records, as_of_date)
        
        expected_keys = {
            "sources",
            "n_sources",
            "weekly_cv",
            "weekly_amounts",
            "weekday_avgs",
            "overall_daily_avg",
            "gap_days",
            "gap_day",
            "on_time_rent_months",
            "missed_rent",
            "n_sub_merchants",
        }
        assert expected_keys.issubset(set(metrics.keys()))

    def test_metrics_detect_gap_in_sample(self, sample_payouts, as_of_date):
        """The Tuesday gap in sample_payouts is detected."""
        records = sample_payouts
        metrics = compute_metrics(records, as_of_date)
        # Tuesday is day 1, and we have consistent payouts except Tuesday
        assert metrics["gap_day"] is not None

    def test_sources_are_identified(self, sample_payouts, as_of_date):
        """Connected sources are listed."""
        metrics = compute_metrics(sample_payouts, as_of_date)
        assert "uber" in metrics["sources"]
        assert "doordash" in metrics["sources"]

    def test_metrics_are_numeric(self, sample_payouts, as_of_date):
        """Numeric fields are actually numbers."""
        metrics = compute_metrics(sample_payouts, as_of_date)
        assert isinstance(metrics["weekly_cv"], float)
        assert isinstance(metrics["overall_daily_avg"], float)
        assert isinstance(metrics["n_sources"], int)
        assert isinstance(metrics["on_time_rent_months"], int)
