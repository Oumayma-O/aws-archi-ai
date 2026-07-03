"""Property-based test fixtures for AWS Architect AI agentic features.

Provides Hypothesis strategies and shared fixtures for property tests
that validate correctness properties from the design document.
"""

import pytest
from hypothesis import settings, HealthCheck


# Property tests for agents use extended settings: no deadline
# and suppressed health checks since agent tests can be slow.
settings.register_profile(
    "agent_property",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
