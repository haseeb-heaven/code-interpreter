"""Script-mode handler."""

from __future__ import annotations


class ScriptModeHandler:
	def __init__(self, interp):
		self.interp = interp

	def handle(self, task, context=None):
		os_name = (context or {}).get("os_name", "")
		return self.interp.prompt_builder.get_script_prompt(task, os_name)
