"""
Autonomous tool-use loop — LLM picks tools, we execute, feed results back.

Supports a human approval gate (default) or full ``--yolo`` autonomy.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from libs.repl_guards import format_short_llm_error
from libs.tools.bootstrap import build_native_fs_registry
from libs.tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 30

# Error markers that indicate the LLM could not produce a valid response.
_REPAIR_ERROR_MARKERS = (
    "tool_use_failed",
    "failed_generation",
    "badrequesterror",
    "bad request",
    "invalid_request_error",
    "invalid request",
    "context_length_exceeded",
    "context length",
    "maximum context",
)

MAX_REPAIR_ATTEMPTS = 2


class AutonomousAgentLoop:
	"""
	Drives a fully autonomous tool-use loop:

	1. Call LLM with task + tool schemas
	2. LLM returns either tool_calls or a final text answer
	3. If tool_call → dispatch to ToolRegistry → append result → goto 1
	4. If final answer → return to user
	"""

	def __init__(
		self,
		llm_client: Any = None,
		model: str = "gpt-4o-mini",
		auto_mode: bool = False,
		registry: Optional[ToolRegistry] = None,
		completion_fn: Optional[Callable[..., Any]] = None,
		confirm_fn: Optional[Callable[[str, dict], bool]] = None,
		max_iterations: int = MAX_ITERATIONS,
		api_key: Optional[str] = None,
		context_manager: Any = None,
	):
		"""
		Args:
			llm_client: Optional OpenAI-style client (``client.chat.completions.create``).
			model: Model id / config name passed to the completion backend.
			auto_mode: True = execute tools without asking (``--yolo``).
			registry: Tool registry; defaults to native FS/shell tools.
			completion_fn: Optional ``(model, messages, tools) -> response`` override
				(preferred for tests / litellm wiring).
			confirm_fn: Optional ``(tool_name, tool_args) -> bool`` approval callback.
			max_iterations: Hard cap to prevent runaway loops.
			api_key: Optional API key for litellm fallback.
			context_manager: Optional message compactor with ``maybe_compact``.
		"""
		self.llm = llm_client
		self.model = model
		self.auto = auto_mode
		self.registry = registry or build_native_fs_registry()
		self.completion_fn = completion_fn
		self.confirm_fn = confirm_fn
		self.max_iterations = max_iterations
		self.api_key = api_key
		self.context_manager = context_manager

	def run(self, task: str) -> str:
		"""Execute the autonomous loop; never raises.

		All exceptions are caught and returned as a short message.
		"""
		try:
			return self._run_inner(task)
		except Exception as exc:
			logger.error("[AutoLoop] Unhandled error: %s", exc)
			return format_short_llm_error(exc)

	def _run_inner(self, task: str) -> str:
		"""Inner run -- may raise; wrapped by run()."""
		messages: list[dict] = [
			{
				"role": "system",
				"content": (
					"You are an autonomous coding agent with access to filesystem and shell tools. "
					"Use tools when needed to complete the user's task. "
					"When finished, reply with a concise final answer and no further tool calls."
				),
			},
			{"role": "user", "content": task},
		]
		iteration = 0
		repair_attempts = 0

		while iteration < self.max_iterations:
			iteration += 1
			logger.info("[AutoLoop] Iteration %s", iteration)

			if self.context_manager is not None and hasattr(self.context_manager, "maybe_compact"):
				try:
					messages = self.context_manager.maybe_compact(messages, model=self.model)
				except Exception as exc:
					logger.warning("[AutoLoop] Context compaction skipped: %s", exc)

			tools = self.registry.openai_schemas()
			try:
				response = self._complete(messages, tools)
			except Exception as exc:
				short_err = format_short_llm_error(exc)
				err_low = str(exc).lower()
				is_rep = any(m in err_low for m in _REPAIR_ERROR_MARKERS)
				if is_rep and repair_attempts < MAX_REPAIR_ATTEMPTS:
					repair_attempts += 1
					logger.warning("[AutoLoop] Repairable LLM error (attempt %s/%s): %s",
						repair_attempts, MAX_REPAIR_ATTEMPTS, exc)
					messages.append({"role": "user", "content":
						f"Error: {short_err}. Please respond with valid tool call or text."})
					continue
				logger.error("[AutoLoop] LLM error: %s", exc)
				return short_err
			msg = self._extract_message(response)

			if isinstance(msg, dict):
				tool_calls = msg.get("tool_calls")
				content = msg.get("content")
			else:
				tool_calls = getattr(msg, "tool_calls", None)
				content = getattr(msg, "content", None)

			if not tool_calls:
				return content or ""

			# Append assistant turn (dict form for message history portability)
			assistant_msg = self._assistant_message_dict(msg, content, tool_calls)
			messages.append(assistant_msg)

			for tc in tool_calls:
				tool_name, tool_args, tool_call_id = self._parse_tool_call(tc)
				logger.info("[AutoLoop] Tool call: %s(%s)", tool_name, tool_args)

				if not self.auto:
					approved = self._confirm(tool_name, tool_args)
					if not approved:
						result_text = "User denied this tool call."
					else:
						result = self.registry.dispatch(tool_name, tool_args)
						result_text = result.output if result.success else f"ERROR: {result.error}"
				else:
					result = self.registry.dispatch(tool_name, tool_args)
					result_text = result.output if result.success else f"ERROR: {result.error}"
					logger.info("[AutoLoop] Result: %s", (result_text or "")[:200])

				messages.append(
					{
						"role": "tool",
						"tool_call_id": tool_call_id,
						"content": result_text,
					}
				)

		return "[AutoLoop] Max iterations reached. Task may be incomplete."

	def _complete(self, messages: list[dict], tools: list[dict]) -> Any:
		if self.completion_fn is not None:
			return self.completion_fn(model=self.model, messages=messages, tools=tools)

		if self.llm is not None:
			return self.llm.chat.completions.create(
				model=self.model,
				messages=messages,
				tools=tools,
				tool_choice="auto",
			)

		# Default: litellm
		import litellm

		kwargs: dict[str, Any] = {
			"model": self.model,
			"messages": messages,
			"tools": tools,
			"tool_choice": "auto",
		}
		if self.api_key:
			kwargs["api_key"] = self.api_key
		return litellm.completion(**kwargs)

	def _confirm(self, tool_name: str, tool_args: dict) -> bool:
		if self.confirm_fn is not None:
			return bool(self.confirm_fn(tool_name, tool_args))
		try:
			confirm = input(
				f"\n🔧 LLM wants to call `{tool_name}` with {tool_args}\nApprove? [y/N]: "
			)
			return confirm.strip().lower() == "y"
		except EOFError:
			return False

	@staticmethod
	def _extract_message(response: Any) -> Any:
		if isinstance(response, dict):
			choices = response.get("choices") or []
			if choices:
				return choices[0].get("message") or {}
			return response.get("message") or response
		choices = getattr(response, "choices", None)
		if choices:
			return choices[0].message
		return response

	@staticmethod
	def _parse_tool_call(tc: Any) -> tuple[str, dict, str]:
		if isinstance(tc, dict):
			fn = tc.get("function") or {}
			name = fn.get("name") or tc.get("name") or ""
			raw_args = fn.get("arguments") or tc.get("arguments") or "{}"
			call_id = tc.get("id") or name
		else:
			fn = getattr(tc, "function", None)
			name = getattr(fn, "name", "") if fn else getattr(tc, "name", "")
			raw_args = getattr(fn, "arguments", "{}") if fn else "{}"
			call_id = getattr(tc, "id", None) or name

		if isinstance(raw_args, dict):
			args = raw_args
		else:
			try:
				args = json.loads(raw_args or "{}")
			except json.JSONDecodeError:
				args = {}
		return name, args, str(call_id)

	@staticmethod
	def _assistant_message_dict(msg: Any, content: Optional[str], tool_calls: Any) -> dict:
		serialized_calls = []
		for tc in tool_calls:
			if isinstance(tc, dict):
				serialized_calls.append(tc)
				continue
			fn = getattr(tc, "function", None)
			serialized_calls.append(
				{
					"id": getattr(tc, "id", ""),
					"type": "function",
					"function": {
						"name": getattr(fn, "name", "") if fn else "",
						"arguments": getattr(fn, "arguments", "{}") if fn else "{}",
					},
				}
			)
		return {
			"role": "assistant",
			"content": content,
			"tool_calls": serialized_calls,
		}
