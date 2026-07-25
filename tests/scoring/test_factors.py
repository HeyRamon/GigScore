"""Tests for factors.py

Validates factor level assignment from metrics.
"""

import pytest
import sys
sys.path.insert(0, 'src/gigscore/score')

from factors import (
    assign_rent_level,
    assign_consistency_level,
    assign_diversity_level,
    assign_trajectory_level,
    assign_all_factors,
)


class TestRentLevel:
    """Rent & subscriptions factor assignment."""

    def test_excellent_rent(self):
        """12+ months on-time rent is Excellent."""
        thresholds = {"rent_excellent_months": 12, "rent_good_months": 6}
        level, why = assign_rent_level(thresholds, 12, False)
        assert level == "EXCELLENT"
        assert "12" in why

    def test_good_rent(self):
        """6-11 months on-time rent is Good."""
        thresholds = {"rent_excellent_months": 12, "rent_good_months": 6}
        level, why = assign_rent_level(thresholds, 8, False)
        assert level == "GOOD"
        assert "8" in why

    def test_fair_rent(self):
        """Less than 6 months is Fair."""
        thresholds = {"rent_excellent_months": 12, "rent_good_months": 6}
        level, why = assign_rent_level(thresholds, 3, False)
        assert level == "FAIR"

    def test_missed_rent_is_needs_work(self):
        """Any missed payment overrides to Needs Work."""
        thresholds = {"rent_excellent_months": 12, "rent_good_months": 6}
        level, why = assign_rent_level(thresholds, 24, True)
        assert level == "NEEDS_WORK"
        assert "missed" in why.lower()

    def test_zero_rent_is_fair(self):
        """No rent history is Fair."""
        thresholds = {"rent_excellent_months": 12, "rent_good_months": 6}
        level, why = assign_rent_level(thresholds, 0, False)
        assert level == "FAIR"


class TestConsistencyLevel:
    """Earnings consistency factor assignment."""

    def test_excellent_consistency(self):
        """CV <= 0.15 is Excellent."""
        thresholds = {
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        level, why = assign_consistency_level(thresholds, 0.10)
        assert level == "EXCELLENT"

    def test_good_consistency(self):
        """CV 0.15–0.35 is Good."""
        thresholds = {
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        level, why = assign_consistency_level(thresholds, 0.25)
        assert level == "GOOD"

    def test_fair_consistency(self):
        """CV 0.35–0.60 is Fair."""
        thresholds = {
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        level, why = assign_consistency_level(thresholds, 0.50)
        assert level == "FAIR"

    def test_needs_work_consistency(self):
        """CV > 0.60 is Needs Work."""
        thresholds = {
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        level, why = assign_consistency_level(thresholds, 0.75)
        assert level == "NEEDS_WORK"


class TestDiversityLevel:
    """Platform diversity factor assignment."""

    def test_excellent_diversity_five_sources(self):
        """5 connected sources is Excellent."""
        level, why = assign_diversity_level(5)
        assert level == "EXCELLENT"
        assert "5" in why

    def test_good_diversity_three_sources(self):
        """3 connected sources is Good."""
        level, why = assign_diversity_level(3)
        assert level == "GOOD"

    def test_fair_diversity_two_sources(self):
        """2 connected sources is Fair."""
        level, why = assign_diversity_level(2)
        assert level == "FAIR"

    def test_needs_work_diversity_one_source(self):
        """1 source is Needs Work."""
        level, why = assign_diversity_level(1)
        assert level == "NEEDS_WORK"

    def test_needs_work_diversity_no_sources(self):
        """0 sources is Needs Work."""
        level, why = assign_diversity_level(0)
        assert level == "NEEDS_WORK"


class TestTrajectoryLevel:
    """Income trajectory factor assignment."""

    def test_gap_day_is_needs_work(self):
        """Detected gap day triggers Needs Work."""
        level, why = assign_trajectory_level("Tuesday", [1000, 1100, 900])
        assert level == "NEEDS_WORK"
        assert "Tuesday" in why

    def test_trending_up_is_good(self):
        """Recent weeks higher than early weeks is Good."""
        weekly_amounts = [500, 600, 1100, 1200]
        level, why = assign_trajectory_level(None, weekly_amounts)
        assert level == "GOOD"
        assert "trending up" in why.lower()

    def test_stable_earnings_is_fair(self):
        """Stable earnings without trend is Fair."""
        weekly_amounts = [1000, 1000, 1000]
        level, why = assign_trajectory_level(None, weekly_amounts)
        assert level == "FAIR"
        assert "steady" in why.lower()

    def test_no_gap_no_trend_is_fair(self):
        """No gap and no uptrend defaults to Fair."""
        level, why = assign_trajectory_level(None, [900, 950, 920, 940])
        assert level == "FAIR"

    def test_insufficient_data_is_fair(self):
        """Less than 4 weeks of data is Fair (not Excellent)."""
        level, why = assign_trajectory_level(None, [1000, 2000])
        assert level == "FAIR"


class TestAssignAllFactors:
    """Full factor assignment works end-to-end."""

    def test_returns_four_factors(self):
        """All 4 factors are returned."""
        thresholds = {
            "rent_excellent_months": 12,
            "rent_good_months": 6,
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        metrics = {
            "on_time_rent_months": 12,
            "missed_rent": False,
            "weekly_cv": 0.20,
            "n_sources": 3,
            "gap_day": None,
            "weekly_amounts": [1000, 1100, 1050],
        }
        factors, flags = assign_all_factors(thresholds, metrics)
        assert len(factors) == 4

    def test_factor_keys_are_correct(self):
        """Factor keys match the scoring model."""
        thresholds = {
            "rent_excellent_months": 12,
            "rent_good_months": 6,
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        metrics = {
            "on_time_rent_months": 12,
            "missed_rent": False,
            "weekly_cv": 0.20,
            "n_sources": 3,
            "gap_day": None,
            "weekly_amounts": [1000, 1100, 1050],
        }
        factors, _ = assign_all_factors(thresholds, metrics)
        keys = [fk for fk, _, _ in factors]
        assert "rent_subscriptions" in keys
        assert "earnings_consistency" in keys
        assert "platform_diversity" in keys
        assert "income_trajectory" in keys

    def test_gap_flag_is_set_when_gap_detected(self):
        """Flags dict includes gap_day when detected."""
        thresholds = {
            "rent_excellent_months": 12,
            "rent_good_months": 6,
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        metrics = {
            "on_time_rent_months": 12,
            "missed_rent": False,
            "weekly_cv": 0.20,
            "n_sources": 3,
            "gap_day": "Tuesday",
            "weekly_amounts": [1000, 1100, 1050],
        }
        _, flags = assign_all_factors(thresholds, metrics)
        assert "gap_day" in flags
        assert flags["gap_day"] == "Tuesday"

    def test_no_gap_flag_when_no_gap(self):
        """Flags dict is empty when no issues detected."""
        thresholds = {
            "rent_excellent_months": 12,
            "rent_good_months": 6,
            "cv_excellent_max": 0.15,
            "cv_good_max": 0.35,
            "cv_fair_max": 0.60,
        }
        metrics = {
            "on_time_rent_months": 12,
            "missed_rent": False,
            "weekly_cv": 0.20,
            "n_sources": 3,
            "gap_day": None,
            "weekly_amounts": [1000, 1100, 1050],
        }
        _, flags = assign_all_factors(thresholds, metrics)
        assert len(flags) == 0