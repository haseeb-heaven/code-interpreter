# -*- coding: utf-8 -*-
"""Rich terminal formatting helpers (Issue #223)."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)


def _fmt_cell(v: Any) -> str:
	try:
		if isinstance(v, float):
			return f"{v:,.4f}" if abs(v) < 1e6 else f"{v:.4e}"
		if isinstance(v, int) and not isinstance(v, bool):
			return f"{v:,}"
		return str(v)
	except Exception:
		return str(v)


def print_dataframe(df, title: str = "", max_rows: int = 20, console=None) -> None:
	"""Print a pandas DataFrame as a Rich table when available."""
	try:
		import pandas as pd
		from rich import box
		from rich.console import Console
		from rich.table import Table

		con = console or Console(legacy_windows=False)
		table = Table(
			title=title or None,
			box=box.ROUNDED,
			show_header=True,
			header_style="bold cyan",
			row_styles=["none", "dim"],
		)
		for col in df.columns:
			justify = "right" if pd.api.types.is_numeric_dtype(df[col]) else "left"
			table.add_column(str(col), justify=justify)
		for _, row in df.head(max_rows).iterrows():
			table.add_row(*[_fmt_cell(v) for v in row])
		if len(df) > max_rows:
			table.caption = f"... {len(df) - max_rows} more rows"
		con.print(table)
	except Exception as exc:
		logger.debug("rich dataframe print failed: %s", exc)
		print(df.head(max_rows).to_string(index=False))


def print_stats(stats: Mapping[str, Any], console=None) -> None:
	try:
		from rich.console import Console
		from rich.panel import Panel
		from rich.table import Table
		from rich import box

		con = console or Console(legacy_windows=False)
		table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
		table.add_column("Metric", style="bold")
		table.add_column("Value", style="cyan")
		for k, v in stats.items():
			table.add_row(str(k), str(v))
		con.print(Panel(table, title="Results", border_style="green"))
	except Exception:
		for k, v in stats.items():
			print(f"{k}: {v}")


def print_code(code: str, language: str = "python", console=None) -> None:
	try:
		from rich.console import Console
		from rich.syntax import Syntax

		(console or Console(legacy_windows=False)).print(
			Syntax(code or "", language, theme="monokai", line_numbers=True)
		)
	except Exception:
		print(code)


def print_error(error: str, console=None) -> None:
	try:
		from rich.console import Console
		from rich.panel import Panel

		(console or Console(legacy_windows=False)).print(
			Panel(error or "", title="Error", border_style="red", style="red")
		)
	except Exception:
		print(error)
