"""Code-mode helpers (simple-task simplification)."""

from __future__ import annotations

import re


class CodeModeHandler:
	"""CODE_MODE post-processing for over-engineered model responses."""

	def __init__(self, interp):
		self.interp = interp

	@staticmethod
	def task_has_any(text, phrases) -> bool:
		return any(phrase in text for phrase in phrases)

	def is_simple_directory_listing_task(self, task_lower) -> bool:
		if not task_lower:
			return False

		list_phrases = (
			"print current files",
			"list current files",
			"show current files",
			"print files in directory",
			"list files in directory",
			"show files in directory",
			"print files in the directory",
			"list files in the directory",
			"show files in the directory",
			"print files in current directory",
			"list files in current directory",
			"show files in current directory",
			"print current files in directory",
			"list current files in directory",
			"show current files in directory",
		)
		disallowed = ("chart", "graph", "plot", "table", "markdown", "html", "png", "csv", "image", "size in mb", "size")
		return self.task_has_any(task_lower, list_phrases) and not self.task_has_any(task_lower, disallowed)

	def maybe_simplify_generated_code(self, task, code_snippet):
		interp = self.interp
		if not interp.CODE_MODE or not isinstance(task, str) or not isinstance(code_snippet, str):
			return code_snippet

		task_lower = task.lower()
		exact_print_match = re.search(r"print(?:s)? exactly ['\"](.+?)['\"]", task, re.IGNORECASE)
		if exact_print_match:
			literal = exact_print_match.group(1)
			if interp.INTERPRETER_LANGUAGE == "python":
				return f"print({literal!r})"
			if interp.INTERPRETER_LANGUAGE == "javascript":
				return f"console.log({literal!r})"

		if "current working directory" in task_lower and interp.CODE_MODE:
			if interp.INTERPRETER_LANGUAGE == "python":
				return "import os\nprint(os.getcwd())"
			if interp.INTERPRETER_LANGUAGE == "javascript":
				return "console.log(process.cwd())"

		if self.is_simple_directory_listing_task(task_lower):
			if interp.INTERPRETER_LANGUAGE == "python":
				return "import os\nfor name in os.listdir():\n    print(name)"
			if interp.INTERPRETER_LANGUAGE == "javascript":
				return (
					"const fs = require('fs');\n"
					"for (const name of fs.readdirSync(process.cwd())) {\n"
					"  console.log(name);\n"
					"}"
				)

		return code_snippet

	def handle(self, task, context):
		"""Mode interface: build the code-mode prompt for ``task``."""
		os_name = context.get("os_name", "")
		return self.interp.prompt_builder.get_code_prompt(task, os_name)
