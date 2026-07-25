"""GigScore — a credit-readiness engine that turns verified gig earnings into a
live score, and graduates workers into Capital One products.

Pipeline phases (mirrors the pitch deck exactly):
    INGEST     Python webhook listeners, AWS Lambda triggers
    NORMALIZE  Python transforms data, AWS Lambda organizes
    SCORE      Python rules engine, SQL-stored weights
    EXPLAIN    Python orchestrates LLM, SQL audit log
"""

__version__ = "0.1.0"

SCORE_MIN = 300
SCORE_MAX = 850
