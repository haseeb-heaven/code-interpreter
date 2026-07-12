"""
MCP stdio client — JSON-RPC 2.0 over a subprocess stdin/stdout.

Connects to any MCP server (e.g. ``npx -y @modelcontextprotocol/server-filesystem .``),
discovers tools, and proxies calls for the autonomous agent loop.

Uses a synchronous ``subprocess.Popen`` transport so ToolRegistry dispatch from the
sync auto-loop does not depend on a long-lived asyncio event loop.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class MCPClient:
	"""
	Connects to an MCP server via stdio transport (JSON-RPC 2.0).

	Usage::

	    client = MCPClient(["npx", "-y", "@modelcontextprotocol/server-filesystem", "."])
	    client.start_sync()
	    tools = client.list_tools_sync()
	    result = client.call_tool_sync("read_file", {"path": "README.md"})
	    client.stop_sync()
	"""

	def __init__(self, server_command: list[str]):
		if not server_command:
			raise ValueError("server_command must be a non-empty list")
		self.cmd = list(server_command)
		self.proc: Optional[subprocess.Popen] = None
		self._req_id = 0
		self._io_lock = threading.Lock()

	# ── Async-compatible API (issue sketch) ─────────────────────────────

	async def start(self) -> None:
		"""Start the MCP server subprocess and complete the initialize handshake."""
		self.start_sync()

	async def list_tools(self) -> list[dict]:
		"""Return tools from the MCP server as OpenAI-compatible schemas."""
		return self.list_tools_sync()

	async def call_tool(self, name: str, arguments: dict) -> str:
		"""Call a tool on the MCP server and return the text result."""
		return self.call_tool_sync(name, arguments)

	async def stop(self) -> None:
		self.stop_sync()

	# ── Sync API (preferred for CLI / ToolRegistry) ─────────────────────

	def start_sync(self) -> None:
		logger.info("[MCP] Starting server: %s", " ".join(self.cmd))
		self.proc = subprocess.Popen(
			self.cmd,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			bufsize=1,
		)
		init_id = self._next_id()
		self._send(
			{
				"jsonrpc": "2.0",
				"id": init_id,
				"method": "initialize",
				"params": {
					"protocolVersion": "2024-11-05",
					"capabilities": {},
					"clientInfo": {"name": "code-interpreter", "version": "3.4.0"},
				},
			}
		)
		resp = self._recv()
		if "error" in resp:
			raise RuntimeError(f"MCP initialize failed: {resp['error']}")
		self._send(
			{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
		)
		logger.info("[MCP] Connected to server: %s", " ".join(self.cmd))

	def list_tools_sync(self) -> list[dict]:
		req_id = self._next_id()
		self._send(
			{"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": {}}
		)
		resp = self._recv()
		if "error" in resp:
			raise RuntimeError(f"MCP tools/list failed: {resp['error']}")
		mcp_tools = resp.get("result", {}).get("tools", []) or []
		return self._convert_to_openai_schema(mcp_tools)

	def call_tool_sync(self, name: str, arguments: dict) -> str:
		req_id = self._next_id()
		self._send(
			{
				"jsonrpc": "2.0",
				"id": req_id,
				"method": "tools/call",
				"params": {"name": name, "arguments": arguments or {}},
			}
		)
		resp = self._recv()
		if "error" in resp:
			raise RuntimeError(f"MCP tools/call failed: {resp['error']}")
		content = resp.get("result", {}).get("content", []) or []
		texts = [c.get("text", "") for c in content if c.get("type") == "text"]
		return "\n".join(texts)

	def stop_sync(self) -> None:
		if self.proc is None:
			return
		try:
			self.proc.terminate()
			self.proc.wait(timeout=5)
		except Exception:
			try:
				self.proc.kill()
			except Exception:
				pass
		finally:
			self.proc = None
			logger.info("[MCP] Server stopped")

	def _next_id(self) -> int:
		self._req_id += 1
		return self._req_id

	def _send(self, payload: dict) -> None:
		if self.proc is None or self.proc.stdin is None:
			raise RuntimeError("MCP server is not started")
		line = json.dumps(payload) + "\n"
		with self._io_lock:
			self.proc.stdin.write(line)
			self.proc.stdin.flush()

	def _recv(self) -> dict:
		if self.proc is None or self.proc.stdout is None:
			raise RuntimeError("MCP server is not started")
		# Skip blank lines / non-JSON noise (some servers log to stdout).
		while True:
			line = self.proc.stdout.readline()
			if line == "" and self.proc.poll() is not None:
				stderr = ""
				try:
					stderr = self.proc.stderr.read() if self.proc.stderr else ""
				except Exception:
					pass
				raise RuntimeError(
					f"MCP server closed stdout unexpectedly. stderr={stderr[:500]!r}"
				)
			text = (line or "").strip()
			if not text:
				continue
			try:
				return json.loads(text)
			except json.JSONDecodeError:
				logger.debug("[MCP] Ignoring non-JSON stdout: %s", text[:200])
				continue

	@staticmethod
	def _convert_to_openai_schema(mcp_tools: list) -> list[dict]:
		"""Convert MCP tool definitions to OpenAI function-calling schema format."""
		result = []
		for tool in mcp_tools:
			name = tool.get("name")
			if not name:
				continue
			result.append(
				{
					"type": "function",
					"function": {
						"name": name,
						"description": tool.get("description", "") or "",
						"parameters": tool.get("inputSchema")
						or {"type": "object", "properties": {}},
					},
				}
			)
		return result
