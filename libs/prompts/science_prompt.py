# -*- coding: utf-8 -*-
"""Scientific computing system prompt layer (Issue #223)."""

from __future__ import annotations

import re

SCIENCE_SYSTEM_PROMPT = """
You are a scientific computing assistant. When performing data analysis:

- Statistics: use scipy.stats for hypothesis tests (t-test, ANOVA, chi-square, Mann-Whitney)
- Regression: use sklearn or statsmodels, always report R2, p-values, confidence intervals
- Signal processing: use scipy.signal for filtering, FFT, spectral analysis
- Optimization: use scipy.optimize for curve fitting and minimization
- Linear algebra: use numpy.linalg, never implement from scratch
- Always report: sample size (n), effect size, p-value, confidence interval for any statistical test
- Plots: use seaborn for statistical plots (violin, box, swarm, regression), matplotlib for everything else
- Never round p-values — report full precision (e.g., p=0.0023, not p<0.05)
- Always set random seeds for reproducible results: np.random.seed(42)
""".strip()

_SCIENCE_HINTS = re.compile(
	r"\b(p[- ]?value|correlation|regression|hypothesis|significance|"
	r"confidence\s+interval|anova|t[- ]?test|mann[- ]?whitney|"
	r"distribution\s+fit|chi[- ]?square|effect\s+size|scipy|sklearn)\b",
	re.IGNORECASE,
)


def looks_like_science_task(text: str) -> bool:
	"""Return True when the user task likely needs scientific computing guidance."""
	return bool(text and _SCIENCE_HINTS.search(text))


def science_prompt_block(*, force: bool = False, task: str = "") -> str:
	"""Return the science system prompt when forced or auto-detected."""
	if force or looks_like_science_task(task):
		return SCIENCE_SYSTEM_PROMPT
	return ""
