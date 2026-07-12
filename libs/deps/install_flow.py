# -*- coding: utf-8 -*-
"""Interactive missing-binary recovery: search → ask → optional safe install."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from libs.deps.missing_binary import (
	BinarySpec,
	detect_missing_binary,
	format_install_hints,
	is_missing_binary_error,
	preferred_install_method,
)

logger = logging.getLogger(__name__)

ConfirmFn = Callable[[str], bool]
SearchFn = Callable[[str], str]
InstallFn = Callable[[BinarySpec, str], Tuple[bool, str]]


@dataclass
class HandleResult:
	"""Outcome of a missing-binary recovery attempt."""

	detected: bool = False
	binary: Optional[BinarySpec] = None
	installed: bool = False
	observation: str = ""
	search_notes: str = ""
	skipped: bool = False


class MissingBinaryHandler:
	"""Detect missing tools, optionally search the web, ask user, then install safely.

	Consent rules:
	- Default: always prompt (Y/N).
	- ``yolo=True`` alone: still prompt (auto-suggest install options, do not silent-install).
	- ``yolo=True`` and ``auto_yes=True`` (``--yes`` / ``INTERPRETER_YES``): auto-approve install.
	"""

	def __init__(
		self,
		*,
		confirm_fn: Optional[ConfirmFn] = None,
		search_fn: Optional[SearchFn] = None,
		install_fn: Optional[InstallFn] = None,
		platform: Optional[str] = None,
		print_fn: Optional[Callable[[str], None]] = None,
	):
		self.confirm_fn = confirm_fn or self._default_confirm
		self.search_fn = search_fn
		self.install_fn = install_fn or attempt_safe_install
		self.platform = platform or sys.platform
		self.print_fn = print_fn or (lambda msg: None)

	@staticmethod
	def _default_confirm(prompt: str) -> bool:
		try:
			answer = input(prompt)
		except EOFError:
			return False
		return answer.strip().lower() in ("y", "yes")

	def handle(
		self,
		error_text: str,
		*,
		auto_yes: bool = False,
		yolo: bool = False,
		do_search: bool = False,
	) -> HandleResult:
		"""Classify *error_text* and optionally recover a missing binary."""
		if not is_missing_binary_error(error_text):
			return HandleResult(detected=False, observation="")

		spec = detect_missing_binary(error_text)
		if spec is None:
			# Generic missing command without a known catalog entry — report only.
			return HandleResult(
				detected=True,
				binary=None,
				observation=(
					"MISSING_TOOL: A required command appears to be missing from PATH. "
					"Install it manually, then retry.\n"
					f"Original error:\n{error_text[:500]}"
				),
				skipped=True,
			)

		hints = format_install_hints(spec, platform=self.platform)
		search_notes = ""
		if do_search and self.search_fn is not None:
			try:
				query = f"install {spec.name} {self.platform} winget choco apt brew"
				search_notes = (self.search_fn(query) or "").strip()
				self.print_fn(f"Search tips for {spec.name}:\n{search_notes[:800]}")
			except Exception as exc:
				logger.debug("Missing-binary web search failed: %s", exc)
				search_notes = f"(search failed: {exc})"

		method = preferred_install_method(spec, platform=self.platform)
		prompt = (
			f"\nMissing tool detected: [bold]{spec.name}[/bold]\n"
			f"{hints}\n"
			f"Download/install via '{method}' now? [y/N]: "
		)
		# Strip rich tags for plain input prompts
		plain_prompt = (
			f"\nMissing tool detected: {spec.name}\n"
			f"{hints}\n"
			f"Download/install via '{method}' now? [y/N]: "
		)

		auto_approve = bool(yolo and auto_yes)
		if auto_approve:
			approved = True
			self.print_fn(
				f"YOLO+YES: auto-approving install of '{spec.name}' via {method}."
			)
		else:
			self.print_fn(prompt if "[" in prompt else plain_prompt)
			approved = bool(self.confirm_fn(plain_prompt))

		if not approved:
			obs = (
				f"MISSING_TOOL: '{spec.name}' is not installed. "
				f"User declined automatic install.\n{hints}"
			)
			if search_notes:
				obs += f"\nSearch notes:\n{search_notes[:600]}"
			return HandleResult(
				detected=True,
				binary=spec,
				installed=False,
				observation=obs,
				search_notes=search_notes,
				skipped=True,
			)

		ok, detail = self.install_fn(spec, method)
		if ok:
			obs = (
				f"MISSING_TOOL_INSTALLED: '{spec.name}' installed via {method}. "
				f"{detail} Retry the previous action."
			)
			return HandleResult(
				detected=True,
				binary=spec,
				installed=True,
				observation=obs,
				search_notes=search_notes,
			)

		obs = (
			f"MISSING_TOOL_INSTALL_FAILED: could not install '{spec.name}' via {method}. "
			f"{detail}\n{hints}"
		)
		if search_notes:
			obs += f"\nSearch notes:\n{search_notes[:600]}"
		return HandleResult(
			detected=True,
			binary=spec,
			installed=False,
			observation=obs,
			search_notes=search_notes,
			skipped=True,
		)


def attempt_safe_install(spec: BinarySpec, method: str) -> Tuple[bool, str]:
	"""Run a fixed argv install for an allow-listed binary (no shell interpolation).

	Returns ``(success, detail_message)``. On Windows prefers winget, then choco, scoop.
	Never installs arbitrary user-supplied package names — only :class:`BinarySpec` fields.
	"""
	method = (method or "").lower().strip()
	try:
		if method == "winget" and spec.winget_id:
			return _run_pm(
				["winget", "install", "--id", spec.winget_id, "-e", "--accept-package-agreements",
				 "--accept-source-agreements"],
				label="winget",
			)
		if method == "choco" and spec.choco_id:
			return _run_pm(["choco", "install", spec.choco_id, "-y"], label="choco")
		if method == "scoop" and spec.scoop_id:
			return _run_pm(["scoop", "install", spec.scoop_id], label="scoop")
		if method == "brew" and spec.brew_id:
			return _run_pm(["brew", "install", spec.brew_id], label="brew")
		if method == "apt" and spec.apt_id:
			return _run_pm(
				["sudo", "apt-get", "install", "-y", spec.apt_id],
				label="apt",
			)
		if method == "pip" and spec.pip_id:
			return _run_pm(
				[sys.executable, "-m", "pip", "install", "-q", spec.pip_id],
				label="pip",
			)
		if method == "docs" or not method:
			url = spec.docs_url or "(no docs URL)"
			# Open docs in browser when possible (non-blocking, best-effort).
			try:
				import webbrowser

				if spec.docs_url:
					webbrowser.open(spec.docs_url)
			except Exception as exc:
				logger.debug("Could not open docs URL: %s", exc)
			return False, f"Opened docs: {url}. Install manually, then retry."
	except Exception as exc:
		logger.warning("Safe install of %s failed: %s", spec.name, exc)
		return False, str(exc)

	return False, f"No safe installer configured for method '{method}'."


def _run_pm(argv: list, *, label: str, timeout: int = 600) -> Tuple[bool, str]:
	"""Execute package-manager argv; require the binary to exist on PATH first."""
	exe = argv[0]
	if shutil.which(exe) is None and exe not in (sys.executable,):
		return False, f"'{exe}' not found on PATH; install {label} or use docs."
	logger.info("Running safe install: %s", " ".join(argv))
	try:
		proc = subprocess.run(
			argv,
			capture_output=True,
			text=True,
			timeout=timeout,
			shell=False,
			check=False,
		)
	except subprocess.TimeoutExpired:
		return False, f"{label} timed out after {timeout}s"
	except OSError as exc:
		return False, f"{label} could not start: {exc}"

	out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
	if proc.returncode == 0:
		return True, (out[:400] or f"{label} succeeded")
	return False, f"{label} exit {proc.returncode}: {out[:400]}"


def maybe_handle_missing_binary(
	error_text: str,
	*,
	handler: Optional[MissingBinaryHandler] = None,
	auto_yes: bool = False,
	yolo: bool = False,
	do_search: bool = False,
) -> Optional[HandleResult]:
	"""Convenience: return a :class:`HandleResult` only when a missing tool is detected."""
	if not is_missing_binary_error(error_text):
		return None
	h = handler or MissingBinaryHandler()
	return h.handle(error_text, auto_yes=auto_yes, yolo=yolo, do_search=do_search)
