"""Shared pytest fixtures for offline unit/integration tests (#224)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session")
def mock_llm_response():
	"""Factory for fake LiteLLM-style completion responses."""

	def _make(content: str):
		return MagicMock(
			choices=[MagicMock(message=MagicMock(content=content))],
			usage=MagicMock(total_tokens=100, prompt_tokens=80, completion_tokens=20),
		)

	return _make


@pytest.fixture
def mock_litellm(mock_llm_response):
	"""Patch litellm.completion for the duration of a test."""
	with patch("litellm.completion") as mock:
		mock.return_value = mock_llm_response('```python\nprint("mocked")\n```')
		yield mock


@pytest.fixture
def block_external_dns(monkeypatch):
	"""
	Optional fixture: block non-localhost DNS resolution.
	Not autouse — many existing tests mock HTTP at a higher level.
	"""
	import socket

	original_getaddrinfo = socket.getaddrinfo

	def patched(host, *args, **kwargs):
		if host not in ("localhost", "127.0.0.1", "::1", None):
			raise ConnectionError(f"Test tried to make real network call to: {host}")
		return original_getaddrinfo(host, *args, **kwargs)

	monkeypatch.setattr(socket, "getaddrinfo", patched)
