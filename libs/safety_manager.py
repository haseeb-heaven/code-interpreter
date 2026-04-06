import os
import re
import ast
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# =========================
# DATA CLASSES
# =========================
@dataclass
class SandboxContext:
	cwd: str
	env: dict
	timeout_seconds: int = 30


@dataclass
class Decision:
	allowed: bool
	reasons: list[str] = field(default_factory=list)


@dataclass
class RepairCircuitBreaker:
	max_attempts: int = 3
	attempts: int = 0
	seen_errors: set[str] = field(default_factory=set)

	def should_continue(self, error_text: str) -> bool:
		normalized = self._normalize_error(error_text)

		#  stop if same error repeated
		if normalized in self.seen_errors:
			return False

		#  stop if max attempts reached
		if self.attempts >= self.max_attempts:
			return False

		self.seen_errors.add(normalized)
		self.attempts += 1
		return True

	def _normalize_error(self, error_text: str) -> str:
		error_text = (error_text or "").strip().lower()
		error_text = re.sub(r"\s+", " ", error_text)
		return error_text


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
	# These cover:
	#   open(..., 'w')   open(..., 'wb')  open(..., 'wa')  open(..., 'wt')
	#   open(..., 'ab')  open(..., 'xb')  open(..., mode='w')  etc.
	#   open(..., 'w+')  open(..., 'r+')  open(..., 'rb+')     (read-write)
	#   Path.write_text()  Path.write_bytes()       (pathlib)
	#   fs.writeFile()     fs.writeFileSync()       (Node.js)
	#   df.to_csv(path)    df.to_json(path)  df.to_html(path)  (pandas)
	_WRITE_PATTERNS = [
		# open() explicit write modes — text and binary variants with optional '+'
		r"open\s*\([^)]*['\"]w[btax]?\+?['\"]" ,  # 'w', 'wb', 'wt', 'wa', 'wx', 'w+', 'wb+', 'wt+', 'wa+', 'wx+'
		r"open\s*\([^)]*['\"]a[btx]?\+?['\"]"  ,  # 'a', 'ab', 'at', 'a+', 'ab+', 'at+', 'ax+'
		r"open\s*\([^)]*['\"]x[bt]?\+?['\"]"   ,  # 'x', 'xb', 'xt', 'x+', 'xb+', 'xt+'
		r"open\s*\([^)]*['\"]r[bt]?\+['\"]"    ,  # 'r+', 'rb+', 'rt+' (read-write modes)
		# keyword mode= argument
		r"open\s*\([^)]*mode\s*=\s*['\"]w[btax]?\+?"  ,  # mode='w', mode="wb", mode='w+', mode='wb+', …
		r"open\s*\([^)]*mode\s*=\s*['\"]a[btx]?\+?"  ,  # mode='a', mode='a+', mode='ab+', …
		r"open\s*\([^)]*mode\s*=\s*['\"]x[bt]?\+?"  ,  # mode='x', mode='x+', mode='xb+', …
		r"open\s*\([^)]*mode\s*=\s*['\"]r[bt]?\+"  ,  # mode='r+', mode='rb+', mode='rt+'
		# pathlib — Path.write_text() / write_bytes()
		r"\.write_text\s*\(",
		r"\.write_bytes\s*\(",
		# Node.js filesystem writes
		r"\bwriteFile\s*\(",
		r"\bwriteFileSync\s*\(",
		r"\bappendFile\s*\(",
		r"\bappendFileSync\s*\(",
		# pandas / DataFrame export with path argument
		r"\.to_csv\s*\([^)]*['\"/]",   # to_csv('some/path') or to_csv("/abs")
		r"\.to_json\s*\([^)]*['\"/]",
		r"\.to_html\s*\([^)]*['\"/]",
		r"\.to_excel\s*\([^)]*['\"/]",
		r"\.to_parquet\s*\([^)]*['\"/]",
	]

	# Sensitive POSIX system path prefixes that are ALWAYS blocked (even for reads).
	# These expose credentials, secrets, kernel internals, or device nodes.
	_SENSITIVE_POSIX_PREFIXES = [
		r"/etc/\w+",
		r"/root/\w+",
		r"/proc/\w+",
		r"/sys/\w+",
		r"/dev/\w+",
		r"/boot/\w+",
	]

	# Known-dangerous call targets for .remove() / .unlink() / .rmtree().
	# Used by _ast_check to avoid blocking list.remove(), dict.pop(), etc.
	_DANGEROUS_ATTR_OWNERS = frozenset({"os", "shutil", "pathlib", "path"})

	def __init__(self, unsafe_mode: bool = False):
		self.unsafe_mode = unsafe_mode

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

				# Narrow deletion check to known-dangerous call targets only.
				# This avoids false positives on e.g. list.remove("item") or
				# custom_obj.unlink() that are unrelated to filesystem ops.
				if isinstance(node.func, ast.Attribute):
					attr = node.func.attr
					if attr in ("remove", "unlink", "rmtree"):
						# Only block when the object is a known-dangerous module/type
						owner_name = ""
						if isinstance(node.func.value, ast.Name):
							owner_name = node.func.value.id.lower()
						elif isinstance(node.func.value, ast.Attribute):
							owner_name = node.func.value.attr.lower()
						if owner_name in self._DANGEROUS_ATTR_OWNERS or owner_name == "":
							# Empty owner means bare Path().unlink() style — block it
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
		blocked in SAFE mode.  Covers binary open() modes, pathlib, Node.js,
		and pandas export helpers — patterns that the old open()-only check
		missed entirely.
		"""
		return any(re.search(p, code, re.IGNORECASE) for p in self._WRITE_PATTERNS)

	# =========================
	# HOST ABSOLUTE PATH CHECK
	# =========================
	def _is_host_absolute_path(self, code: str) -> bool:
		"""Return True if *code* references a host absolute path.

		Covers:
		- Windows drive-letter paths: C:\\ or C:/
		- POSIX absolute paths in quoted strings: open('/etc/passwd')
		- Unquoted well-known POSIX system paths: /etc/passwd, /tmp/x
		- open() calls whose first arg is an absolute path
		"""
		# Windows drive-letter path
		if re.search(r"[a-z]:[\\/]", code.lower()):
			return True

		# Quoted POSIX absolute path: '/...' or "/..."
		if re.search(r"""["']/[^"'\s]""", code):
			return True

		# Unquoted well-known POSIX system directory prefixes
		_posix_system_prefixes = [
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
		if any(re.search(p, code, re.IGNORECASE) for p in _posix_system_prefixes):
			return True

		# open() call whose first positional argument is an absolute path string
		open_args = re.findall(r"open\s*\(\s*([\"'][^\"']+[\"'])", code, re.IGNORECASE)
		for arg in open_args:
			path = arg.strip("'\"")
			if path.startswith("/") or re.match(r"[a-zA-Z]:[\\/]", path):
				return True

		return False

	def _is_sensitive_posix_path(self, code: str) -> bool:
		"""Return True if *code* references a sensitive POSIX system path.

		These paths expose credentials, kernel internals, or device nodes and
		must be blocked even for read-only access (unlike general absolute paths
		which are only blocked when paired with write operations).
		"""
		return any(re.search(p, code, re.IGNORECASE) for p in self._SENSITIVE_POSIX_PREFIXES)

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

		#  UNSAFE MODE - still detect dangerous operations but allow with warnings
		if self.unsafe_mode:
			warnings = []
			if self.is_dangerous_operation(code):
				warnings.append("Dangerous operation detected")
			return Decision(True, warnings)

		# =========================
		# AST BLOCK
		# =========================
		ast_reasons = self._ast_check(code)
		if ast_reasons:
			return Decision(False, ast_reasons)

		# =========================
		# GLOBAL WRITE BLOCK
		# Catches binary/pathlib/JS/pandas write bypasses that the old
		# is_path_access-gated open()-only check missed entirely.
		# =========================
		if self._has_write_operation(code):
			return Decision(False, ["Write blocked (read-only mode)."])

		# =========================
		# DELETE BLOCK (STRICT)
		# =========================
		delete_patterns = [
			r"\bunlink\b",
			r"\bunlinksync\b",
			r"\bremove\(",
			r"\bos\.remove\b",
			r"\brmtree\b",
			r"\bdel\s+",
			r"\brm\s+",
			r"\berase\s+",
			r"\bdelete\b",
			r"\bremove-item\b",
			r"\brd\s+",
		]

		if any(re.search(p, code_lower) for p in delete_patterns):
			return Decision(False, ["Deletion operations are strictly blocked."])

		# =========================
		# SHELL BLOCK
		# =========================
		shell_patterns = [
			"subprocess",
			"os.system",
			"powershell",
			"cmd.exe",
			"bash",
		]

		if any(p in code_lower for p in shell_patterns):
			return Decision(False, ["Shell execution is blocked."])

		# =========================
		# FILESYSTEM / HOST PATH BLOCK
		#
		# Sensitive system paths (/etc, /root, /proc, /sys, /dev, /boot) are
		# ALWAYS blocked — even for read-only access — because they expose
		# credentials, secrets, and kernel internals.
		#
		# General absolute paths (Windows drive letters, /tmp, /home, etc.)
		# are only blocked when a write operation is also present.  Pure
		# read-only access to absolute paths is permitted so that legitimate
		# tasks like reading a user-supplied data file are not rejected.
		# =========================
		if self._is_sensitive_posix_path(code):
			return Decision(False, ["Host filesystem access blocked (sensitive system path)."])

		if self._is_host_absolute_path(code) and self._has_write_operation(code):
			return Decision(False, ["Host filesystem access blocked (absolute path write)."])

		# =========================
		# COMMAND MODE RULE
		# =========================
		if mode == "command" and "\n" in code.strip():
			return Decision(False, ["Command must be single line."])

		return Decision(True, [])

	# =========================
	# DANGEROUS OPERATION DETECTION
	# =========================
	def is_dangerous_operation(self, code: str) -> bool:
		"""
		Check if the code contains dangerous operations that require user confirmation.
		Returns True if dangerous patterns are detected.
		"""
		if not code or not code.strip():
			return False
		
		code_lower = code.lower()
		
		dangerous_patterns = [
			r"\bunlink\b",
			r"\bunlinksync\b",
			r"\bremove\(",
			r"\bos\.remove\b",
			r"\brmtree\b",
			r"\bdel\s+",
			r"\brm\s+",
			r"\berase\s+",
			r"\bdelete\b",
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
		]
		
		return any(re.search(p, code_lower) for p in dangerous_patterns)

	# =========================
	# ARTIFACT EXPORT  (Critical #2 fix)
	# =========================
	def export_artifacts(
		self,
		context: "SandboxContext | None",
		dest_dir: Optional[str] = None,
	) -> Dict[str, str]:
		"""Copy generated artifact files out of the sandbox before cleanup.

		Scans *context.cwd* for files whose extension is in ARTIFACT_EXTENSIONS
		and copies them to *dest_dir*.

		Security hardening (Critical #2):
		- dest_dir defaults to a fresh temporary directory, NOT os.getcwd().
		  Using os.getcwd() allowed sandbox code to plant a symlink that
		  shutil.copy2 would follow, overwriting arbitrary host files.
		- Source symlinks are skipped unconditionally (islink guard).
		- Only regular files are copied (isfile guard).
		- Destination names are collision-safe (fname_1.ext, fname_2.ext …).
		- shutil.copy2 is called with follow_symlinks=False so the copy
		  itself never follows a symlink even if one slips through.

		Returns a mapping of {original_filename: dest_path} for every file
		that was successfully exported.  Returns an empty dict when *context*
		is None or the sandbox directory no longer exists.
		"""
		if not context or not context.cwd or not os.path.isdir(context.cwd):
			return {}

		# Default to a fresh isolated temp dir — never the host cwd.
		if dest_dir is None:
			dest_dir = tempfile.mkdtemp(prefix="ci_artifacts_")

		os.makedirs(dest_dir, exist_ok=True)

		exported: Dict[str, str] = {}

		try:
			for fname in os.listdir(context.cwd):
				src = os.path.join(context.cwd, fname)

				# Skip symlinks — a malicious script could plant one pointing
				# to /etc/passwd or any other host file.
				if os.path.islink(src):
					continue

				# Skip non-regular files (dirs, device nodes, pipes, …)
				if not os.path.isfile(src):
					continue

				_, ext = os.path.splitext(fname)
				if ext.lower() not in self.ARTIFACT_EXTENSIONS:
					continue

				# Collision-safe destination: fname.ext → fname_1.ext → fname_2.ext
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
					# Best-effort: skip files that cannot be copied
					pass
		except Exception:
			pass

		return exported

	# =========================
	# REAL SANDBOX
	# =========================
	def build_sandbox_context(self) -> SandboxContext:
		env = {}

		for key in self.SAFE_ENV_KEYS:
			val = os.getenv(key)
			if val:
				env[key] = val

		env["PYTHONIOENCODING"] = "utf-8"

		cwd = tempfile.mkdtemp(prefix="ci_sandbox_")

		return SandboxContext(
			cwd=cwd,
			env=env,
			timeout_seconds=30
		)

	def cleanup_sandbox_context(self, context: "SandboxContext | None"):
		if context and context.cwd and os.path.exists(context.cwd):
			shutil.rmtree(context.cwd, ignore_errors=True)
