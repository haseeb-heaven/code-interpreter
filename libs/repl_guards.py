"""
REPL input guards -- classify user input before starting expensive LLM calls.

Provides:
  - is_non_task_input(text): True when the text is a traceback / litellm dump.
  - format_short_llm_error(exc): Compact, user-friendly error string.
  - is_repl_slash_command(text): True when text is a known REPL slash command.
  - is_unknown_slash_command(text): True when text starts with / but is unknown.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slash commands that NEVER start a ReAct / LLM turn.
# ---------------------------------------------------------------------------
REPL_SLASH_COMMANDS = frozenset({
    "/clear",
    "/config",
    "/cofig",
    "/mode",
    "/help",
    "/free",
    "/model",
    "/exit",
    "/quit",
    "/models",
    "/memory",
    "/tools",
})

# ---------------------------------------------------------------------------
# Non-task input detection
# ---------------------------------------------------------------------------
_NON_TASK_PATTERNS = (
    re.compile(r"^Traceback \(most recent call last\)", re.MULTILINE),
    re.compile(r'^  File "[^"]+", line \d+', re.MULTILINE),
    re.compile(
        r"^(Error|Exception|ValueError|TypeError|AttributeError|KeyError"
        r"|ImportError|OSError|IOError|RuntimeError|NameError|IndexError"
        r"|NotImplementedError|StopIteration|SystemExit|MemoryError"
        r")\s*:",
        re.MULTILINE,
    ),
    re.compile(r"\blitellm\b.*\berror\b", re.IGNORECASE),
    re.compile(r"litellm\.exceptions\.", re.IGNORECASE),
    re.compile(r"\burl\s*=\s*api_base\b", re.IGNORECASE),
    re.compile(r"\bapi_base\s*=\s*['\"]https?://", re.IGNORECASE),
)


def is_non_task_input(text: str) -> bool:
    """Return True when *text* looks like a pasted traceback / error dump."""
    if not text or not str(text).strip():
        return False
    sample = str(text).strip()
    return any(p.search(sample) for p in _NON_TASK_PATTERNS)


def is_repl_slash_command(text: str) -> bool:
    """Return True when *text* is a known REPL slash command."""
    stripped = str(text or "").strip().lower()
    if not stripped.startswith("/"):
        return False
    cmd = stripped.split()[0] if stripped.split() else stripped
    return cmd in REPL_SLASH_COMMANDS


def is_unknown_slash_command(text: str) -> bool:
    """Return True when *text* starts with '/' but is not a known REPL command."""
    stripped = str(text or "").strip().lower()
    if not stripped.startswith("/"):
        return False
    cmd = stripped.split()[0] if stripped.split() else stripped
    return cmd not in REPL_SLASH_COMMANDS


# ---------------------------------------------------------------------------
# Short LLM error formatter
# ---------------------------------------------------------------------------
_PROVIDER_ERROR_MARKERS = (
    "litellm", "openrouter", "openai", "anthropic", "groq", "gemini",
    "rate limit", "rate_limit", "429", "503", "502", "timeout",
    "connection", "api key", "api_key", "quota", "billing", "auth",
    "invalid model", "model_not_found", "bad gateway", "overloaded",
    "all providers failed",
)

_MAX_SHORT_ERROR_LEN = 200


def format_short_llm_error(exc: Any) -> str:
    """Return a compact, single-line error string suitable for REPL display."""
    if exc is None:
        return "[LLM Error] Unknown error"
    raw = str(exc).strip()
    first_line = raw.split("\n")[0].strip()
    if len(first_line) > _MAX_SHORT_ERROR_LEN:
        first_line = first_line[:_MAX_SHORT_ERROR_LEN - 3] + "..."
    low = first_line.lower()
    is_provider = any(marker in low for marker in _PROVIDER_ERROR_MARKERS)
    prefix = "[LLM Error]" if is_provider else "[Error]"
    return f"{prefix} {first_line}"
