"""Base abstractions for callable interpreter tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolResult:
	success: bool
	output: str = ""
	error: str = ""
	metadata: dict = field(default_factory=dict)


class BaseTool(ABC):
	name: str = ""
	description: str = ""
	input_schema: dict | None = None

	def schema(self) -> dict:
		return {
			"name": self.name,
			"description": self.description,
			"input_schema": self.input_schema or {},
		}

	@abstractmethod
	def run(self, input_data):
		raise NotImplementedError
