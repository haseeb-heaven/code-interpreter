# -*- coding: utf-8 -*-
"""Multi-format export for analysis results (Issue #222)."""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_EXPORT_DIR = Path.home() / ".code_interpreter" / "exports"


def export_dir(home: Optional[Path] = None) -> Path:
	base = Path(home) if home is not None else Path.home()
	path = base / ".code_interpreter" / "exports"
	path.mkdir(parents=True, exist_ok=True)
	return path


def export_dataframe(
	df: pd.DataFrame,
	fmt: str,
	*,
	home: Optional[Path] = None,
	stem: Optional[str] = None,
	charts: Optional[Iterable[Path]] = None,
	summary_text: str = "",
) -> Path:
	"""Export ``df`` to csv|excel|json|markdown|html|report|pdf."""
	if df is None:
		raise ValueError("No dataframe to export — load data first")
	fmt_l = (fmt or "csv").lower().strip()
	ts = datetime.now().strftime("%Y%m%d_%H%M%S")
	name = stem or f"export_{ts}"
	out = export_dir(home)
	try:
		if fmt_l == "csv":
			path = out / f"{name}.csv"
			df.to_csv(path, index=False)
		elif fmt_l in ("excel", "xlsx"):
			path = out / f"{name}.xlsx"
			df.to_excel(path, index=False)
		elif fmt_l == "json":
			path = out / f"{name}.json"
			df.to_json(path, orient="records", indent=2)
		elif fmt_l in ("markdown", "md"):
			path = out / f"{name}.md"
			try:
				path.write_text(df.to_markdown(index=False), encoding="utf-8")
			except Exception:
				path.write_text(df.to_string(index=False), encoding="utf-8")
		elif fmt_l == "html":
			path = out / f"{name}.html"
			path.write_text(df.to_html(index=False), encoding="utf-8")
		elif fmt_l == "report":
			path = out / f"{name}_report.html"
			path.write_text(_build_report_html(df, charts or []), encoding="utf-8")
		elif fmt_l == "pdf":
			path = out / f"{name}_report.pdf"
			_export_pdf_report(df, list(charts or []), path, summary_text=summary_text)
		else:
			raise ValueError(f"Unsupported export format: {fmt}")
		logger.info("Exported %s", path)
		return path
	except Exception as exc:
		logger.error("Export failed (%s): %s", fmt_l, exc)
		raise


def _export_pdf_report(
	df: pd.DataFrame,
	charts: list,
	path: Path,
	*,
	summary_text: str = "",
) -> None:
	"""Generate a simple PDF report with reportlab (optional dependency)."""
	try:
		from reportlab.lib.pagesizes import letter
		from reportlab.lib.styles import getSampleStyleSheet
		from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table
	except ImportError as exc:
		raise ImportError(
			"reportlab is required for PDF export. Install with: pip install reportlab"
		) from exc

	doc = SimpleDocTemplate(str(path), pagesize=letter)
	styles = getSampleStyleSheet()
	story = [
		Paragraph("Code Interpreter Analysis Report", styles["Title"]),
		Spacer(1, 12),
		Paragraph(
			f"Rows={df.shape[0]} Cols={df.shape[1]}",
			styles["Normal"],
		),
		Spacer(1, 12),
	]
	if summary_text:
		story.append(Paragraph(summary_text.replace("\n", "<br/>"), styles["Normal"]))
		story.append(Spacer(1, 12))

	preview = df.head(15).astype(str).values.tolist()
	header = [str(c) for c in df.columns]
	story.append(Table([header] + preview))
	story.append(Spacer(1, 12))

	for chart in charts:
		try:
			p = Path(chart)
			if p.suffix.lower() in (".png", ".jpg", ".jpeg") and p.is_file():
				story.append(Paragraph(p.name, styles["Heading3"]))
				story.append(Image(str(p), width=400, height=250))
				story.append(Spacer(1, 8))
		except Exception as exc:
			logger.warning("Skip PDF chart %s: %s", chart, exc)

	doc.build(story)


def _build_report_html(df: pd.DataFrame, charts: Iterable[Path]) -> str:
	imgs = []
	for p in charts:
		try:
			data = Path(p).read_bytes()
			b64 = base64.b64encode(data).decode("ascii")
			imgs.append(
				f'<h3>{Path(p).name}</h3><img alt="{Path(p).name}" '
				f'src="data:image/png;base64,{b64}" style="max-width:100%"/>'
			)
		except Exception as exc:
			logger.warning("Skip chart embed %s: %s", p, exc)
	table = df.head(200).to_html(index=False)
	return (
		"<!DOCTYPE html><html><head><meta charset='utf-8'/>"
		"<title>Code Interpreter Report</title>"
		"<style>body{font-family:sans-serif;margin:2rem} table{border-collapse:collapse}"
		"td,th{border:1px solid #ccc;padding:4px 8px}</style></head><body>"
		f"<h1>Analysis Report</h1><p>Rows={df.shape[0]} Cols={df.shape[1]}</p>"
		+ "".join(imgs)
		+ f"<h2>Data preview</h2>{table}"
		"</body></html>"
	)
