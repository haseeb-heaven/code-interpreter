"""Streaming integration — chunk assembly + tool_call buffering (#226)."""

from __future__ import annotations

import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from libs.streaming import StreamingPrinter, stream_llm_call


def _chunk(content=None, tool_calls=None, finish_reason=None):
	delta = SimpleNamespace(content=content, tool_calls=tool_calls)
	choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
	return SimpleNamespace(choices=[choice])


class TestStreamingIntegration(unittest.TestCase):
	def test_streaming_output_assembles_correctly(self):
		chunks = [
			_chunk("Hello"),
			_chunk(", "),
			_chunk("world"),
			_chunk("!", finish_reason="stop"),
		]
		buf = io.StringIO()
		printer = StreamingPrinter(show_stream=True, file=buf)
		full, tools = printer.print_stream(iter(chunks))
		self.assertEqual(full, "Hello, world!")
		self.assertIsNone(tools)
		self.assertIn("Hello", buf.getvalue())

	def test_streaming_respects_tool_call_chunks(self):
		tc0 = SimpleNamespace(
			index=0,
			id="call_1",
			function=SimpleNamespace(name="read_file", arguments='{"p'),
		)
		tc1 = SimpleNamespace(
			index=0,
			id=None,
			function=SimpleNamespace(name=None, arguments='ath":'),
		)
		tc2 = SimpleNamespace(
			index=0,
			id=None,
			function=SimpleNamespace(name=None, arguments='"foo"}'),
		)
		chunks = [
			_chunk(tool_calls=[tc0]),
			_chunk(tool_calls=[tc1]),
			_chunk(tool_calls=[tc2], finish_reason="tool_calls"),
		]
		printer = StreamingPrinter(show_stream=False)
		full, tools = printer.print_stream(iter(chunks))
		self.assertEqual(full, "")
		self.assertIsNotNone(tools)
		self.assertEqual(len(tools), 1)
		self.assertEqual(tools[0]["function"]["name"], "read_file")
		self.assertIn("foo", tools[0]["function"]["arguments"])

	def test_stream_llm_call_wrapper(self):
		chunks = [_chunk("ab"), _chunk("c", finish_reason="stop")]

		def completion_fn(model, **kwargs):
			self.assertTrue(kwargs.get("stream"))
			return iter(chunks)

		text, tools = stream_llm_call(
			completion_fn,
			model="gpt-4o",
			messages=[{"role": "user", "content": "hi"}],
			show_stream=False,
		)
		self.assertEqual(text, "abc")
		self.assertIsNone(tools)


if __name__ == "__main__":
	unittest.main()
