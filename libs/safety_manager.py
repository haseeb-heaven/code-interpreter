import os
import re
import ast
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# =========================
# DATA CLASSES
# =========================
class SafetyLevel(str, Enum):
	STRICT = "strict"
	STANDARD = "standard"
	RELAXED = "relaxed"
	OFF = "off"


@dataclass
class SandboxContext:
	cwd: str
	env: dict
	timeout_seconds: int = 30


@dataclass
class Decision:
	allowed: bool
	reasons: list[str] = field(default_factory=list)


# RepairCircuitBreaker lives in libs.execution.repairer; re-exported here for
# backward-compatible imports (`from libs.safety_manager import RepairCircuitBreaker`).
from libs.execution.repairer import RepairCircuitBreaker  # noqa: E402


# =========================
# MAIN SAFETY MANAGER
# =========================
class ExecutionSafetyManager:

	SAFE_ENV_KEYS = [
		"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
		"TEMP", "TMP", "USERPROFILE", "HOME", "USERNAME",
		"TERM", "PYTHONIOENCODING",
	]

	# Artifact extensions that callers care about (plots, tables, reports)
	ARTIFACT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".md", ".csv", ".txt", ".html", ".json"}

	# Write-mode patterns that must be blocked in SAFE mode regardless of path.
	# BUG FIX #1: Removed bare r"\.write\s*\(" — it was far too broad and
	# blocked sys.stdout.write(), buf.write(), socket.write(), etc.
	# The open()-mode patterns below already catch file writes via open().
	# pathlib / JS / pandas patterns are kept as they are unambiguous.
	#
	# SYNTAX FIX: patterns containing a quote character class are written as
	# single-quoted raw strings  r'...'  so that ['"] is unambiguous.
	# Using r"...['\""]..." caused the bare trailing `"` to prematurely close
	# the outer double-quoted string → E999 SyntaxError at line 74.
	_WRITE_PATTERNS = [
		# open() explicit write modes — text and binary variants with optional '+'
		r'open\s*\([^)]*[\'"]w[btax]?\+?[\'"]',
		r'open\s*\([^)]*[\'"]a[btx]?\+?[\'"]',
		r'open\s*\([^)]*[\'"]x[bt]?\+?[\'"]',
		r'open\s*\([^)]*[\'"]r[bt]?\+[\'"]',
		# keyword mode= argument
		r'open\s*\([^)]*mode\s*=\s*[\'"]w[btax]?\+?',
		r'open\s*\([^)]*mode\s*=\s*[\'"]a[btx]?\+?',
		r'open\s*\([^)]*mode\s*=\s*[\'"]x[bt]?\+?',
		r'open\s*\([^)]*mode\s*=\s*[\'"]r[bt]?\+',
		# pathlib — unambiguous file-write APIs
		r"\.write_text\s*\(",
		r"\.write_bytes\s*\(",
		# Node.js filesystem writes
		r"\bwriteFile\s*\(",
		r"\bwriteFileSync\s*\(",
		r"\bappendFile\s*\(",
		r"\bappendFileSync\s*\(",
		# pandas / DataFrame export with path argument
		r'\.to_csv\s*\([^)]*[\'"/]',
		r'\.to_json\s*\([^)]*[\'"/]',
		r'\.to_html\s*\([^)]*[\'"/]',
		r'\.to_excel\s*\([^)]*[\'"/]',
		r'\.to_parquet\s*\([^)]*[\'"/]',
	]

	# BUG FIX (test_blocks_write_function_with_absolute_path):
	# When code opens a file handle (any mode, including 'r') and then calls
	# .write() on that handle, the operation must be blocked if the open()
	# references an absolute path.  We keep this pattern SEPARATE from
	# _WRITE_PATTERNS so it is only evaluated in the combined absolute-path
	# write check — preventing false positives like sys.stdout.write() on
	# purely relative / non-file code paths.
	_WRITE_ON_HANDLE_PATTERNS = [
		r"\.write\s*\(",
	]

	# Sensitive POSIX system path prefixes that are ALWAYS blocked (even for reads).
	_SENSITIVE_POSIX_PREFIXES = [
		r"/etc/\w+",
		r"/root/\w+",
		r"/proc/\w+",
		r"/sys/\w+",
		r"/dev/\w+",
		r"/boot/\w+",
	]

	_POSIX_SYSTEM_PREFIXES = [
		r"/etc/\w+",
		r"/tmp/\w+",
		r"/var/\w+",
		r"/usr/\w+",
		r"/root/\w+",
		r"/home/\w+/",
		r"/proc/\w+",
		r"/sys/\w+",
		r"/dev/\w+",
		r"/boot/\w+",
		r"/opt/\w+",
		r"/mnt/\w+",
		r"/media/\w+",
	]

	_WRITE_PATTERNS_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _WRITE_PATTERNS)
	_WRITE_ON_HANDLE_PATTERNS_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _WRITE_ON_HANDLE_PATTERNS)
	_SENSITIVE_POSIX_PREFIXES_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _SENSITIVE_POSIX_PREFIXES)
	_POSIX_SYSTEM_PREFIXES_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _POSIX_SYSTEM_PREFIXES)

	# Known-dangerous call targets for .remove() / .unlink() / .rmtree().
	_DANGEROUS_ATTR_OWNERS = frozenset({"os", "shutil", "pathlib", "path"})

	# =========================
	# FIX 1+5: Shared destructive patterns list.
	# Used by BOTH assess_execution() (safe-mode block) AND is_dangerous_operation()
	# (unsafe-mode warning). Keeping one source of truth prevents the regression
	# where system-destructive commands were in is_dangerous_operation() but NOT
	# in the safe-mode delete_patterns block inside assess_execution().
	#
	# BUG FIX #3: r"\bremove\(" replaced with r"os\.remove\s*\(" — the old
	# pattern fired on list.remove(), set.remove(), dict.remove(), etc.
	# Also dropped the leading \b because in raw strings (e.g. r"import os\nos.remove()")
	# the literal \n means 'n' precedes 'o' — both word chars — so \b never fires.
	# The dot anchor in "os\.remove" is already sufficient and more reliable.
	#
	# BUG FIX #3b: r"\bdelete\b" tightened to r"\bdelete\s+\S" to avoid
	# false-positives on SQL DELETE keyword used as a string literal in
	# data-analysis code (e.g. cursor.execute("DELETE FROM ...")).
	# =========================
	_DESTRUCTIVE_PATTERNS = [
		# Filesystem deletes
		r"\bunlink\b",
		r"\bunlinksync\b",
		r"os\.remove\s*\(",          # FIX: dropped leading \b — dot is sufficient anchor
		r"\brmtree\b",
		r"\bdel\s+",
		r"\brm\s+",
		r"\berase\s+",
		r"\bdelete\s+\S",            # FIX #3b: was r"\bdelete\b" — caught SQL literals
		r"\bremove-item\b",
		r"\brd\s+",
		r"\bshutil\.rmtree\b",
		r"\bos\.rmdir\b",
		# Destructive system commands
		r"\bshutdown\b",
		r"\breboot\b",
		r"\binit\s+0\b",
		r"\binit\s+6\b",
		r"\bmkfs\b",
		r"\bdd\s+if=",
		r"\bformat\s+[a-z]:",
		r"\bdiskpart\b",
	]

	# =========================
	# BUG FIX #2: Shell patterns now use re.search() with \b word boundaries
	# instead of plain `in` substring matching. Previously "bash" matched
	# any identifier containing "bash" (e.g. "rehash", "bashful").
	# =========================
	_SHELL_PATTERNS = [
		r"\bsubprocess\b",
		r"\bos\.system\b",
		r"\bpowershell\b",
		r"\bcmd\.exe\b",
		r"\bbash\b",
	]

	_DESTRUCTIVE_PATTERNS_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _DESTRUCTIVE_PATTERNS)
	_SHELL_PATTERNS_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _SHELL_PATTERNS)

	_NETWORK_PATTERNS = [
		r"\bsocket\b",
		r"\burllib\b",
		r"\brequests\b",
		r"\bhttp\.client\b",
		r"\bhttpx\b",
		r"\baiohttp\b",
		r"\bftplib\b",
	]
	_NETWORK_PATTERNS_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in _NETWORK_PATTERNS)

	def __init__(self, unsafe_mode: bool = False, safety_level: SafetyLevel | str | None = None):
		self._resolve_safety_level(unsafe_mode, safety_level)
		# B8: Absolute paths explicitly mentioned in the user task.
		self._user_intent_paths: List[str] = []

	def _resolve_safety_level(self, unsafe_mode: bool, safety_level: SafetyLevel | str | None) -> None:
		if safety_level is None:
			self.safety_level = SafetyLevel.OFF if unsafe_mode else SafetyLevel.STANDARD
		elif isinstance(safety_level, SafetyLevel):
			self.safety_level = safety_level
		else:
			try:
				self.safety_level = SafetyLevel(str(safety_level).lower())
			except (ValueError, TypeError, AttributeError):
				# Non-string mocks / unknown values -> safe default.
				self.safety_level = SafetyLevel.OFF if unsafe_mode else SafetyLevel.STANDARD
		# Legacy flag: only OFF disables all checks via unsafe_mode.
		if self.safety_level == SafetyLevel.OFF:
			self.unsafe_mode = True
		else:
			self.unsafe_mode = False

	def set_safety_level(self, safety_level: SafetyLevel | str | None) -> None:
		"""Update the active safety level in place (e.g. from ``/settings`` or
		``/safety <level>``). Without this, changing safety after startup only
		updated the CLI ``args`` object cosmetically — this instance, which
		every execution/safety check actually reads, never changed, so
		"safety=off" set mid-session kept blocking code as if still on the
		startup default (standard).
		"""
		self._resolve_safety_level(self.unsafe_mode, safety_level)

	# =========================
	# USER INTENT PATH TRACKING (B8)
	# =========================

	@staticmethod
	def extract_absolute_paths_from_text(text: str) -> List[str]:
		"""Return deduplicated absolute paths found in *text*."""
		import re as _re
		paths: List[str] = []
		seen: set = set()
		for m in _re.finditer(r"[a-zA-Z]:[\\/][^\s\"'<>|*?]+", text):
			p = m.group(0).rstrip(".,;:!)")
			if p not in seen:
				seen.add(p)
				paths.append(p)
		for m in _re.finditer(r"(?:^|[\s'\"(])(/[^\s\"'<>|*?:]{2,})", text, _re.MULTILINE):
			p = m.group(1).rstrip(".,;:!)")
			if p not in seen:
				seen.add(p)
				paths.append(p)
		return paths

	def set_user_intent_paths(self, task_text: str) -> None:
		"""Extract and remember absolute paths from the user task description."""
		self._user_intent_paths = self.extract_absolute_paths_from_text(task_text or "")

	def _is_user_intent_path(self, code: str) -> bool:
		"""True when every absolute path in *code* was mentioned in the task."""
		if not self._user_intent_paths:
			return False
		code_paths = self.extract_absolute_paths_from_text(code)
		if not code_paths:
			return False
		intent_lower = [p.lower() for p in self._user_intent_paths]
		for cp in code_paths:
			cp_low = cp.lower()
			if not any(cp_low.startswith(ip) or ip.startswith(cp_low) for ip in intent_lower):
				return False
		return True

	# =========================
	# AST CHECK (PYTHON ONLY)
	# =========================
	def _ast_check(self, code: str) -> list[str]:
		reasons = []
		try:
			tree = ast.parse(code)
		except Exception:
			return reasons

		for node in ast.walk(tree):
			if isinstance(node, ast.Call):

				if isinstance(node.func, ast.Attribute):
					attr = node.func.attr
					if attr in ("remove", "unlink", "rmtree"):
						owner_name = ""
						if isinstance(node.func.value, ast.Name):
							owner_name = node.func.value.id.lower()
						elif isinstance(node.func.value, ast.Attribute):
							owner_name = node.func.value.attr.lower()
						if owner_name in self._DANGEROUS_ATTR_OWNERS or owner_name == "":
							reasons.append(f"AST: deletion blocked ({owner_name or 'unknown'}.{attr}).")

				# getattr obfuscation
				if isinstance(node.func, ast.Name) and node.func.id == "getattr":
					if len(node.args) >= 2:
						if isinstance(node.args[1], ast.Constant):
							if node.args[1].value in ["remove", "unlink", "rmtree"]:
								reasons.append("AST: obfuscated deletion blocked.")

				# eval / exec
				if isinstance(node.func, ast.Name):
					if node.func.id in ["eval", "exec"]:
						reasons.append("AST: dynamic execution blocked.")

		return reasons

	# =========================
	# WRITE DETECTION (GLOBAL)
	# =========================
	def _has_write_operation(self, code: str) -> bool:
		"""Return True if *code* contains any write operation that must be
		blocked in SAFE mode.
		"""
		return any(p.search(code) for p in self._WRITE_PATTERNS_COMPILED)

	# =========================
	# WRITE-ON-HANDLE DETECTION
	# Only used when code is already known to reference an absolute path.
	# Catches: open('C:\\file', 'r') followed by f.write('data')
	# Without triggering on sys.stdout.write() in safe relative-path code.
	# =========================
	def _has_write_on_handle(self, code: str) -> bool:
		"""Return True if *code* calls .write() on any object (handle check).
		This is intentionally only evaluated when an absolute path is present.
		"""
		return any(p.search(code) for p in self._WRITE_ON_HANDLE_PATTERNS_COMPILED)

	# =========================
	# HOST ABSOLUTE PATH CHECK
	# =========================
	def _is_host_absolute_path(self, code: str) -> bool:
		"""Return True if *code* references a host absolute path."""
		# Windows drive-letter path
		if re.search(r"[a-z]:[\\/]", code.lower()):
			return True

		# Quoted POSIX absolute path: '/...' or "/..."
		if re.search(r"""["']/[^"'\s]""", code):
			return True

		# Unquoted well-known POSIX system directory prefixes
		if any(p.search(code) for p in self._POSIX_SYSTEM_PREFIXES_COMPILED):
			return True

		# open() call whose first positional argument is an absolute path string
		open_args = re.findall(r"open\s*\(\s*([\"'][^\"']+[\"'])", code, re.IGNORECASE)
		for arg in open_args:
			path = arg.strip("'\"")
			if path.startswith("/") or re.match(r"[a-zA-Z]:[\\/]", path):
				return True

		return False

	def _is_sensitive_posix_path(self, code: str) -> bool:
		"""Return True if *code* references a sensitive POSIX system path."""
		return any(p.search(code) for p in self._SENSITIVE_POSIX_PREFIXES_COMPILED)

	# =========================
	# MAIN CHECK
	# =========================
	def assess_execution(self, code: str, mode: str) -> Decision:
		if not code or not code.strip():
			return Decision(False, ["Empty content"])

		code_lower = code.lower()

		#  HARD BLOCK WINDOWS RECURSIVE DELETE (CRITICAL FIX)
		if re.search(r"\brd\s+/s\s+/q\b", code_lower):
			return Decision(False, ["Recursive deletion is blocked."])

		# Path ignore file — always evaluated (even in relaxed) for protected paths.
		try:
			from libs.security.path_ignore import code_references_protected_path

			protected = code_references_protected_path(code)
			if protected and self.safety_level != SafetyLevel.OFF:
				msg = f"Protected path access blocked: {protected[0]}"
				if self.safety_level == SafetyLevel.RELAXED:
					return Decision(True, [msg])
				return Decision(False, [msg])
		except Exception:
			pass

		# OFF — no blocking
		if self.safety_level == SafetyLevel.OFF:
			warnings = []
			if self.is_dangerous_operation(code):
				warnings.append("Dangerous operation detected")
			return Decision(True, warnings)

		# Legacy unsafe_mode without explicit level (should be rare after __init__ sync)
		if self.unsafe_mode and self.safety_level == SafetyLevel.STANDARD:
			warnings = []
			if self.is_dangerous_operation(code):
				warnings.append("Dangerous operation detected")
			return Decision(True, warnings)

		# RELAXED — warn only
		if self.safety_level == SafetyLevel.RELAXED:
			warnings = []
			if self.is_dangerous_operation(code):
				warnings.append("Dangerous operation detected")
			if any(p.search(code_lower) for p in self._SHELL_PATTERNS_COMPILED):
				warnings.append("Shell execution detected")
			return Decision(True, warnings)

		# STRICT — pure computation: no network, no writes, no shell
		if self.safety_level == SafetyLevel.STRICT:
			if any(p.search(code_lower) for p in self._NETWORK_PATTERNS_COMPILED):
				return Decision(False, ["Network access blocked (strict safety)."])
			if any(p.search(code_lower) for p in self._SHELL_PATTERNS_COMPILED):
				return Decision(False, ["Shell execution is blocked (strict safety)."])
			if self._has_write_operation(code):
				return Decision(False, ["File writes blocked (strict safety)."])
			ast_reasons = self._ast_check(code)
			if ast_reasons:
				return Decision(False, ast_reasons)
			if self.is_dangerous_operation(code):
				return Decision(False, ["Destructive operation blocked (strict safety)."])
			return Decision(True, [])

		# =========================
		# STANDARD (default) — existing behavior
		# =========================
		ast_reasons = self._ast_check(code)
		if ast_reasons:
			return Decision(False, ast_reasons)

		# =========================
		# GLOBAL WRITE BLOCK
		# Allow through when the user explicitly requested an absolute write (B8).
		# =========================
		if self._has_write_operation(code):
			if (
				self._is_host_absolute_path(code)
				and not self._is_sensitive_posix_path(code)
				and self._is_user_intent_path(code)
			):
				pass  # Intent-based absolute write -- proceed to path-level checks below.
			else:
				return Decision(False, ["Write blocked (read-only mode)."])

		# =========================
		# DESTRUCTIVE OPERATION BLOCK (unified)
		# Uses _DESTRUCTIVE_PATTERNS which includes system-level commands
		# (shutdown, reboot, mkfs, dd, format, diskpart) in addition to
		# filesystem deletes.
		# =========================
		if any(p.search(code_lower) for p in self._DESTRUCTIVE_PATTERNS_COMPILED):
			return Decision(False, ["Destructive operation blocked."])

		# =========================
		# SHELL BLOCK
		# BUG FIX #2: Uses _SHELL_PATTERNS with \b word-boundary regex instead
		# of plain substring `in` check to avoid false positives.
		# =========================
		if any(p.search(code_lower) for p in self._SHELL_PATTERNS_COMPILED):
			return Decision(False, ["Shell execution is blocked."])

		# =========================
		# FILESYSTEM / HOST PATH BLOCK
		# =========================
		if self._is_sensitive_posix_path(code):
			return Decision(False, ["Host filesystem access blocked (sensitive system path)."])

		# Block absolute path writes unless the user explicitly asked for the path (B8).
		if self._is_host_absolute_path(code) and (
			self._has_write_operation(code) or self._has_write_on_handle(code)
		):
			if self._is_sensitive_posix_path(code):
				return Decision(False, ["Host filesystem access blocked (sensitive system path write)."])
			if self._is_user_intent_path(code):
				pass  # User explicitly asked for this path.
			else:
				return Decision(False, ["Host filesystem access blocked (absolute path write)."])

		# =========================
		# COMMAND MODE RULE
		# =========================
		if mode == "command" and "\n" in code.strip():
			return Decision(False, ["Command must be single line."])

		return Decision(True, [])

	# =========================
	# DANGEROUS OPERATION DETECTION
	# Delegates to shared _DESTRUCTIVE_PATTERNS constant.
	# =========================
	def is_dangerous_operation(self, code: str) -> bool:
		"""
		Check if the code contains dangerous operations that require user confirmation.
		Returns True if dangerous patterns are detected.
		"""
		if not code or not code.strip():
			return False
		code_lower = code.lower()
		return any(p.search(code_lower) for p in self._DESTRUCTIVE_PATTERNS_COMPILED)

	# =========================
	# ARTIFACT EXPORT
	# =========================
	def export_artifacts(
		self,
		context: "SandboxContext | None",
		dest_dir: Optional[str] = None,
	) -> Dict[str, str]:
		"""Copy generated artifact files out of the sandbox before cleanup."""
		if not context or not context.cwd or not os.path.isdir(context.cwd):
			return {}

		if dest_dir is None:
			dest_dir = tempfile.mkdtemp(prefix="ci_artifacts_")

		os.makedirs(dest_dir, exist_ok=True)

		exported: Dict[str, str] = {}

		try:
			for fname in os.listdir(context.cwd):
				src = os.path.join(context.cwd, fname)

				if os.path.islink(src):
					continue

				if not os.path.isfile(src):
					continue

				_, ext = os.path.splitext(fname)
				if ext.lower() not in self.ARTIFACT_EXTENSIONS:
					continue

				dst_base = os.path.join(dest_dir, fname)
				dst = dst_base
				counter = 1
				while os.path.exists(dst):
					base, file_ext = os.path.splitext(dst_base)
					dst = f"{base}_{counter}{file_ext}"
					counter += 1

				try:
					shutil.copy2(src, dst, follow_symlinks=False)
					exported[fname] = dst
				except Exception:
					pass
		except Exception:
			pass

		return exported

	# =========================
	# REAL SANDBOX
	# =========================
	def build_sandbox_context(self, timeout_seconds: int | None = None) -> SandboxContext:
		env = {}

		for key in self.SAFE_ENV_KEYS:
			val = os.getenv(key)
			if val:
				env[key] = val

		env["PYTHONIOENCODING"] = "utf-8"

		cwd = tempfile.mkdtemp(prefix="ci_sandbox_")
		timeout = 30 if timeout_seconds is None else int(timeout_seconds)

		# B7: Point config dirs at sandbox temp to isolate from host HOME.
		env["HOME"] = cwd
		env["USERPROFILE"] = cwd
		_mpl = os.path.join(cwd, ".matplotlib")
		os.makedirs(_mpl, exist_ok=True)
		env["MPLCONFIGDIR"] = _mpl
		_plotly = os.path.join(cwd, ".plotly")
		os.makedirs(_plotly, exist_ok=True)
		env["PLOTLY_DIR"] = _plotly
		_xdg = os.path.join(cwd, ".config")
		os.makedirs(_xdg, exist_ok=True)
		env["XDG_CONFIG_HOME"] = _xdg

		return SandboxContext(
			cwd=cwd,
			env=env,
			timeout_seconds=timeout,
		)

	def cleanup_sandbox_context(self, context: "SandboxContext | None"):
		if context and context.cwd and os.path.exists(context.cwd):
			shutil.rmtree(context.cwd, ignore_errors=True)
