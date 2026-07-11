"""Pytest fixtures for the interactive test suite (#226)."""

from __future__ import annotations

import pytest

from tests.interactive.helpers import make_interp


@pytest.fixture
def mock_interp():
	"""Fully wired mock interpreter ready for interactive loop testing."""
	return make_interp()


@pytest.fixture
def tmp_session_dir(tmp_path):
	"""Temporary directory for session save/load tests."""
	d = tmp_path / "sessions"
	d.mkdir()
	return d
