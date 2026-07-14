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


# Signature seen only after a live scenario already failed to produce its
# expected marker(s) -- checked as a downgrade from FAIL, never as a blanket
# upfront skip (a passing run's output could legitimately mention a retry
# that later succeeded). Scoped narrowly to the plan's quota/billing/auth
# soft-skip criterion: model_router.py only logs "rotating key / backoff"
# when its own ErrorClassifier already tagged the failure AUTH/QUOTA/
# TRANSIENT (see libs/core/model_router.py's _record_retry_failure), i.e.
# this text is the product's own billing/auth-adjacent retry surfacing, not
# generic model-output flakiness. Deliberately excludes the sibling "LLM
# request retry N/M (empty response) -- retrying." message (blank-completion
# retry, unrelated to billing/auth) so that a genuine empty-output bug still
# FAILs and gets root-caused per Task 9 Step 3.
_LIVE_FLAKE_MARKERS: tuple[str, ...] = ("rotating key / backoff",)


def is_transient_live_flake(text: str) -> bool:
	low = (text or "").lower()
	return any(m in low for m in _LIVE_FLAKE_MARKERS)


def redact_output(text: str, *, max_len: int = 2000) -> str:
	cleaned = _TOKEN.sub("[REDACTED]", text or "")
	if len(cleaned) > max_len:
		cleaned = cleaned[: max_len - 3] + "..."
	return cleaned
