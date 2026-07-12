"""Language resolution for ReAct execute actions."""
from __future__ import annotations

from typing import Any, Optional

SUPPORTED_EXECUTE_LANGUAGES = frozenset({"python", "javascript"})

# Common LLM / fence aliases → canonical sandbox language.
LANGUAGE_ALIASES = {
    "py": "python",
    "py3": "python",
    "python3": "python",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    # OS names sometimes leak into Action Input from prompts/history.
    "linux": "python",
    "windows": "python",
    "windows 10": "python",
    "windows 11": "python",
    "mac": "python",
    "macos": "python",
    "darwin": "python",
}

_EMPTY_TOKENS = frozenset({"", "none", "null", "undefined", "nil", "n/a", "na"})


def normalize_execute_language(language: Any) -> Optional[str]:
    """Return canonical language name, or None if missing/unrecognized.

    Recognized values: python, javascript, and LANGUAGE_ALIASES keys.
    """
    if language is None:
        return None
    text = str(language).strip().lower()
    if text in _EMPTY_TOKENS:
        return None
    text = LANGUAGE_ALIASES.get(text, text)
    if text in SUPPORTED_EXECUTE_LANGUAGES:
        return text
    return None


def configured_interpreter_language(code_interpreter: Any, fallback: str = "python") -> str:
    """Read INTERPRETER_LANGUAGE from the interpreter, normalized to a supported lang."""
    raw = getattr(code_interpreter, "INTERPRETER_LANGUAGE", None)
    normalized = normalize_execute_language(raw)
    if normalized:
        return normalized
    fallback_norm = normalize_execute_language(fallback)
    return fallback_norm or "python"


def resolve_react_execute_language(action_input: Any, code_interpreter: Any = None) -> str:
    """Resolve language for a ReAct ``execute`` step.

    Models often omit language, send empty/null, or put prose in Action Input
    (especially on later steps). Missing/invalid values fall back to the
    configured interpreter language (default python) so consecutive executes
    keep working.
    """
    default = configured_interpreter_language(code_interpreter)

    raw: Any = None
    if isinstance(action_input, dict):
        if "language" not in action_input:
            return default
        raw = action_input.get("language")
    elif isinstance(action_input, str):
        # Bare strings are frequently instructions ("run it"), not languages.
        raw = action_input
    elif action_input is None:
        return default
    else:
        raw = action_input

    normalized = normalize_execute_language(raw)
    return normalized if normalized else default
