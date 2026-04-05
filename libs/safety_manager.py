import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

from libs.logger import Logger


@dataclass
class SandboxContext:
	cwd: str
	env: dict
	timeout_seconds: int = 30


@dataclass
class SafetyDecision:
	allowed: bool
	reasons: list[str] = field(default_factory=list)


@dataclass
class RepairCircuitBreaker:
	max_attempts: int = 2
	seen_errors: set[str] = field(default_factory=set)
	attempts: int = 0

	def should_continue(self, error_text: str) -> bool:
		"""
		Decides whether another repair attempt should be made for the given error.
		
		Normalizes the provided error text to determine uniqueness. If the maximum number
		of attempts has been reached or the normalized non-empty error has been seen
		before, no further attempts are allowed. Otherwise the normalized error (when
		non-empty) is recorded and the attempt count is incremented.
		
		Parameters:
			error_text (str): Raw error message used to assess uniqueness for retries.
		
		Returns:
			bool: `True` if a new attempt is permitted, `False` otherwise.
		"""
		normalized = self._normalize_error(error_text)
		if self.attempts >= self.max_attempts:
			return False
		if normalized and normalized in self.seen_errors:
			return False
		if normalized:
			self.seen_errors.add(normalized)
		self.attempts += 1
		return True

	@staticmethod
	def _normalize_error(error_text: str) -> str:
		"""
		Normalize an error message string for comparison by trimming, lowercasing, and collapsing internal whitespace.
		
		Parameters:
			error_text (str): The input error text; may be None or empty.
		
		Returns:
			normalized (str): The normalized error text with surrounding whitespace removed, all characters lowercased, and all runs of internal whitespace replaced by single spaces. If input is None or empty, returns an empty string.
		"""
		error_text = (error_text or "").strip().lower()
		error_text = re.sub(r"\s+", " ", error_text)
		return error_text


class ExecutionSafetyManager:
	SAFE_ENV_KEYS = [
		"PATH",
		"PATHEXT",
		"SYSTEMROOT",
		"WINDIR",
		"COMSPEC",
		"TEMP",
		"TMP",
		"USERPROFILE",
		"HOME",
		"USERNAME",
		"TERM",
		"PYTHONIOENCODING",
	]

	DANGEROUS_PATTERNS = [
		(r"\brm\s+-rf\b", "Recursive deletion is blocked."),
		(r"\bdel\s+/(?:f|q|s)", "Destructive delete command is blocked."),
		(r"\brmdir\s+/(?:s|q)", "Recursive directory removal is blocked."),
		(r"\brd\s+/s\s+/q\b", "Recursive directory removal is blocked."),
		(r"Remove-Item\s+.+-Recurse", "Recursive PowerShell deletion is blocked."),
		(r"\bformat\s+[a-z]:", "Disk formatting is blocked."),
		(r"\bmkfs\b", "Filesystem formatting is blocked."),
		(r"\bshutdown\b", "System shutdown commands are blocked."),
		(r"\breboot\b", "System reboot commands are blocked."),
		(r"\bpoweroff\b", "System power commands are blocked."),
		(r"\breg\s+delete\b", "Registry deletion is blocked."),
		(r"\bcipher\s+/w\b", "Secure wipe commands are blocked."),
		(r"\bdiskpart\b", "Disk management commands are blocked."),
		(r"shutil\.rmtree\s*\(", "Recursive directory deletion in code is blocked."),
		(r"os\.remove\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Deleting absolute-path files is blocked."),
		(r"os\.rmdir\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Removing absolute-path directories is blocked."),
		(r"subprocess\.(?:run|Popen)\s*\(.+(?:rm -rf|shutdown|format)", "Dangerous subprocess invocation is blocked."),
	]

	def __init__(self):
		"""
		Initialize the ExecutionSafetyManager and configure its logger.
		
		Sets up an instance-level logger that writes to logs/interpreter.log and assigns it to `self.logger`.
		"""
		self.logger = Logger.initialize("logs/interpreter.log")

	def build_sandbox_context(self) -> SandboxContext:
		"""
		Create a new sandboxed execution context with a temporary working directory and a restricted environment.
		
		The returned SandboxContext contains a newly created temporary directory as `cwd`, an `env` mapping that includes only allowed environment variables plus `PYTHONIOENCODING="utf-8"`, and a default `timeout_seconds` of 30.
		
		Returns:
			SandboxContext: The sandbox context with `cwd` (temporary directory path), `env` (whitelisted environment variables and `PYTHONIOENCODING`), and `timeout_seconds` set to 30.
		"""
		env = {}
		for key in self.SAFE_ENV_KEYS:
			if os.getenv(key):
				env[key] = os.getenv(key)
		env["PYTHONIOENCODING"] = "utf-8"
		cwd = tempfile.mkdtemp(prefix="interpreter-sandbox-")
		self.logger.info(f"Created sandbox context at '{cwd}'")
		return SandboxContext(cwd=cwd, env=env, timeout_seconds=30)

	def cleanup_sandbox_context(self, context: SandboxContext | None):
		"""
		Recursively remove the sandbox working directory if it exists.
		
		If `context` is provided and `context.cwd` points to an existing directory, that directory
		and its contents are removed. Errors during removal are ignored. If `context` is `None`,
		`context.cwd` is falsy, or the path does not exist, the function does nothing.
		
		Parameters:
			context (SandboxContext | None): Sandbox context containing the `cwd` to delete.
		"""
		if context and context.cwd and os.path.exists(context.cwd):
			shutil.rmtree(context.cwd, ignore_errors=True)

	def assess_execution(self, content: str, mode: str) -> SafetyDecision:
		"""
		Evaluate whether generated content is safe to execute in the sandbox.
		
		Checks that `content` is non-empty, rejects inputs that match the manager's configured dangerous patterns, and enforces mode-specific constraints (for `mode == "command"`, the content must be a single command line).
		
		Parameters:
			content (str): The generated text to assess.
			mode (str): Execution mode; `"command"` requires a single-line command, other values impose only pattern-based checks.
		
		Returns:
			SafetyDecision: `allowed` is `True` when no safety violations were found; `reasons` lists detected issues (e.g., empty output, matched dangerous patterns, or multi-line command in command mode).
		"""
		if not content or not content.strip():
			return SafetyDecision(False, ["Generated output is empty."])

		reasons = []
		for pattern, reason in self.DANGEROUS_PATTERNS:
			if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
				reasons.append(reason)

		if mode == "command":
			stripped = content.strip()
			if "\n" in stripped:
				reasons.append("Command mode must execute a single command line.")

		return SafetyDecision(not reasons, reasons)
