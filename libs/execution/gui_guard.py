"""
GUI mainloop neutralisation for sandbox execution.

When LLM-generated code calls tkinter.mainloop() inside the sandbox,
it blocks indefinitely. This module injects a no-op replacement into
source (subprocess path) and/or exec_globals (in-process path).
"""
from __future__ import annotations

import logging
import re
import types

logger = logging.getLogger(__name__)

_MAINLOOP_RE = re.compile(r"\bmainloop\s*\(", re.IGNORECASE)

_GUARD_SNIPPET = """
# --- code-interpreter sandbox: non-blocking GUI (skip tkinter mainloop) ---
try:
	import tkinter as _ci_tk

	def _ci_noop_mainloop(*_a, **_k):
		return None

	_ci_tk.Misc.mainloop = _ci_noop_mainloop  # type: ignore[method-assign]
	_ci_tk.mainloop = _ci_noop_mainloop
except Exception:
	pass
# --- end GUI guard ---
""".lstrip()


def _noop(*args, **kwargs) -> None:
	"""No-operation replacement for GUI blocking calls."""


def neutralize_gui_mainloop(code_or_globals):
	"""Neutralise tkinter mainloop for sandbox runs.

	- If *code_or_globals* is a str: return source with guard prepended.
	- If it is a dict: inject shim modules into exec globals (in-process).
	"""
	if isinstance(code_or_globals, dict):
		_inject_globals(code_or_globals)
		return None
	code = code_or_globals if isinstance(code_or_globals, str) else str(code_or_globals or "")
	if not code or "mainloop" not in code:
		return code
	if not _MAINLOOP_RE.search(code):
		return code
	if "_ci_noop_mainloop" in code or "code-interpreter sandbox: non-blocking GUI" in code:
		return code
	logger.info("Injecting tkinter mainloop no-op guard for sandbox execution")
	return _GUARD_SNIPPET + "\n" + code


def _inject_globals(exec_globals: dict) -> None:
	try:
		import tkinter as _real_tk

		shim = types.ModuleType("tkinter")
		shim.__dict__.update({k: v for k, v in _real_tk.__dict__.items()})
		shim.mainloop = _noop  # type: ignore[attr-defined]

		class _SafeTk(_real_tk.Tk):
			def mainloop(self, n: int = 0) -> None:  # type: ignore[override]
				logger.debug("[gui_guard] Tk.mainloop() suppressed in sandbox")

		shim.Tk = _SafeTk  # type: ignore[attr-defined]
		exec_globals["tkinter"] = shim
		exec_globals.setdefault("tk", shim)
	except Exception as exc:
		logger.debug("[gui_guard] skip: %s", exc)
