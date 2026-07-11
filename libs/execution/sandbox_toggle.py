"""Sandbox toggle helper extracted from the Interpreter orchestrator."""

from __future__ import annotations


def toggle_sandbox_mode(interp, *, display_fn, input_fn):
	"""Toggle SAFE/UNSAFE sandbox mode with confirmation when disabling."""
	from libs.safety_manager import SafetyLevel

	sandbox_currently_on = not interp.UNSAFE_EXECUTION
	if sandbox_currently_on:
		warning_msg = (
			"\n⚠️  **WARNING: DISABLING SANDBOX MODE** ⚠️\n\n"
			"Turning OFF sandbox will enable UNSAFE MODE which:\n"
			"- Removes all security isolation\n"
			"- Disables execution timeouts\n"
			"- Removes resource limits\n"
			"- Allows full system access\n"
			"- Runs code directly in your working directory\n\n"
			"**This can be dangerous if executing untrusted code!**\n"
		)
		display_fn(warning_msg)
		confirmation = input_fn("Are you sure you want to DISABLE sandbox? (yes/no): ", default="no").strip().lower()
		if confirmation not in ["yes", "y"]:
			display_fn("✓ Sandbox remains **ENABLED** (SAFE MODE active).")
			return not interp.UNSAFE_EXECUTION
		interp.UNSAFE_EXECUTION = True
		interp.safety_manager.unsafe_mode = True
		interp.safety_manager.safety_level = SafetyLevel.OFF
		interp.code_interpreter.UNSAFE_EXECUTION = True
		status_msg = "⚠️ **SANDBOX DISABLED** — UNSAFE MODE is now active. No timeouts, no limits, full system access."
		interp.logger.warning("Sandbox mode DISABLED by /sandbox command.")
	else:
		interp.UNSAFE_EXECUTION = False
		interp.safety_manager.unsafe_mode = False
		interp.safety_manager.safety_level = SafetyLevel.STANDARD
		interp.code_interpreter.UNSAFE_EXECUTION = False
		status_msg = "✅ **SANDBOX ENABLED** — SAFE MODE is now active with timeouts and resource limits."
		interp.logger.info("Sandbox mode ENABLED by /sandbox command.")
	display_fn(status_msg)
	return not interp.UNSAFE_EXECUTION
