"""
Pytest configuration for sheetscut tests.
"""

import pytest
from pathlib import Path


@pytest.fixture
def sample_transcript():
    """Return path to sample transcript in fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_transcript.json"
    if fixture_path.exists():
        return str(fixture_path)
    return None


@pytest.fixture
def sample_producer_text():
    """Return sample producer text for testing."""
    return "This is a test sentence. Another sentence here."
