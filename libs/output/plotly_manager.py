# -*- coding: utf-8 -*-
"""Plotly HTML chart output helpers (Issue #222)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from libs.output.chart_manager import chart_dir, open_file

logger = logging.getLogger(__name__)

PLOTLY_SAVE_SNIPPET = """
from pathlib import Path as _CIPath
from datetime import datetime as _CIdt
_CI_CHART_DIR = _CIPath.home() / '.code_interpreter' / 'charts'
_CI_CHART_DIR.mkdir(parents=True, exist_ok=True)
def _ci_write_html(fig, name=None):
    _ts = _CIdt.now().strftime('%Y%m%d_%H%M%S')
    _path = _CI_CHART_DIR / (name or f'plotly_{_ts}.html')
    fig.write_html(str(_path))
    print(f'Plotly chart saved: {_path}')
    return _path
""".lstrip()


def list_plotly_charts(limit: int = 10, home: Optional[Path] = None) -> List[Path]:
	try:
		files = sorted(
			chart_dir(home).glob("*.html"),
			key=lambda p: p.stat().st_mtime,
			reverse=True,
		)
		return files[: max(0, int(limit))]
	except Exception as exc:
		logger.error("list_plotly_charts failed: %s", exc)
		return []


def needs_plotly_hook(code: str) -> bool:
	lower = (code or "").lower()
	return "plotly" in lower or "write_html" in lower


def inject_plotly_helper(code: str) -> str:
	if not code or not needs_plotly_hook(code):
		return code or ""
	if "_ci_write_html" in code:
		return code
	return PLOTLY_SAVE_SNIPPET + "\n" + code


def plotly_system_hint() -> str:
	return (
		"Always use plotly for visualizations, not matplotlib. "
		"Save charts with fig.write_html() via _ci_write_html(fig) to the charts directory."
	)


def plotly_safety_hint() -> str:
	"""Guidance included unconditionally, independent of the plotly-preference
	toggle above: the model can reach for Plotly on its own even when the user
	declined the interactive-charts preference, and fig.write_image() depends
	on kaleido's headless-Chromium backend, which is unreliable and frequently
	fails on Windows (e.g. "[WinError 10106] The requested service provider
	could not be loaded or initialized").
	"""
	return (
		"If any Plotly figures are created, save them with fig.write_html() "
		"(or the injected _ci_write_html(fig) helper) instead of fig.write_image() "
		"or kaleido, which are unreliable and can fail on Windows."
	)
