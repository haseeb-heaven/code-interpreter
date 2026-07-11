"""Local-model smoke: OpenAI-compatible mock on :11434 + interpreter CLI path."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


class _Handler(BaseHTTPRequestHandler):
	def log_message(self, format, *args):  # noqa: A003
		return

	def do_POST(self):  # noqa: N802
		length = int(self.headers.get("Content-Length", "0"))
		_ = self.rfile.read(length)
		body = {
			"id": "chatcmpl-smoke",
			"object": "chat.completion",
			"choices": [{
				"index": 0,
				"message": {
					"role": "assistant",
					"content": "```python\nprint('smoke-ok')\n```",
				},
				"finish_reason": "stop",
			}],
		}
		payload = json.dumps(body).encode()
		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(payload)))
		self.end_headers()
		self.wfile.write(payload)


def _port_free(port: int) -> bool:
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.settimeout(0.2)
		return sock.connect_ex(("127.0.0.1", port)) != 0


class TestLocalModelSmoke(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.port = 11434
		cls._owned_server = False
		if _port_free(cls.port):
			cls.server = HTTPServer(("127.0.0.1", cls.port), _Handler)
			cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
			cls.thread.start()
			cls._owned_server = True
			time.sleep(0.2)

	@classmethod
	def tearDownClass(cls):
		if getattr(cls, "_owned_server", False):
			cls.server.shutdown()
			cls.server.server_close()

	def test_local_model_generate_content_via_litellm_path(self):
		from argparse import Namespace
		from libs.interpreter_lib import Interpreter

		args = Namespace(
			model="local-model", mode="code", lang="python", save_code=False, exec=False,
			display_code=False, history=False, unsafe=False, sandbox=True, file=None,
			tui=False, cli=True, agent=False, agentic=False,
		)
		env = {
			"OPENAI_API_KEY": "sk-local-smoke",
			"HUGGINGFACE_API_KEY": "hf_local_smoke_placeholder_xx",
		}
		with patch.dict(os.environ, env, clear=False):
			interp = Interpreter(args)
			text = interp.generate_content(
				"print smoke-ok",
				chat_history=[],
				config_values=interp.config_values,
			)
		self.assertIn("```", text)
		self.assertTrue("python" in text.lower() or "print" in text.lower(), text[:200])

	def test_cli_help_lists_local_model_label(self):
		result = subprocess.run(
			[sys.executable, str(ROOT / "interpreter.py"), "--help"],
			cwd=ROOT,
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
	unittest.main()
