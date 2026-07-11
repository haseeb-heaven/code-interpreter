# -*- coding: utf-8 -*-
"""Matplotlib chart auto-save gallery (Issue #222)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CHART_DIR = Path.home() / ".code_interpreter" / "charts"

# Snippet prepended to generated matplotlib scripts.
AUTO_SAVE_SNIPPET = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path as _CIPath
from datetime import datetime as _CIdt
_CI_CHART_DIR = _CIPath.home() / '.code_interpreter' / 'charts'
_CI_CHART_DIR.mkdir(parents=True, exist_ok=True)
_CI_orig_show = plt.show
def _ci_auto_show(*args, **kwargs):
    _ts = _CIdt.now().strftime('%Y%m%d_%H%M%S')
    _path = _CI_CHART_DIR / f'chart_{_ts}.png'
    plt.savefig(_path, dpi=150, bbox_inches='tight')
    print(f'Chart saved: {_path}')
    plt.close('all')
plt.show = _ci_auto_show
""".lstrip()


def chart_dir(home: Optional[Path] = None) -> Path:
	base = Path(home) if home is not None else Path.home()
	path = base / ".code_interpreter" / "charts"
	path.mkdir(parents=True, exist_ok=True)
	return path


def list_charts(limit: int = 10, home: Optional[Path] = None) -> List[Path]:
	"""List saved charts newest-first."""
	try:
		files = sorted(
			chart_dir(home).glob("*.png"),
			key=lambda p: p.stat().st_mtime,
			reverse=True,
		)
		return files[: max(0, int(limit))]
	except Exception as exc:
		logger.error("list_charts failed: %s", exc)
		return []


def save_current_figure(name: Optional[str] = None, home: Optional[Path] = None) -> Path:
	"""Save the current matplotlib figure and return its path."""
	import matplotlib.pyplot as plt

	ts = datetime.now().strftime("%Y%m%d_%H%M%S")
	path = chart_dir(home) / (name or f"chart_{ts}.png")
	plt.savefig(path, dpi=150, bbox_inches="tight")
	plt.close("all")
	logger.info("Chart saved to %s", path)
	return path


def open_file(path: Path) -> bool:
	"""Open a file with the OS default viewer. Returns True on success."""
	try:
		path = Path(path)
		if sys.platform == "win32":
			os.startfile(str(path))  # type: ignore[attr-defined]
		elif sys.platform == "darwin":
			subprocess.run(["open", str(path)], check=False)
		else:
			subprocess.run(["xdg-open", str(path)], check=False)
		return True
	except Exception as exc:
		logger.warning("Could not open %s: %s", path, exc)
		return False


def needs_chart_hook(code: str) -> bool:
	"""Return True when generated code likely uses matplotlib."""
	lower = (code or "").lower()
	return "matplotlib" in lower or "pyplot" in lower or "plt." in lower


def inject_auto_save(code: str) -> str:
	"""Prepend auto-save hook when matplotlib is detected."""
	if not code or not needs_chart_hook(code):
		return code or ""
	if "_ci_auto_show" in code or "Chart saved:" in code:
		return code
	return AUTO_SAVE_SNIPPET + "\n" + code
