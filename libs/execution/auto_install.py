# -*- coding: utf-8 -*-
"""Auto-install missing scientific packages before execution (Issue #223)."""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
from typing import List

logger = logging.getLogger(__name__)

STD_SCIENCE_PACKAGES = {
	"sklearn": "scikit-learn",
	"cv2": "opencv-python",
	"PIL": "Pillow",
	"seaborn": "seaborn",
	"statsmodels": "statsmodels",
	"scipy": "scipy",
	"openpyxl": "openpyxl",
	"duckdb": "duckdb",
	"pyarrow": "pyarrow",
	"reportlab": "reportlab",
	"tabulate": "tabulate",
	"xlrd": "xlrd",
	"numpy": "numpy",
}


def auto_install_missing(code: str, *, enabled: bool = True, print_fn=print) -> List[str]:
	"""Parse imports from code and install any missing mapped packages."""
	if not enabled or not code:
		return []
	try:
		tree = ast.parse(code)
	except SyntaxError:
		return []

	imports = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			for alias in node.names:
				imports.add(alias.name.split(".")[0])
		elif isinstance(node, ast.ImportFrom) and node.module:
			imports.add(node.module.split(".")[0])

	installed: List[str] = []
	for imp in sorted(imports):
		try:
			__import__(imp)
			continue
		except ImportError:
			pass
		pkg = STD_SCIENCE_PACKAGES.get(imp)
		if not pkg:
			continue
		print_fn(f"Installing missing package: {pkg}...")
		try:
			subprocess.run(
				[sys.executable, "-m", "pip", "install", "-q", pkg],
				check=True,
				capture_output=True,
				timeout=300,
			)
			installed.append(pkg)
			logger.info("Auto-installed %s for import %s", pkg, imp)
		except Exception as exc:
			logger.warning("Failed to auto-install %s: %s", pkg, exc)
			print_fn(f"Could not install {pkg}: {exc}")
	return installed
