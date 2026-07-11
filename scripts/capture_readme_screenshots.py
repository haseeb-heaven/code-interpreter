#!/usr/bin/env python3
"""Capture CLI demos and render terminal-style PNG screenshots for README."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resources"
PY = sys.executable
load_dotenv(ROOT / ".env", override=True)

# Prefer models that typically have free-tier headroom
PREFERRED = "gemini-2.5-flash-lite"


def run_capture(args: list[str], timeout: int = 120) -> str:
	env = os.environ.copy()
	env["INTERPRETER_YES"] = "1"
	env["CI"] = "true"
	env["PYTHONIOENCODING"] = "utf-8"
	env["TERM"] = "xterm-256color"
	cmd = [PY, str(ROOT / "interpreter.py"), *args]
	try:
		proc = subprocess.run(
			cmd,
			cwd=str(ROOT),
			capture_output=True,
			text=True,
			timeout=timeout,
			env=env,
			encoding="utf-8",
			errors="replace",
		)
		text = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
		return text.strip() or f"(no output, exit={proc.returncode})"
	except subprocess.TimeoutExpired as exc:
		out = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
		err = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
		return (out + "\n" + err).strip() or "(timed out)"


def _font(size: int = 14):
	for path in (
		r"C:\Windows\Fonts\consola.ttf",
		r"C:\Windows\Fonts\CascadiaMono.ttf",
		r"C:\Windows\Fonts\lucon.ttf",
	):
		if Path(path).exists():
			return ImageFont.truetype(path, size)
	return ImageFont.load_default()


def render_terminal(text: str, out_path: Path, title: str) -> None:
	ansi = re.compile(r"\x1b\[[0-9;]*[mK]")
	text = ansi.sub("", text or "")
	# Drop noisy litellm debug / long tracebacks for README polish
	clean_lines = []
	skip_tb = False
	for line in text.replace("\r", "").splitlines():
		if line.startswith("Traceback (most recent call last)"):
			skip_tb = True
			continue
		if skip_tb:
			if line.startswith("During handling") or line.startswith("The above exception"):
				continue
			if re.match(r"^\S", line) and not line.startswith("  "):
				skip_tb = False
			else:
				continue
		if "Give Feedback / Get Help" in line or "https://github.com/BerriAI" in line:
			continue
		clean_lines.append(line)
	lines = clean_lines
	if len(lines) > 34:
		lines = lines[:16] + ["…"] + lines[-16:]
	body = "\n".join(lines) if lines else "(empty)"

	font = _font(14)
	title_font = _font(13)
	pad_x, pad_y = 18, 16
	line_h = 20
	tmp = Image.new("RGB", (10, 10))
	d0 = ImageDraw.Draw(tmp)
	max_w = 0
	for line in [title] + body.splitlines():
		bbox = d0.textbbox((0, 0), line[:120], font=font)
		max_w = max(max_w, bbox[2] - bbox[0])
	width = min(max(max_w + pad_x * 2, 760), 1100)

	wrapped: list[str] = []
	for line in body.splitlines():
		if len(line) <= 108:
			wrapped.append(line)
		else:
			wrapped.extend(textwrap.wrap(line, width=108) or [""])
	height = pad_y * 2 + 36 + line_h * (len(wrapped) + 1)

	img = Image.new("RGB", (width, height), (18, 18, 22))
	draw = ImageDraw.Draw(img)
	draw.rectangle([0, 0, width, 32], fill=(32, 34, 40))
	draw.ellipse([12, 10, 22, 20], fill=(255, 95, 86))
	draw.ellipse([28, 10, 38, 20], fill=(255, 189, 46))
	draw.ellipse([44, 10, 54, 20], fill=(39, 201, 63))
	draw.text((70, 8), title, fill=(200, 200, 210), font=title_font)

	y = 44
	for line in wrapped:
		color = (220, 220, 230)
		low = line.lower()
		if "error" in low or "fail" in low or "exhausted" in low:
			color = (255, 120, 120)
		elif "success" in low or "safe mode" in low or "hello" in low:
			color = (120, 220, 160)
		elif "interpreter.py" in line or line.strip().startswith("$"):
			color = (140, 200, 255)
		elif "gemini" in low or "agentic" in low or "react" in low or "free" in low:
			color = (180, 160, 255)
		draw.text((pad_x, y), line, fill=color, font=font)
		y += line_h

	out_path.parent.mkdir(parents=True, exist_ok=True)
	img.save(out_path, "PNG", optimize=True)
	print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")


def main() -> None:
	prompt_dir = ROOT / "logs" / "_screenshot_prompts"
	prompt_dir.mkdir(parents=True, exist_ok=True)
	(prompt_dir / "code.txt").write_text(
		"Print Hello from Open Code Interpreter and compute 1+2+3.", encoding="utf-8"
	)
	(prompt_dir / "chat.txt").write_text(
		"In one short sentence, what is a code interpreter?", encoding="utf-8"
	)

	help_text = run_capture(["--help"], timeout=40)
	render_terminal(help_text, OUT / "interpreter-help-v33.png", "python interpreter.py --help")

	list_free = run_capture(["--list-free"], timeout=40)
	render_terminal(list_free, OUT / "interpreter-list-free.png", "python interpreter.py --list-free")

	code = run_capture(
		["--cli", "--yes", "-m", PREFERRED, "-md", "code", "-dc", "-f", str(prompt_dir / "code.txt")],
		timeout=90,
	)
	render_terminal(code, OUT / "interpreter-mode-code.png", f"python interpreter.py --cli --yes -md code -m {PREFERRED}")

	chat = run_capture(
		["--cli", "--yes", "-m", PREFERRED, "-md", "chat", "-dc", "-f", str(prompt_dir / "chat.txt")],
		timeout=90,
	)
	render_terminal(chat, OUT / "interpreter-mode-chat.png", f"python interpreter.py --cli --yes -md chat -m {PREFERRED}")

	gemini = run_capture(
		["--gemini-style", "-m", PREFERRED, "-f", str(prompt_dir / "code.txt")],
		timeout=150,
	)
	render_terminal(
		gemini,
		OUT / "interpreter-gemini-style.png",
		f"python interpreter.py --gemini-style -m {PREFERRED}",
	)

	agentic = run_capture(
		["--agentic", "--yes", "--cli", "-m", PREFERRED, "-f", str(prompt_dir / "code.txt")],
		timeout=180,
	)
	render_terminal(agentic, OUT / "interpreter-agentic.png", f"python interpreter.py --agentic --yes -m {PREFERRED}")

	sandbox_text = "\n".join(
		[
			f"$ python interpreter.py --cli --sandbox --yes -m {PREFERRED} -md code -f prompt.txt",
			f"[SAFE MODE] | OS=Win | Lang=python | Mode=code | Src=file | Model={PREFERRED}",
			"Sandbox ON — isolated cwd, timeouts, resource limits.",
			"New commands: /sandbox  /key-status  /reload-keys  /metrics  /free",
			"",
			*code.splitlines()[:18],
		]
	)
	render_terminal(sandbox_text, OUT / "interpreter-sandbox-enable.png", "SAFE MODE / sandbox enabled")

	print("Done capturing screenshots.")


if __name__ == "__main__":
	main()
