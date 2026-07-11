"""Per-execution timing / resource measurement (#225)."""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResourceUsage:
	duration_ms: int = 0
	peak_memory_mb: Optional[float] = None
	cpu_user_ms: Optional[float] = None

	def summary(self) -> str:
		parts = [f"{self.duration_ms}ms"]
		if self.peak_memory_mb is not None:
			parts.append(f"{self.peak_memory_mb:.1f} MB peak memory")
		if self.cpu_user_ms is not None:
			parts.append(f"{self.cpu_user_ms:.0f}ms CPU")
		return " | ".join(parts)


@contextmanager
def measure() -> Iterator[ResourceUsage]:
	"""Context manager that fills ResourceUsage after the block exits."""
	usage = ResourceUsage()
	start = time.perf_counter()
	ru_start = None
	if sys.platform != "win32":
		try:
			import resource as res

			ru_start = res.getrusage(res.RUSAGE_CHILDREN)
		except Exception as exc:  # pragma: no cover
			logger.debug("rusage unavailable: %s", exc)
	try:
		yield usage
	finally:
		usage.duration_ms = int((time.perf_counter() - start) * 1000)
		if sys.platform != "win32" and ru_start is not None:
			try:
				import resource as res

				ru_end = res.getrusage(res.RUSAGE_CHILDREN)
				# Linux ru_maxrss is KB; macOS is bytes
				rss = float(ru_end.ru_maxrss)
				if sys.platform == "darwin":
					usage.peak_memory_mb = rss / (1024 * 1024)
				else:
					usage.peak_memory_mb = rss / 1024.0
				usage.cpu_user_ms = (ru_end.ru_utime - ru_start.ru_utime) * 1000.0
			except Exception as exc:  # pragma: no cover
				logger.debug("Failed to read child rusage: %s", exc)
