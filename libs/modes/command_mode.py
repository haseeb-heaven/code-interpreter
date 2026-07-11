"""Command-mode handler."""

from __future__ import annotations


class CommandModeHandler:
	def __init__(self, interp):
		self.interp = interp

	def handle(self, task, context=None):
		os_name = (context or {}).get("os_name", "")
		return self.interp.prompt_builder.get_command_prompt(task, os_name)
