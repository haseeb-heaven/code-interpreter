"""
Web search tool for the autonomous agent loop (#217).

Providers:
- duckduckgo (default, free, no API key)
- tavily / serper (optional, require API keys)
"""

from __future__ import annotations

import logging
from typing import Optional

from libs.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
	"""
	Real-time web search as an LLM-callable tool.

	Also usable standalone via ``search()`` for the ``/search`` REPL command.
	"""

	name = "web_search"
	description = (
		"Search the web for real-time information. Use when you need current "
		"data, documentation, library versions, error solutions, or anything "
		"that may not be in your training data."
	)
	input_schema = {
		"type": "object",
		"properties": {
			"query": {
				"type": "string",
				"description": "The search query string.",
			},
			"max_results": {
				"type": "integer",
				"description": "Maximum number of results to return. Default 5.",
				"default": 5,
			},
		},
		"required": ["query"],
	}

	TOOL_SCHEMA = {
		"type": "function",
		"function": {
			"name": "web_search",
			"description": (
				"Search the web for real-time information. Use when you need current "
				"data, documentation, library versions, error solutions, or anything "
				"that may not be in your training data."
			),
			"parameters": {
				"type": "object",
				"properties": {
					"query": {
						"type": "string",
						"description": "The search query string.",
					},
					"max_results": {
						"type": "integer",
						"description": "Maximum number of results to return. Default 5.",
						"default": 5,
					},
				},
				"required": ["query"],
			},
		},
	}

	def __init__(self, provider: str = "duckduckgo", api_key: Optional[str] = None):
		"""
		Args:
			provider: 'duckduckgo' (default, free) | 'tavily' | 'serper'
			api_key: Required only for 'tavily' or 'serper' providers.
		"""
		self.provider = (provider or "duckduckgo").strip().lower()
		self.api_key = api_key
		self._validate_provider()

	def _validate_provider(self) -> None:
		if self.provider not in ("duckduckgo", "tavily", "serper"):
			raise ValueError(
				f"Unknown search provider: {self.provider!r}. "
				"Use duckduckgo, tavily, or serper."
			)
		if self.provider in ("tavily", "serper") and not self.api_key:
			raise ValueError(f"API key required for provider '{self.provider}'.")

	def run(self, input_data) -> ToolResult:
		"""BaseTool entrypoint used by ToolRegistry.dispatch/call."""
		input_data = input_data or {}
		query = input_data.get("query")
		if not query or not str(query).strip():
			return ToolResult(success=False, error="query is required")
		max_results = int(input_data.get("max_results", 5) or 5)
		try:
			text = self.search(str(query).strip(), max_results=max_results)
			# Soft-failure messages from missing deps still return success=False
			if text.startswith("duckduckgo-search not installed") or text.startswith(
				"requests not installed"
			):
				return ToolResult(success=False, output=text, error=text)
			if text.startswith("Search failed:") or text.startswith("Unknown search provider"):
				return ToolResult(success=False, output=text, error=text)
			return ToolResult(
				success=True,
				output=text,
				metadata={"provider": self.provider, "query": str(query), "max_results": max_results},
			)
		except Exception as exc:
			logger.exception("[WebSearch] run failed")
			return ToolResult(success=False, error=str(exc))

	def search(self, query: str, max_results: int = 5) -> str:
		"""Execute a web search and return formatted results as a string."""
		logger.info("[WebSearch] Query: %r via %s", query, self.provider)
		try:
			if self.provider == "duckduckgo":
				return self._search_duckduckgo(query, max_results)
			if self.provider == "tavily":
				return self._search_tavily(query, max_results)
			if self.provider == "serper":
				return self._search_serper(query, max_results)
			return f"Unknown search provider: {self.provider}"
		except Exception as exc:
			logger.error("[WebSearch] Failed: %s", exc)
			return f"Search failed: {exc}"

	def _search_duckduckgo(self, query: str, max_results: int) -> str:
		ddgs_cls = self._import_ddgs()
		if ddgs_cls is None:
			return (
				"duckduckgo-search not installed. "
				"Run: pip install duckduckgo-search"
			)

		results = []
		# Newer packages may or may not be context managers.
		client = ddgs_cls()
		try:
			if hasattr(client, "__enter__"):
				with client as ddgs:
					hits = list(ddgs.text(query, max_results=max_results) or [])
			else:
				hits = list(client.text(query, max_results=max_results) or [])
		finally:
			close = getattr(client, "close", None)
			if callable(close) and not hasattr(client, "__enter__"):
				try:
					close()
				except Exception:
					pass

		for item in hits:
			title = item.get("title") or "Untitled"
			url = item.get("href") or item.get("link") or item.get("url") or ""
			body = item.get("body") or item.get("snippet") or item.get("content") or ""
			results.append(f"### {title}\nURL: {url}\n{body}\n")

		if not results:
			return f"No results found for: {query}"
		return f"Search results for '{query}':\n\n" + "\n---\n".join(results)

	@staticmethod
	def _import_ddgs():
		"""Import DDGS from duckduckgo_search or the newer ddgs package."""
		try:
			from duckduckgo_search import DDGS  # type: ignore

			return DDGS
		except ImportError:
			pass
		try:
			from ddgs import DDGS  # type: ignore

			return DDGS
		except ImportError:
			return None

	def _search_tavily(self, query: str, max_results: int) -> str:
		try:
			import requests
		except ImportError:
			return "requests not installed."

		resp = requests.post(
			"https://api.tavily.com/search",
			json={
				"api_key": self.api_key,
				"query": query,
				"max_results": max_results,
			},
			timeout=15,
		)
		resp.raise_for_status()
		data = resp.json()
		results = []
		for item in data.get("results", []) or []:
			results.append(
				f"### {item.get('title', 'Untitled')}\n"
				f"URL: {item.get('url', '')}\n"
				f"{item.get('content', '')}\n"
			)
		if not results:
			return f"No results found for: {query}"
		return f"Search results for '{query}':\n\n" + "\n---\n".join(results)

	def _search_serper(self, query: str, max_results: int) -> str:
		try:
			import requests
		except ImportError:
			return "requests not installed."

		resp = requests.post(
			"https://google.serper.dev/search",
			headers={
				"X-API-KEY": self.api_key,
				"Content-Type": "application/json",
			},
			json={"q": query, "num": max_results},
			timeout=15,
		)
		resp.raise_for_status()
		data = resp.json()
		results = []
		for item in data.get("organic", []) or []:
			results.append(
				f"### {item.get('title', 'Untitled')}\n"
				f"URL: {item.get('link', '')}\n"
				f"{item.get('snippet', '')}\n"
			)
		if not results:
			return f"No results found for: {query}"
		return f"Search results for '{query}':\n\n" + "\n---\n".join(results)
