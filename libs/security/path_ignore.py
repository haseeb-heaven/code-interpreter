"""Path ignore patterns for protected locations (#225)."""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_IGNORE_PATHS = [
	Path.home() / ".config" / "code_interpreter" / "ignore",
	Path.home() / ".code_interpreter" / "ignore",
]


def default_ignore_file() -> Path:
	return DEFAULT_IGNORE_PATHS[0]


def load_ignore_patterns(path: Path | None = None) -> list[str]:
	"""Load ignore patterns from the user ignore file (comments/# blank skipped)."""
	candidates = [path] if path else DEFAULT_IGNORE_PATHS
	for candidate in candidates:
		if candidate is None:
			continue
		try:
			if not candidate.is_file():
				continue
			patterns: list[str] = []
			for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
				line = line.strip()
				if not line or line.startswith("#"):
					continue
				patterns.append(os.path.expanduser(line))
			return patterns
		except Exception as exc:
			logger.warning("Failed to read ignore file %s: %s", candidate, exc)
	return []


def is_path_protected(file_path: str, patterns: list[str] | None = None) -> bool:
	"""Return True if the absolute path matches any ignore pattern."""
	if not file_path:
		return False
	patterns = patterns if patterns is not None else load_ignore_patterns()
	if not patterns:
		return False
	try:
		resolved = str(Path(os.path.expanduser(file_path)).resolve())
	except Exception:
		resolved = os.path.abspath(os.path.expanduser(file_path))
	norm = resolved.replace("\\", "/")
	home = str(Path.home().resolve()).replace("\\", "/")
	for pat in patterns:
		expanded = os.path.expanduser(pat).replace("\\", "/")
		if expanded.startswith("~/"):
			expanded = home + expanded[1:]
		# Directory prefix style: ~/.ssh/
		if expanded.endswith("/"):
			if norm.startswith(expanded.rstrip("/") + "/") or norm == expanded.rstrip("/"):
				return True
		if fnmatch.fnmatch(norm, expanded) or fnmatch.fnmatch(os.path.basename(norm), expanded):
			return True
		# **/.env style
		if "**" in expanded:
			rx = fnmatch.translate(expanded)
			if re.search(rx, norm):
				return True
	return False


_PATH_LITERAL_RE = re.compile(
	r"""['"]([^'"]+\.(?:env|pem|key|json|yml|yaml|txt|csv|py|sh))['"]"""
	r"""|['"](~?/[^'"]+)['"]"""
	r"""|['"]([A-Za-z]:\\[^'"]+)['"]""",
	re.IGNORECASE,
)


def code_references_protected_path(code: str, patterns: list[str] | None = None) -> list[str]:
	"""Return protected path strings referenced as literals in code."""
	hits: list[str] = []
	if not code:
		return hits
	for m in _PATH_LITERAL_RE.finditer(code):
		candidate = next((g for g in m.groups() if g), None)
		if candidate and is_path_protected(candidate, patterns):
			hits.append(candidate)
	return hits
