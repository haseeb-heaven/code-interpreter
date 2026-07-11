"""Pre-execution secret scanning (#225)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SecretMatch:
	pattern_name: str
	line_number: int
	masked_value: str


SECRET_PATTERNS: list[tuple[str, str]] = [
	("OpenAI API Key", r"sk-[A-Za-z0-9]{20,}"),
	("AWS Access Key", r"AKIA[0-9A-Z]{16}"),
	("GitHub Token", r"gh[pousr]_[A-Za-z0-9_]{36,}"),
	("Google API Key", r"AIza[0-9A-Za-z_-]{35}"),
	("Stripe Secret Key", r"sk_live_[0-9a-zA-Z]{24,}"),
	("Hardcoded Password", r'(?i)password\s*=\s*["\'][^"\' ]{8,}["\']'),
	("Private Key Header", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
	(
		"Generic Secret",
		r'(?i)(api_key|secret_key|auth_token)\s*=\s*["\'][^"\' ]{10,}["\']',
	),
]


def _mask(val: str) -> str:
	if len(val) <= 8:
		return "****"
	return val[:4] + "****" + val[-4:]


def scan_code(code: str) -> list[SecretMatch]:
	"""Scan code for secrets. Empty list means no matches."""
	matches: list[SecretMatch] = []
	if not code:
		return matches
	for i, line in enumerate(code.splitlines(), 1):
		for name, pattern in SECRET_PATTERNS:
			m = re.search(pattern, line)
			if m:
				matches.append(SecretMatch(name, i, _mask(m.group(0))))
				logger.info("Secret pattern hit: %s at line %s", name, i)
	return matches


def format_secret_warning(matches: list[SecretMatch]) -> str:
	if not matches:
		return ""
	lines = ["Secret detected in generated code before execution:"]
	for m in matches:
		lines.append(f"  Line {m.line_number} — {m.pattern_name}: {m.masked_value}")
	return "\n".join(lines)
