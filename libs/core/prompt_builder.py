"""Prompt construction for all Interpreter modes."""

from __future__ import annotations

from typing import List


class PromptBuilder:
	"""Builds LLM message lists and mode-specific task prompts.

	Operates against an Interpreter-like object that exposes the historical
	mode flags (CODE_MODE, SCRIPT_MODE, ...) and INTERPRETER_* attributes.
	"""

	def __init__(self, interp):
		self.interp = interp

	def get_prompt(self, message: str, chat_history: List[dict]) -> List[dict] | str:
		system_message: str = ""
		assistant_message = "Please generate code wrapped inside triple backticks known as codeblock."
		interp = self.interp

		if interp.CODE_MODE:
			system_message = (
				interp.system_message
				+ "\nReturn exactly one executable code block."
				+ "\nDo not include explanations, comments, docstrings, markdown headings, or text outside the code block."
				+ "\nDo not use subprocess, os.system, or any shell execution."
				+ "\nOnly create tables, charts, plots, files, or visual outputs IF explicitly required."
				+ "\nIf not explicitly requested, do NOT generate them."
			)
			assistant_message = (
				f"Return only executable {interp.INTERPRETER_LANGUAGE} code wrapped in triple backticks."
				f" No explanations. No comments. No text outside the code block."
				f" Do not use subprocess, os.system, or shell execution."
			)

		elif interp.SCRIPT_MODE:
			system_message = (
				"Generate a Python script only."
				"\nSTRICT RULES:"
				"\n- Do NOT use bash, sh, cmd, or powershell"
				"\n- Do NOT use subprocess, os.system, or shell execution"
				"\n- Script must be fully self-contained and executable"
				"\n- Return exactly one code block with no explanations"
			)
			assistant_message = (
				"Return only Python script inside triple backticks."
				" No explanations. No comments outside code."
			)

		elif interp.COMMAND_MODE:
			system_message = (
				"Generate only a single executable command."
				"\nSTRICT RULES:"
				"\n- Do NOT use shell built-in commands (dir, ls, cd, copy, del, Get-ChildItem)"
				"\n- Do NOT use cmd, powershell, bash, or shell syntax"
				"\n- Do NOT use &&, ||, |, ;, >, <, $, or chaining"
				"\n- Always use python -c for filesystem or logic tasks"
				"\n- Command must be directly executable without shell"
			)
			assistant_message = (
				"Return only a single-line executable command."
				" Do NOT return a code block."
				" Do NOT use triple backticks."
				" No explanations. No extra text."
			)

		elif interp.VISION_MODE:
			system_message = (
				"Please generate a well-written description of the image that is precise, easy to understand"
			)
			assistant_message = (
				"Return only the description. No code. No formatting. No markdown."
			)

		elif interp.CHAT_MODE:
			system_message = "Please generate a well-written response that is precise, easy to understand"
			assistant_message = "Return a clear and helpful response."

			if chat_history:
				system_message += (
					"\n\nThis is user chat history. Use it as context if needed:\n\n"
					+ str(chat_history)
				)

		# Claude (Anthropic) expects a structured user content list.
		if "claude" in interp.INTERPRETER_MODEL:
			combined = f"{system_message}\n\n{assistant_message}\n\nUser: {message}"
			messages = [
				{
					"role": "user",
					"content": [
						{
							"type": "text",
							"text": combined,
						}
					],
				}
			]
		else:
			messages = [
				{"role": "system", "content": system_message},
				{"role": "assistant", "content": assistant_message},
				{"role": "user", "content": message},
			]

		return messages

	def get_code_prompt(self, task, os_name):
		interp = self.interp
		if interp.INTERPRETER_LANGUAGE not in ["python", "javascript"]:
			interp.INTERPRETER_LANGUAGE = "python"

		return (
			f"Generate executable {interp.INTERPRETER_LANGUAGE} code for this task: '{task}'.\n"
			f"Target operating system: {os_name}.\n"
			"Return exactly one fenced code block and nothing else.\n"
			"Do not include explanations, comments, docstrings, markdown prose, or usage notes.\n"
			"Use production-ready syntax with correct indentation and imports.\n"
			"Do not use subprocess, os.system, or any shell execution.\n"
			"Only create tables, charts, plots, files, or visual outputs IF the task explicitly requires them.\n"
			"If the task does NOT explicitly request tables, charts, plots, or files, do NOT generate them.\n"
			"If the task only asks to print, list, or show something, generate only the few lines needed to do that exact action.\n"
			"Handle common filesystem and permission errors safely when relevant.\n"
			"If multiple solutions exist, choose the most direct working solution."
		)

	def get_script_prompt(self, task, os_name):
		interp = self.interp
		# Force Python for safety and consistency
		interp.INTERPRETER_LANGUAGE = "python"
		script_type = "Python script"

		prompt = (
			f"Generate only the {script_type} for this task:\n"
			f"Task: '{task}'\n"
			f"Operating System: {os_name}\n"
			"NOTE: Script must be fully self-contained and executable without any shell usage.\n"
			"Do NOT use bash, sh, cmd, or powershell.\n"
			"Do NOT use subprocess, os.system, or shell invocation.\n"
			"Only generate tables, charts, plots, or files IF explicitly required by the task.\n"
			"Do not generate unnecessary outputs or extra files.\n"
			"Output should only contain the script, with no additional text.\n"
			"Do not add unrelated package installs or extra logic unless required."
		)
		interp.logger.info(f"Script Prompt: {prompt}")
		return prompt

	def get_command_prompt(self, task, os_name):
		prompt = (
			f"Generate only the single executable command for this task:\n"
			f"Task: '{task}'\n"
			f"Operating System: {os_name}\n"
			"IMPORTANT: Do NOT use shell built-in commands (dir, cd, copy, del, Get-ChildItem).\n"
			"Instead, generate a python -c command to perform the task.\n"
			"The command must be directly executable without shell.\n"
			"Do not use &&, ||, |, ;, >, <, $, or chaining.\n"
			"Output only the command, nothing else."
		)
		self.interp.logger.info(f"Command Prompt: {prompt}")
		return prompt

	def handle_vision_mode(self, task):
		return (
			f"Give accurate and detailed information about the image provided "
			f"and be very detailed about the image '{task}'."
		)

	def handle_chat_mode(self, task):
		return (
			f"Give accurate and detailed response to the question provided "
			f"and be very detailed about the question '{task}'."
		)

	def get_mode_prompt(self, task, os_name):
		interp = self.interp
		if interp.CODE_MODE:
			interp.logger.info("Getting code prompt.")
			return self.get_code_prompt(task, os_name)
		if interp.SCRIPT_MODE:
			interp.logger.info("Getting script prompt.")
			return self.get_script_prompt(task, os_name)
		if interp.COMMAND_MODE:
			interp.logger.info("Getting command prompt.")
			return self.get_command_prompt(task, os_name)
		if interp.VISION_MODE:
			interp.logger.info("Getting vision prompt.")
			return self.handle_vision_mode(task)
		if interp.CHAT_MODE:
			interp.logger.info("Getting chat prompt.")
			return self.handle_chat_mode(task)
		return None

	def build(self, task: str, os_name: str) -> str:
		"""Public mode-dispatch entry used by the modular API."""
		return self.get_mode_prompt(task, os_name)
