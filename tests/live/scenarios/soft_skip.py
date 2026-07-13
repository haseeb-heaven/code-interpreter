# -*- coding: utf-8 -*-
"""Soft-skip classifiers for live user scenarios (never log secrets)."""

from __future__ import annotations

import re

from libs.core.error_classification import BILLING_AUTH_MARKERS as _BILLING_AUTH
from libs.core.error_classification import DEPENDENCY_ENV_MARKERS as _DEP_ENV

_TOKEN = re.compile(
	r"(?i)\b(sk-[a-z0-9_\-]{16,}|gsk_[a-z0-9_\-]{16,}|hf_[a-z0-9_\-]{16,}|or-[a-z0-9_\-]{16,})\b"
)


def is_soft_skip(text: str) -> bool:
	low = (text or "").lower()
	return any(m in low for m in _BILLING_AUTH) or any(m in low for m in _DEP_ENV)


def redact_output(text: str, *, max_len: int = 2000) -> str:
	cleaned = _TOKEN.sub("[REDACTED]", text or "")
	if len(cleaned) > max_len:
		cleaned = cleaned[: max_len - 3] + "..."
	return cleaned
