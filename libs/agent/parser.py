"""ReAct Thought / Action / Action Input parser (Yao et al., 2022)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional


class ParseError(ValueError):
    """Raised when model output is not a valid ReAct step."""


@dataclass
class ReactStep:
    thought: str
    action: str
    action_input: Any
    observation: Optional[str] = None


_THOUGHT_RE = re.compile(r"^\s*Thought\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_ACTION_RE = re.compile(r"^\s*Action\s*:\s*([A-Za-z_]+)\s*$", re.IGNORECASE | re.MULTILINE)
_ACTION_INPUT_RE = re.compile(
    r"^\s*Action\s*Input\s*:\s*(.*?)(?=^\s*(?:Thought|Action|Observation)\s*:|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

VALID_ACTIONS = frozenset({"code", "execute", "review", "debug", "finish"})


def _parse_action_input(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def parse_react_step(text: str) -> ReactStep:
    """Extract Thought, Action, and Action Input from model output."""
    if not text or not str(text).strip():
        raise ParseError("Empty ReAct step text")

    action_match = _ACTION_RE.search(text)
    if not action_match:
        raise ParseError("Missing Action field")

    thought_match = _THOUGHT_RE.search(text)
    thought = thought_match.group(1).strip() if thought_match else ""

    # Thought may span until Action; prefer line after Thought: if multi-line
    if thought_match:
        after_thought = text[thought_match.end() :]
        before_action = after_thought.split("Action:", 1)[0]
        # Keep first-line thought; append extra lines if present
        extra = before_action.strip()
        if extra and not thought.endswith(extra):
            # If Thought: captured only first line via ^...$, gather rest until Action
            first = thought_match.group(1).rstrip()
            # Re-parse thought block more carefully
            thought_block = re.search(
                r"Thought\s*:\s*(.*?)(?=^\s*Action\s*:)",
                text,
                re.IGNORECASE | re.MULTILINE | re.DOTALL,
            )
            if thought_block:
                thought = thought_block.group(1).strip()
            else:
                thought = first

    action = action_match.group(1).strip().lower()
    if action not in VALID_ACTIONS:
        raise ParseError(f"Unknown action: {action}")

    input_match = _ACTION_INPUT_RE.search(text)
    action_input = _parse_action_input(input_match.group(1) if input_match else "")

    return ReactStep(thought=thought, action=action, action_input=action_input, observation=None)


def format_trajectory(trajectory: list[dict]) -> str:
    """Render prior steps for the next LLM prompt."""
    parts: list[str] = []
    for item in trajectory:
        parts.append(f"Thought: {item.get('thought', '')}")
        parts.append(f"Action: {item.get('action', '')}")
        action_input = item.get("action_input", {})
        if isinstance(action_input, (dict, list)):
            parts.append(f"Action Input: {json.dumps(action_input)}")
        else:
            parts.append(f"Action Input: {action_input}")
        parts.append(f"Observation: {item.get('observation', '')}")
        parts.append("")
    return "\n".join(parts).strip()
