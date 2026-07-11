"""Unit tests for multimodal image_handler (#216)."""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from libs.vision.image_handler import (
	SUPPORTED_EXTENSIONS,
	build_multimodal_message,
	inject_images_into_messages,
	is_vision_model,
	load_image_as_content_block,
)


class TestImageHandler(unittest.TestCase):
	def test_url_passthrough(self):
		block = load_image_as_content_block("https://example.com/diagram.png")
		self.assertEqual(block["type"], "image_url")
		self.assertEqual(block["image_url"]["url"], "https://example.com/diagram.png")
		self.assertEqual(block["image_url"]["detail"], "auto")

	def test_local_file_base64(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			path = Path(tmpdir) / "sample.png"
			# Minimal PNG header bytes (not a real image; encoding still works)
			raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
			path.write_bytes(raw)
			block = load_image_as_content_block(str(path))
			url = block["image_url"]["url"]
			self.assertTrue(url.startswith("data:image/png;base64,"))
			encoded = url.split(",", 1)[1]
			self.assertEqual(base64.b64decode(encoded), raw)

	def test_missing_file_raises(self):
		with self.assertRaises(FileNotFoundError):
			load_image_as_content_block("definitely-missing-image-216.png")

	def test_unsupported_extension_raises(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			path = Path(tmpdir) / "notes.txt"
			path.write_text("nope", encoding="utf-8")
			with self.assertRaises(ValueError):
				load_image_as_content_block(str(path))

	def test_build_multimodal_message_order(self):
		msg = build_multimodal_message("what is this?", ["https://example.com/a.png"])
		self.assertEqual(msg["role"], "user")
		self.assertEqual(msg["content"][0]["type"], "image_url")
		self.assertEqual(msg["content"][-1], {"type": "text", "text": "what is this?"})

	def test_inject_images_replaces_last_user(self):
		messages = [
			{"role": "system", "content": "sys"},
			{"role": "user", "content": "old"},
		]
		out = inject_images_into_messages(messages, "new q", ["https://example.com/x.png"])
		self.assertEqual(out[0]["role"], "system")
		self.assertEqual(out[1]["role"], "user")
		self.assertIsInstance(out[1]["content"], list)
		self.assertEqual(out[1]["content"][-1]["text"], "new q")

	def test_is_vision_model(self):
		self.assertTrue(is_vision_model("gpt-4o"))
		self.assertTrue(is_vision_model("gemini-2.5-flash"))
		self.assertTrue(is_vision_model("claude-sonnet-4-6"))
		self.assertFalse(is_vision_model("groq-llama-3.1-8b"))
		self.assertIn(".png", SUPPORTED_EXTENSIONS)


class TestStreamImageCliFlags(unittest.TestCase):
	def test_parser_stream_and_image_flags(self):
		import interpreter as interpreter_mod

		parser = interpreter_mod.build_parser()
		args = parser.parse_args(["--no-stream", "--image", "a.png", "https://x/b.png", "--cli"])
		self.assertFalse(args.stream)
		self.assertEqual(args.image, ["a.png", "https://x/b.png"])

	def test_gemini_style_forces_stream(self):
		import interpreter as interpreter_mod

		parser = interpreter_mod.build_parser()
		args = parser.parse_args(["--gemini-style", "--no-stream", "-m", "local-model"])
		args = interpreter_mod.prepare_args(args, ["interpreter.py", "--gemini-style", "--no-stream"])
		self.assertTrue(args.stream)
		self.assertTrue(args.gemini_style)


if __name__ == "__main__":
	unittest.main()
