"""Extra WebSearchTool unit coverage with providers mocked."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from libs.tools.web_search_tool import WebSearchTool


class TestWebSearchToolExtra(unittest.TestCase):
	def test_missing_query(self):
		tool = WebSearchTool(provider="duckduckgo")
		result = tool.run({})
		self.assertFalse(result.success)
		self.assertIn("query", result.error)

	def test_tavily_requires_key(self):
		with self.assertRaises(ValueError):
			WebSearchTool(provider="tavily", api_key=None)

	def test_unknown_provider(self):
		with self.assertRaises(ValueError):
			WebSearchTool(provider="bing")

	@patch.object(WebSearchTool, "_import_ddgs", return_value=None)
	def test_duckduckgo_missing_dep(self, _imp):
		tool = WebSearchTool(provider="duckduckgo")
		result = tool.run({"query": "python"})
		self.assertFalse(result.success)
		self.assertIn("duckduckgo-search not installed", result.error)

	@patch.object(WebSearchTool, "_import_ddgs")
	def test_duckduckgo_formats_hits(self, import_mock):
		client = MagicMock()
		client.__enter__ = MagicMock(return_value=client)
		client.__exit__ = MagicMock(return_value=False)
		client.text.return_value = [
			{"title": "Py", "href": "https://python.org", "body": "Lang"},
		]
		import_mock.return_value = MagicMock(return_value=client)
		tool = WebSearchTool(provider="duckduckgo")
		result = tool.run({"query": "python", "max_results": 1})
		self.assertTrue(result.success, result.error)
		self.assertIn("python.org", result.output)

	@patch("requests.post")
	def test_tavily_search(self, post_mock):
		resp = MagicMock()
		resp.raise_for_status = MagicMock()
		resp.json.return_value = {
			"results": [{"title": "A", "url": "https://a.test", "content": "body"}],
		}
		post_mock.return_value = resp
		tool = WebSearchTool(provider="tavily", api_key="tvly-test")
		text = tool.search("q", max_results=1)
		self.assertIn("a.test", text)


if __name__ == "__main__":
	unittest.main()
