"""Unit tests for WebSearchTool (#217) with mocked providers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from libs.key_manager import resolve_search_provider
from libs.tools import ToolRegistry
from libs.tools.web_search_tool import WebSearchTool


class TestWebSearchTool(unittest.TestCase):
	def test_validate_requires_key_for_tavily(self):
		with self.assertRaises(ValueError):
			WebSearchTool(provider="tavily", api_key=None)

	def test_duckduckgo_formats_results(self):
		fake_hits = [
			{"title": "LiteLLM", "href": "https://example.com/litellm", "body": "docs"},
			{"title": "PyPI", "href": "https://pypi.org/project/litellm/", "body": "package"},
		]

		class FakeDDGS:
			def __enter__(self):
				return self

			def __exit__(self, *args):
				return False

			def text(self, query, max_results=5):
				self.query = query
				self.max_results = max_results
				return fake_hits

		with patch.object(WebSearchTool, "_import_ddgs", return_value=FakeDDGS):
			tool = WebSearchTool(provider="duckduckgo")
			text = tool.search("litellm version", max_results=2)

		self.assertIn("Search results for 'litellm version'", text)
		self.assertIn("LiteLLM", text)
		self.assertIn("https://example.com/litellm", text)
		self.assertIn("---", text)

	def test_duckduckgo_missing_package_message(self):
		with patch.object(WebSearchTool, "_import_ddgs", return_value=None):
			tool = WebSearchTool(provider="duckduckgo")
			text = tool.search("anything")
		self.assertIn("duckduckgo-search not installed", text)

	def test_tavily_mocked_http(self):
		mock_resp = MagicMock()
		mock_resp.raise_for_status.return_value = None
		mock_resp.json.return_value = {
			"results": [
				{"title": "Tavily Hit", "url": "https://tavily.example/a", "content": "snippet"}
			]
		}
		with patch("requests.post", return_value=mock_resp) as post:
			tool = WebSearchTool(provider="tavily", api_key="tvly-test")
			text = tool.search("hello", max_results=3)

		self.assertIn("Tavily Hit", text)
		self.assertIn("https://tavily.example/a", text)
		args, kwargs = post.call_args
		self.assertEqual(args[0], "https://api.tavily.com/search")
		self.assertEqual(kwargs["json"]["api_key"], "tvly-test")
		self.assertEqual(kwargs["timeout"], 15)

	def test_serper_mocked_http(self):
		mock_resp = MagicMock()
		mock_resp.raise_for_status.return_value = None
		mock_resp.json.return_value = {
			"organic": [
				{"title": "Serper Hit", "link": "https://serper.example/b", "snippet": "snip"}
			]
		}
		with patch("requests.post", return_value=mock_resp) as post:
			tool = WebSearchTool(provider="serper", api_key="serper-test")
			text = tool.search("world", max_results=1)

		self.assertIn("Serper Hit", text)
		self.assertIn("https://serper.example/b", text)
		headers = post.call_args.kwargs["headers"]
		self.assertEqual(headers["X-API-KEY"], "serper-test")

	def test_run_and_registry_enable(self):
		class FakeDDGS:
			def __enter__(self):
				return self

			def __exit__(self, *args):
				return False

			def text(self, query, max_results=5):
				return [{"title": "A", "href": "https://a.example", "body": "b"}]

		registry = ToolRegistry()
		result = registry.dispatch("web_search", {"query": "x"})
		self.assertFalse(result.success)
		self.assertIn("--search", result.error)

		with patch.object(WebSearchTool, "_import_ddgs", return_value=FakeDDGS):
			registry.enable_web_search(provider="duckduckgo")
			result = registry.dispatch("web_search", {"query": "x", "max_results": 1})

		self.assertTrue(result.success, result.error)
		self.assertIn("https://a.example", result.output)
		names = {s["function"]["name"] for s in registry.openai_schemas()}
		self.assertIn("web_search", names)


class TestResolveSearchProvider(unittest.TestCase):
	def test_cli_provider_wins(self):
		provider, key = resolve_search_provider(cli_provider="duckduckgo", cli_api_key=None)
		self.assertEqual(provider, "duckduckgo")
		self.assertIsNone(key)

	def test_env_tavily(self):
		with patch("libs.key_manager.os.getenv", side_effect=lambda n, d=None: {
			"TAVILY_API_KEY": "tvly-x",
			"SERPER_API_KEY": "s",
		}.get(n, d)):
			provider, key = resolve_search_provider()
		self.assertEqual(provider, "tavily")
		self.assertEqual(key, "tvly-x")

	def test_env_serper_when_no_tavily(self):
		with patch.dict("os.environ", {"TAVILY_API_KEY": "", "SERPER_API_KEY": "serper-x"}, clear=False):
			# Empty TAVILY should fall through — getenv returns ""
			# Force tavily absent
			with patch("libs.key_manager.os.getenv", side_effect=lambda n, d=None: {
				"TAVILY_API_KEY": None,
				"SERPER_API_KEY": "serper-x",
			}.get(n, d)):
				provider, key = resolve_search_provider()
		self.assertEqual(provider, "serper")
		self.assertEqual(key, "serper-x")


class TestSearchCliFlags(unittest.TestCase):
	def test_parser_search_flags(self):
		import interpreter as interpreter_mod

		parser = interpreter_mod.build_parser()
		args = parser.parse_args(
			["--search", "--search-provider", "tavily", "--search-api-key", "k", "--cli"]
		)
		self.assertTrue(args.search)
		self.assertEqual(args.search_provider, "tavily")
		self.assertEqual(args.search_api_key, "k")


if __name__ == "__main__":
	unittest.main()
