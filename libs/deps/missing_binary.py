# -*- coding: utf-8 -*-
"""Missing system-binary detection for agentic / YOLO / ReAct flows."""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BinarySpec:
	"""Known external tool with safe install hints per platform."""

	name: str
	aliases: tuple = ()
	# Package-manager ids (never shell-interpolated raw user text)
	winget_id: str = ""
	choco_id: str = ""
	scoop_id: str = ""
	apt_id: str = ""
	brew_id: str = ""
	docs_url: str = ""
	# Optional pip fallback (rare; most binaries are not pip packages)
	pip_id: str = ""


# Curated allow-list — only these may be auto-installed via package managers.
KNOWN_BINARIES: Dict[str, BinarySpec] = {
	"ffmpeg": BinarySpec(
		name="ffmpeg",
		aliases=("ffprobe",),
		winget_id="Gyan.FFmpeg",
		choco_id="ffmpeg",
		scoop_id="ffmpeg",
		apt_id="ffmpeg",
		brew_id="ffmpeg",
		docs_url="https://ffmpeg.org/download.html",
	),
	"ffprobe": BinarySpec(
		name="ffprobe",
		aliases=("ffmpeg",),
		winget_id="Gyan.FFmpeg",
		choco_id="ffmpeg",
		scoop_id="ffmpeg",
		apt_id="ffmpeg",
		brew_id="ffmpeg",
		docs_url="https://ffmpeg.org/download.html",
	),
	"convert": BinarySpec(
		name="convert",
		aliases=("magick", "imagemagick"),
		winget_id="ImageMagick.ImageMagick",
		choco_id="imagemagick",
		scoop_id="imagemagick",
		apt_id="imagemagick",
		brew_id="imagemagick",
		docs_url="https://imagemagick.org/script/download.php",
	),
	"magick": BinarySpec(
		name="magick",
		aliases=("convert", "imagemagick"),
		winget_id="ImageMagick.ImageMagick",
		choco_id="imagemagick",
		scoop_id="imagemagick",
		apt_id="imagemagick",
		brew_id="imagemagick",
		docs_url="https://imagemagick.org/script/download.php",
	),
	"sox": BinarySpec(
		name="sox",
		winget_id="ChrisBagshaw.SoX",
		choco_id="sox",
		scoop_id="sox",
		apt_id="sox",
		brew_id="sox",
		docs_url="http://sox.sourceforge.net/",
	),
	"pandoc": BinarySpec(
		name="pandoc",
		winget_id="JohnMacFarlane.Pandoc",
		choco_id="pandoc",
		scoop_id="pandoc",
		apt_id="pandoc",
		brew_id="pandoc",
		docs_url="https://pandoc.org/installing.html",
	),
	"git": BinarySpec(
		name="git",
		winget_id="Git.Git",
		choco_id="git",
		scoop_id="git",
		apt_id="git",
		brew_id="git",
		docs_url="https://git-scm.com/downloads",
	),
	"node": BinarySpec(
		name="node",
		aliases=("nodejs",),
		winget_id="OpenJS.NodeJS.LTS",
		choco_id="nodejs",
		scoop_id="nodejs",
		apt_id="nodejs",
		brew_id="node",
		docs_url="https://nodejs.org/",
	),
	"npm": BinarySpec(
		name="npm",
		aliases=("node",),
		winget_id="OpenJS.NodeJS.LTS",
		choco_id="nodejs",
		scoop_id="nodejs",
		apt_id="npm",
		brew_id="node",
		docs_url="https://nodejs.org/",
	),
}


# Patterns that strongly indicate a missing executable on PATH.
_MISSING_PATTERNS = (
	re.compile(r"(?i)command not found"),
	re.compile(r"(?i)is not recognized as an internal or external command"),
	re.compile(r"(?i)No such file or directory"),
	re.compile(r"(?i)\[WinError\s*2\]"),
	re.compile(r"(?i)The system cannot find the file specified"),
	re.compile(r"(?i)not installed"),
	re.compile(r"(?i)Executable .+ not found"),
	re.compile(r"(?i)Cannot find .+ executable"),
	re.compile(r"(?i)Failed to find .+ binary"),
)

