# -*- coding: utf-8 -*-
"""Soft-skip classifiers for live user scenarios (never log secrets)."""

from __future__ import annotations

import re

_BILLING_AUTH = (
	"429",
	"rate limit",
	"ratelimit",
	"rate_limit",
	"quota",
	"free-models-per-day",
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
	"all free",
	"models failed",
	"provider returned error",
	"no healthy upstream",
	"overloaded",
	"capacity",
	"503",
	"502",
	"stealth",
)

_DEP_ENV = (
	"modulenotfounderror",
	"no module named",
	"filenotfounderror",
	"connection refused",
	"connection reset",
	"timed out",
	"timeout",
	"temporarily unavailable",
	"not installed",
	"command not found",
	"local endpoint",
	"could not connect",
)

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
