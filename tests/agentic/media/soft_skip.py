# -*- coding: utf-8 -*-
"""Soft-skip classifiers and secret redaction for agentic media suite."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_BILLING_AUTH = (
	"429",
	"rate limit",
	"ratelimit",
	"quota",
	"insufficient balance",
	"billing",
	"please recharge",
	"credit balance",
	"unauthorized",
	"authentication",
	"api key",
	"401",
	"403",
	"forbidden",
	"payment required",
	"resource_exhausted",
)

_DEP_ENV = (
	"modulenotfounderror",
	"no module named",
	"filenotfounderror",
	"ffmpeg",
	"connection refused",
	"connection reset",
	"timed out",
	"timeout",
	"temporarily unavailable",
	"no such file",
	"cannot find",
	"not installed",
	"command not found",
)

_KEY_LINE = re.compile(
	r"(?im)^(\s*[\w]*API_KEY\s*=\s*).+$"
)
_TOKEN = re.compile(
	r"(?i)\b(sk-[a-z0-9_\-]{16,}|gsk_[a-z0-9_\-]{16,}|hf_[a-z0-9_\-]{16,})\b"
)


def is_billing_or_auth_failure(text: str) -> bool:
	"""True when output indicates quota/billing/auth — soft-skip."""
	low = (text or "").lower()
	return any(m in low for m in _BILLING_AUTH)


def is_dep_or_env_failure(text: str) -> bool:
	"""True when output indicates missing deps or env/runtime issues."""
	low = (text or "").lower()
	return any(m in low for m in _DEP_ENV)


def redact_output(text: str) -> str:
	"""Mask API key assignment lines and long sk-/gsk_/hf_ tokens."""
	if not text:
		return ""
	out = _KEY_LINE.sub(r"\1[REDACTED]", text)
	out = _TOKEN.sub("[REDACTED]", out)
	return out
