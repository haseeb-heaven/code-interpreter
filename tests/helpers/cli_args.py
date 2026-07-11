"""Shared argparse Namespace helpers for Interpreter unit tests."""

from __future__ import annotations

from argparse import Namespace


def make_interpreter_args(**overrides) -> Namespace:
	"""Return a complete Namespace so MagicMock-like truthy gaps cannot trip wire_components."""
	args = Namespace(
		exec=False,
		save_code=False,
		mode="code",
		model="gpt-4o",
		display_code=False,
		lang="python",
		file=None,
		history=False,
		upgrade=False,
		unsafe=False,
		sandbox=True,
		tui=False,
		cli=True,
		agent=False,
		agentic=False,
		yes=False,
		yolo=False,
		search=False,
		search_provider=None,
		search_api_key=None,
		output_format="plain",
		no_color=False,
		stream=False,
		mcp=None,
		max_context_tokens=8000,
		gemini_style=False,
	)
	for key, value in overrides.items():
		setattr(args, key, value)
	return args
