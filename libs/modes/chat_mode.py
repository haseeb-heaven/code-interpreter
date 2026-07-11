"""Chat-mode handler."""

from __future__ import annotations


class ChatModeHandler:
	def __init__(self, interp):
		self.interp = interp

	def handle(self, task, context=None):
		return self.interp.prompt_builder.handle_chat_mode(task)
