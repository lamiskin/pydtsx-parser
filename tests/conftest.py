"""Shared pytest configuration for the SSIS Parser test suite."""

from hypothesis import settings

# Disable Hypothesis deadlines globally — parallel workers (pytest-xdist)
# have cold-start overhead that causes flaky DeadlineExceeded on first example.
settings.register_profile("ci", deadline=None)
settings.load_profile("ci")
