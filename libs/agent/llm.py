"""Shared LLM helper for ReAct agent actions."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import litellm

logger = logging.getLogger(__name__)


def call_llm(
    model_name: str,
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
) -> Tuple[str, Dict[str, float]]:
    """Call litellm and return (content, {cost, tokens})."""
    try:
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
        }
        if api_key:
            kwargs["api_key"] = api_key
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content or ""
        try:
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:
            cost = 0.0
        tokens = int(response.usage.total_tokens) if response.usage else 0
        return content, {"cost": cost, "tokens": tokens}
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise
