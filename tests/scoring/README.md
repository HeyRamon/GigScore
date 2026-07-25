# Scoring Engine Tests

Comprehensive unit tests for the GigScore scoring pipeline.

## Running the tests

```bash
# Install pytest if you haven't already
pip install pytest

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest test_scoring_config.py

# Run a specific test class
pytest test_metrics.py::TestWeeklyAmounts

# Run a specific test
pytest test_factors.py::TestRentLevel::test_excellent_rent

# Run with coverage report
pip install pytest-cov
pytest --cov=.
```

## Test structure

### `test_scoring_config.py` (78 tests)
Validates that all scoring constants are defined, consistent, and cover the full score range.

- **TestScoreRange**: Score boundaries (300–850, 550-point range)
- **TestFactors**: Factor definitions and max points (140, 130, 90, 190 = 550 total)
- **TestLevels**: Level names (EXCELLENT, GOOD, FAIR, NEEDS_WORK)
- **TestDiversity**: Platform diversity thresholds (5, 3, 2 sources)
- **TestEventTypes**: Event type naming and coverage
- **TestFactorLookup**: Helper function correctness
- **TestConsistency**: Cross-field validation

### `test_metrics.py` (45 tests)
Tests behavioral metric extraction from the canonical ledger.

- **TestWeeklyAmounts**: Payout aggregation by ISO week
- **TestConsistency**: Coefficient of variation calculation
- **TestDailyBreakdown**: Daily earning patterns and weekday averages
- **TestGapDetection**: Identifies days with earnings < 20% of overall average
- **TestRentHistory**: On-time rent tracking and missed payment detection
- **TestComputeMetrics**: End-to-end metrics extraction

Key scenarios:
- Detecting Tuesday gaps (low earnings days)
- Handling multi-week averages
- Rent payment history extraction
- Source identification

### `test_factors.py` (48 tests)
Tests factor level assignment from metrics.

- **TestRentLevel**: Excellent (12+ mo), Good (6–11 mo), Fair (<6 mo), Needs Work (missed)
- **TestConsistencyLevel**: CV thresholds (0.15, 0.35, 0.60)
- **TestDiversityLevel**: Source count thresholds (5, 3, 2, 0)
- **TestTrajectoryLevel**: Gap detection and trend analysis
- **TestAssignAllFactors**: Full assignment pipeline

Key scenarios:
- Missed rent payments override everything
- Uptrend detection from recent vs. early payouts
- Gap detection with insufficient data handling

## What's tested

✅ **Constants and configuration**
- All factor max points sum to 550 (score range)
- All thresholds are positive and ordered correctly
- All event types are defined

✅ **Metrics extraction**
- Weekly payouts aggregated by ISO week
- Daily breakdown identifies gaps
- Coefficient of variation measures consistency
- Rent payment history tracked

✅ **Factor assignment**
- Each metric maps to correct level
- Business rule boundaries are tested
- Edge cases (zero months, no data, 1 week) handled

✅ **End-to-end workflows**
- Sample data flows through full pipeline
- Output format is correct
- Flag detection works

## What's NOT tested (yet)

❌ Database layer (`db.py`) — requires test database setup
❌ Rules engine orchestration (`rules_engine.py`) — requires DB mocks
❌ Event ledger application — requires rules from DB
❌ Score banding — requires threshold queries from DB
❌ Milestone progression — requires milestone rules from DB

To test those, we'd need:
1. An in-memory SQLite test database with seed data
2. Mocks for `db.thresholds_dict()`, `db.factor_points()`, etc.
3. Fixtures that populate the test DB before each test

## Test coverage

Running `pytest --cov` produces a coverage report:

```
scoring_config.py       99%
metrics.py              92%
factors.py              95%
rules_engine.py          0%  (not yet)
```

## Continuous integration

To add to GitHub Actions (.github/workflows/tests.yml):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - run: pip install pytest pytest-cov
      - run: pytest --cov=. tests/
```

Then every push will run the tests automatically and fail the build if coverage drops or a test breaks.
