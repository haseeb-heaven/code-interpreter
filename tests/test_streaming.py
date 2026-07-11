"""Unit tests for StreamingPrinter and stream helpers (#216)."""

from __future__ import annotations

import io
import unittest
from types import SimpleNamespace

from libs.streaming import StreamingPrinter, looks_like_completion_response, stream_llm_call


def _chunk(content=None, finish_reason=None, tool_calls=None):
	delta = SimpleNamespace(content=content, tool_calls=tool_calls)
	choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
	return SimpleNamespace(choices=[choice])


class TestStreamingPrinter(unittest.TestCase):
	def test_print_stream_buffers_and_prints_tokens(self):
		buf = io.StringIO()
		printer = StreamingPrinter(show_stream=True, file=buf)
		chunks = [
			_chunk("Hello"),
			_chunk(" "),
			_chunk("world", finish_reason="stop"),
		]
		text, tool_calls = printer.print_stream(chunks)
		self.assertEqual(text, "Hello world")
		self.assertIsNone(tool_calls)
		self.assertIn("Hello", buf.getvalue())
		self.assertIn("world", buf.getvalue())

	def test_print_stream_accumulates_tool_calls(self):
		printer = StreamingPrinter(show_stream=False)
		tc1 = SimpleNamespace(
			index=0,
			id="call_1",
			function=SimpleNamespace(name="read_file", arguments=""),
		)
		tc2 = SimpleNamespace(
			index=0,
			id=None,
			function=SimpleNamespace(name=None, arguments='{"path":'),
		)
		tc3 = SimpleNamespace(
			index=0,
			id=None,
			function=SimpleNamespace(name=None, arguments='"a.txt"}'),
		)
		chunks = [
			_chunk(tool_calls=[tc1]),
			_chunk(tool_calls=[tc2]),
			_chunk(tool_calls=[tc3], finish_reason="tool_calls"),
		]
		text, tool_calls = printer.print_stream(chunks)
		self.assertEqual(text, "")
		self.assertEqual(len(tool_calls), 1)
		self.assertEqual(tool_calls[0]["function"]["name"], "read_file")
		self.assertEqual(tool_calls[0]["function"]["arguments"], '{"path":"a.txt"}')

	def test_looks_like_completion_response(self):
		completion = SimpleNamespace(
			choices=[SimpleNamespace(message=SimpleNamespace(content="hi", tool_calls=None))]
		)
		self.assertTrue(looks_like_completion_response(completion))
		self.assertFalse(looks_like_completion_response([_chunk("x")]))

	def test_stream_llm_call_fallback_on_completion_object(self):
		def completion_fn(model, **kwargs):
			self.assertTrue(kwargs.get("stream"))
			return SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content="fallback", tool_calls=None))]
			)

		buf_out = io.StringIO()
		# Temporarily redirect via printer path — stream_llm_call prints to stdout
		import contextlib
		with contextlib.redirect_stdout(buf_out):
			text, tool_calls = stream_llm_call(completion_fn, "gpt-4o", [{"role": "user", "content": "hi"}])
		self.assertEqual(text, "fallback")
		self.assertIsNone(tool_calls)


class TestBuildCompletionStreamFlag(unittest.TestCase):
	def test_build_completion_kwargs_stream(self):
		from libs.llm_dispatcher import build_completion_kwargs

		kwargs = build_completion_kwargs(
			model="gpt-4o-mini",
			messages=[{"role": "user", "content": "x"}],
			temperature=0.1,
			max_tokens=64,
			config_provider="",
			api_base="None",
			stream=True,
		)
		self.assertTrue(kwargs.get("stream"))


if __name__ == "__main__":
	unittest.main()
