# -*- coding: utf-8 -*-
"""Smart multi-format file ingestion with schema extraction."""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED = {
	".csv",
	".tsv",
	".xlsx",
	".xls",
	".json",
	".parquet",
	".feather",
	".sqlite",
	".db",
	".txt",
	".log",
}


class FileIngestError(Exception):
	"""Raised when a file cannot be ingested."""


def ingest(path: str, *, max_rows: Optional[int] = None) -> dict[str, Any]:
	"""
	Read any supported file and return a structured ingest payload.

	Returns:
	  df, schema, preview, shape, file_type, encoding, null_summary, numeric_summary
	"""
	p = Path(path).expanduser().resolve()
	if not p.is_file():
		raise FileIngestError(f"File not found: {path}")

	ext = p.suffix.lower()
	encoding = "utf-8"
	logger.info("Ingesting file %s (ext=%s)", p, ext)

	try:
		if ext in (".csv", ".tsv"):
			df, encoding = _read_csv_auto(p, default_sep="\t" if ext == ".tsv" else None)
		elif ext in (".xlsx", ".xls"):
			df = pd.read_excel(p)
		elif ext == ".json":
			df = _read_json(p)
		elif ext == ".parquet":
			df = pd.read_parquet(p)
		elif ext == ".feather":
			df = pd.read_feather(p)
		elif ext in (".sqlite", ".db"):
			df = _read_sqlite_first_table(p)
		elif ext in (".txt", ".log"):
			df, encoding = _read_text_as_table(p)
		else:
			raise FileIngestError(f"Unsupported format: {ext}")
	except FileIngestError:
		raise
	except Exception as exc:
		logger.exception("Failed to ingest %s", p)
		raise FileIngestError(f"Failed to ingest {path}: {exc}") from exc

	if max_rows is not None and len(df) > max_rows:
		df = df.head(max_rows).copy()

	null_cols = df.isnull().sum()
	null_cols = null_cols[null_cols > 0]
	numeric_cols = df.select_dtypes(include="number")

	preview = _safe_markdown(df.head(5))
	numeric_summary = (
		_safe_markdown(numeric_cols.describe())
		if len(numeric_cols.columns)
		else "No numeric columns"
	)

	return {
		"df": df,
		"schema": _schema_str(df),
		"preview": preview,
		"shape": tuple(df.shape),
		"file_type": ext,
		"encoding": encoding,
		"null_summary": null_cols.to_string() if len(null_cols) else "No nulls found",
		"numeric_summary": numeric_summary,
		"path": str(p),
	}


def prompt_context(ingest_result: dict[str, Any]) -> str:
	"""Format ingest metadata for LLM prompt injection (no raw dataframe)."""
	path = ingest_result.get("path") or "unknown"
	shape = ingest_result.get("shape") or (0, 0)
	return (
		f"Active dataset file: {path}\n"
		f"Shape: {shape[0]} rows × {shape[1]} columns\n"
		f"File type: {ingest_result.get('file_type', '')}\n"
		f"Encoding: {ingest_result.get('encoding', 'utf-8')}\n"
		f"Schema:\n{ingest_result.get('schema', '')}\n"
		f"Preview (first 5 rows):\n{ingest_result.get('preview', '')}\n"
		f"Null summary:\n{ingest_result.get('null_summary', '')}\n"
		f"Numeric summary:\n{ingest_result.get('numeric_summary', '')}\n"
		"Use these exact column names and dtypes when generating analysis code."
	)


def _read_csv_auto(p: Path, default_sep: Optional[str] = None) -> tuple[pd.DataFrame, str]:
	"""Try utf-8 first, fall back to latin-1/cp1252. Auto-detect delimiter when possible."""
	for enc in ("utf-8", "latin-1", "cp1252"):
		try:
			sample = p.read_bytes()[:8192].decode(enc, errors="strict")
			sep = default_sep
			if sep is None:
				try:
					dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
					sep = dialect.delimiter
				except csv.Error:
					sep = ","
			df = pd.read_csv(p, encoding=enc, sep=sep)
			return df, enc
		except Exception:
			continue
	df = pd.read_csv(p, encoding="utf-8", on_bad_lines="skip")
	return df, "utf-8"


def _read_json(p: Path) -> pd.DataFrame:
	try:
		return pd.read_json(p)
	except ValueError:
		return pd.read_json(p, lines=True)


def _read_text_as_table(p: Path) -> tuple[pd.DataFrame, str]:
	for enc in ("utf-8", "latin-1", "cp1252"):
		try:
			text = p.read_text(encoding=enc)
			lines = [ln for ln in text.splitlines() if ln.strip()]
			df = pd.DataFrame({"line": lines})
			return df, enc
		except Exception:
			continue
	raise FileIngestError(f"Could not decode text file: {p}")


def _read_sqlite_first_table(p: Path) -> pd.DataFrame:
	con = sqlite3.connect(str(p))
	try:
		tables = pd.read_sql(
			"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
			con,
		)
		if tables.empty:
			raise FileIngestError("No tables found in SQLite file")
		table = str(tables.iloc[0, 0])
		# Quote identifier safely for SQLite
		safe = table.replace('"', '""')
		return pd.read_sql(f'SELECT * FROM "{safe}" LIMIT 10000', con)
	finally:
		con.close()


def _schema_str(df: pd.DataFrame) -> str:
	return "\n".join(f"  {col}: {dtype}" for col, dtype in df.dtypes.items())


def _safe_markdown(df: pd.DataFrame) -> str:
	try:
		return df.to_markdown(index=False)
	except Exception:
		return df.to_string(index=False)
