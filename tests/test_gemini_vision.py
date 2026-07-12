# -*- coding: utf-8 -*-
"""Unit tests for libs.gemini_vision.GeminiVision (mocked litellm)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestGeminiVision(unittest.TestCase):
	def test_init_with_api_key(self):
		with patch("libs.gemini_vision.Logger.initialize"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key="sk-test")
			self.assertEqual(gv.api_key, "sk-test")

	def test_init_missing_key_raises(self):
		with patch("libs.gemini_vision.Logger.initialize"), patch(
			"libs.gemini_vision.load_dotenv"
		), patch("libs.gemini_vision.os.getenv", return_value=None):
			from libs.gemini_vision import GeminiVision

			with self.assertRaises(ValueError):
				GeminiVision(api_key=None)

	def test_init_loads_env_key(self):
		with patch("libs.gemini_vision.Logger.initialize"), patch(
			"libs.gemini_vision.load_dotenv"
		), patch("libs.gemini_vision.os.getenv", return_value="env-key"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key=None)
			# api_key attribute stays None; env used only for validation
			self.assertIsNone(gv.api_key)

	def test_generate_text(self):
		with patch("libs.gemini_vision.Logger.initialize"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key="sk")
			fake = {"choices": [{"message": {"content": "a cat"}}]}
			with patch("libs.gemini_vision.litellm.completion", return_value=fake) as comp:
				out = gv.generate_text("what?", "https://img")
			self.assertEqual(out, "a cat")
			comp.assert_called_once()

	def test_gemini_vision_url(self):
		with patch("libs.gemini_vision.Logger.initialize"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key="sk")
			with patch.object(gv, "generate_text", return_value="ok") as gen:
				self.assertEqual(gv.gemini_vision_url("p", "http://x"), "ok")
				gen.assert_called_with("p", "http://x")

	def test_gemini_vision_url_error(self):
		with patch("libs.gemini_vision.Logger.initialize"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key="sk")
			with patch.object(gv, "generate_text", side_effect=RuntimeError("boom")):
				with self.assertRaises(RuntimeError):
					gv.gemini_vision_url("p", "http://x")

	def test_gemini_vision_path(self):
		with patch("libs.gemini_vision.Logger.initialize"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key="sk")
			with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
				path = fh.name
				fh.write(b"x")
			try:
				with patch.object(gv, "generate_text", return_value="ok") as gen:
					self.assertEqual(gv.gemini_vision_path("p", path), "ok")
					gen.assert_called()
			finally:
				Path(path).unlink(missing_ok=True)

	def test_gemini_vision_path_missing(self):
		with patch("libs.gemini_vision.Logger.initialize"):
			from libs.gemini_vision import GeminiVision

			gv = GeminiVision(api_key="sk")
			with self.assertRaises(ValueError):
				gv.gemini_vision_path("p", "/no/such/image.png")


class TestAgentGraphExport(unittest.TestCase):
	def test_agent_graph_reexports_controller(self):
		from libs.agent.react_controller import ReActController
		from libs.agent_graph import AgentGraph

		self.assertIs(AgentGraph, ReActController)


if __name__ == "__main__":
	unittest.main()
