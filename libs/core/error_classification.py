# -*- coding: utf-8 -*-
"""Shared billing/auth/dependency error classification.

Single source of truth for "this looks like a quota/billing/auth condition,
not a code bug" — consumed by both the live-scenario test harness
(``tests/live/scenarios/soft_skip.py``) and the product's own recoverable-error
detection (``libs/core/model_router.py``) so the two classifications can never
drift apart.
"""

from __future__ import annotations

from typing import Tuple

BILLING_AUTH_MARKERS: Tuple[str, ...] = (
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

DEPENDENCY_ENV_MARKERS: Tuple[str, ...] = (
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
	"indentationerror",
	"syntaxerror",
	"unterminated string",
)


def is_billing_or_auth_condition(text: str) -> bool:
	low = (text or "").lower()
	return any(marker in low for marker in BILLING_AUTH_MARKERS)


def is_dependency_or_env_condition(text: str) -> bool:
	low = (text or "").lower()
	return any(marker in low for marker in DEPENDENCY_ENV_MARKERS)
