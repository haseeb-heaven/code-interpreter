"""Persistent context window memory with keyword relevance retrieval."""

from __future__ import annotations

import json
import os
import re

from libs.memory.memory_entry import MemoryEntry


class ContextWindowManager:
	_KEYWORDS_RE = re.compile(r"[a-z0-9_]+")
	_TOKENS_RE = re.compile(r"\S+")

	def __init__(self, max_tokens: int = 8000, history_file: str = "history/history.json"):
		self.max_tokens = max_tokens
		self.history_file = history_file
		self.entries = []
		self._load()
		self._enforce_budget()

	def add(self, entry: MemoryEntry | dict) -> None:
		if isinstance(entry, dict):
			entry = MemoryEntry.from_dict(entry)
		if not entry.tokens:
			entry.tokens = self._estimate_tokens(f"{entry.task} {entry.content}")
		self.entries.append(entry)
		self._enforce_budget()
		self._save()

	def get_context(self, task: str, limit: int = 3) -> list[dict]:
		selected = []
		seen = set()

		for entry in self._find_relevant(task, limit=limit):
			key = (entry.timestamp, entry.role, entry.content)
			if key not in seen:
				selected.append(entry)
				seen.add(key)

		for entry in reversed(self.entries[-limit:]):
			key = (entry.timestamp, entry.role, entry.content)
			if key not in seen:
				selected.append(entry)
				seen.add(key)
			if len(selected) >= limit:
				break

		return [entry.to_dict() for entry in selected[:limit]]

	def _find_relevant(self, task: str, limit: int = 3) -> list[MemoryEntry]:
		task_words = self._keywords(task)
		if not task_words:
			return []

		scored = []
		for index, entry in enumerate(self.entries):
			entry_words = self._keywords(f"{entry.task} {entry.content} {' '.join(entry.tags)}")
			score = len(task_words.intersection(entry_words))
			if score:
				scored.append((score, entry.timestamp, index, entry))

		scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
		return [item[3] for item in scored[:limit]]

	def _estimate_tokens(self, text: str) -> int:
		words = self._TOKENS_RE.findall(text or "")
		return max(1, len(words)) if text else 0

	def _enforce_budget(self) -> None:
		while self.entries and self._total_tokens() > self.max_tokens:
			self.entries.pop(0)

	def _total_tokens(self) -> int:
		return sum(max(0, int(entry.tokens or 0)) for entry in self.entries)

	def _save(self) -> None:
		history_dir = os.path.dirname(self.history_file)
		if history_dir:
			os.makedirs(history_dir, exist_ok=True)
		with open(self.history_file, "w", encoding="utf-8") as file:
			json.dump([entry.to_dict() for entry in self.entries], file)

	def _load(self) -> None:
		if not os.path.exists(self.history_file):
			self.entries = []
			self._save()
			return
		if os.path.getsize(self.history_file) == 0:
			self.entries = []
			return
		with open(self.history_file, "r", encoding="utf-8") as file:
			data = json.load(file)
		self.entries = []
		for item in data:
			if not isinstance(item, dict):
				continue
			entry = self._entry_from_data(item)
			if not entry.tokens:
				entry.tokens = self._estimate_tokens(f"{entry.task} {entry.content}")
			self.entries.append(entry)

	def clear(self) -> None:
		self.entries = []
		self._save()

	def stats(self) -> dict:
		return {
			"entry_count": len(self.entries),
			"total_tokens": self._total_tokens(),
			"max_tokens": self.max_tokens,
			"history_file": self.history_file,
		}

	def _keywords(self, text: str) -> set[str]:
		return set(self._KEYWORDS_RE.findall((text or "").lower()))

	def _entry_from_data(self, data: dict) -> MemoryEntry:
		if "assistant" not in data:
			return MemoryEntry.from_dict(data)

		assistant = data.get("assistant") or {}
		system = data.get("system") or {}
		content = system.get("output") or system.get("code") or data.get("user", "")
		tags = [
			value for value in [
				assistant.get("mode"),
				assistant.get("language"),
				assistant.get("model"),
			]
			if value
		]
		return MemoryEntry(
			role="assistant",
			content=str(content or ""),
			task=str(assistant.get("task", "")),
			tokens=int(data.get("tokens", 0) or 0),
			success=not bool(system.get("error")),
			tags=tags,
		)
