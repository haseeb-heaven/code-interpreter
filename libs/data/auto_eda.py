# -*- coding: utf-8 -*-
"""Auto-EDA prompt builder and deterministic summary helpers (Issue #222)."""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def build_eda_prompt(path: str, ingest_result: dict[str, Any]) -> str:
	"""Build an EDA code-generation prompt with schema context injected."""
	schema = ingest_result.get("schema", "")
	preview = ingest_result.get("preview", "")
	shape = ingest_result.get("shape", (0, 0))
	nulls = ingest_result.get("null_summary", "")
	nums = ingest_result.get("numeric_summary", "")
	abs_path = ingest_result.get("path") or path
	return (
		f"Perform a full exploratory data analysis (EDA) on the dataset at:\n"
		f"  {abs_path}\n"
		f"Shape: {shape[0]} rows x {shape[1]} columns\n"
		f"Schema:\n{schema}\n"
		f"Preview:\n{preview}\n"
		f"Null summary:\n{nulls}\n"
		f"Numeric summary:\n{nums}\n\n"
		"Write Python code that:\n"
		"1. Loads the file with pandas using the absolute path above\n"
		"2. Prints shape, dtypes, and missing-value counts\n"
		"3. Prints describe() for numeric columns and value_counts (top 10) for categoricals\n"
		"4. Saves a correlation heatmap to eda_correlation.png (matplotlib Agg)\n"
		"5. Saves distribution plots to eda_distributions.png\n"
		"6. If any column has >5% nulls, save eda_missing.png\n"
		"7. Prints a short plain-English summary of key findings\n"
		"Use matplotlib with Agg backend. Do not call plt.show() without saving first.\n"
		"Output only executable Python code in a fenced block."
	)


def deterministic_eda_summary(df: pd.DataFrame, *, max_cats: int = 5) -> str:
	"""Produce a lightweight offline EDA text summary (no LLM required)."""
	try:
		lines = [
			f"Rows: {df.shape[0]} | Columns: {df.shape[1]}",
			"Dtypes:",
		]
		for col, dtype in df.dtypes.items():
			lines.append(f"  - {col}: {dtype}")
		nulls = df.isnull().sum()
		nulls = nulls[nulls > 0]
		if len(nulls):
			lines.append("Null counts:")
			for col, count in nulls.items():
				pct = 100.0 * float(count) / max(len(df), 1)
				lines.append(f"  - {col}: {int(count)} ({pct:.1f}%)")
		else:
			lines.append("Null counts: none")
		numeric = df.select_dtypes(include="number")
		if len(numeric.columns):
			lines.append("Numeric describe():")
			lines.append(numeric.describe().to_string())
		cats = df.select_dtypes(exclude="number")
		for col in list(cats.columns)[:max_cats]:
			vc = df[col].astype(str).value_counts().head(10)
			lines.append(f"Top values for {col}:")
			lines.append(vc.to_string())
		return "\n".join(lines)
	except Exception as exc:
		logger.error("deterministic_eda_summary failed: %s", exc)
		return f"EDA summary failed: {exc}"
