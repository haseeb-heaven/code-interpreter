"""Unit tests for code generation modes (#212)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from libs.code_generator import CodeGenerator, resolve_codegen_task, run_codegen_cli


class TestCodeGeneratorSnippet(unittest.TestCase):
	def test_generate_snippet_writes_file_without_execution(self):
		llm_text = "```python\ndef binary_search(arr, x):\n    return -1\n```"

		def completion_fn(model, **kwargs):
			return SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content=llm_text))]
			)

		with tempfile.TemporaryDirectory() as tmpdir:
			out = Path(tmpdir) / "bs.py"
			gen = CodeGenerator(completion_fn=completion_fn, model="test-model")
			result = gen.generate_snippet(
				"write binary search",
				language="python",
				output_path=str(out),
			)
			self.assertEqual(result.mode, "generate")
			self.assertTrue(Path(result.path).is_file())
			content = Path(result.path).read_text(encoding="utf-8")
			self.assertIn("def binary_search", content)
			self.assertNotIn("```", content)


class TestCodeGeneratorProject(unittest.TestCase):
	def test_generate_project_creates_required_files(self):
		llm_text = (
			"```python:main.py\n"
			"import fastapi\n"
			"app = None\n"
			"```\n"
			"```README.md\n"
			"# API\n"
			"```\n"
		)

		def completion_fn(model, **kwargs):
			return SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content=llm_text))]
			)

		with tempfile.TemporaryDirectory() as tmpdir:
			out = Path(tmpdir) / "proj"
			gen = CodeGenerator(completion_fn=completion_fn, model="test-model")
			result = gen.generate_project(
				"create a REST API with FastAPI",
				output_dir=str(out),
				language="python",
			)
			self.assertEqual(result.mode, "project")
			self.assertTrue(Path(result.path).is_dir())
			names = {Path(p).name.lower() for p in result.files}
			self.assertIn("main.py", names)
			self.assertIn("readme.md", names)
			self.assertIn("requirements.txt", names)
			reqs = (out / "requirements.txt").read_text(encoding="utf-8")
			self.assertIn("fastapi", reqs)

	def test_ensure_basics_when_llm_returns_nothing_useful(self):
		def completion_fn(model, **kwargs):
			return SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content="Sorry, no code."))]
			)

		with tempfile.TemporaryDirectory() as tmpdir:
			out = Path(tmpdir) / "emptyish"
			gen = CodeGenerator(completion_fn=completion_fn, model="test-model")
			result = gen.generate_project("hello world app", output_dir=str(out))
			self.assertTrue((out / "main.py").is_file())
			self.assertTrue((out / "README.md").is_file())
			self.assertTrue((out / "requirements.txt").is_file())
			self.assertGreaterEqual(len(result.files), 3)


class TestCodegenCliHelpers(unittest.TestCase):
	def test_resolve_task_from_flag(self):
		args = SimpleNamespace(task="do the thing", file=None)
		self.assertEqual(resolve_codegen_task(args), "do the thing")

	def test_resolve_task_from_file(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			path = Path(tmpdir) / "prompt.txt"
			path.write_text("from file", encoding="utf-8")
			args = SimpleNamespace(task=None, file=str(path))
			self.assertEqual(resolve_codegen_task(args), "from file")

	def test_resolve_task_requires_input(self):
		with self.assertRaises(ValueError):
			resolve_codegen_task(SimpleNamespace(task=None, file=None))

	def test_parser_accepts_generate_and_project(self):
		import interpreter as interpreter_mod

		parser = interpreter_mod.build_parser()
		args = parser.parse_args(
			["--mode", "generate", "--task", "x", "--output", "out.py", "--cli", "-m", "local-model"]
		)
		self.assertEqual(args.mode, "generate")
		self.assertEqual(args.task, "x")
		self.assertEqual(args.output, "out.py")

		args2 = parser.parse_args(["-md", "project", "-t", "scaffold me", "-o", "proj"])
		self.assertEqual(args2.mode, "project")
		self.assertEqual(args2.task, "scaffold me")

	def test_run_codegen_cli_snippet(self):
		llm_text = "```python\nprint(1)\n```"

		def completion_fn(model, **kwargs):
			return SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content=llm_text))]
			)

		with tempfile.TemporaryDirectory() as tmpdir:
			out = Path(tmpdir) / "s.py"
			args = SimpleNamespace(
				mode="generate",
				task="print one",
				file=None,
				lang="python",
				output=str(out),
				model="test",
				unsafe=True,
			)
			# Patch generator completion via interpreter=None path by monkeypatching class
			from libs import code_generator as cg

			original = cg.CodeGenerator
			class Patched(original):
				def __init__(self, *a, **k):
					super().__init__(*a, **k)
					self.completion_fn = completion_fn

			cg.CodeGenerator = Patched
			try:
				result = run_codegen_cli(args, interpreter=None)
			finally:
				cg.CodeGenerator = original
			self.assertTrue(Path(result.path).is_file())
			self.assertIn("print(1)", Path(result.path).read_text(encoding="utf-8"))


if __name__ == "__main__":
	unittest.main()
