"""Persistent context window memory with keyword relevance retrieval.

Also provides ``ContextManager`` (#215) for in-loop conversation compaction.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Optional

from libs.memory.memory_entry import MemoryEntry

logger = logging.getLogger(__name__)


class ContextManager:
	"""
	Automatically compacts chat message history when it exceeds a token budget.

	Preserves system messages and the last N turns verbatim; summarizes the middle
	with an optional summarizer callable (or a simple truncation fallback).
	"""

	def __init__(self, token_limit: int = 100_000, preserve_last_n: int = 6):
		self.token_limit = token_limit
		self.preserve_last = preserve_last_n

	def maybe_compact(
		self,
		messages: list[dict],
		dispatcher: Any = None,
		model: str = "",
		summarize_fn: Optional[Callable[[str], str]] = None,
	) -> list[dict]:
		total_tokens = self._estimate_tokens(messages)
		if total_tokens < self.token_limit:
			return messages

		logger.info(
			"[ContextManager] Compacting: %s tokens exceeds limit %s",
			total_tokens,
			self.token_limit,
		)

		system_msgs = [m for m in messages if m.get("role") == "system"]
		non_system = [m for m in messages if m.get("role") != "system"]
		if len(non_system) <= self.preserve_last:
			return messages

		tail_msgs = non_system[-self.preserve_last :]
		middle_msgs = non_system[: -self.preserve_last]
		if not middle_msgs:
			return messages

		summary_prompt = (
			"Summarize the following conversation history concisely. "
			"Preserve all key facts, file paths, and decisions made:\n\n"
			+ "\n".join(
				f"{m.get('role', '?').upper()}: {str(m.get('content', '') or '')[:500]}"
				for m in middle_msgs
			)
		)

		summary = self._summarize(summary_prompt, dispatcher, model, summarize_fn)
		compacted = system_msgs + [
			{"role": "assistant", "content": f"[Context Summary]\n{summary}"}
		] + tail_msgs
		logger.info(
			"[ContextManager] Compacted to %s tokens",
			self._estimate_tokens(compacted),
		)
		return compacted

	def _summarize(
		self,
		prompt: str,
		dispatcher: Any,
		model: str,
		summarize_fn: Optional[Callable[[str], str]],
	) -> str:
		if summarize_fn is not None:
			return str(summarize_fn(prompt) or "")
		if dispatcher is not None and hasattr(dispatcher, "dispatch"):
			try:
				return str(
					dispatcher.dispatch(
						messages=[{"role": "user", "content": prompt}],
						model=model,
					)
					or ""
				)
			except Exception as exc:
				logger.warning("[ContextManager] Summarizer failed: %s", exc)
		# Fallback: truncate the prompt body itself as a crude summary
		return prompt[:2000] + ("…" if len(prompt) > 2000 else "")

	def _estimate_tokens(self, messages: list[dict]) -> int:
		# Rough estimate: 4 chars ≈ 1 token
		total = 0
		for message in messages:
			total += len(str(message.get("content", "") or ""))
			# Include tool call argument text in the estimate
			for tc in message.get("tool_calls") or []:
				fn = (tc.get("function") if isinstance(tc, dict) else None) or {}
				total += len(str(fn.get("arguments", "") if isinstance(fn, dict) else ""))
		return total // 4


class ContextWindowManager:
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
		words = re.findall(r"\S+", text or "")
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
		return set(re.findall(r"[a-z0-9_]+", (text or "").lower()))

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