# Extract binary name from common error shapes.
_NAME_EXTRACTORS = (
	re.compile(r"(?i)'([a-z0-9_.+-]+)'\s+is not recognized"),
	re.compile(r"(?i)([a-z0-9_.+-]+):\s*command not found"),
	re.compile(r"(?i)\[Errno\s*2\].*?'([a-z0-9_.+-]+)'"),
	re.compile(r"(?i)cannot find the file specified:\s*'([a-z0-9_.+-]+)'"),
	re.compile(r"(?i)FileNotFoundError:.*?\b([a-z0-9_.+-]+)\b"),
	re.compile(r"(?i)No such file or directory:\s*'([a-z0-9_.+-]+)'"),
)


def is_missing_binary_error(text: str) -> bool:
	"""True when *text* looks like a missing PATH binary / tool failure."""
	if not text:
		return False
	low = text.lower()
	# Fast path: known binary name + missing-tool phrasing
	if any(p.search(text) for p in _MISSING_PATTERNS):
		if detect_missing_binary(text) is not None:
			return True
		# Generic missing-command language even if name unknown
		return "command not found" in low or "is not recognized" in low
	# Mention of a known binary with "not found" / "missing"
	for name in KNOWN_BINARIES:
		if name in low and any(
			tok in low for tok in ("not found", "missing", "no such file", "not installed", "cannot find")
		):
			return True
	return False


def detect_missing_binary(text: str) -> Optional[BinarySpec]:
	"""Return the matching :class:`BinarySpec` if a known tool is missing."""
	if not text:
		return None
	low = text.lower()

	# Prefer explicit extraction from error phrasing.
	for rx in _NAME_EXTRACTORS:
		m = rx.search(text)
		if not m:
			continue
		candidate = m.group(1).lower().strip()
		# Strip path / extension noise
		candidate = candidate.replace(".exe", "").split("/")[-1].split("\\")[-1]
		spec = _lookup(candidate)
		if spec is not None:
			return spec

	# Fall back: known name present alongside missing-tool signals.
	missing_signal = any(p.search(text) for p in _MISSING_PATTERNS) or any(
		tok in low for tok in ("not found", "missing", "not installed", "cannot find")
	)
	if not missing_signal:
		return None

	# Prefer longer / more specific names first (ffprobe before ffmpeg substring issues)
	for name in sorted(KNOWN_BINARIES.keys(), key=len, reverse=True):
		if re.search(rf"(?i)\b{re.escape(name)}\b", text):
			return KNOWN_BINARIES[name]
	return None


def _lookup(name: str) -> Optional[BinarySpec]:
	name = (name or "").lower().strip()
	if name in KNOWN_BINARIES:
		return KNOWN_BINARIES[name]
	for spec in KNOWN_BINARIES.values():
		if name in spec.aliases or name == spec.name:
			return spec
	return None


def format_install_hints(spec: Optional[BinarySpec], platform: Optional[str] = None) -> str:
	"""Human-readable install options for *spec* on the current (or given) platform."""
	if spec is None:
		return ""
	plat = (platform or sys.platform).lower()
	lines: List[str] = [f"Install options for '{spec.name}':"]
	if plat.startswith("win"):
		if spec.winget_id:
			lines.append(f"  • winget:  winget install --id {spec.winget_id} -e")
		if spec.choco_id:
			lines.append(f"  • chocolatey:  choco install {spec.choco_id} -y")
		if spec.scoop_id:
			lines.append(f"  • scoop:  scoop install {spec.scoop_id}")
	elif plat == "darwin":
		if spec.brew_id:
			lines.append(f"  • brew:  brew install {spec.brew_id}")
	else:
		if spec.apt_id:
			lines.append(f"  • apt:  sudo apt-get install -y {spec.apt_id}")
		if spec.brew_id:
			lines.append(f"  • brew:  brew install {spec.brew_id}")
	if spec.pip_id:
		lines.append(f"  • pip:  pip install {spec.pip_id}")
	if spec.docs_url:
		lines.append(f"  • docs:  {spec.docs_url}")
	return "\n".join(lines)


def preferred_install_method(spec: BinarySpec, platform: Optional[str] = None) -> str:
	"""Return the first available package-manager method key for this platform."""
	plat = (platform or sys.platform).lower()
	if plat.startswith("win"):
		for key, attr in (("winget", "winget_id"), ("choco", "choco_id"), ("scoop", "scoop_id")):
			if getattr(spec, attr):
				return key
	elif plat == "darwin":
		if spec.brew_id:
			return "brew"
	else:
		if spec.apt_id:
			return "apt"
		if spec.brew_id:
			return "brew"
	if spec.pip_id:
		return "pip"
	return "docs"
