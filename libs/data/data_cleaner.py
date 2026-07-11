# -*- coding: utf-8 -*-
"""Data cleaning helpers for /clean shortcuts (Issue #222)."""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def clean_nulls(df: pd.DataFrame, strategy: str = "drop") -> Tuple[pd.DataFrame, str]:
	"""Drop or fill null values. strategy: drop|mean|median|mode|zero."""
	before = int(df.isnull().sum().sum())
	out = df.copy()
	strat = (strategy or "drop").lower().strip()
	try:
		if strat == "drop":
			out = out.dropna()
		elif strat == "mean":
			out = out.fillna(out.mean(numeric_only=True))
		elif strat == "median":
			out = out.fillna(out.median(numeric_only=True))
		elif strat == "mode":
			for col in out.columns:
				mode = out[col].mode(dropna=True)
				if len(mode):
					out[col] = out[col].fillna(mode.iloc[0])
		elif strat == "zero":
			out = out.fillna(0)
		else:
			raise ValueError(f"Unknown null strategy: {strategy}")
	except Exception as exc:
		logger.error("clean_nulls failed: %s", exc)
		raise
	after = int(out.isnull().sum().sum())
	msg = f"Nulls before={before} after={after} strategy={strat} rows={len(df)}->{len(out)}"
	return out, msg


def clean_dupes(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
	before = len(df)
	out = df.drop_duplicates()
	removed = before - len(out)
	return out, f"Removed {removed} duplicate row(s); {before}->{len(out)}"


def clean_types(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
	out = df.copy()
	changed = []
	for col in out.columns:
		if out[col].dtype == object:
			converted = pd.to_numeric(out[col], errors="ignore")
			if str(converted.dtype) != str(out[col].dtype):
				out[col] = converted
				changed.append(col)
	return out, f"Type-inferred columns: {', '.join(changed) if changed else 'none'}"


def clean_dates(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
	out = df.copy()
	changed = []
	for col in out.columns:
		if out[col].dtype == object or "date" in str(col).lower() or "time" in str(col).lower():
			parsed = pd.to_datetime(out[col], errors="coerce", utc=False)
			# Only keep if a reasonable share parsed
			ok = parsed.notna().mean()
			if ok >= 0.5:
				out[col] = parsed.dt.strftime("%Y-%m-%dT%H:%M:%S")
				changed.append(col)
	return out, f"Date-standardized columns: {', '.join(changed) if changed else 'none'}"


def clean_whitespace(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
	out = df.copy()
	n = 0
	for col in out.select_dtypes(include=["object", "string"]).columns:
		before = out[col].astype(str)
		stripped = before.str.strip()
		n += int((before != stripped).sum())
		out[col] = stripped
	return out, f"Stripped whitespace in object cells (changed≈{n})"


def clean_all(df: pd.DataFrame, null_strategy: str = "median") -> Tuple[pd.DataFrame, str]:
	msgs = []
	out, m = clean_whitespace(df)
	msgs.append(m)
	out, m = clean_dupes(out)
	msgs.append(m)
	out, m = clean_types(out)
	msgs.append(m)
	out, m = clean_dates(out)
	msgs.append(m)
	out, m = clean_nulls(out, strategy=null_strategy)
	msgs.append(m)
	return out, " | ".join(msgs)
