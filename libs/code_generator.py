"""
Code generation modes (#212) — produce snippets or project scaffolds without execution.

Modes:
- ``generate`` — single-file snippet written to disk
- ``project`` — multi-file directory scaffold (main entry, README, requirements)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Language → default file extension
_LANG_EXT = {
	"python": ".py",
	"py": ".py",
	"javascript": ".js",
	"js": ".js",
	"typescript": ".ts",
	"ts": ".ts",
	"bash": ".sh",
	"shell": ".sh",
	"go": ".go",
	"rust": ".rs",
	"java": ".java",
	"c": ".c",
	"cpp": ".cpp",
	"csharp": ".cs",
	"ruby": ".rb",
}

_SNIPPET_SYSTEM = (
	"You are a code generation assistant. Return exactly one executable code block "
	"for the requested language. Do not execute anything. Do not explain outside the "
	"code fence unless a short comment inside the code is necessary."
)

_PROJECT_SYSTEM = (
	"You are a project scaffolding assistant. Given a user task, output a multi-file "
	"project as markdown fenced code blocks. Each fence MUST start with a filename, e.g.\n"
	"```python:main.py\n"
	"...code...\n"
	"```\n"
	"or\n"
	"```main.py\n"
	"...code...\n"
	"```\n"
	"Include at least: an entrypoint (main.py or app.py), requirements.txt (or package.json), "
	"and README.md. Do not execute code. Prefer a small, runnable scaffold."
)


@dataclass
class GenerationResult:
	"""Result of a generate_snippet / generate_project call."""

	mode: str
	path: str
	files: list[str] = field(default_factory=list)
	warnings: list[str] = field(default_factory=list)
	raw_llm: str = ""


class CodeGenerator:
	"""
	Generate code artifacts via LLM without running the interpreter execution pipeline.
	"""

	def __init__(
		self,
		completion_fn: Optional[Callable[..., Any]] = None,
		model: str = "gpt-4o-mini",
		safety_manager: Any = None,
		config_values: Optional[dict] = None,
	):
		self.completion_fn = completion_fn
		self.model = model
		self.safety_manager = safety_manager
		self.config_values = config_values or {}

	def generate_snippet(
		self,
		task: str,
		language: str = "python",
		output_path: Optional[str] = None,
	) -> GenerationResult:
		"""
		Generate a single code snippet and write it to ``output_path`` (no execution).
		"""
		if not task or not str(task).strip():
			raise ValueError("task is required for generate_snippet")

		language = (language or "python").strip().lower()
		ext = _LANG_EXT.get(language, ".txt")
		if not output_path:
			output_path = os.path.join("output", f"generated_snippet{ext}")

		messages = [
			{"role": "system", "content": _SNIPPET_SYSTEM},
			{
				"role": "user",
				"content": (
					f"Language: {language}\n"
					f"Task: {task.strip()}\n"
					"Return only one fenced code block."
				),
			},
		]
		raw = self._complete(messages)
		code = self._extract_primary_code(raw, language)
		warnings = self._scan_safety(code)

		path = self._write_text(output_path, code)
		logger.info("[CodeGen] Snippet written to %s (%d chars)", path, len(code))
		return GenerationResult(
			mode="generate",
			path=path,
			files=[path],
			warnings=warnings,
			raw_llm=raw,
		)

	def generate_project(
		self,
		task: str,
		output_dir: Optional[str] = None,
		language: str = "python",
	) -> GenerationResult:
		"""
		Generate a multi-file project scaffold under ``output_dir`` (no execution).
		"""
		if not task or not str(task).strip():
			raise ValueError("task is required for generate_project")

		language = (language or "python").strip().lower()
		if not output_dir:
			output_dir = os.path.join("output", "generated_project")

		messages = [
			{"role": "system", "content": _PROJECT_SYSTEM},
			{
				"role": "user",
				"content": (
					f"Preferred language: {language}\n"
					f"Project task: {task.strip()}\n"
					"Emit fenced files with filenames in the fence header."
				),
			},
		]
		raw = self._complete(messages)
		files_map = self._parse_project_files(raw, language=language, task=task.strip())
		warnings: list[str] = []

		# Ensure required artifacts
		self._ensure_project_basics(files_map, task=task.strip(), language=language)

		written: list[str] = []
		root = Path(output_dir)
		for rel_path, content in sorted(files_map.items()):
			warnings.extend(self._scan_safety(content))
			abs_path = root / rel_path
			written.append(self._write_text(str(abs_path), content))

		logger.info("[CodeGen] Project scaffolded at %s (%d files)", output_dir, len(written))
		return GenerationResult(
			mode="project",
			path=str(root.resolve()),
			files=written,
			warnings=sorted(set(warnings)),
			raw_llm=raw,
		)

	# ── LLM ────────────────────────────────────────────────────────────

	def _complete(self, messages: list[dict]) -> str:
		import litellm

		from libs.llm_dispatcher import build_completion_kwargs
		from libs.streaming import looks_like_completion_response

		cfg = self.config_values
		model = str(cfg.get("model") or self.model)
		temperature = float(cfg.get("temperature", 0.2) or 0.2)
		max_tokens = int(cfg.get("max_tokens", 4096) or 4096)
		provider = str(cfg.get("provider") or cfg.get("config_provider") or "")
		api_base = str(cfg.get("api_base") or "None")

		kwargs = build_completion_kwargs(
			model=model,
			messages=messages,
			temperature=temperature,
			max_tokens=max_tokens,
			config_provider=provider,
			api_base=api_base,
			stream=False,
		)
		completion_fn = self.completion_fn or litellm.completion
		response = completion_fn(model, **kwargs)

		if isinstance(response, str):
			return response
		if looks_like_completion_response(response):
			if isinstance(response, dict):
				return response["choices"][0]["message"].get("content") or ""
			return getattr(response.choices[0].message, "content", None) or ""
		return str(response or "")

	# ── Parsing helpers ────────────────────────────────────────────────

	@staticmethod
	def _extract_primary_code(raw: str, language: str) -> str:
		"""Extract the first fenced code block, or return stripped raw text."""
		if not raw:
			return ""
		# ```lang\n...\n``` or ```\n...\n```
		pattern = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
		match = pattern.search(raw)
		if match:
			body = match.group(2).strip("\n")
			return body.strip() + ("\n" if body and not body.endswith("\n") else "")
		# No fence — return as-is
		text = raw.strip()
		return text + ("\n" if text and not text.endswith("\n") else "")

	def _parse_project_files(self, raw: str, language: str, task: str) -> dict[str, str]:
		"""
		Parse fenced blocks into {relative_path: content}.

		Accepted headers:
		- ```python:main.py
		- ```main.py
		- ```python path=main.py
		- ```file:src/app.py
		"""
		files: dict[str, str] = {}
		pattern = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
		for match in pattern.finditer(raw or ""):
			header = (match.group(1) or "").strip()
			body = match.group(2).strip("\n")
			if not body.strip():
				continue
			rel = self._filename_from_fence_header(header, language)
			if not rel:
				continue
			# Normalize separators
			rel = rel.replace("\\", "/").lstrip("./")
			if rel in files:
				logger.warning("[CodeGen] Duplicate file in LLM output: %s (keeping first)", rel)
				continue
			files[rel] = body if body.endswith("\n") else body + "\n"
		return files

	@staticmethod
	def _filename_from_fence_header(header: str, language: str) -> Optional[str]:
		if not header:
			return None
		header = header.strip().strip("`")

		# path=foo or file=foo
		path_eq = re.search(r"(?:path|file)\s*=\s*([^\s]+)", header, re.IGNORECASE)
		if path_eq:
			return path_eq.group(1).strip().strip("'\"")

		# lang:path or file:path
		if ":" in header:
			left, right = header.split(":", 1)
			right = right.strip()
			if right and ("/" in right or "." in right or right.lower() in ("readme", "makefile")):
				return right
			# file:main.py style where left is "file"
			if left.lower() in ("file", "path", "filename") and right:
				return right

		# Bare filename in header (main.py, requirements.txt)
		tokens = header.split()
		for token in tokens:
			token = token.strip()
			if "." in token or token.lower() in ("makefile", "dockerfile", "readme"):
				# skip pure language tags like python, javascript
				if token.lower() in _LANG_EXT or token.lower() in ("python", "javascript", "bash", "shell", "json", "yaml", "yml", "toml", "text", "txt", "md", "markdown"):
					# Could be `python` alone — not a filename
					if "." not in token and "/" not in token:
						continue
				if re.match(r"^[\w./\\-]+$", token):
					return token

		return None

	def _ensure_project_basics(self, files_map: dict[str, str], task: str, language: str) -> None:
		"""Guarantee main entry, README.md, and requirements.txt exist."""
		# Entrypoint
		has_entry = any(
			name.lower() in ("main.py", "app.py", "index.js", "main.js", "src/main.py", "src/app.py")
			or name.lower().endswith("/main.py")
			or name.lower().endswith("/app.py")
			for name in files_map
		)
		if not has_entry:
			ext = _LANG_EXT.get(language, ".py")
			entry = f"main{ext}"
			if language in ("javascript", "js"):
				entry = "index.js"
				files_map[entry] = (
					"// Auto-generated entrypoint\n"
					f"console.log({task!r});\n"
				)
			else:
				files_map[entry] = (
					'"""Auto-generated entrypoint."""\n\n'
					"def main():\n"
					f"    print({task!r})\n\n"
					'if __name__ == "__main__":\n'
					"    main()\n"
				)

		# README
		if not any(n.lower() == "readme.md" for n in files_map):
			files_map["README.md"] = (
				f"# Generated Project\n\n"
				f"{task}\n\n"
				f"## Setup\n\n"
				f"```bash\npip install -r requirements.txt\npython main.py\n```\n"
			)

		# requirements.txt
		if not any(n.lower() == "requirements.txt" for n in files_map):
			reqs = self._infer_requirements(files_map)
			files_map["requirements.txt"] = reqs if reqs.endswith("\n") else reqs + "\n"

	@staticmethod
	def _infer_requirements(files_map: dict[str, str]) -> str:
		"""Extract third-party imports from Python files for a minimal requirements.txt."""
		stdlibish = {
			"os", "sys", "re", "json", "math", "time", "datetime", "pathlib", "typing",
			"collections", "itertools", "functools", "logging", "subprocess", "asyncio",
			"unittest", "argparse", "hashlib", "base64", "copy", "random", "string",
			"tempfile", "shutil", "glob", "io", "csv", "sqlite3", "http", "urllib",
			"email", "html", "xml", "threading", "multiprocessing", "concurrent",
			"dataclasses", "enum", "abc", "contextlib", "traceback", "pprint",
		}
		found: set[str] = set()
		import_re = re.compile(
			r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)",
			re.MULTILINE,
		)
		for name, content in files_map.items():
			if not name.endswith(".py"):
				continue
			for match in import_re.finditer(content or ""):
				mod = match.group(1)
				if mod and mod not in stdlibish:
					found.add(mod)
		if not found:
			return "# No third-party imports detected\n"
		return "\n".join(sorted(found)) + "\n"

	def _scan_safety(self, code: str) -> list[str]:
		warnings: list[str] = []
		if not code or self.safety_manager is None:
			return warnings
		try:
			if hasattr(self.safety_manager, "is_dangerous_operation"):
				if self.safety_manager.is_dangerous_operation(code):
					warnings.append("Safety scan flagged potentially dangerous operations in generated code.")
		except Exception as exc:
			logger.warning("[CodeGen] Safety scan skipped: %s", exc)
		return warnings

	@staticmethod
	def _write_text(path: str, content: str) -> str:
		target = Path(path)
		target.parent.mkdir(parents=True, exist_ok=True)
		target.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
		return str(target.resolve())


def resolve_codegen_task(args) -> str:
	"""Resolve task text from ``--task``, ``-f`` prompt file, or raise."""
	task = getattr(args, "task", None)
	if task and str(task).strip():
		return str(task).strip()
	file_arg = getattr(args, "file", None)
	if file_arg:
		path = Path(file_arg)
		if not path.exists():
			raise FileNotFoundError(f"Prompt file not found: {file_arg}")
		return path.read_text(encoding="utf-8").strip()
	raise ValueError(
		"Code generation requires --task TEXT or -f prompt.txt "
		"(modes: --mode generate | --mode project)."
	)


def run_codegen_cli(args, interpreter=None) -> GenerationResult:
	"""
	CLI entry for ``--mode generate|project``.

	When ``interpreter`` is provided, reuse its model config and safety manager.
	"""
	from libs.safety_manager import ExecutionSafetyManager

	task = resolve_codegen_task(args)
	language = getattr(args, "lang", None) or "python"
	output = getattr(args, "output", None)

	config_values = {}
	model = getattr(args, "model", None) or "gpt-4o-mini"
	safety = None
	if interpreter is not None:
		config_values = getattr(interpreter, "config_values", None) or {}
		model = str(config_values.get("model") or getattr(interpreter, "INTERPRETER_MODEL", model))
		safety = getattr(interpreter, "safety_manager", None)

	if safety is None:
		unsafe = bool(getattr(args, "unsafe", False))
		safety = ExecutionSafetyManager(unsafe_mode=unsafe)

	generator = CodeGenerator(
		model=model,
		safety_manager=safety,
		config_values=config_values,
	)

	mode = (getattr(args, "mode", "") or "").lower()
	if mode == "generate":
		result = generator.generate_snippet(task, language=language, output_path=output)
		print(f"Generated snippet (no execution): {result.path}")
	elif mode == "project":
		result = generator.generate_project(task, output_dir=output, language=language)
		print(f"Generated project scaffold (no execution): {result.path}")
		print(f"Files ({len(result.files)}):")
		for path in result.files:
			print(f"  - {path}")
	else:
		raise ValueError(f"Unsupported codegen mode: {mode}")

	for warning in result.warnings:
		print(f"WARNING: {warning}")
	return result
