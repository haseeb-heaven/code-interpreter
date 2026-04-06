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
	max_attempts: int = 3
	seen_errors: set[str] = field(default_factory=set)
	attempts: int = 0

	def should_continue(self, error_text: str) -> bool:
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
		(r"\brm\s+/", "Absolute-path deletion is blocked."),
		(r"\bdel\s+/(?:f|q|s)", "Destructive delete command is blocked."),
		(r"\bdel\s+[A-Za-z]:(?:\\\\|/)", "Absolute-path deletion is blocked."),
		# Block quoted absolute-path del (e.g. del "D:\Temp\*.txt" or del 'C:\folder\file')
		(r'\bdel\s+["\'][A-Za-z]:[/\\\\]', "Absolute-path deletion is blocked."),
		(r"\brmdir\s+/(?:s|q)", "Recursive directory removal is blocked."),
		(r"\brd\s+/s\s+/q\b", "Recursive directory removal is blocked."),
		(r"Remove-Item\s+.+-Recurse", "Recursive PowerShell deletion is blocked."),
		(r"Remove-Item\s+[\"'](?:[A-Za-z]:\\\\|/)", "Deleting absolute-path items in PowerShell is blocked."),
		(r"\bformat\s+[a-z]:", "Disk formatting is blocked."),
		(r"\bmkfs\b", "Filesystem formatting is blocked."),
		(r"\bshutdown\b", "System shutdown commands are blocked."),
		(r"\breboot\b", "System reboot commands are blocked."),
		(r"\bpoweroff\b", "System power commands are blocked."),
		(r"\breg\s+delete\b", "Registry deletion is blocked."),
		(r"\bcipher\s+/w\b", "Secure wipe commands are blocked."),
		(r"\bdiskpart\b", "Disk management commands are blocked."),
		(r"shutil\.rmtree\s*\(", "Recursive directory deletion in code is blocked."),
		# Block direct absolute-path deletes.
		(r"os\.remove\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Deleting absolute-path files is blocked."),
		(r"os\.rmdir\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Removing absolute-path directories is blocked."),
		# Block absolute-path deletes when the path is constructed via os.path.join().
		(r"os\.remove\s*\(\s*os\.path\.join\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Deleting absolute-path files is blocked."),
		(r"os\.rmdir\s*\(\s*os\.path\.join\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Removing absolute-path directories is blocked."),
		(r"shutil\.rmtree\s*\(\s*os\.path\.join\s*\(\s*[\"'](?:[A-Za-z]:\\\\|/)", "Recursive directory deletion in code is blocked."),
		# Catch absolute-path string literals anywhere inside delete function calls.
		(r"os\.remove\s*\(\s*[^)]*[\"'](?:[A-Za-z]:\\\\|/)", "Deleting absolute-path files is blocked."),
		(r"os\.rmdir\s*\(\s*[^)]*[\"'](?:[A-Za-z]:\\\\|/)", "Removing absolute-path directories is blocked."),
		# Node.js filesystem deletions on absolute paths:
		# In practice we see patterns like:
		#   const directory = 'D:\\Temp';
		#   const filePath = path.join(directory, file);
		#   fs.unlinkSync(filePath);
		# The absolute path isn't inside unlinkSync(...), so we match both in the same script.
		(r"(?s)(?=.*fs\.(?:unlinkSync|rmSync))(?=.*[`'\"][A-Za-z]:[\\\\/])", "Deleting absolute-path files is blocked."),
		(r"(?s)(?=.*fs\.rmdirSync)(?=.*[`'\"][A-Za-z]:[\\\\/])", "Removing absolute-path directories is blocked."),
		(r"subprocess\.(?:run|Popen)\s*\(.+(?:rm -rf|shutdown|format)", "Dangerous subprocess invocation is blocked."),
	]

	def __init__(self):
		self.logger = Logger.initialize("logs/interpreter.log")

	def build_sandbox_context(self) -> SandboxContext:
		env = {}
		for key in self.SAFE_ENV_KEYS:
			if os.getenv(key):
				env[key] = os.getenv(key)
		env["PYTHONIOENCODING"] = "utf-8"
		cwd = tempfile.mkdtemp(prefix="interpreter-sandbox-")
		self.logger.info(f"Created sandbox context at '{cwd}'")
		return SandboxContext(cwd=cwd, env=env, timeout_seconds=30)

	def cleanup_sandbox_context(self, context: SandboxContext | None):
		if context and context.cwd and os.path.exists(context.cwd):
			shutil.rmtree(context.cwd, ignore_errors=True)

	def assess_execution(self, content: str, mode: str) -> SafetyDecision:
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
