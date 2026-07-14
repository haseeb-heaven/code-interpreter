#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A protocol-aware OpenAI-compatible stub LLM server for real end-to-end CLI runs.

Unlike a single fixed-response stub, this one inspects the *system prompt* of
each request to recognize which internal agent is calling (ReAct step /
Coder / Reviewer / Debugger / IntentRouter / Planner / multi-agent Reviewer /
AutoLoop tool-use) and replies with a protocol-correct message so that the
real, unmodified pipeline (litellm dispatch -> HTTP -> response parse ->
ReAct/AutoLoop/pipeline control flow -> sandbox execution) can run all the
way to completion — driving the actual `interpreter.py` binary the same way
a human would, just without a real paid model behind it.

No network calls happen outside localhost. This does not replace live
smoke tests against real providers (``tests/smoke/test_live_model_smoke.py``,
``SMOKE_LIVE=1``); it exists to exercise the CLI plumbing for every mode
when no provider API keys are configured.

Usage as a script::

    python scripts/live_stub_llm_server.py --port 11434

Usage as a library (tests)::

    from scripts.live_stub_llm_server import StubLLMServer
    with StubLLMServer(port=11434):
        ...
"""

from __future__ import annotations

import json
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def _system_content(messages: list[dict]) -> str:
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content")
            return content if isinstance(content, str) else ""
    return ""


def _last_user_content(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            return content if isinstance(content, str) else ""
    return ""


def _chat_response(content: str, *, tool_calls: list[dict] | None = None) -> dict:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
        message["content"] = None
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "model": "local-model",
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _react_step_response(user_content: str) -> str:
    """Cycle a ReAct agent through code -> execute -> review -> finish."""
    if "Action: code" not in user_content:
        return (
            "Thought: I will write code to satisfy the task.\n"
            "Action: code\n"
            'Action Input: {"instruction": "Write minimal Python that satisfies the task"}\n'
        )
    if "Action: execute" not in user_content:
        return (
            "Thought: Now run the code I wrote.\n"
            "Action: execute\n"
            'Action Input: {"language": "python"}\n'
        )
    if "Action: review" not in user_content:
        return (
            "Thought: Check whether the execution satisfied the task.\n"
            "Action: review\n"
            "Action Input: {}\n"
        )
    return (
        "Thought: Review passed, the task is complete.\n"
        "Action: finish\n"
        'Action Input: {"summary": "Task completed by stub agent"}\n'
    )


def _autoloop_response(messages: list[dict]) -> tuple[str | None, list[dict] | None]:
    """AutoLoop (--yolo/native tool_calls): call one tool, then finish."""
    already_ran_tool = any(msg.get("role") == "tool" for msg in messages)
    if already_ran_tool:
        return "Done — tool call completed.", None

    task = _last_user_content(messages)

    if re.search(r"search the web|web search|\bsearch\b", task, re.IGNORECASE):
        query_match = re.search(r"search(?: the web)? for ['\"]?([^'\".]+)", task, re.IGNORECASE)
        query = query_match.group(1).strip() if query_match else task[:60]
        tool_calls = [{
            "id": "call_stub_1",
            "type": "function",
            "function": {
                "name": "web_search",
                "arguments": json.dumps({"query": query, "max_results": 3}),
            },
        }]
        return None, tool_calls

    path_match = re.search(r"file(?:\s+named)?\s+([^\s,]+)", task, re.IGNORECASE)
    content_match = re.search(r"content(?:ing)?\s+([^\s,.]+)", task, re.IGNORECASE)
    path = path_match.group(1) if path_match else "yolo_stub_output.txt"
    content = content_match.group(1) if content_match else "YOLO_STUB_OK"

    tool_calls = [{
        "id": "call_stub_1",
        "type": "function",
        "function": {
            "name": "write_file",
            "arguments": json.dumps({"path": path, "content": content}),
        },
    }]
    return None, tool_calls


def _route(body: dict) -> dict:
    messages = body.get("messages") or []
    tools = body.get("tools")
    system = _system_content(messages)
    user = _last_user_content(messages)

    if tools:
        content, tool_calls = _autoloop_response(messages)
        return _chat_response(content or "", tool_calls=tool_calls)

    if "ReAct code agent" in system:
        return _chat_response(_react_step_response(user))

    if "You are the Coder agent" in system:
        return _chat_response("```python\nprint('stub agent: task executed')\n```")

    if "You are the Reviewer agent" in system:
        return _chat_response('{"passed": true, "reason": "execution succeeded"}')

    if "You are the Debugger agent" in system:
        return _chat_response("Root cause: stub. Fix: retry with corrected code.")

    if "intent classifier" in system:
        return _chat_response('{"intent": "code", "confidence": 0.95}')

    if "task planner" in system:
        return _chat_response(
            '{"steps": ["Write code", "Execute", "Verify"], "mode": "code", '
            '"language": "python", "complexity": "simple"}'
        )

    if "code output reviewer" in system:
        return _chat_response('{"approved": true, "reason": "matches task"}')

    # Default: classic single-shot fenced-code response (--cli, multi-agent Executor).
    return _chat_response("```python\nprint('stub agent: task executed')\n```")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A002 - silence default access log
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {}
        payload = json.dumps(_route(body)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class StubLLMServer:
    """Context-manager wrapper: start/stop the stub on a background thread.

    Refuses to bind (and marks itself as not-owned) if the port is already
    occupied by something else — callers should treat that as "reuse the
    existing server" rather than an error, mirroring the existing
    ``tests/smoke/test_local_model_smoke.py`` pattern.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 11434):
        self.host = host
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.owned = False

    def __enter__(self) -> "StubLLMServer":
        if _port_free(self.port, self.host):
            self.server = HTTPServer((self.host, self.port), _Handler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.owned = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.owned and self.server is not None:
            self.server.shutdown()
            self.server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11434)
    args = parser.parse_args()

    httpd = HTTPServer((args.host, args.port), _Handler)
    print(f"Stub LLM server listening on http://{args.host}:{args.port}/v1")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
