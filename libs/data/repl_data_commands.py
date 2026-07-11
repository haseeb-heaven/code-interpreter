# -*- coding: utf-8 -*-
"""REPL command handlers for data analysis features (Issue #222)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def ensure_data_session(interp) -> Any:
	"""Return interp.data_session, creating an empty one if needed."""
	session = getattr(interp, "data_session", None)
	if session is None:
		from libs.data.session_data import DataSession

		session = DataSession()
		interp.data_session = session
	return session


def handle_data_repl_command(interp, task: str, display_fn: Callable[[str], None]) -> bool:
	"""Handle /eda /charts /export /clean /sql /templates /chart-style.

	Returns True when the command was consumed.
	"""
	raw = (task or "").strip()
	lower = raw.lower()
	if not lower.startswith(
		("/eda", "/charts", "/export", "/clean", "/sql", "/templates", "/chart-style")
	):
		return False

	session = ensure_data_session(interp)

	try:
		if lower.startswith("/eda"):
			return _cmd_eda(interp, session, raw, display_fn)
		if lower.startswith("/charts"):
			return _cmd_charts(session, raw, display_fn)
		if lower.startswith("/export"):
			return _cmd_export(session, raw, display_fn)
		if lower.startswith("/clean"):
			return _cmd_clean(session, raw, display_fn)
		if lower.startswith("/sql"):
			return _cmd_sql(interp, session, raw, display_fn)
		if lower.startswith("/templates"):
			return _cmd_templates(raw, display_fn)
		if lower.startswith("/chart-style"):
			return _cmd_chart_style(session, raw, display_fn)
	except Exception as exc:
		logger.exception("Data REPL command failed")
		display_fn(f"Error: {exc}")
		return True
	return False


def _cmd_eda(interp, session, raw: str, display_fn) -> bool:
	from libs.data.auto_eda import build_eda_prompt, deterministic_eda_summary

	parts = raw.split(maxsplit=1)
	path = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else session.active_file
	if not path:
		display_fn("Usage: `/eda path/to/file.csv`")
		return True
	result = session.load_file(path)
	summary = deterministic_eda_summary(session.df)
	display_fn("**EDA summary (offline)**\n\n```\n" + summary + "\n```")
	prompt = build_eda_prompt(path, result)
	interp._pending_eda_prompt = prompt
	display_fn(
		"EDA context loaded. Follow up in natural language for LLM-driven charts. "
		"Charts save under `~/.code_interpreter/charts`."
	)
	session.record_operation(f"eda:{path}")
	return True


def _cmd_charts(session, raw: str, display_fn) -> bool:
	from libs.output.chart_manager import chart_dir, list_charts, open_file
	from libs.output.plotly_manager import list_plotly_charts

	parts = raw.split()
	sub = parts[1].lower() if len(parts) > 1 else "list"
	if sub in ("list",):
		pngs = list_charts(10)
		htmls = list_plotly_charts(10)
		if not pngs and not htmls:
			display_fn("No charts saved yet.")
			return True
		lines = ["Saved charts (newest first):"]
		for i, p in enumerate(pngs, 1):
			lines.append(f"  {i}. {p}")
		for i, p in enumerate(htmls, 1):
			lines.append(f"  H{i}. {p}")
		display_fn("\n".join(lines))
		return True
	if sub == "dir":
		path = chart_dir()
		open_file(path)
		display_fn(f"Charts directory: `{path}`")
		return True
	if sub == "open":
		if len(parts) < 3:
			display_fn("Usage: `/charts open <n>`")
			return True
		idx = int(parts[2]) - 1
		pngs = list_charts(50)
		if idx < 0 or idx >= len(pngs):
			display_fn("Chart index out of range.")
			return True
		open_file(pngs[idx])
		display_fn(f"Opened `{pngs[idx]}`")
		return True
	display_fn("Usage: `/charts` | `/charts open N` | `/charts dir`")
	return True


def _cmd_export(session, raw: str, display_fn) -> bool:
	from libs.output.chart_manager import list_charts
	from libs.output.exporter import export_dataframe

	parts = raw.split(maxsplit=1)
	fmt = parts[1].strip().lower() if len(parts) > 1 else "csv"
	if session.df is None:
		display_fn("No active dataset. Load with `/file` or `/eda` first.")
		return True
	path = export_dataframe(session.df, fmt, charts=list_charts(20))
	session.record_operation(f"export:{fmt}:{path}")
	display_fn(f"Exported to `{path}`")
	return True


def _cmd_clean(session, raw: str, display_fn) -> bool:
	from libs.data import data_cleaner as dc

	if session.df is None:
		display_fn("No active dataset. Load with `/file` or `/eda` first.")
		return True
	parts = raw.split()
	op = parts[1].lower() if len(parts) > 1 else "all"
	strategy = parts[2].lower() if len(parts) > 2 else "median"
	handlers = {
		"nulls": lambda: dc.clean_nulls(session.df, strategy=strategy),
		"dupes": lambda: dc.clean_dupes(session.df),
		"types": lambda: dc.clean_types(session.df),
		"dates": lambda: dc.clean_dates(session.df),
		"whitespace": lambda: dc.clean_whitespace(session.df),
		"all": lambda: dc.clean_all(session.df, null_strategy=strategy),
	}
	if op not in handlers:
		display_fn("Usage: `/clean nulls|dupes|types|dates|whitespace|all [strategy]`")
		return True
	new_df, msg = handlers[op]()
	session.df = new_df
	session.record_operation(f"clean:{op}")
	display_fn(msg)
	return True


def _cmd_sql(interp, session, raw: str, display_fn) -> bool:
	from libs.data.sql_runner import build_nl_sql_prompt, run_sql_on_df

	parts = raw.split(maxsplit=1)
	if len(parts) < 2 or not parts[1].strip():
		display_fn('Usage: `/sql "SELECT ..."` or `/sql show top 10 rows`')
		return True
	if session.df is None:
		display_fn("No active dataset. Load with `/file` or `/eda` first.")
		return True
	question = parts[1].strip().strip('"').strip("'")
	# If it looks like SQL, run directly; else stash NL prompt for LLM.
	looks_sql = question.lower().lstrip().startswith(("select", "with", "pragma", "show", "describe"))
	if looks_sql:
		result, engine = run_sql_on_df(session.df, question)
		session.df = result  # last result becomes exportable
		session.record_operation(f"sql:{engine}")
		try:
			table = result.head(50).to_markdown(index=False)
		except Exception:
			table = result.head(50).to_string(index=False)
		display_fn(f"SQL via {engine} ({len(result)} rows):\n\n{table}")
		return True
	prompt = build_nl_sql_prompt(question, session.schema or "")
	interp._pending_sql_prompt = prompt
	display_fn(
		"Natural-language SQL queued. Generating SQL via the model on your next run, "
		"or paste a SELECT directly: `/sql SELECT * FROM data LIMIT 10`"
	)
	return True


def _cmd_templates(raw: str, display_fn) -> bool:
	from libs.data.templates import format_templates

	parts = raw.split(maxsplit=1)
	cat = parts[1].strip() if len(parts) > 1 else "data"
	display_fn(format_templates(cat))
	return True


def _cmd_chart_style(session, raw: str, display_fn) -> bool:
	parts = raw.split(maxsplit=1)
	if len(parts) < 2:
		display_fn(f"Current chart style: `{session.chart_style}`. Usage: `/chart-style plotly|matplotlib`")
		return True
	style = parts[1].strip().lower()
	if style not in ("plotly", "matplotlib"):
		display_fn("Usage: `/chart-style plotly|matplotlib`")
		return True
	session.chart_style = style
	session.record_operation(f"chart-style:{style}")
	display_fn(f"Chart style set to `{style}`")
	return True


def check_rscript_available() -> Optional[str]:
	"""Return path to Rscript if found, else None."""
	return shutil.which("Rscript")
