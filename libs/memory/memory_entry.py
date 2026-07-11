"""Memory entry model for context window management."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field


@dataclass
class MemoryEntry:
	role: str
	content: str
	task: str = ""
	tokens: int = 0
	timestamp: float = field(default_factory=time.time)
	success: bool = True
	tags: list = field(default_factory=list)

	def to_dict(self) -> dict:
		return asdict(self)

	@classmethod
	def from_dict(cls, data: dict) -> "MemoryEntry":
		return cls(
			role=str(data.get("role", "")),
			content=str(data.get("content", "")),
			task=str(data.get("task", "")),
			tokens=int(data.get("tokens", 0) or 0),
			timestamp=float(data.get("timestamp", time.time()) or time.time()),
			success=bool(data.get("success", True)),
			tags=list(data.get("tags", []) or []),
		)
