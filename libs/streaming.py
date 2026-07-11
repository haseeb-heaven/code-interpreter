"""
Real-time token streaming helpers for LiteLLM completion responses.

Buffers the full assistant text for downstream code extraction while printing
tokens live to the terminal.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StreamingPrinter:
	"""
	Consume a LiteLLM / OpenAI-style streaming response.

	Prints each content token as it arrives and accumulates tool_call fragments.
	"""

	def __init__(self, show_stream: bool = True, color: str = "", file=None):
		self.show_stream = show_stream
		self.color = color or ""
		self.reset = "\033[0m" if color else ""
		self.file = file or sys.stdout

	def print_stream(self, stream_response) -> tuple[str, Optional[list]]:
		"""
		Consume a streaming response.

		Returns:
			(full_text, tool_calls_or_none)
		"""
		full_text = ""
		tool_calls_buffer: list[dict] = []

		try:
			for chunk in stream_response:
				delta, finish_reason = self._extract_delta(chunk)
				if delta is None:
					continue

				content = self._get_attr(delta, "content")
				if content:
					full_text += content
					if self.show_stream:
						print(f"{self.color}{content}{self.reset}", end="", flush=True, file=self.file)

				tool_calls = self._get_attr(delta, "tool_calls")
				if tool_calls:
					self._accumulate_tool_calls(tool_calls_buffer, tool_calls)

				if finish_reason in ("stop", "tool_calls"):
					break

		except KeyboardInterrupt:
			print("\n[Interrupted]", flush=True, file=self.file)
		finally:
			if self.show_stream:
				print(file=self.file)

		return full_text, tool_calls_buffer or None

	@staticmethod
	def _extract_delta(chunk) -> tuple[Any, Any]:
		"""Return (delta, finish_reason) from object or dict chunks."""
		try:
			if isinstance(chunk, dict):
				choices = chunk.get("choices") or []
				if not choices:
					return None, None
				choice = choices[0]
				if isinstance(choice, dict):
					return choice.get("delta"), choice.get("finish_reason")
				return getattr(choice, "delta", None), getattr(choice, "finish_reason", None)

			choices = getattr(chunk, "choices", None) or []
			if not choices:
				return None, None
			choice = choices[0]
			return getattr(choice, "delta", None), getattr(choice, "finish_reason", None)
		except Exception:
			return None, None

	@staticmethod
	def _get_attr(obj, name: str):
		if obj is None:
			return None
		if isinstance(obj, dict):
			return obj.get(name)
		return getattr(obj, name, None)

	def _accumulate_tool_calls(self, buffer: list[dict], tool_calls) -> None:
		for tc_chunk in tool_calls:
			idx = self._get_attr(tc_chunk, "index")
			if idx is None:
				idx = 0
			idx = int(idx)
			while len(buffer) <= idx:
				buffer.append(
					{
						"id": "",
						"type": "function",
						"function": {"name": "", "arguments": ""},
					}
				)
			tc_id = self._get_attr(tc_chunk, "id")
			if tc_id:
				buffer[idx]["id"] = tc_id

			fn = self._get_attr(tc_chunk, "function")
			if fn is None:
				continue
			name = self._get_attr(fn, "name")
			if name:
				buffer[idx]["function"]["name"] += str(name)
			arguments = self._get_attr(fn, "arguments")
			if arguments:
				buffer[idx]["function"]["arguments"] += str(arguments)


def looks_like_completion_response(response: Any) -> bool:
	"""True when ``response`` is a finished chat completion (not a stream)."""
	if response is None:
		return False
	if isinstance(response, dict):
		choices = response.get("choices") or []
		if not choices:
			return False
		choice = choices[0]
		msg = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
		return msg is not None
	choices = getattr(response, "choices", None)
	if not choices:
		return False
	return getattr(choices[0], "message", None) is not None


def stream_llm_call(
	completion_fn,
	model: str,
	messages: list,
	tools: list = None,
	show_stream: bool = True,
	**extra_kwargs,
) -> tuple[str, Any]:
	"""
	Make a streaming LLM call and return ``(full_text, tool_calls)``.

	Falls back to non-streaming when the provider/mock does not support streams.
	``completion_fn`` should match ``litellm.completion(model, **kwargs)``.
	"""
	printer = StreamingPrinter(show_stream=show_stream)
	kwargs = {"messages": messages, "stream": True, **extra_kwargs}
	if tools:
		kwargs["tools"] = tools
		kwargs["tool_choice"] = "auto"

	try:
		response = completion_fn(model, **kwargs)
	except TypeError:
		response = completion_fn(model=model, **kwargs)

	if looks_like_completion_response(response):
		msg = response.choices[0].message if not isinstance(response, dict) else response["choices"][0]["message"]
		if isinstance(msg, dict):
			text = msg.get("content") or ""
			tool_calls = msg.get("tool_calls")
		else:
			text = getattr(msg, "content", None) or ""
			tool_calls = getattr(msg, "tool_calls", None)
		if show_stream and text:
			print(text)
		return text, tool_calls

	try:
		return printer.print_stream(response)
	except Exception as exc:
		logger.warning("Streaming failed for %s, falling back: %s", model, exc)
		kwargs = dict(kwargs)
		kwargs["stream"] = False
		try:
			response = completion_fn(model, **kwargs)
		except TypeError:
			response = completion_fn(model=model, **kwargs)
		if looks_like_completion_response(response):
			if isinstance(response, dict):
				msg = response["choices"][0]["message"]
				text = msg.get("content") or ""
				tool_calls = msg.get("tool_calls")
			else:
				msg = response.choices[0].message
				text = getattr(msg, "content", None) or ""
				tool_calls = getattr(msg, "tool_calls", None)
			if show_stream and text:
				print(text)
			return text, tool_calls
		raise
