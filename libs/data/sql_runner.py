# -*- coding: utf-8 -*-
"""Natural-language / raw SQL over local files via DuckDB or pandas (Issue #222)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def run_sql_on_df(df: pd.DataFrame, sql: str, *, table_name: str = "data") -> Tuple[pd.DataFrame, str]:
	"""Execute SQL against an in-memory table built from ``df``.

	Prefers DuckDB when installed; falls back to sqlite3 + pandas.
	"""
	query = (sql or "").strip()
	if not query:
		raise ValueError("Empty SQL query")
	try:
		import duckdb  # type: ignore

		con = duckdb.connect(database=":memory:")
		try:
			con.register(table_name, df)
			result = con.execute(query).df()
			return result, "duckdb"
		finally:
			con.close()
	except ImportError:
		logger.info("duckdb not installed; using sqlite3 fallback")
	except Exception as exc:
		logger.warning("duckdb query failed (%s); trying sqlite3", exc)

	# sqlite3 fallback — register via to_sql
	con = sqlite3.connect(":memory:")
	try:
		df.to_sql(table_name, con, index=False, if_exists="replace")
		result = pd.read_sql_query(query, con)
		return result, "sqlite3"
	finally:
		con.close()


def build_nl_sql_prompt(question: str, schema: str, table_name: str = "data") -> str:
	"""Prompt the LLM to emit a single SQL SELECT for the active table."""
	return (
		f"You are a SQL analyst. The table name is `{table_name}`.\n"
		f"Schema:\n{schema}\n\n"
		f"User question: {question}\n\n"
		"Reply with ONLY a single SQL SELECT statement (no markdown fences, no explanation). "
		f"Query the `{table_name}` table."
	)
