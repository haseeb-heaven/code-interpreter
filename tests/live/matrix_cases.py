"""Build reduced but axis-complete live matrix cases."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_CLASSIC_PROVIDERS = 3
_MAX_AGENTIC_PROVIDERS = 2


def _family_available(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Prefer family reps; fall back to free_catalog when family missing."""
	families = [p for p in providers if p.get("source") == "family" and p.get("available")]
	if families:
		return families
	return [p for p in providers if p.get("available")]


def build_matrix_cases(
	providers: list[dict[str, Any]],
	runtimes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
	"""Return case dicts covering stream/sandbox/mode/language axes.

	Unavailable providers/runtimes become ``expected=skip`` rows so reports stay complete.
	"""
	cases: list[dict[str, Any]] = []

	for prov in providers:
		if prov.get("source") not in ("family", "local"):
			continue
		for stream in (False, True):
			expected = "run" if prov.get("available") else "skip"
			reason = None if expected == "run" else (
				"local endpoint down" if prov["id"] == "local" else f"missing {prov.get('env_key')}"
			)
			cases.append(
				{
					"id": f"llm:{prov['id']}:stream={'on' if stream else 'off'}",
					"kind": "llm_ping",
					"provider": prov["id"],
					"config": prov["config"],
					"env_key": prov.get("env_key"),
					"stream": stream,
					"sandbox": None,
					"language": None,
					"mode": "llm",
					"expected": expected,
					"skip_reason": reason,
				}
			)

	for prov in providers:
		if prov.get("source") != "free_catalog" or not prov.get("available"):
			continue
		if any(
			c["kind"] == "llm_ping" and c["config"] == prov["config"] and c.get("expected") == "run"
			for c in cases
		):
			continue
		cases.append(
			{
				"id": f"llm:free:{prov['id']}:stream=off",
				"kind": "llm_ping",
				"provider": prov["id"],
				"config": prov["config"],
				"env_key": prov.get("env_key"),
				"stream": False,
				"sandbox": None,
				"language": None,
				"mode": "llm",
				"expected": "run",
				"skip_reason": None,
				"tier": prov.get("tier"),
			}
		)
		break

	available_families = _family_available(providers)[:_MAX_CLASSIC_PROVIDERS]
	langs = ("python", "javascript", "r")

	for idx, prov in enumerate(available_families):
		for lang in langs:
			lang_ok = bool(runtimes.get(lang, {}).get("available"))
			sandbox_opts = ("on", "off") if lang == "python" else ("on",)
			stream_opts = (False, True) if lang == "python" and idx == 0 else (False,)
			for sandbox in sandbox_opts:
				for stream in stream_opts:
					expected = "run" if lang_ok else "skip"
					cases.append(
						{
							"id": (
								f"classic:{prov['id']}:{lang}:"
								f"sandbox={sandbox}:stream={'on' if stream else 'off'}"
							),
							"kind": "classic_smoke",
							"provider": prov["id"],
							"config": prov["config"],
							"env_key": prov.get("env_key"),
							"stream": stream,
							"sandbox": sandbox,
							"language": lang,
							"mode": "classic",
							"expected": expected,
							"skip_reason": None if lang_ok else f"{lang} runtime missing",
						}
					)

	if not available_families:
		for lang in langs:
			lang_ok = bool(runtimes.get(lang, {}).get("available"))
			cases.append(
				{
					"id": f"classic:none:{lang}:sandbox=on:stream=off",
					"kind": "classic_smoke",
					"provider": "none",
					"config": None,
					"env_key": None,
					"stream": False,
					"sandbox": "on",
					"language": lang,
					"mode": "classic",
					"expected": "skip",
					"skip_reason": "no available providers" if lang_ok else f"{lang} runtime missing",
				}
			)

	agentic_providers = _family_available(providers)[:_MAX_AGENTIC_PROVIDERS]
	py_ok = bool(runtimes.get("python", {}).get("available"))
	for prov in agentic_providers:
		expected = "run" if py_ok else "skip"
		cases.append(
			{
				"id": f"agentic:{prov['id']}:python:sandbox=on:stream=off",
				"kind": "agentic_smoke",
				"provider": prov["id"],
				"config": prov["config"],
				"env_key": prov.get("env_key"),
				"stream": False,
				"sandbox": "on",
				"language": "python",
				"mode": "agentic",
				"expected": expected,
				"skip_reason": None if py_ok else "python runtime missing",
			}
		)

	if not agentic_providers:
		cases.append(
			{
				"id": "agentic:none:python:sandbox=on:stream=off",
				"kind": "agentic_smoke",
				"provider": "none",
				"config": None,
				"env_key": None,
				"stream": False,
				"sandbox": "on",
				"language": "python",
				"mode": "agentic",
				"expected": "skip",
				"skip_reason": "no available providers",
			}
		)

	logger.info("Built %d matrix cases", len(cases))
	return cases
