"""Shared agent abstractions: AgentContext + BaseAgent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
	"""Mutable state passed through the agent pipeline."""

	task: str
	os_name: str
	language: str
	intent: str = ""  # filled by IntentRouter
	plan: list = field(default_factory=list)
	code: str = ""
	output: str = ""
	error: str = ""
	approved: bool = False
	verified: bool = False
	safe: bool = True
	metadata: dict = field(default_factory=dict)


class BaseAgent(ABC):
	"""Abstract base class all pipeline agents inherit from."""

	def __init__(self, model_router: Any, logger: Any):
		self.model_router = model_router
		self.logger = logger
		self.name = self.__class__.__name__

	@abstractmethod
	def run(self, context: AgentContext) -> AgentContext:
		raise NotImplementedError

	def _log(self, msg: str) -> None:
		self.logger.info(f"[{self.name}] {msg}")
