"""Integration: CLI flag wiring through build_parser / prepare_args / main routing."""

from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch


class TestGeminiStyleFlagWiring(unittest.TestCase):
	def test_gemini_style_enables_agentic_free_cli_stream(self):
		from interpreter import build_parser, prepare_args

		args = build_parser().parse_args(["--gemini-style", "-m", "openrouter-free"])
		args = prepare_args(args, ["interpreter.py", "--gemini-style", "-m", "openrouter-free"])

		self.assertTrue(args.agentic)
		self.assertTrue(args.free)
		self.assertTrue(args.cli)
		self.assertFalse(args.tui)
		self.assertTrue(args.stream)
		self.assertEqual(args.model, "openrouter-free")


class TestStructuredOutputFlagWiring(unittest.TestCase):
	def test_json_output_forces_cli_and_disables_stream(self):
		from interpreter import build_parser, prepare_args

		args = build_parser().parse_args(
			[
				"--agent",
				"--yes",
				"--output-format",
				"json",
				"--cli",
				"-m",
				"gpt-4o",
				"--mode",
				"code",
				"-f",
				"task.txt",
			]
		)
		args = prepare_args(args, ["interpreter.py", "--agent", "--yes", "--output-format", "json"])

		self.assertTrue(args.agent)
		self.assertTrue(args.yes)
		self.assertEqual(args.output_format, "json")
		self.assertTrue(args.cli)
		self.assertFalse(args.tui)
		self.assertFalse(args.stream)


class TestSessionAndSandboxFlagWiring(unittest.TestCase):
	def test_session_forces_classic_cli(self):
		from interpreter import build_parser, prepare_args

		args = build_parser().parse_args(
			["--session", "demo-proj", "--cli", "-m", "gpt-4o", "--mode", "code"]
		)
		args = prepare_args(args, ["interpreter.py", "--session", "demo-proj"])

		self.assertEqual(args.session, "demo-proj")
		self.assertTrue(args.cli)
		self.assertFalse(args.tui)

	def test_no_sandbox_maps_to_unsafe_and_safety_off(self):
		from interpreter import build_parser, prepare_args

		argv = ["interpreter.py", "--no-sandbox", "--cli", "-m", "gpt-4o", "--mode", "code"]
		args = build_parser().parse_args(argv[1:])
		args = prepare_args(args, argv)

		self.assertEqual(args.sandbox, "off")
		self.assertTrue(args.unsafe)
		self.assertEqual(args.sandbox_backend, "none")
		self.assertEqual(args.safety, "off")

	def test_search_and_yolo_flags_parse(self):
		from interpreter import build_parser, prepare_args

		argv = [
			"interpreter.py",
			"--search",
			"--search-provider",
			"duckduckgo",
			"--yolo",
			"--yes",
			"--cli",
			"-m",
			"gpt-4o",
			"--mode",
			"code",
		]
		args = build_parser().parse_args(argv[1:])
		args = prepare_args(args, argv)

		self.assertTrue(args.search)
		self.assertEqual(args.search_provider, "duckduckgo")
		self.assertTrue(args.yolo)
		self.assertTrue(args.cli)
		self.assertFalse(args.tui)


class TestMainRoutingIntegration(unittest.TestCase):
	def test_agentic_flag_routes_to_agentic_main(self):
		from interpreter import main

		with patch("interpreter.Interpreter") as mock_cls, \
		     patch("interpreter.prepare_args", side_effect=lambda a, _argv: a), \
		     patch("interpreter.maybe_show_first_run_welcome"), \
		     patch("interpreter._handle_session_mgmt_flags", return_value=False):
			inst = mock_cls.return_value
			main(
				[
					"interpreter.py",
					"--agentic",
					"--cli",
					"-m",
					"gpt-4o",
					"--mode",
					"code",
					"-f",
					"prompt.txt",
				]
			)
			inst.interpreter_agentic_main.assert_called_once()
			inst.interpreter_main.assert_not_called()
			inst.interpreter_auto_main.assert_not_called()

	def test_yolo_routes_to_auto_main(self):
		from interpreter import main

		with patch("interpreter.Interpreter") as mock_cls, \
		     patch("interpreter.prepare_args", side_effect=lambda a, _argv: a), \
		     patch("interpreter.maybe_show_first_run_welcome"), \
		     patch("interpreter._handle_session_mgmt_flags", return_value=False):
			inst = mock_cls.return_value
			main(
				[
					"interpreter.py",
					"--yolo",
					"--yes",
					"--cli",
					"-m",
					"gpt-4o",
					"--mode",
					"code",
				]
			)
			inst.interpreter_auto_main.assert_called_once()
			inst.interpreter_agentic_main.assert_not_called()

	def test_list_free_exits_without_interpreter_boot(self):
		from interpreter import main

		with patch("interpreter.Interpreter") as mock_cls, \
		     patch("libs.free_llms.FreeLLMCatalog.load") as mock_load, \
		     patch("sys.stdout", new_callable=io.StringIO) as buf:
			mock_load.return_value.format_table.return_value = "FREE TABLE"
			main(["interpreter.py", "--list-free"])
			self.assertIn("FREE TABLE", buf.getvalue())
			mock_cls.assert_not_called()


class TestCiAutoYesWiring(unittest.TestCase):
	def test_interpreter_yes_env_enables_yes(self):
		from interpreter import build_parser, prepare_args

		with patch.dict(os.environ, {"INTERPRETER_YES": "1", "CI": ""}, clear=False):
			args = build_parser().parse_args(["--cli", "-m", "gpt-4o", "--mode", "code"])
			args = prepare_args(args, ["interpreter.py", "--cli"])
			self.assertTrue(args.yes)


class TestFilePromptDefaultConst(unittest.TestCase):
	def test_bare_file_flag_defaults_to_prompt_txt(self):
		from interpreter import build_parser

		args = build_parser().parse_args(["-f", "--cli", "-m", "gpt-4o", "--mode", "code"])
		self.assertEqual(args.file, "prompt.txt")


if __name__ == "__main__":
	unittest.main()
