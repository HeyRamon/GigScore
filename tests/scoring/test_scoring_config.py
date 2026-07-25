"""Tests for scoring_config.py

Validates that all constants are defined, consistent, and match the scoring range.
"""

import pytest
from scoring_config import (
    FACTORS,
    SCORE_MIN,
    SCORE_MAX,
    SCORE_RANGE,
    LEVELS,
    DIVERSITY_LEVELS,
    DIVERSITY_POINTS_PER_SOURCE,
    DIVERSITY_SOURCE_CAP,
    EVENT_TYPES,
    get_factor_label,
    get_factor_max_points,
    get_level_display,
)


class TestScoreRange:
    """Score boundaries are consistent and sensible."""

    def test_score_bounds(self):
        """Score range is 300-850 (550 point span)."""
        assert SCORE_MIN == 300
        assert SCORE_MAX == 850
        assert SCORE_RANGE == 550

    def test_max_is_greater_than_min(self):
        """Maximum score is higher than minimum."""
        assert SCORE_MAX > SCORE_MIN


class TestFactors:
    """Factor definitions are complete and consistent."""

    def test_four_factors_defined(self):
        """Exactly 4 factors in the model."""
        assert len(FACTORS) == 4

    def test_factor_keys_unique(self):
        """Each factor key is unique."""
        keys = [fk for fk, _, _ in FACTORS]
        assert len(keys) == len(set(keys))

    def test_factor_max_points_sum(self):
        """Factor max points sum to 550 (filling the range)."""
        total = sum(max_pts for _, _, max_pts in FACTORS)
        assert total == SCORE_RANGE

    def test_all_factor_keys_have_labels(self):
        """Every factor key has a non-empty label."""
        for factor_key, label, _ in FACTORS:
            assert label
            assert len(label) > 0

    def test_all_factor_points_positive(self):
        """All factor max points are positive."""
        for _, _, max_pts in FACTORS:
            assert max_pts > 0

    def test_rent_subscriptions_is_highest(self):
        """Rent is the largest single factor (140 pts)."""
        max_factor = max((max_pts for _, _, max_pts in FACTORS))
        rent_points = next(
            (max_pts for fk, _, max_pts in FACTORS if fk == "rent_subscriptions"),
            None,
        )
        assert rent_points == max_factor


class TestLevels:
    """Level names are defined and consistent."""

    def test_four_levels(self):
        """Four standard levels."""
        assert len(LEVELS) == 4

    def test_level_keys(self):
        """All standard level keys are present."""
        expected = {"EXCELLENT", "GOOD", "FAIR", "NEEDS_WORK"}
        assert set(LEVELS.keys()) == expected

    def test_level_display_names(self):
        """Each level has a non-empty display name."""
        for key, display in LEVELS.items():
            assert display
            assert len(display) > 0
            # Display names should start with capital letter
            assert display[0].isupper()


class TestDiversity:
    """Platform diversity configuration is sensible."""

    def test_diversity_levels_are_ordered(self):
        """Diversity levels decrease with fewer sources."""
        thresholds = sorted(DIVERSITY_LEVELS.keys(), reverse=True)
        assert thresholds[0] == 5  # Excellent at 5 sources
        assert thresholds[-1] == 2  # Fair at 2 sources

    def test_diversity_points_calculation(self):
        """Max diversity points = points per source * cap."""
        max_diversity = DIVERSITY_POINTS_PER_SOURCE * DIVERSITY_SOURCE_CAP
        # Should be 90 (the factor's max)
        assert max_diversity == 90

    def test_diversity_cap_is_positive(self):
        """Can't have negative or zero source cap."""
        assert DIVERSITY_SOURCE_CAP > 0


class TestEventTypes:
    """Event types are defined and reasonable."""

    def test_event_types_not_empty(self):
        """At least some event types defined."""
        assert len(EVENT_TYPES) > 0

    def test_event_type_names_are_snake_case(self):
        """Event type names follow snake_case convention."""
        for event_type in EVENT_TYPES:
            assert event_type.islower()
            assert "_" in event_type or event_type.isalpha()

    def test_includes_rent_events(self):
        """Rent events are defined."""
        rent_events = {e for e in EVENT_TYPES if "rent" in e}
        assert len(rent_events) >= 1

    def test_includes_consistency_events(self):
        """Consistency tracking events are defined."""
        consistency_events = {e for e in EVENT_TYPES if "consistency" in e or "streak" in e}
        assert len(consistency_events) >= 1


class TestFactorLookup:
    """Helper functions work correctly."""

    def test_get_factor_label(self):
        """Can look up factor label by key."""
        label = get_factor_label("rent_subscriptions")
        assert label == "Rent & subscriptions"

    def test_get_factor_label_missing(self):
        """Missing factor key returns None."""
        label = get_factor_label("nonexistent_factor")
        assert label is None

    def test_get_factor_max_points(self):
        """Can look up factor max points by key."""
        points = get_factor_max_points("rent_subscriptions")
        assert points == 140

    def test_get_factor_max_points_all(self):
        """All factors in FACTORS have retrievable max points."""
        for factor_key, _, expected_points in FACTORS:
            points = get_factor_max_points(factor_key)
            assert points == expected_points

    def test_get_level_display(self):
        """Can look up level display name."""
        display = get_level_display("EXCELLENT")
        assert display == "Excellent"

    def test_get_level_display_all(self):
        """All levels have display names."""
        for level_key in LEVELS.keys():
            display = get_level_display(level_key)
            assert display in LEVELS.values()


class TestConsistency:
    """Configuration is internally consistent."""

    def test_no_factor_exceeds_range(self):
        """No single factor max exceeds total range."""
        for _, _, max_pts in FACTORS:
            assert max_pts <= SCORE_RANGE

    def test_all_level_keys_in_dictionary(self):
        """Every level key that factors might use is defined."""
        # If we see NEEDS_WORK, FAIR, GOOD, EXCELLENT in tests, they're all in LEVELS
        required_levels = {"NEEDS_WORK", "FAIR", "GOOD", "EXCELLENT"}
        assert required_levels.issubset(set(LEVELS.keys()))
