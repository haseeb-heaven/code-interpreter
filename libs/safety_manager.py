import os
import re
import ast
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List


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

				# delete functions
				if isinstance(node.func, ast.Attribute):
					if node.func.attr in ["remove", "unlink", "rmtree"]:
						reasons.append("AST: deletion blocked.")

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
		# FILESYSTEM RULES
		# =========================
		# Detect Windows drive-letter paths (e.g., C:\) OR POSIX absolute paths (e.g., /tmp/)
		is_path_access = bool(re.search(r"[a-z]:[\\/]", code_lower))

		# Detect POSIX absolute paths in quoted strings  e.g. open('/etc/passwd')
		if not is_path_access:
			is_path_access = bool(re.search(r'''["']/[^"'\s]''', code))

		# Bug #5 fix: detect unquoted POSIX absolute paths — e.g. /etc/passwd, /tmp/x
		# These bypassed the quoted-string check above.
		if not is_path_access:
			posix_absolute_patterns = [
				r"/etc/\w+",
				r"/tmp/\w+",
				r"/var/\w+",
				r"/usr/\w+",
				r"/root/\w+",
				r"/home/\w+/",
				r"/proc/\w+",
				r"/sys/\w+",
				r"/dev/\w+",
			]
			if any(re.search(p, code, re.IGNORECASE) for p in posix_absolute_patterns):
				return Decision(False, ["Host filesystem access blocked (absolute path)."])

		# Check open() calls for absolute path arguments
		if not is_path_access:
			open_calls = re.findall(r'open\s*\(\s*(["\'][^"\']+["\'])', code, re.IGNORECASE)
			for path_match in open_calls:
				path = path_match.strip('\'"')
				if path.startswith('/') or re.match(r'[a-zA-Z]:[\\/]', path):
					is_path_access = True
					break

		if is_path_access:

			# =========================
			#  HANDLE open() PROPERLY
			# =========================
			open_calls = re.findall(r'(open\s*\(.*?\)|\.open\s*\(.*?\))', code, re.IGNORECASE)

			for call in open_calls:
				call_lower = call.lower()

				#  WRITE MODES → BLOCK
				if ("'w'" in call_lower or '"w"' in call_lower or
					"'a'" in call_lower or '"a"' in call_lower or
					"'x'" in call_lower or '"x"' in call_lower):
					return Decision(False, ["Write blocked (read-only mode)."])

			# =========================
			#  BLOCK WRITE FUNCTIONS
			# =========================
			if ("write(" in code_lower or
				"save(" in code_lower or
				"dump(" in code_lower or
				"to_csv" in code_lower or
				"to_json" in code_lower):
				return Decision(False, ["Write blocked (read-only mode)."])

			# =========================
			#  BLOCK DELETE
			# =========================
			if ("remove" in code_lower or
				"unlink" in code_lower or
				"del " in code_lower or
				"rm " in code_lower or
				"rmtree" in code_lower):
				return Decision(False, ["Filesystem delete blocked."])

			#  OTHERWISE → READ → ALLOWED

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
		]
		
		return any(re.search(p, code_lower) for p in dangerous_patterns)

	# =========================
	# ARTIFACT EXPORT  (Bug #3 fix)
	# =========================
	def export_artifacts(self, context: "SandboxContext | None", dest_dir: str | None = None) -> Dict[str, str]:
		"""Copy generated artifact files out of the sandbox before cleanup.

		Scans *context.cwd* for files whose extension is in ARTIFACT_EXTENSIONS
		and copies them to *dest_dir* (defaults to the current working directory).

		Returns a mapping of ``{original_filename: dest_path}`` for every file
		that was successfully exported.  Returns an empty dict when *context* is
		``None`` or the sandbox directory no longer exists.
		"""
		if not context or not context.cwd or not os.path.isdir(context.cwd):
			return {}

		if dest_dir is None:
			dest_dir = os.getcwd()

		exported: Dict[str, str] = {}

		try:
			for fname in os.listdir(context.cwd):
				_, ext = os.path.splitext(fname)
				if ext.lower() not in self.ARTIFACT_EXTENSIONS:
					continue
				src = os.path.join(context.cwd, fname)
				dst = os.path.join(dest_dir, fname)
				try:
					shutil.copy2(src, dst)
					exported[fname] = dst
				except Exception:
					# Best-effort: log but don't crash
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
