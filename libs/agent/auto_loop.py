"""
Autonomous tool-use loop — LLM picks tools, we execute, feed results back.

Supports a human approval gate (default) or full ``--yolo`` autonomy.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

from libs.repl_guards import format_short_llm_error
from libs.tools.bootstrap import build_native_fs_registry
from libs.tools.tool_registry import ToolRegistry
from libs.agent.step_ui import make_step_presenter
from libs.deps.install_flow import MissingBinaryHandler
from libs.deps.missing_binary import is_missing_binary_error

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

# Cap shared by exception repairs and malformed tool-markup repairs.
MAX_REPAIR_ATTEMPTS = 8

# Known native tool names that models sometimes dump as fake XML instead of tool_calls.
_KNOWN_TOOL_NAMES = (
	"write_file",
	"read_file",
	"run_shell",
	"list_dir",
	"glob_search",
	"web_search",
)

_MALFORMED_TOOL_RE = re.compile(
	r"(?:"
	r"</?\s*function\b"
	r"|</?\s*tool_call\b"
	r"|</?\s*tool_calls\b"
	r"|<\s*(?:" + "|".join(_KNOWN_TOOL_NAMES) + r")\b"
	r"|invoke\s+(?:" + "|".join(_KNOWN_TOOL_NAMES) + r")\b"
	r")",
	re.IGNORECASE,
)

_TASK_NEEDS_TOOLS_RE = re.compile(
	r"\b(?:"
	r"chart|png|plot|matplotlib|write|create|save|generate|file|csv|json|"
	r"shell|run|execute|read|list|directory|folder|tmp|path"
	r")\b",
	re.IGNORECASE,
)

_REPAIR_TOOL_MARKUP_PROMPT = (
	"Your previous reply dumped invalid tool markup as plain text "
	"(e.g. <write_file ...</function>) instead of structured tool_calls. "
	"Do NOT invent XML/HTML tags. Emit proper OpenAI-style tool_calls JSON only. "
	"Use write_file / run_shell (or other available tools) to complete the task — "
	"for chart work, write Python that generates the requested PNG files and run it. "
	"When the work is actually done, reply with a short final answer and no tool calls."
)

_REPAIR_NO_TOOLS_PROMPT = (
	"You returned a final answer without using any tools, but this task still needs "
	"filesystem/shell work (write files, run Python, create charts, etc.). "
	"Emit proper tool_calls now (write_file / run_shell / …). "
	"Do not dump XML tags. Do not claim success until tools have executed."
)


def looks_like_malformed_tool_markup(content: Optional[str]) -> bool:
	"""True when assistant text looks like failed/pseudo tool XML, not a real answer."""
	if not content or not isinstance(content, str):
		return False
	text = content.strip()
	if not text:
		return False
	if _MALFORMED_TOOL_RE.search(text):
		return True
	# Angle-bracket + known tool name + JSON-ish payload (Groq-style dumps).
	lower = text.lower()
	if "<" in text and any(name in lower for name in _KNOWN_TOOL_NAMES):
		if "{" in text or "</" in text:
			return True
	return False


def task_likely_needs_tools(task: str) -> bool:
	"""Heuristic: user task looks like it requires write/run/file tools."""
	if not task or not isinstance(task, str):
		return False
	return bool(_TASK_NEEDS_TOOLS_RE.search(task))


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
		*,
		enable_free_fallback: bool = False,
		configs_dir: str = "configs",
		catalog: Any = None,
		on_fallback: Optional[Callable[[dict], None]] = None,
		sleep_fn=None,
		rate_limit_retries: int = 2,
		gemini_style: bool = False,
		quiet_ui: bool = False,
		step_presenter: Any = None,
		auto_yes: bool = False,
		missing_binary_handler: Optional[MissingBinaryHandler] = None,
		install_confirm_fn: Optional[Callable[[str], bool]] = None,
		enable_missing_binary_search: bool = False,
		max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
	):
		"""
		Args:
			llm_client: Optional OpenAI-style client (``client.chat.completions.create``).
			model: Model id / config name passed to the completion backend.
			auto_mode: True = execute tools without asking (``--yolo``).
			registry: Tool registry; defaults to native FS/shell tools.
			completion_fn: Optional ``(model, messages, tools) -> response`` override
				(preferred for tests / litellm wiring). Ignored when
				``enable_free_fallback`` is True (uses catalog fallback instead).
			confirm_fn: Optional ``(tool_name, tool_args) -> bool`` approval callback.
			max_iterations: Hard cap to prevent runaway loops.
			api_key: Optional API key for litellm fallback.
			context_manager: Optional message compactor with ``maybe_compact``.
			enable_free_fallback: Use free-catalog rotation on OR 429 / daily quota / 502.
			configs_dir: Directory of model JSON configs.
			catalog: Optional ``FreeLLMCatalog`` instance.
			on_fallback: Called with the winning candidate dict after a fallback.
			sleep_fn: Injectable sleep for rate-limit retries (tests).
			rate_limit_retries: Same-model retries before falling through.
			gemini_style: Use Gemini-CLI style step spinner / Thought panels.
			quiet_ui: Suppress step UX (structured output).
			step_presenter: Optional injected presenter.
			auto_yes: ``--yes`` / ``INTERPRETER_YES`` — with yolo, auto-approve installs.
			missing_binary_handler: Optional injected missing-tool recovery handler.
			install_confirm_fn: Optional ``(prompt) -> bool`` for install consent.
			enable_missing_binary_search: Web-search install tips when a tool is missing.
			max_repair_attempts: Cap for exception / malformed-tool repairs (default 8).
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
		self.enable_free_fallback = enable_free_fallback
		self.configs_dir = configs_dir
		self.catalog = catalog
		self.on_fallback = on_fallback
		self.sleep_fn = sleep_fn
		self.rate_limit_retries = rate_limit_retries
		self.gemini_style = bool(gemini_style)
		self.auto_yes = bool(auto_yes)
		self.enable_missing_binary_search = bool(enable_missing_binary_search)
		self.max_repair_attempts = max(1, int(max_repair_attempts))
		# Live step UX when gemini_style is requested (interpreter_auto_main sets this).
		self.presenter = step_presenter or make_step_presenter(
			gemini_style=bool(gemini_style),
			quiet=quiet_ui,
		)
		self.missing_binary_handler = missing_binary_handler
		self.install_confirm_fn = install_confirm_fn

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
					"Always emit structured tool_calls (never invent XML tags like "
					"<write_file> or </function>). "
					"When finished, reply with a concise final answer and no further tool calls."
				),
			},
			{"role": "user", "content": task},
		]
		iteration = 0
		repair_attempts = 0
		tools_attempted = 0
		expects_tools = task_likely_needs_tools(task)

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
				with self.presenter.thinking(iteration):
					response = self._complete(messages, tools)
			except Exception as exc:
				short_err = format_short_llm_error(exc)
				err_low = str(exc).lower()
				is_rep = any(m in err_low for m in _REPAIR_ERROR_MARKERS)
				if is_rep and repair_attempts < self.max_repair_attempts:
					repair_attempts += 1
					logger.warning(
						"[AutoLoop] Repairable LLM error (attempt %s/%s): %s",
						repair_attempts,
						self.max_repair_attempts,
						exc,
					)
					messages.append(
						{
							"role": "user",
							"content": (
								f"Error: {short_err}. "
								"Please respond with valid tool_calls JSON or a short final text answer. "
								"Do not emit XML tool tags."
							),
						}
					)
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
				content_str = content if isinstance(content, str) else (str(content) if content else "")
				malformed = looks_like_malformed_tool_markup(content_str)
				# Require tool attempts for write/run/chart-style tasks; denials still count.
				incomplete = (
					expects_tools
					and tools_attempted == 0
					and bool(content_str.strip())
					and not malformed
				)

				if (malformed or incomplete) and repair_attempts < self.max_repair_attempts:
					repair_attempts += 1
					reason = "malformed tool markup" if malformed else "final answer with no tools used"
					logger.warning(
						"[AutoLoop] Repairable incomplete turn (%s, attempt %s/%s)",
						reason,
						repair_attempts,
						self.max_repair_attempts,
					)
					preview = (content_str or "")[:240].replace("\n", " ")
					self.presenter.show_observation(
						iteration,
						f"[repair] Invalid/incomplete tool use detected — retrying "
						f"({repair_attempts}/{self.max_repair_attempts}). "
						f"Preview: {preview}",
					)
					messages.append({"role": "assistant", "content": content_str or ""})
					messages.append(
						{
							"role": "user",
							"content": (
								_REPAIR_TOOL_MARKUP_PROMPT if malformed else _REPAIR_NO_TOOLS_PROMPT
							),
						}
					)
					continue

				if malformed:
					# Exhausted repairs — do not surface broken XML as the answer.
					logger.error(
						"[AutoLoop] Exhausted repairs on malformed tool markup after %s attempts",
						repair_attempts,
					)
					self.presenter.show_observation(
						iteration,
						"[repair] Model kept emitting invalid tool markup; stopping.",
					)
					return (
						"[AutoLoop] Model kept emitting invalid tool markup after "
						f"{repair_attempts} repair attempts. Task may be incomplete."
					)

				if content:
					self.presenter.show_observation(iteration, content)
				return content or ""

			# Append assistant turn (dict form for message history portability)
			assistant_msg = self._assistant_message_dict(msg, content, tool_calls)
			messages.append(assistant_msg)
			if content:
				self.presenter.show_thought(iteration, content)

			for tc in tool_calls:
				tool_name, tool_args, tool_call_id = self._parse_tool_call(tc)
				logger.info("[AutoLoop] Tool call: %s(%s)", tool_name, tool_args)
				self.presenter.show_action(iteration, tool_name, tool_args)

				tools_attempted += 1
				if not self.auto:
					approved = self._confirm(tool_name, tool_args)
					if not approved:
						result_text = "User denied this tool call."
					else:
						with self.presenter.acting(iteration, tool_name):
							result = self.registry.dispatch(tool_name, tool_args)
						result_text = result.output if result.success else f"ERROR: {result.error}"
				else:
					with self.presenter.acting(iteration, tool_name):
						result = self.registry.dispatch(tool_name, tool_args)
					result_text = result.output if result.success else f"ERROR: {result.error}"
					logger.info("[AutoLoop] Result: %s", (result_text or "")[:200])

				# Missing binary recovery (ffmpeg, etc.) — ask unless yolo+yes.
				if is_missing_binary_error(result_text):
					result_text = self._recover_missing_binary(result_text)

				self.presenter.show_observation(iteration, result_text)
				messages.append(
					{
						"role": "tool",
						"tool_call_id": tool_call_id,
						"content": result_text,
					}
				)

		return "[AutoLoop] Max iterations reached. Task may be incomplete."

	def _recover_missing_binary(self, result_text: str) -> str:
		"""Prompt (or auto-approve with yolo+yes) to install a missing PATH tool."""
		handler = self.missing_binary_handler
		if handler is None:
			search_fn = self._default_search if self.enable_missing_binary_search else None
			handler = MissingBinaryHandler(
				confirm_fn=self.install_confirm_fn,
				search_fn=search_fn,
			)
		do_search = bool(self.enable_missing_binary_search or handler.search_fn)
		if do_search and hasattr(self.presenter, "searching"):
			with self.presenter.searching("install missing tool"):
				result = handler.handle(
					result_text,
					auto_yes=self.auto_yes,
					yolo=self.auto,
					do_search=True,
				)
		else:
			result = handler.handle(
				result_text,
				auto_yes=self.auto_yes,
				yolo=self.auto,
				do_search=False,
			)
		if result.detected and result.observation:
			return f"{result_text}\n\n{result.observation}"
		return result_text

	@staticmethod
	def _default_search(query: str) -> str:
		try:
			from libs.tools.web_search_tool import WebSearchTool

			tool = WebSearchTool(provider="duckduckgo")
			out = tool.search(query, max_results=3)
			return out if isinstance(out, str) else str(out)
		except Exception as exc:
			logger.debug("[AutoLoop] missing-binary search failed: %s", exc)
			return f"(web search unavailable: {exc})"

	def _on_fallback_candidate(self, candidate: dict) -> None:
		config_name = str(candidate.get("config") or candidate.get("model") or "").strip()
		if config_name:
			self.model = config_name
		if callable(self.on_fallback):
			try:
				self.on_fallback(candidate)
			except Exception as exc:
				logger.debug("[AutoLoop] on_fallback hook failed: %s", exc)

	def _complete(self, messages: list[dict], tools: list[dict]) -> Any:
		if self.enable_free_fallback:
			from libs.agent.llm import complete_with_free_fallback

			response, metrics = complete_with_free_fallback(
				self.model,
				messages,
				self.api_key,
				tools=tools,
				tool_choice="auto",
				enable_free_fallback=True,
				configs_dir=self.configs_dir,
				catalog=self.catalog,
				on_fallback=self._on_fallback_candidate,
				rate_limit_retries=self.rate_limit_retries,
				sleep_fn=self.sleep_fn,
			)
			used = str(metrics.get("config_used") or metrics.get("model_used") or "").strip()
			if used:
				self.model = used
			return response

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
