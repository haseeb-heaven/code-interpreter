# -*- coding: utf-8 -*-
"""Cross-turn data session memory (Issue #222)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

import pandas as pd

from libs.data.file_ingestor import ingest, prompt_context

logger = logging.getLogger(__name__)


@dataclass
class DataSession:
	"""Holds the current data context across REPL turns."""

	active_file: Optional[str] = None
	df: Optional[pd.DataFrame] = None
	schema: Optional[str] = None
	preview: Optional[str] = None
	ingest_meta: dict = field(default_factory=dict)
	history: List[str] = field(default_factory=list)
	chart_style: str = "matplotlib"  # or plotly
	notebook_cells: List[dict] = field(default_factory=list)

	def load_file(self, path: str) -> dict[str, Any]:
		"""Ingest a file and store it as the active dataset."""
		try:
			result = ingest(path)
		except Exception as exc:
			logger.error("Failed to load data file %s: %s", path, exc)
			raise
		self.active_file = result.get("path") or path
		self.df = result["df"]
		self.schema = result.get("schema")
		self.preview = result.get("preview")
		self.ingest_meta = {k: v for k, v in result.items() if k != "df"}
		self.record_operation(f"load:{self.active_file}")
		self.record_cell(
			"markdown",
			f"Loaded dataset `{self.active_file}` shape={self.df.shape}",
		)
		return result

	def record_cell(self, cell_type: str, source: str, output: str = "") -> None:
		self.notebook_cells.append(
			{"type": cell_type, "source": source or "", "output": output or ""}
		)
		if len(self.notebook_cells) > 200:
			self.notebook_cells = self.notebook_cells[-200:]

	def context_block(self) -> str:
		"""Return the context string to inject into prompts while a file is loaded."""
		if self.df is None:
			return ""
		meta = dict(self.ingest_meta)
		meta["path"] = self.active_file
		meta["schema"] = self.schema
		meta["preview"] = self.preview
		meta["shape"] = tuple(self.df.shape)
		base = prompt_context(meta)
		ops = ", ".join(self.history[-5:]) if self.history else "none"
		return f"{base}\nPrevious operations: {ops}\nChart style preference: {self.chart_style}\n"

	def record_operation(self, op: str) -> None:
		self.history.append(str(op))
		if len(self.history) > 50:
			self.history = self.history[-50:]

	def clear(self) -> None:
		self.active_file = None
		self.df = None
		self.schema = None
		self.preview = None
		self.ingest_meta = {}
		self.history = []
		self.notebook_cells = []
