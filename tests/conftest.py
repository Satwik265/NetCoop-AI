"""Pytest configuration and test isolation fixtures."""

import pytest
from netcoop.config import settings


@pytest.fixture(autouse=True)
def configure_test_isolation(request):
    """Enable dev in-process fallback for general offline unit tests unless marked strict_isolation."""
    if "strict_isolation" in request.keywords or "http_only" in request.keywords:
        # Strict isolation mode: completely disable any in-process fallback
        settings.in_process_fallback = False
        settings.allow_dev_in_process_fallback = False
    else:
        # Default unit tests run offline with dev fallback explicitly enabled
        settings.allow_dev_in_process_fallback = True
    yield
    # Restore production defaults (fail closed)
    settings.in_process_fallback = False
    settings.allow_dev_in_process_fallback = False
