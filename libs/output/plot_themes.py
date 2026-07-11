# -*- coding: utf-8 -*-
"""Publication-quality matplotlib plot themes (Issue #223)."""

from __future__ import annotations

PLOT_THEMES = {
	"paper": {
		"style": "seaborn-v0_8-paper",
		"rc": {
			"figure.dpi": 300,
			"savefig.dpi": 300,
			"font.family": "serif",
			"figure.figsize": (10, 6),
		},
	},
	"talk": {
		"style": "seaborn-v0_8-talk",
		"rc": {"figure.dpi": 150, "figure.figsize": (10, 6)},
	},
	"dark": {
		"style": "dark_background",
		"rc": {
			"figure.dpi": 150,
			"axes.facecolor": "#1a1a2e",
			"figure.figsize": (10, 6),
		},
	},
	"minimal": {
		"style": "seaborn-v0_8-whitegrid",
		"rc": {
			"figure.dpi": 150,
			"axes.spines.top": False,
			"axes.spines.right": False,
			"figure.figsize": (10, 6),
		},
	},
}


def theme_setup_snippet(theme: str = "minimal") -> str:
	"""Return Python code that applies a named plot theme."""
	name = (theme or "minimal").lower().strip()
	cfg = PLOT_THEMES.get(name, PLOT_THEMES["minimal"])
	style = cfg["style"]
	rc_items = ", ".join(f"{k!r}: {v!r}" for k, v in cfg["rc"].items())
	return (
		"import matplotlib.pyplot as plt\n"
		"try:\n"
		f"    plt.style.use({style!r})\n"
		"except Exception:\n"
		"    pass\n"
		f"plt.rcParams.update({{{rc_items}}})\n"
	)


def inject_plot_theme(code: str, theme: str | None) -> str:
	"""Prepend theme setup when matplotlib is used and a theme is selected."""
	if not theme or not code:
		return code or ""
	lower = code.lower()
	if "matplotlib" not in lower and "pyplot" not in lower and "plt." not in lower:
		return code
	if "_ci_plot_theme" in code:
		return code
	snip = theme_setup_snippet(theme)
	return f"# _ci_plot_theme={theme}\n{snip}\n{code}"
