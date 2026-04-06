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
    # Unix/Linux/macOS
    (r"\brm\s+-rf\b", "Recursive deletion is blocked."),
    (r"\brm\s+/", "Absolute-path deletion is blocked."),
    (r"\brmdir\s+/", "Absolute-path directory removal is blocked."),
    (r"\bfind\s+.+-delete\b", "Find-based deletion is blocked."),
    (r"\bmkfs(?:\.ext[234]|fs)?\b", "Filesystem formatting is blocked."),
    (r"\bwipefs\b", "Filesystem wiping is blocked."),
    (r"\bshred\s+-u\b", "Secure file wiping is blocked."),

    # Windows CMD - FIXED quoted/unquoted absolute paths
    (r"\bdel\s+/(?:f|q|s)\b", "Destructive delete command is blocked."),
    (r"\bdel\s+[A-Za-z]:[\\\\/]", "Absolute-path deletion is blocked."),
    (r"\bdel\s+['\"][A-Za-z]:[\\\\/][^'\"]*['\"]?", "Quoted absolute-path deletion is blocked."),
    (r"\berase\s+[A-Za-z]:[\\\\/]", "Absolute-path deletion is blocked."),
    (r"\berase\s+['\"][A-Za-z]:[\\\\/][^'\"]*['\"]?", "Quoted absolute-path deletion is blocked."),
    (r"\brmdir\s+/(?:s|q)\b", "Recursive directory removal is blocked."),
    (r"\brd\s+/s\s+/q\b", "Recursive directory removal is blocked."),
    (r"\bformat\s+[A-Za-z]:", "Disk formatting is blocked."),
    (r"\bcipher\s+/w\b", "Secure wipe commands are blocked."),
    (r"\bdiskpart\b", "Disk management commands are blocked."),
    (r"\breg\s+delete\b", "Registry deletion is blocked."),

    # PowerShell
    (r"Remove-Item\s+.+-Recurse", "Recursive PowerShell deletion is blocked."),
    (r"Remove-Item\s+.+-Force", "Forced PowerShell deletion is blocked."),
    (r"Remove-Item\s+['\"][A-Za-z]:[\\\\/]", "Deleting absolute-path items in PowerShell is blocked."),
    (r"Remove-Item\s+-Path\s+['\"][A-Za-z]:[\\\\/]", "Deleting absolute-path items in PowerShell is blocked."),
    (r"Remove-Item\s+-LiteralPath\s+['\"][A-Za-z]:[\\\\/]", "Deleting absolute-path items in PowerShell is blocked."),
    (r"Get-ChildItem\s+.+\|\s*Remove-Item\b", "Pipeline-based PowerShell deletion is blocked."),
    (r"ForEach-Object\s*\{[^}]*Remove-Item\b", "Loop-based PowerShell deletion is blocked."),

    # System commands
    (r"\bshutdown\b", "System shutdown commands are blocked."),
    (r"\breboot\b", "System reboot commands are blocked."),
    (r"\bpoweroff\b", "System power commands are blocked."),

    # Python - FIXED joined absolute paths + loops
    (r"shutil\.rmtree\s*\(", "Recursive directory deletion in code is blocked."),
    (r"os\.(?:remove|unlink)\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Deleting absolute-path files is blocked."),
    (r"os\.rmdir\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Removing absolute-path directories is blocked."),
    (r"os\.(?:remove|unlink|rmdir)\s*\(\s*os\.path\.join\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Absolute-path joined deletion is blocked."),
    (r"os\.remove\s*\(\s*os\.path\.join\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Deleting absolute-path files is blocked."),
    (r"for\s+.+\s+in\s+os\.listdir\s*\([^)]*\)\s*:\s*.*os\.(?:remove|unlink)\s*\(", "Loop-based file deletion is blocked."),
    (r"for\s+.+\s+in\s+glob\.glob\s*\([^)]*\)\s*:\s*.*os\.(?:remove|unlink)\s*\(", "Glob-based file deletion is blocked."),
    (r"for\s+.+\s+in\s+.+\.glob\s*\([^)]*\)\s*:\s*.*(?:os\.(?:remove|unlink)|.+\.unlink\s*\()", "Path glob deletion is blocked."),
    (r"pathlib\.Path\s*\(\s*['\"][A-Za-z]:[\\\\/][^'\"]*['\"]?\)\.unlink\s*\(", "Absolute-path pathlib deletion is blocked."),

    # JavaScript - FIXED joined absolute paths + loops
    (r"fs\.(?:rmSync|rmdirSync)\s*\(", "Directory deletion in JavaScript is blocked."),
    (r"fs\.unlinkSync\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Absolute-path file deletion in JavaScript is blocked."),
    (r"fs\.unlink\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Absolute-path file deletion in JavaScript is blocked."),
    (r"fs\.unlinkSync\s*\(\s*path\.join\s*\(\s*['\"][A-Za-z]:[\\\\/]", "Absolute-path joined JavaScript deletion is blocked."),
    (r"(?s)(?:const|let|var)\s+\w+\s*=\s*['\"][A-Za-z]:[\\\\/].*?fs\.unlinkSync\s*\(\s*path\.join\s*\(\s*\w+\s*,", "Variable absolute-path JS deletion is blocked."),
    (r"(?s)fs\.readdirSync\s*\(\s*\w+\s*\)\.forEach\s*\(.*?fs\.unlinkSync\s*\(\s*path\.join\s*\(\s*\w+\s*,", "JS readdir loop deletion is blocked."),
    (r"(?s)for\s*\([^)]*\)\s*\{[^}]*path\.join\s*\(\s*\w+\s*,[^}]*fs\.unlinkSync\s*\(", "JS for-loop deletion is blocked."),

    # Subprocess
    (r"subprocess\.(?:run|Popen)\s*\(.+(?:rm -rf|shutdown|format|del\s+|Remove-Item|mkfs)", "Dangerous subprocess invocation is blocked."),
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
