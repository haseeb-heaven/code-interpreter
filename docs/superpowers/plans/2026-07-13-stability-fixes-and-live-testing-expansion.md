# Stability Fixes + Live Testing Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the classic `--cli` REPL from crashing with a raw `AllKeysExhaustedError` traceback, stop the persistent banner from wrapping/truncating on narrow terminals, extend the committed live-scenario fixture set and test cases to cover seven new file types (`zip`, `mp3`, `java`, `sqlite`, `docx`, `svg`, `webm`) across the create/analyze/summarize/convert/edit action matrix, add explicit key-rotation and all-modes-smoke coverage, then run the full live suite for real and replicate CI locally as the merge gate.

**Architecture:** Two isolated bug fixes (`libs/key_manager.py` + `libs/core/main_loop.py` + `libs/core/model_router.py` for exhaustion handling; `libs/agent/gemini_ui.py` + `libs/core/session.py` for banner width) land first with unit tests, since later live-suite tasks depend on the REPL not crashing. Testing expansion is additive: new committed fixtures in `tests/fixtures/input/`, new dict keys in `tests/live/scenarios/fixtures.py`, new `ScenarioCase` entries in `tests/live/scenarios/cases.py` — no changes to the harness runner itself. Everything is stdlib-only (`zipfile`/`sqlite3`/`xml.etree.ElementTree`) so new scenarios never depend on `javac`, `python-docx`, or video codecs being present in CI.

**Tech Stack:** Python 3.11+, `unittest`, `argparse`, Rich (console rendering), stdlib `zipfile`/`sqlite3`/`xml.etree.ElementTree`/`shutil`.

## Global Constraints

- Never hardcode `D:\tmp\dummy_media` or `D:\tmp` anywhere in code — fixture content is copied once into `tests/fixtures/input/` (committed) and consumed only via `INTERPRETER_TEST_DATA_DIR`/`TEST_DATA_DIR` at test time.
- Never print or commit API key secrets, in code, logs, or test assertions.
- Work in a git worktree/branch; merge to `develop` only when the full suite (unit + live medium/complex + replicated CI commands) is green. Do NOT push to `origin` without separate authorization.
- Preserve the exact existing `AllKeysExhaustedError` message wording (`"All keys exhausted for provider '{provider}'. Earliest recovery: {eta_str}"`) — `tests/test_e2e_retry.py` asserts on it.
- All new committed fixtures must be small (representative single files, not the full ~35-file `dummy_media` set).
- Follow the existing `tests/live/scenarios/cases.py` convention: tab indentation, `ScenarioCase(id=, category=, tier=, kind=, no_sandbox=, code=(...), expect_markers=, expect_artifacts=[...], timeout_s=)`. Build any generated-code output text with `.format()`/string concatenation, not nested f-strings — the file already has one latent nested-f-string bug (`offline_analyze_json`, line 164, double-braced literal that never actually interpolates `rev`); do not introduce more instances of that pattern into new cases.

---

### Task 1: `AllKeysExhaustedError` structured attributes

**Files:**
- Modify: `libs/key_manager.py:28-29` (class definition), `libs/key_manager.py:544-557` (`raise_if_exhausted`)
- Test: `tests/test_key_manager.py`

**Interfaces:**
- Produces: `AllKeysExhaustedError(message, *, provider=None, earliest_recovery_ts=None)` — instances now expose `.provider: Optional[str]` and `.earliest_recovery_ts: Optional[float]` in addition to the existing `str(err)` message. Consumed by Task 2 (`main_loop.py`) and Task 3 (`model_router.py`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_key_manager.py` (same file already has `setUp`/`tearDown` calling `KeyManager.reset_singleton()` and a `_env(self, mapping)` helper — add this as a new method on the existing test class that contains `test_full_rotation_exhaustion_recovery`):

```python
	def test_all_keys_exhausted_error_has_structured_attributes(self):
		from libs.key_manager import AllKeysExhaustedError

		env = {"OPENAI_API_KEY_1": "sk-1", "OPENAI_API_KEY_2": "sk-2"}
		km = KeyManager(getenv_fn=self._env(env))
		for i in range(2):
			km.record_failure("openai", i, is_rate_limit=True, rate_limit_seconds=120.0)
		with self.assertRaises(AllKeysExhaustedError) as ctx:
			km.raise_if_exhausted("openai")
		err = ctx.exception
		self.assertIn("All keys exhausted for provider 'openai'", str(err))
		self.assertIn("Earliest recovery:", str(err))
		self.assertEqual(err.provider, "openai")
		self.assertIsInstance(err.earliest_recovery_ts, float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_key_manager.TestKeyManager.test_all_keys_exhausted_error_has_structured_attributes -v`
Expected: FAIL with `AttributeError: 'AllKeysExhaustedError' object has no attribute 'provider'`

- [ ] **Step 3: Implement the structured exception**

In `libs/key_manager.py`, replace lines 28-29:

```python
class AllKeysExhaustedError(Exception):
	"""Raised when every key for a provider is unavailable."""
```

with:

```python
class AllKeysExhaustedError(Exception):
	"""Raised when every key for a provider is unavailable."""

	def __init__(
		self,
		message: str,
		*,
		provider: Optional[str] = None,
		earliest_recovery_ts: Optional[float] = None,
	) -> None:
		super().__init__(message)
		self.provider = provider
		self.earliest_recovery_ts = earliest_recovery_ts
```

- [ ] **Step 4: Wire the new kwargs through the raise site**

In `libs/key_manager.py`, replace lines 544-557:

```python
	def raise_if_exhausted(self, provider: str) -> None:
		"""Raise only when a pool exists and every key is unavailable.

		No pool (bare-env / tests without keys) is not exhaustion — callers
		should fall through to the normal single-key path.
		"""
		pool = self.get_pool(provider)
		if pool is None:
			return
		if pool.available_count() == 0:
			eta = pool.earliest_recovery()
			eta_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(eta))
			raise AllKeysExhaustedError(
				f"All keys exhausted for provider '{provider}'. Earliest recovery: {eta_str}"
			)
```

with:

```python
	def raise_if_exhausted(self, provider: str) -> None:
		"""Raise only when a pool exists and every key is unavailable.

		No pool (bare-env / tests without keys) is not exhaustion — callers
		should fall through to the normal single-key path.
		"""
		pool = self.get_pool(provider)
		if pool is None:
			return
		if pool.available_count() == 0:
			eta = pool.earliest_recovery()
			eta_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(eta))
			raise AllKeysExhaustedError(
				f"All keys exhausted for provider '{provider}'. Earliest recovery: {eta_str}",
				provider=provider,
				earliest_recovery_ts=eta,
			)
```

No new import is needed — `Optional` is already imported at the top of `libs/key_manager.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_key_manager.TestKeyManager.test_all_keys_exhausted_error_has_structured_attributes -v`
Expected: PASS

- [ ] **Step 6: Run the full key-manager suite to check for regressions**

Run: `python -m unittest tests.test_key_manager -v`
Expected: all PASS (the exact message string is unchanged, so `test_full_rotation_exhaustion_recovery` and any other message-asserting test keep passing).

- [ ] **Step 7: Commit**

```bash
git add libs/key_manager.py tests/test_key_manager.py
git commit -m "fix(key-manager): add structured provider/eta attributes to AllKeysExhaustedError"
```

---

### Task 2: Classic REPL — catch exhaustion instead of crashing, and de-duplicate quota/billing classification

**Files:**
- Create: `libs/core/error_classification.py`
- Modify: `tests/live/scenarios/soft_skip.py:8-36` (replace inline tuples with imports from the new shared module)
- Modify: `libs/core/model_router.py:148-168` (`is_recoverable_runtime_error` reuses the shared billing/auth marker set instead of its own copy)
- Modify: `libs/core/main_loop.py` (module imports near line 1-10; final except-block at lines 1149-1157)
- Test: `tests/core/test_error_classification.py` (new), `tests/live/scenarios/test_fixtures.py` or existing soft-skip test coverage, `tests/core/test_model_router.py`, `tests/interactive/test_cli_interactive_live.py`

**Interfaces:**
- Consumes: `AllKeysExhaustedError.provider`, `AllKeysExhaustedError.earliest_recovery_ts` from Task 1; `tests/interactive/helpers.py::make_interp(**overrides)` fixture factory (existing, unmodified).
- Produces: `libs.core.error_classification.BILLING_AUTH_MARKERS: Tuple[str, ...]`, `DEPENDENCY_ENV_MARKERS: Tuple[str, ...]`, `is_billing_or_auth_condition(text: str) -> bool` — the single source of truth for "this looks like a quota/billing/auth condition, not a code bug," consumed by both `tests/live/scenarios/soft_skip.py::is_soft_skip` and `libs/core/model_router.py::is_recoverable_runtime_error`. `run_interpreter_main` no longer propagates `AllKeysExhaustedError` out of the REPL loop — it prints a friendly message and `continue`s.

**Why this shape:** the spec requires reusing `soft_skip.py`'s classification strings as the single source of truth rather than re-declaring them. `AllKeysExhaustedError` itself is already a structured, unambiguous signal — no text classification is needed to know *it* is a quota condition. But `libs/core/model_router.py::is_recoverable_runtime_error` (consumed by this same Task 2's except-block, for the non-`AllKeysExhaustedError` branch) independently re-declares an overlapping billing/auth marker list (`"rate limit"`, `"quota"`, `"429"`, `"api key"`, `"authentication"`, `"unauthorized"`, `"resource_exhausted"`, confirmed at `libs/core/model_router.py:149-166`) — this is exactly the drift the spec warns about. Since production code (`libs/core/model_router.py`) must not import from the test tree (`tests/live/scenarios/soft_skip.py`), the fix is to extract the shared constant into a new non-test module both sides import from. `tests/live/scenarios/test_cli_interactive_live.py::_BILLING_MARKERS` and `model_router.py::is_retryable_request_error`'s two marker lists are a separate, lower-priority duplication not touched here — reconciling every classification list in the codebase is a larger refactor than this bug-fix task warrants; only the one directly implicated by this task's own except-block change is folded in.

- [ ] **Step 1: Write the failing test for the shared module**

Create `tests/core/test_error_classification.py`:

```python
# -*- coding: utf-8 -*-
"""Tests for the shared billing/auth/dependency error classification constants."""

from __future__ import annotations

import unittest

from libs.core.error_classification import (
	BILLING_AUTH_MARKERS,
	DEPENDENCY_ENV_MARKERS,
	is_billing_or_auth_condition,
)


class TestErrorClassification(unittest.TestCase):
	def test_billing_auth_markers_cover_common_quota_errors(self):
		for marker in ("429", "rate limit", "quota", "insufficient balance", "unauthorized"):
			self.assertIn(marker, BILLING_AUTH_MARKERS)

	def test_dependency_env_markers_cover_common_local_errors(self):
		for marker in ("modulenotfounderror", "connection refused", "timeout"):
			self.assertIn(marker, DEPENDENCY_ENV_MARKERS)

	def test_is_billing_or_auth_condition_true_for_quota_text(self):
		self.assertTrue(is_billing_or_auth_condition("Error: 429 rate limit exceeded"))
		self.assertTrue(is_billing_or_auth_condition("insufficient balance on account"))

	def test_is_billing_or_auth_condition_false_for_unrelated_text(self):
		self.assertFalse(is_billing_or_auth_condition("division by zero"))


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.core.test_error_classification -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libs.core.error_classification'`

- [ ] **Step 3: Create the shared classification module**

Create `libs/core/error_classification.py` with the exact tuple contents currently declared in `tests/live/scenarios/soft_skip.py:8-54` (copied verbatim, this module becomes their sole owner):

```python
# -*- coding: utf-8 -*-
"""Shared billing/auth/dependency error classification.

Single source of truth for "this looks like a quota/billing/auth condition,
not a code bug" — consumed by both the live-scenario test harness
(``tests/live/scenarios/soft_skip.py``) and the product's own recoverable-error
detection (``libs/core/model_router.py``) so the two classifications can never
drift apart.
"""

from __future__ import annotations

from typing import Tuple

BILLING_AUTH_MARKERS: Tuple[str, ...] = (
	"429",
	"rate limit",
	"ratelimit",
	"rate_limit",
	"quota",
	"free-models-per-day",
	"insufficient balance",
	"billing",
	"please recharge",
	"credit balance",
	"unauthorized",
	"authentication",
	"api key",
	"401",
	"403",
	"forbidden",
	"payment required",
	"resource_exhausted",
	"all free",
	"models failed",
	"provider returned error",
	"no healthy upstream",
	"overloaded",
	"capacity",
	"503",
	"502",
	"stealth",
)

DEPENDENCY_ENV_MARKERS: Tuple[str, ...] = (
	"modulenotfounderror",
	"no module named",
	"filenotfounderror",
	"connection refused",
	"connection reset",
	"timed out",
	"timeout",
	"temporarily unavailable",
	"not installed",
	"command not found",
	"local endpoint",
	"could not connect",
	"indentationerror",
	"syntaxerror",
	"unterminated string",
)


def is_billing_or_auth_condition(text: str) -> bool:
	low = (text or "").lower()
	return any(marker in low for marker in BILLING_AUTH_MARKERS)


def is_dependency_or_env_condition(text: str) -> bool:
	low = (text or "").lower()
	return any(marker in low for marker in DEPENDENCY_ENV_MARKERS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.core.test_error_classification -v`
Expected: PASS

- [ ] **Step 5: Point `soft_skip.py` at the shared module instead of re-declaring**

Replace `tests/live/scenarios/soft_skip.py` lines 1-63 (everything through `is_soft_skip`, leaving `_TOKEN`/`redact_output` at the bottom untouched):

```python
# -*- coding: utf-8 -*-
"""Soft-skip classifiers for live user scenarios (never log secrets)."""

from __future__ import annotations

import re

from libs.core.error_classification import BILLING_AUTH_MARKERS as _BILLING_AUTH
from libs.core.error_classification import DEPENDENCY_ENV_MARKERS as _DEP_ENV

_TOKEN = re.compile(
	r"(?i)\b(sk-[a-z0-9_\-]{16,}|gsk_[a-z0-9_\-]{16,}|hf_[a-z0-9_\-]{16,}|or-[a-z0-9_\-]{16,})\b"
)


def is_soft_skip(text: str) -> bool:
	low = (text or "").lower()
	return any(m in low for m in _BILLING_AUTH) or any(m in low for m in _DEP_ENV)
```

The trailing `redact_output` function (existing lines 66-70) is unchanged — append it back after this block exactly as it was.

- [ ] **Step 6: Run the existing soft-skip-dependent live scenario tests to confirm no behavior change**

Run: `python -m unittest discover -s tests/live -v`
Expected: all PASS — `is_soft_skip`'s return value is byte-for-byte identical for every input, since `_BILLING_AUTH`/`_DEP_ENV` now reference the exact same tuple contents, just sourced from the shared module.

- [ ] **Step 7: Write the failing test for `is_recoverable_runtime_error` reuse**

Add to `tests/core/test_model_router.py` (as a method on the existing `TestModelRouter` class):

```python
	def test_is_recoverable_runtime_error_uses_shared_billing_auth_markers(self):
		from libs.core.error_classification import BILLING_AUTH_MARKERS

		for marker in BILLING_AUTH_MARKERS:
			self.assertTrue(
				ModelRouter.is_recoverable_runtime_error(f"boom: {marker} happened"),
				f"expected marker {marker!r} to be recoverable",
			)
```

- [ ] **Step 8: Run test to verify it fails**

Run: `python -m unittest tests.core.test_model_router.TestModelRouter.test_is_recoverable_runtime_error_uses_shared_billing_auth_markers -v`
Expected: FAIL on whichever markers exist in `BILLING_AUTH_MARKERS` but not in `is_recoverable_runtime_error`'s current inline list (e.g. `"free-models-per-day"`, `"please recharge"`, `"credit balance"`, `"forbidden"`, `"payment required"`, `"all free"`, `"models failed"`, `"provider returned error"`, `"no healthy upstream"`, `"overloaded"`, `"capacity"`, `"503"`, `"502"`, `"stealth"`, `"401"`, `"403"`, `"ratelimit"`, `"rate_limit"`, `"insufficient balance"`, `"billing"`).

- [ ] **Step 9: Update `is_recoverable_runtime_error` to reuse the shared markers**

In `libs/core/model_router.py`, replace lines 147-168:

```python
	@staticmethod
	def is_recoverable_runtime_error(error_text) -> bool:
		recoverable_errors = [
			"rate limit",
			"ratelimit",
			"quota",
			"credits",
			"requires more credits",
			"resource_exhausted",
			"temporarily rate-limited",
			"402",
			"429",
			"api key",
			"authentication",
			"unauthorized",
			"model_not_found",
			"not found",
			"timeout",
			"connection",
		]
		error_text = (error_text or "").lower()
		return any(error in error_text for error in recoverable_errors)
```

with:

```python
	@staticmethod
	def is_recoverable_runtime_error(error_text) -> bool:
		from libs.core.error_classification import BILLING_AUTH_MARKERS, is_billing_or_auth_condition

		error_text = (error_text or "").lower()
		if is_billing_or_auth_condition(error_text):
			return True
		extra_recoverable_errors = [
			"credits",
			"requires more credits",
			"temporarily rate-limited",
			"402",
			"model_not_found",
			"not found",
			"timeout",
			"connection",
		]
		return any(error in error_text for error in extra_recoverable_errors)
```

`BILLING_AUTH_MARKERS` is imported here for parity with Step 7's test even though only `is_billing_or_auth_condition` is called directly — the import makes the dependency explicit and matches the module's public surface used elsewhere in this task. `"credits"`/`"requires more credits"`/`"temporarily rate-limited"`/`"402"`/`"model_not_found"`/`"not found"`/`"timeout"`/`"connection"` are kept as `model_router.py`-specific extras since they are not part of the shared billing/auth vocabulary (some, like `"timeout"`/`"connection"`, are dependency/env-shaped, not billing-shaped, and were never in `_DEP_ENV` either — they stay local rather than being force-fit into the shared module).

- [ ] **Step 10: Run tests to verify they pass**

Run: `python -m unittest tests.core.test_model_router.TestModelRouter.test_is_recoverable_runtime_error_uses_shared_billing_auth_markers -v`
Expected: PASS

Run: `python -m unittest tests.core.test_model_router -v`
Expected: all PASS (no regression on the pre-existing recoverable-error tests, since every marker that was already in the inline list is also present in `BILLING_AUTH_MARKERS` or the kept `extra_recoverable_errors` list).

- [ ] **Step 11: Commit the shared-classification extraction**

```bash
git add libs/core/error_classification.py tests/core/test_error_classification.py tests/live/scenarios/soft_skip.py libs/core/model_router.py tests/core/test_model_router.py
git commit -m "refactor(errors): extract shared billing/auth classification so product and test detection never drift"
```

- [ ] **Step 12: Write the failing test for the REPL crash fix**

Add to `tests/interactive/test_cli_interactive_live.py`, a new test class after `TestInteractiveSlashCommandsMocked`:

```python
class TestInteractiveKeyExhaustion(unittest.TestCase):
	"""AllKeysExhaustedError must degrade gracefully, not crash the REPL."""

	def test_all_keys_exhausted_prints_friendly_message_and_continues(self):
		from libs.core.main_loop import run_interpreter_main
		from libs.key_manager import AllKeysExhaustedError
		from tests.interactive.helpers import make_interp

		interp = make_interp()
		interp.args.free = False
		interp._safe_input.side_effect = ["do something", "/exit"]
		interp._generate_content_with_retries = MagicMock(
			side_effect=AllKeysExhaustedError(
				"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
				provider="openai",
				earliest_recovery_ts=1815000000.0,
			)
		)

		with patch("libs.interpreter_lib.display_markdown_message") as md, \
		     patch("libs.interpreter_lib.display_code"):
			run_interpreter_main(interp, "3.4.0")

		self.assertTrue(md.called)
		messages = " ".join(str(call.args[0]) for call in md.call_args_list if call.args)
		self.assertIn("openai", messages)
		self.assertIn("2026-07-13T12:00:00Z", messages)
```

This requires `MagicMock`/`patch` to already be imported in `tests/interactive/test_cli_interactive_live.py` — they are (line 41: `from unittest.mock import MagicMock, patch`).

- [ ] **Step 13: Run test to verify it fails**

Run: `python -m unittest tests.interactive.test_cli_interactive_live.TestInteractiveKeyExhaustion -v`
Expected: FAIL — either the raw `AllKeysExhaustedError` propagates out of `run_interpreter_main` (uncaught), or `md.called` is `False`/the message doesn't mention `"openai"`.

- [ ] **Step 14: Add the import**

In `libs/core/main_loop.py`, after the existing imports (line 1-10: `from __future__ import annotations; import json, os, shutil, subprocess, time; from libs.logger import Logger`), add:

```python
from libs.key_manager import AllKeysExhaustedError
```

- [ ] **Step 15: Handle the exception in the final except-block**

In `libs/core/main_loop.py`, replace the current lines 1149-1157:

```python
	except Exception as exception:
		error_text = str(exception)
		if interp._is_recoverable_runtime_error(error_text):
			interp.logger.warning(f"Recoverable interpreter error: {error_text}")
			display_markdown_message(f"Request failed: {interp._format_runtime_error_message(error_text)}")
			display_markdown_message("Try `/model <name>` to switch models or `/list` to see the available options.")
			continue
		interp.logger.error(f"An error occurred in interpreter_lib: {error_text}")
		raise
```

with:

```python
	except Exception as exception:
		if isinstance(exception, AllKeysExhaustedError):
			provider = exception.provider or "the configured provider"
			eta = exception.earliest_recovery_ts
			eta_str = (
				time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(eta))
				if eta is not None
				else "unknown"
			)
			interp.logger.warning(
				f"All keys exhausted for provider '{provider}'. Earliest recovery: {eta_str}"
			)
			display_markdown_message(
				f"**All API keys for `{provider}` are currently exhausted.** Earliest recovery: `{eta_str}`."
			)
			display_markdown_message(
				"Try `/model <name>` to switch providers, or re-run with `--free` to "
				"auto-fallback to a free model next time."
			)
			continue
		error_text = str(exception)
		if interp._is_recoverable_runtime_error(error_text):
			interp.logger.warning(f"Recoverable interpreter error: {error_text}")
			display_markdown_message(f"Request failed: {interp._format_runtime_error_message(error_text)}")
			display_markdown_message("Try `/model <name>` to switch models or `/list` to see the available options.")
			continue
		interp.logger.error(f"An error occurred in interpreter_lib: {error_text}")
		raise
```

`time` is already imported at module top (confirmed), so no new import is needed for `time.strftime`/`time.gmtime`.

- [ ] **Step 16: Run test to verify it passes**

Run: `python -m unittest tests.interactive.test_cli_interactive_live.TestInteractiveKeyExhaustion -v`
Expected: PASS

- [ ] **Step 17: Run the full interactive suite to check for regressions**

Run: `python -m unittest discover -s tests/interactive -v`
Expected: all PASS

- [ ] **Step 18: Commit**

```bash
git add libs/core/main_loop.py tests/interactive/test_cli_interactive_live.py
git commit -m "fix(repl): catch AllKeysExhaustedError instead of crashing with a raw traceback"
```

---

### Task 3: Free-model fallback on exhaustion (agentic/yolo parity for classic path)

**Files:**
- Modify: `libs/core/model_router.py` (new method `_attempt_free_fallback_retry`; wrap bodies of `generate_content_with_retries` and `generate_content_with_retries_async`)
- Test: `tests/core/test_model_router.py`

**Interfaces:**
- Consumes: `libs.agent.llm.complete_with_free_fallback(model_name, messages, *, enable_free_fallback=True, ...) -> Tuple[Any, Dict[str, Any]]` (existing, unmodified); `interp.get_prompt(message, chat_history)` (existing, unmodified); `interp.utility_manager._extract_content(response)` (existing, unmodified); `AllKeysExhaustedError.provider`/`.earliest_recovery_ts` from Task 1.
- Produces: `ModelRouter._attempt_free_fallback_retry(self, interp, message, chat_history, config_values) -> Optional[str]` — returns extracted response text on success, `None` on failure. `generate_content_with_retries`/`generate_content_with_retries_async` now attempt one free-fallback call before re-raising `AllKeysExhaustedError`, gated by `getattr(interp.args, "free", False)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_model_router.py` (the existing file has no `import os` — add it alongside the existing `import unittest` / `from argparse import Namespace` / `from unittest.mock import ...` imports at the top):

```python
	def test_generate_content_with_retries_free_fallback_success(self):
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = True
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback") as fallback, \
		     patch.object(interp.utility_manager, "_extract_content", return_value="fallback text"):
			fake_response = MagicMock()
			fallback.return_value = (fake_response, {"provider": "groq"})
			result = interp.model_router.generate_content_with_retries(
				"hello", [], config_values={},
				sleep_fn=lambda *_: None, display_fn=lambda *_: None,
			)

		self.assertEqual(result, "fallback text")
		fallback.assert_called_once()

	def test_generate_content_with_retries_free_fallback_disabled_raises(self):
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = False
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback") as fallback:
			with self.assertRaises(AllKeysExhaustedError):
				interp.model_router.generate_content_with_retries(
					"hello", [], config_values={},
					sleep_fn=lambda *_: None, display_fn=lambda *_: None,
				)
		fallback.assert_not_called()

	def test_generate_content_with_retries_free_fallback_itself_fails_raises_original(self):
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = True
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback", side_effect=RuntimeError("no free provider configured")):
			with self.assertRaises(AllKeysExhaustedError):
				interp.model_router.generate_content_with_retries(
					"hello", [], config_values={},
					sleep_fn=lambda *_: None, display_fn=lambda *_: None,
				)

	def test_generate_content_with_retries_async_free_fallback_success(self):
		import asyncio
		from libs.key_manager import AllKeysExhaustedError

		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 1
		interp.config_values = {}
		interp.args.free = True
		km = MagicMock()
		km.acquire_key.return_value = None
		km.has_pool.return_value = True
		km.raise_if_exhausted.side_effect = AllKeysExhaustedError(
			"All keys exhausted for provider 'openai'. Earliest recovery: 2026-07-13T12:00:00Z",
			provider="openai",
			earliest_recovery_ts=1815000000.0,
		)
		interp._key_manager = km

		with patch("libs.agent.llm.complete_with_free_fallback") as fallback, \
		     patch.object(interp.utility_manager, "_extract_content", return_value="async fallback text"):
			fake_response = MagicMock()
			fallback.return_value = (fake_response, {"provider": "groq"})
			result = asyncio.run(
				interp.model_router.generate_content_with_retries_async(
					"hello", [], config_values={},
					sleep_fn=lambda *_: None, display_fn=lambda *_: None,
				)
			)

		self.assertEqual(result, "async fallback text")
		fallback.assert_called_once()
```

These four new tests are methods on the existing `TestModelRouter` class (the one whose `_make_interp` helper is quoted in this plan's Task 7 section — same class, added alongside the existing 6 tests).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.core.test_model_router.TestModelRouter -v -k free_fallback`
Expected: FAIL — `AllKeysExhaustedError` propagates uncaught in every case (no fallback attempt exists yet).

- [ ] **Step 3: Add the fallback helper method**

In `libs/core/model_router.py`, add this method to the `ModelRouter` class (near the other private helpers, e.g. directly above or below `_prepare_retry_key`):

```python
	def _attempt_free_fallback_retry(self, interp, message, chat_history, config_values):
		"""One-shot fallback to a free/open model after the configured provider is exhausted.

		Returns the extracted response text on success, or ``None`` if the fallback
		itself failed (callers should then surface the original exhaustion error).
		"""
		from libs.agent.llm import complete_with_free_fallback

		prompt = interp.get_prompt(message, chat_history)
		messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": str(prompt)}]
		try:
			response, _metrics = complete_with_free_fallback(
				model_name=getattr(interp, "INTERPRETER_MODEL", "gpt-4o"),
				messages=messages,
				enable_free_fallback=True,
			)
		except Exception:
			return None
		return interp.utility_manager._extract_content(response)
```

- [ ] **Step 4: Wrap `generate_content_with_retries` in the outer try/except**

In `libs/core/model_router.py`, locate `def generate_content_with_retries(self, message, chat_history, *, config_values=None, image_file=None, sleep_fn=None, display_fn=None):` (or its exact current signature). Wrap its entire existing body (the `for attempt in range(...): ...` loop, unchanged internally) as follows — keep every line of the current body exactly as-is, only adding the `try:` before it (indented one level in) and the `except AllKeysExhaustedError:` block after:

```python
	def generate_content_with_retries(self, message, chat_history, *, config_values=None, image_file=None, sleep_fn=None, display_fn=None):
		interp = self.interp
		try:
			# <<< existing method body, unchanged, indented one level deeper >>>
			...
		except AllKeysExhaustedError as exc:
			if getattr(interp.args, "free", False):
				fallback_text = self._attempt_free_fallback_retry(
					interp, message, chat_history, config_values
				)
				if fallback_text is not None:
					return fallback_text
			raise
```

Do this by indenting the current method body one level and adding the `try:`/`except` wrapper around it — no internal line of the existing body changes.

- [ ] **Step 5: Wrap `generate_content_with_retries_async` the same way**

Apply the identical wrap to `generate_content_with_retries_async`, using `await asyncio.to_thread(...)` since `_attempt_free_fallback_retry` is synchronous:

```python
	async def generate_content_with_retries_async(self, message, chat_history, *, config_values=None, image_file=None, sleep_fn=None, display_fn=None):
		interp = self.interp
		try:
			# <<< existing method body, unchanged, indented one level deeper >>>
			...
		except AllKeysExhaustedError as exc:
			if getattr(interp.args, "free", False):
				fallback_text = await asyncio.to_thread(
					self._attempt_free_fallback_retry, interp, message, chat_history, config_values
				)
				if fallback_text is not None:
					return fallback_text
			raise
```

`asyncio` must already be imported in `libs/core/model_router.py` for the async method to exist at all — if the top-of-file import list does not already include `import asyncio`, add it.

- [ ] **Step 6: Add the `AllKeysExhaustedError` import**

At the top of `libs/core/model_router.py`, add (if not already present):

```python
from libs.key_manager import AllKeysExhaustedError
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m unittest tests.core.test_model_router.TestModelRouter -v -k free_fallback`
Expected: all 4 PASS

- [ ] **Step 8: Run the full model_router suite to check for regressions**

Run: `python -m unittest tests.core.test_model_router -v`
Expected: all PASS (the pre-existing 6 tests plus the 4 new ones plus Task 7's rotation test once added)

- [ ] **Step 9: Commit**

```bash
git add libs/core/model_router.py tests/core/test_model_router.py
git commit -m "feat(model-router): attempt one free-model fallback before surfacing key exhaustion"
```

---

### Task 4: Banner/status-line width — never wrap or truncate

**Files:**
- Modify: `libs/agent/gemini_ui.py` (module imports; `_safe_print`; `render_banner`)
- Modify: `libs/core/session.py` (`display_session_banner`)
- Test: `tests/test_gemini_ui.py`, `tests/test_unit_coverage_gaps2.py`

**Interfaces:**
- Produces: `_safe_print` now always calls `console.print(..., overflow="crop", no_wrap=True)`; `render_banner`'s resolved width is `min(explicit_or_console_width, shutil.get_terminal_size(fallback=(80, 24)).columns)`; `display_session_banner` prints with `overflow="crop"` instead of `overflow="ignore"`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_gemini_ui.py`. First add the missing imports at the top of the file (it currently has `from __future__ import annotations; import io; import unittest;` and a `from libs.agent.gemini_ui import (...)` block, with no `unittest.mock`/`os` imports):

```python
import os
from unittest.mock import MagicMock, patch
```

Then add these two new tests (as a new test class, e.g. after `TestBannerRendering`):

```python
class TestSafePrintOverflow(unittest.TestCase):
	def test_safe_print_forces_crop_and_no_wrap(self):
		from libs.agent.gemini_ui import _safe_print

		console = MagicMock()
		_safe_print(console, "hello", "hello-ascii")
		console.print.assert_called_once_with("hello", overflow="crop", no_wrap=True)


class TestRenderBannerTerminalSizeCrossCheck(TestBannerRendering):
	def test_render_banner_uses_min_of_console_width_and_terminal_size(self):
		from libs.agent.gemini_ui import render_banner

		console, buf = self._console(width=200)
		with patch(
			"libs.agent.gemini_ui.shutil.get_terminal_size",
			return_value=os.terminal_size((20, 24)),
		):
			render_banner(console)
		self.assertIn("INTERPRETER", buf.getvalue())
```

`TestRenderBannerTerminalSizeCrossCheck` subclasses `TestBannerRendering` to reuse its `_console(self, width=100, encoding="utf-8", legacy_windows=False)` helper (confirmed existing at line 137-141).

Also strengthen the existing assertion in `tests/test_unit_coverage_gaps2.py::TestCoreSessionHelpers.test_cli_coercion_helpers` (around line 319, the `console.print.assert_called()` line inside the `display_session_banner(...)` block):

```python
		console.print.assert_called()
		self.assertEqual(console.print.call_args.kwargs.get("overflow"), "crop")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_gemini_ui.TestSafePrintOverflow tests.test_gemini_ui.TestRenderBannerTerminalSizeCrossCheck -v`
Expected: FAIL — `_safe_print` currently calls `console.print(renderable)` with no `overflow`/`no_wrap` kwargs; `render_banner` currently has no `shutil` cross-check so `console.width=200` alone drives `pixel_width=2` (not the ascii-fallback path).

Run: `python -m unittest tests.test_unit_coverage_gaps2.TestCoreSessionHelpers.test_cli_coercion_helpers -v`
Expected: FAIL — `call_args.kwargs.get("overflow")` is currently `"ignore"`, not `"crop"`.

- [ ] **Step 3: Fix `_safe_print` in `libs/agent/gemini_ui.py`**

Add `import shutil` to the module's import block (currently lines 1-15, no `shutil` import). Replace the current `_safe_print` body:

```python
def _safe_print(console, renderable, ascii_fallback: str) -> None:
	"""Print ``renderable``; fall back to plain ASCII text on encode errors.

	Mirrors the Windows cp1252-safe pattern already used by
	``libs/onboarding.py`` so glyph-heavy output never crashes narrow consoles.
	"""
	try:
		console.print(renderable)
	except UnicodeEncodeError:
		logger.debug("Unicode render failed; using ASCII-safe fallback")
		try:
			console.print(ascii_fallback)
		except Exception:
			print(ascii_fallback)
	except Exception as exc:
		logger.debug("Console print failed (%s); using ASCII-safe fallback", exc)
		try:
			console.print(ascii_fallback)
		except Exception:
			print(ascii_fallback)
```

with:

```python
def _safe_print(console, renderable, ascii_fallback: str) -> None:
	"""Print ``renderable``; fall back to plain ASCII text on encode errors.

	Mirrors the Windows cp1252-safe pattern already used by
	``libs/onboarding.py`` so glyph-heavy output never crashes narrow consoles.
	Always forces ``overflow="crop", no_wrap=True`` so a wrong width reading
	degrades to a clipped-but-legible line instead of wraparound corruption.
	"""
	try:
		console.print(renderable, overflow="crop", no_wrap=True)
	except UnicodeEncodeError:
		logger.debug("Unicode render failed; using ASCII-safe fallback")
		try:
			console.print(ascii_fallback, overflow="crop", no_wrap=True)
		except Exception:
			print(ascii_fallback)
	except Exception as exc:
		logger.debug("Console print failed (%s); using ASCII-safe fallback", exc)
		try:
			console.print(ascii_fallback, overflow="crop", no_wrap=True)
		except Exception:
			print(ascii_fallback)
```

- [ ] **Step 4: Add the `shutil` width cross-check to `render_banner`**

In `libs/agent/gemini_ui.py`, `render_banner` currently resolves width as:

```python
	term_width = int(width if width is not None else getattr(console, "width", 80) or 80)
```

Replace with:

```python
	term_width = int(width if width is not None else getattr(console, "width", 80) or 80)
	try:
		term_width = min(term_width, shutil.get_terminal_size(fallback=(80, 24)).columns)
	except Exception:
		pass
```

- [ ] **Step 5: Fix `display_session_banner` in `libs/core/session.py`**

Replace the current final line:

```python
	console.print(f"[{mode_style}]{session_line}[/{mode_style}]", overflow="ignore", no_wrap=True)
```

with:

```python
	console.print(f"[{mode_style}]{session_line}[/{mode_style}]", overflow="crop", no_wrap=True)
```

No `shutil` cross-check is added to `display_session_banner` — unlike `render_banner`, this function has no `term_width` variable at all; it is a single-line `console.print` call that relies entirely on Rich's own auto-detected `console.width`, so only the `overflow` mode needed fixing.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m unittest tests.test_gemini_ui -v`
Expected: all PASS, including the existing `test_render_banner_does_not_crash_at_standard_widths` (loops widths 40/60/80/100/120 — unaffected since in a non-tty test run `shutil.get_terminal_size(fallback=(80,24))` returns the `(80, 24)` fallback, so `min(120, 80) = 80` still yields `pixel_width=2`, non-breaking) and `test_render_banner_narrow_width_falls_back_to_plain_text`.

Run: `python -m unittest tests.test_unit_coverage_gaps2.TestCoreSessionHelpers.test_cli_coercion_helpers -v`
Expected: PASS

- [ ] **Step 7: Manual terminal-resize verification (not unit-testable)**

This is a rendering bug — per the design spec, the real proof is a terminal transcript, not just a unit test. Run interactively in a real terminal:

```bash
python interpreter.py --cli --gemini-style
```

Resize the terminal window narrower (e.g. to ~40 columns) and wider (e.g. to ~160 columns) while the banner/status line is visible, and confirm no wraparound or mid-word truncation in either case (e.g. no repeat of the `Src=inpu` cut). Record the observation in the plan's execution notes (Task 12).

- [ ] **Step 8: Commit**

```bash
git add libs/agent/gemini_ui.py libs/core/session.py tests/test_gemini_ui.py tests/test_unit_coverage_gaps2.py
git commit -m "fix(ui): force crop overflow and cross-check terminal size so banners never wrap"
```

---

### Task 5: Fixtures — commit representative dummy_media files

**Files:**
- Create: `tests/fixtures/input/archive.zip`, `tests/fixtures/input/audio.mp3`, `tests/fixtures/input/Hello.java`, `tests/fixtures/input/app.sqlite`, `tests/fixtures/input/document.docx`, `tests/fixtures/input/logo.svg`, `tests/fixtures/input/clip.webm`
- Modify: `tests/live/scenarios/fixtures.py:93-123` (the `paths` dict inside `ensure_scenario_fixtures`)

**Interfaces:**
- Produces: `ensure_scenario_fixtures()["paths"]` gains 7 new input keys (`archive_zip`, `audio_mp3`, `java_src`, `app_sqlite`, `docx_doc`, `svg_logo`, `video_webm`) and 11 new output keys (`zip_list_txt`, `zip_extract_dir`, `zip_extract_manifest`, `zip_created`, `java_summary_txt`, `sqlite_report_txt`, `sqlite_edit_copy`, `docx_text_txt`, `svg_analysis_txt`, `webm_probe_txt`, `mp3_probe_txt`), consumed by Task 6's new `ScenarioCase` entries.

- [ ] **Step 1: Copy the 7 source files into committed fixtures**

```bash
mkdir -p tests/fixtures/input
cp "D:\tmp\dummy_media\backup_archive.zip" tests/fixtures/input/archive.zip
cp "D:\tmp\dummy_media\demo_audio.mp3" tests/fixtures/input/audio.mp3
cp "D:\tmp\dummy_media\HelloWorld.java" tests/fixtures/input/Hello.java
cp "D:\tmp\dummy_media\local_database.sqlite" tests/fixtures/input/app.sqlite
cp "D:\tmp\dummy_media\demo_word.docx" tests/fixtures/input/document.docx
cp "D:\tmp\dummy_media\vector_logo.svg" tests/fixtures/input/logo.svg
cp "D:\tmp\dummy_media\video_webm_30fps.webm" tests/fixtures/input/clip.webm
```

This is the only place `D:\tmp\dummy_media` is ever referenced — a one-time local copy command run by the implementer, never checked into any script or source file (satisfies the "never hardcode `D:\tmp\dummy_media`" constraint: the path appears only in this plan's shell instructions, not in the repository).

- [ ] **Step 2: Verify the files are picked up by the generic copy loop**

`tests/live/scenarios/fixtures.py`'s `ensure_scenario_fixtures` already does:

```python
	for src in REPO_INPUT.iterdir():
		if src.is_file():
			shutil.copy2(src, input_dir / src.name)
```

No change is needed to this loop — any new file under `tests/fixtures/input/` is copied automatically into the per-run workdir.

- [ ] **Step 3: Extend the `paths` dict**

In `tests/live/scenarios/fixtures.py`, the `paths = {` dict currently ends (lines 93-123):

```python
		paths = {
			"json": _p("input", "sales.json"),
			"png": _p("input", "sample.png"),
			"pdf": _p("input", "sample.pdf"),
			"csv": _p("input", "sales.csv"),
			"edit_csv": _p("input", "editable.csv"),
			"notes": _p("input", "notes.txt"),
			"md": _p("input", "brief.md"),
			"expected_csv": _p("expected", "sales_from_json.csv"),
			"expected_summary": _p("expected", "summary_example.txt"),
			"expected_report": _p("expected", "report_example.txt"),
			"abs_read": str(abs_read.resolve()),
			"abs_write": _p("output", "user_intent_out.txt"),
			"chart_png": _p("output", "chart_mpl.png"),
			"pipe_csv": _p("output", "pipeline_sales.csv"),
			"pipe_chart": _p("output", "pipeline_chart.png"),
			"stats_report": _p("output", "csv_stats_report.txt"),
			"chart_plotly": _p("output", "chart_plotly.html"),
			"jpg_out": _p("output", "converted.jpg"),
			"crop_out": _p("output", "cropped.jpg"),
			"crop_png_out": _p("output", "cropped.png"),
			"csv_from_json": _p("output", "sales_from_json.csv"),
			"report_txt": _p("output", "report.txt"),
			"summary_txt": _p("output", "summary.txt"),
			"agentic_summary": _p("output", "agentic_summary_report.txt"),
			"analysis_txt": _p("output", "analysis.txt"),
			"app_script": _p("apps", "hello_app.py"),
			"app_out": _p("apps", "hello_out.txt"),
			"complex_app": _p("apps", "complex_mini_app.py"),
			"complex_app_out": _p("apps", "complex_mini_out.txt"),
			"search_report": _p("output", "search_report.txt"),
			"free_fallback_marker": _p("output", "free_fallback_ok.txt"),
			"fixture_dir": str(fixture_dir.resolve()),
			"repo_fixtures": str(REPO_FIXTURES.resolve()),
			"out_dir": str(out_dir.resolve()),
			"apps_dir": str(apps_dir.resolve()),
		}
```

Replace it with (same dict, 18 new entries added — 7 input keys inserted after `"notes"`, 11 output keys inserted after `"analysis_txt"`):

```python
		paths = {
			"json": _p("input", "sales.json"),
			"png": _p("input", "sample.png"),
			"pdf": _p("input", "sample.pdf"),
			"csv": _p("input", "sales.csv"),
			"edit_csv": _p("input", "editable.csv"),
			"notes": _p("input", "notes.txt"),
			"archive_zip": _p("input", "archive.zip"),
			"audio_mp3": _p("input", "audio.mp3"),
			"java_src": _p("input", "Hello.java"),
			"app_sqlite": _p("input", "app.sqlite"),
			"docx_doc": _p("input", "document.docx"),
			"svg_logo": _p("input", "logo.svg"),
			"video_webm": _p("input", "clip.webm"),
			"md": _p("input", "brief.md"),
			"expected_csv": _p("expected", "sales_from_json.csv"),
			"expected_summary": _p("expected", "summary_example.txt"),
			"expected_report": _p("expected", "report_example.txt"),
			"abs_read": str(abs_read.resolve()),
			"abs_write": _p("output", "user_intent_out.txt"),
			"chart_png": _p("output", "chart_mpl.png"),
			"pipe_csv": _p("output", "pipeline_sales.csv"),
			"pipe_chart": _p("output", "pipeline_chart.png"),
			"stats_report": _p("output", "csv_stats_report.txt"),
			"chart_plotly": _p("output", "chart_plotly.html"),
			"jpg_out": _p("output", "converted.jpg"),
			"crop_out": _p("output", "cropped.jpg"),
			"crop_png_out": _p("output", "cropped.png"),
			"csv_from_json": _p("output", "sales_from_json.csv"),
			"report_txt": _p("output", "report.txt"),
			"summary_txt": _p("output", "summary.txt"),
			"agentic_summary": _p("output", "agentic_summary_report.txt"),
			"analysis_txt": _p("output", "analysis.txt"),
			"zip_list_txt": _p("output", "zip_list.txt"),
			"zip_extract_dir": _p("output", "zip_extract"),
			"zip_extract_manifest": _p("output", "zip_extract_manifest.txt"),
			"zip_created": _p("output", "created_archive.zip"),
			"java_summary_txt": _p("output", "java_summary.txt"),
			"sqlite_report_txt": _p("output", "sqlite_report.txt"),
			"sqlite_edit_copy": _p("output", "app_edited.sqlite"),
			"docx_text_txt": _p("output", "docx_text.txt"),
			"svg_analysis_txt": _p("output", "svg_analysis.txt"),
			"webm_probe_txt": _p("output", "webm_probe.txt"),
			"mp3_probe_txt": _p("output", "mp3_probe.txt"),
			"app_script": _p("apps", "hello_app.py"),
			"app_out": _p("apps", "hello_out.txt"),
			"complex_app": _p("apps", "complex_mini_app.py"),
			"complex_app_out": _p("apps", "complex_mini_out.txt"),
			"search_report": _p("output", "search_report.txt"),
			"free_fallback_marker": _p("output", "free_fallback_ok.txt"),
			"fixture_dir": str(fixture_dir.resolve()),
			"repo_fixtures": str(REPO_FIXTURES.resolve()),
			"out_dir": str(out_dir.resolve()),
			"apps_dir": str(apps_dir.resolve()),
		}
```

`zip_extract_dir` is a directory path, not a file — it does not need to exist yet when `ensure_scenario_fixtures` runs; Task 6's `dummy_zip_extract` scenario creates it at run time with `os.makedirs(extract_dir, exist_ok=True)`.

- [ ] **Step 4: Write a fixtures smoke test**

Add to `tests/live/scenarios/test_fixtures.py` if it exists, else create it:

```python
# -*- coding: utf-8 -*-
"""Smoke tests for the live-scenario fixture sync."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests.live.scenarios.fixtures import ensure_scenario_fixtures


class TestScenarioFixturesNewFileTypes(unittest.TestCase):
	def test_new_dummy_media_fixtures_are_synced(self):
		with tempfile.TemporaryDirectory() as tmp:
			result = ensure_scenario_fixtures(root=Path(tmp))
			paths = result["paths"]
			for key in (
				"archive_zip", "audio_mp3", "java_src", "app_sqlite",
				"docx_doc", "svg_logo", "video_webm",
			):
				self.assertTrue(os.path.isfile(paths[key]), f"{key} -> {paths[key]}")
				self.assertGreater(os.path.getsize(paths[key]), 0)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 5: Run the test**

Run: `python -m unittest tests.live.scenarios.test_fixtures -v`
Expected: PASS (fails first if Step 1's copy was skipped — confirms the fixture files actually landed in `tests/fixtures/input/`)

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/input/archive.zip tests/fixtures/input/audio.mp3 tests/fixtures/input/Hello.java tests/fixtures/input/app.sqlite tests/fixtures/input/document.docx tests/fixtures/input/logo.svg tests/fixtures/input/clip.webm tests/live/scenarios/fixtures.py tests/live/scenarios/test_fixtures.py
git commit -m "test(fixtures): commit representative zip/mp3/java/sqlite/docx/svg/webm fixtures"
```

---

### Task 6: New `ScenarioCase` entries for the 7 new file types

**Files:**
- Modify: `tests/live/scenarios/cases.py` (add 10 new `ScenarioCase` entries to the list built inside `build_scenario_cases`, in the same `cases.extend([...])` block that holds the existing `offline_exec` cases)

**Interfaces:**
- Consumes: `p` (the `paths` dict from Task 5's `ensure_scenario_fixtures()["paths"]`, already the variable name used throughout `cases.py`'s existing `offline_exec` cases); `ScenarioCase(id, category, tier, kind, no_sandbox, code, expect_markers, expect_artifacts, timeout_s)` and `ArtifactExpect(path, min_bytes=1, kind="any", contains=None, optional=False)` (both existing, unmodified).
- Produces: 10 new scenario IDs consumed by `scripts/run_live_scenarios.py` and Task 9's live run: `dummy_zip_list`, `dummy_zip_extract`, `dummy_zip_create`, `dummy_java_summarize`, `dummy_sqlite_report`, `dummy_sqlite_edit`, `dummy_docx_extract_text`, `dummy_svg_analyze`, `dummy_webm_probe`, `dummy_mp3_probe`.

- [ ] **Step 1: Write the failing test**

Add to `tests/live/scenarios/test_fixtures.py` (from Task 5) or a new `tests/live/scenarios/test_cases.py`:

```python
# -*- coding: utf-8 -*-
"""Structural checks for the dummy_media ScenarioCase additions."""

from __future__ import annotations

import unittest

from tests.live.scenarios.cases import build_scenario_cases

_EXPECTED_DUMMY_IDS = {
	"dummy_zip_list", "dummy_zip_extract", "dummy_zip_create",
	"dummy_java_summarize", "dummy_sqlite_report", "dummy_sqlite_edit",
	"dummy_docx_extract_text", "dummy_svg_analyze", "dummy_webm_probe",
	"dummy_mp3_probe",
}


class TestDummyMediaScenarioCases(unittest.TestCase):
	def test_all_dummy_media_cases_present(self):
		cases = build_scenario_cases()
		ids = {c.id for c in cases}
		missing = _EXPECTED_DUMMY_IDS - ids
		self.assertFalse(missing, f"missing scenario ids: {missing}")

	def test_all_dummy_media_cases_cover_create_analyze_summarize_convert_edit(self):
		cases = {c.id: c for c in build_scenario_cases() if c.id in _EXPECTED_DUMMY_IDS}
		categories = {c.category for c in cases.values()}
		self.assertTrue({"create", "analyze", "summarize", "convert", "edit"} <= categories)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.live.scenarios.test_cases -v`
Expected: FAIL — `missing scenario ids` lists all 10.

- [ ] **Step 3: Add the 10 `ScenarioCase` entries**

In `tests/live/scenarios/cases.py`, inside the `cases.extend([...])` block that already holds `offline_analyze_json`/`offline_convert_json_csv`/etc. (the `offline_exec` block, `no_sandbox=True` cases), append these 10 entries before the block's closing `]`:

```python
			ScenarioCase(
				id="dummy_zip_list",
				category="analyze",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import zipfile\n"
					f"zf = zipfile.ZipFile(r'{p['archive_zip']}')\n"
					"names = zf.namelist()\n"
					"lines = ['{} {}'.format(n, zf.getinfo(n).file_size) for n in names]\n"
					f"open(r'{p['zip_list_txt']}', 'w', encoding='utf-8').write('\\n'.join(lines) + '\\n')\n"
					"print('ZIP_LIST_OK', len(names))\n"
				),
				expect_markers=["ZIP_LIST_OK"],
				expect_artifacts=[
					ArtifactExpect(p["zip_list_txt"], kind="txt"),
				],
			),
			ScenarioCase(
				id="dummy_zip_extract",
				category="convert",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import os, zipfile\n"
					f"extract_dir = r'{p['zip_extract_dir']}'\n"
					"os.makedirs(extract_dir, exist_ok=True)\n"
					f"zf = zipfile.ZipFile(r'{p['archive_zip']}')\n"
					"zf.extractall(extract_dir)\n"
					"extracted = sorted(os.listdir(extract_dir))\n"
					f"open(r'{p['zip_extract_manifest']}', 'w', encoding='utf-8').write('\\n'.join(extracted) + '\\n')\n"
					"print('ZIP_EXTRACT_OK', len(extracted))\n"
				),
				expect_markers=["ZIP_EXTRACT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["zip_extract_manifest"], kind="txt"),
				],
			),
			ScenarioCase(
				id="dummy_zip_create",
				category="create",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import zipfile\n"
					f"with zipfile.ZipFile(r'{p['zip_created']}', 'w', zipfile.ZIP_DEFLATED) as zf:\n"
					f"    zf.write(r'{p['notes']}', arcname='notes.txt')\n"
					f"created = zipfile.ZipFile(r'{p['zip_created']}')\n"
					"names = created.namelist()\n"
					"assert 'notes.txt' in names\n"
					"print('ZIP_CREATE_OK', names)\n"
				),
				expect_markers=["ZIP_CREATE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["zip_created"], kind="any"),
				],
			),
			ScenarioCase(
				id="dummy_java_summarize",
				category="summarize",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import re\n"
					f"src = open(r'{p['java_src']}', encoding='utf-8').read()\n"
					"cls_match = re.search(r'class\\s+(\\w+)', src)\n"
					"cls_name = cls_match.group(1) if cls_match else 'unknown'\n"
					"methods = re.findall(r'(?:public|private|protected)\\s+[\\w<>\\[\\]]+\\s+(\\w+)\\s*\\([^)]*\\)', src)\n"
					"out_lines = ['CLASS=' + cls_name, 'METHODS=' + ','.join(methods)]\n"
					f"open(r'{p['java_summary_txt']}', 'w', encoding='utf-8').write('\\n'.join(out_lines) + '\\n')\n"
					"print('JAVA_SUMMARY_OK', cls_name, len(methods))\n"
				),
				expect_markers=["JAVA_SUMMARY_OK"],
				expect_artifacts=[
					ArtifactExpect(p["java_summary_txt"], kind="txt", contains="CLASS="),
				],
			),
			ScenarioCase(
				id="dummy_sqlite_report",
				category="analyze",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import sqlite3\n"
					f"conn = sqlite3.connect(r'{p['app_sqlite']}')\n"
					"cur = conn.cursor()\n"
					"cur.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")\n"
					"tables = [row[0] for row in cur.fetchall()]\n"
					"lines = []\n"
					"for t in tables:\n"
					"    cur.execute('SELECT COUNT(*) FROM \"' + t + '\"')\n"
					"    lines.append(t + ': ' + str(cur.fetchone()[0]) + ' rows')\n"
					"conn.close()\n"
					f"open(r'{p['sqlite_report_txt']}', 'w', encoding='utf-8').write('\\n'.join(lines) + '\\n')\n"
					"print('SQLITE_REPORT_OK', len(tables))\n"
				),
				expect_markers=["SQLITE_REPORT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["sqlite_report_txt"], kind="txt"),
				],
			),
			ScenarioCase(
				id="dummy_sqlite_edit",
				category="edit",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import shutil, sqlite3\n"
					f"shutil.copy2(r'{p['app_sqlite']}', r'{p['sqlite_edit_copy']}')\n"
					f"conn = sqlite3.connect(r'{p['sqlite_edit_copy']}')\n"
					"cur = conn.cursor()\n"
					"cur.execute('CREATE TABLE IF NOT EXISTS _edit_marker (note TEXT)')\n"
					"cur.execute('INSERT INTO _edit_marker (note) VALUES (?)', ('dummy_sqlite_edit scenario',))\n"
					"conn.commit()\n"
					"cur.execute('SELECT COUNT(*) FROM _edit_marker')\n"
					"count = cur.fetchone()[0]\n"
					"conn.close()\n"
					"assert count >= 1\n"
					"print('SQLITE_EDIT_OK', count)\n"
				),
				expect_markers=["SQLITE_EDIT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["sqlite_edit_copy"], kind="any"),
				],
			),
			ScenarioCase(
				id="dummy_docx_extract_text",
				category="convert",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import zipfile\n"
					"import xml.etree.ElementTree as ET\n"
					f"zf = zipfile.ZipFile(r'{p['docx_doc']}')\n"
					"xml_bytes = zf.read('word/document.xml')\n"
					"root = ET.fromstring(xml_bytes)\n"
					"wns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'\n"
					"paragraphs = []\n"
					"for p_el in root.iter(wns + 'p'):\n"
					"    texts = [t.text or '' for t in p_el.iter(wns + 't')]\n"
					"    paragraphs.append(''.join(texts))\n"
					f"open(r'{p['docx_text_txt']}', 'w', encoding='utf-8').write('\\n'.join(paragraphs) + '\\n')\n"
					"print('DOCX_TEXT_OK', len(paragraphs))\n"
				),
				expect_markers=["DOCX_TEXT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["docx_text_txt"], kind="txt"),
				],
			),
			ScenarioCase(
				id="dummy_svg_analyze",
				category="analyze",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import xml.etree.ElementTree as ET\n"
					f"tree = ET.parse(r'{p['svg_logo']}')\n"
					"root = tree.getroot()\n"
					"width = root.get('width', 'unknown')\n"
					"height = root.get('height', 'unknown')\n"
					"elem_count = sum(1 for _ in root.iter())\n"
					"out_lines = ['WIDTH=' + str(width), 'HEIGHT=' + str(height), 'ELEMENTS=' + str(elem_count)]\n"
					f"open(r'{p['svg_analysis_txt']}', 'w', encoding='utf-8').write('\\n'.join(out_lines) + '\\n')\n"
					"print('SVG_ANALYZE_OK', elem_count)\n"
				),
				expect_markers=["SVG_ANALYZE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["svg_analysis_txt"], kind="txt", contains="ELEMENTS="),
				],
			),
			ScenarioCase(
				id="dummy_webm_probe",
				category="analyze",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import os\n"
					f"path = r'{p['video_webm']}'\n"
					"data = open(path, 'rb').read(4)\n"
					"is_ebml = data == b'\\x1a\\x45\\xdf\\xa3'\n"
					"size_bytes = os.path.getsize(path)\n"
					"out_lines = ['EBML_HEADER=' + str(is_ebml), 'SIZE_BYTES=' + str(size_bytes)]\n"
					f"open(r'{p['webm_probe_txt']}', 'w', encoding='utf-8').write('\\n'.join(out_lines) + '\\n')\n"
					"assert is_ebml\n"
					"print('WEBM_PROBE_OK', size_bytes)\n"
				),
				expect_markers=["WEBM_PROBE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["webm_probe_txt"], kind="txt", contains="EBML_HEADER=True"),
				],
			),
			ScenarioCase(
				id="dummy_mp3_probe",
				category="analyze",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import os\n"
					f"path = r'{p['audio_mp3']}'\n"
					"data = open(path, 'rb').read(4)\n"
					"has_id3 = data[:3] == b'ID3'\n"
					"has_frame_sync = len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0\n"
					"is_mp3 = has_id3 or has_frame_sync\n"
					"size_bytes = os.path.getsize(path)\n"
					"out_lines = ['IS_MP3=' + str(is_mp3), 'SIZE_BYTES=' + str(size_bytes)]\n"
					f"open(r'{p['mp3_probe_txt']}', 'w', encoding='utf-8').write('\\n'.join(out_lines) + '\\n')\n"
					"assert is_mp3\n"
					"print('MP3_PROBE_OK', size_bytes)\n"
				),
				expect_markers=["MP3_PROBE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["mp3_probe_txt"], kind="txt", contains="IS_MP3=True"),
				],
			),
```

Note: this covers create (`dummy_zip_create`), analyze (`dummy_zip_list`, `dummy_sqlite_report`, `dummy_svg_analyze`, `dummy_webm_probe`, `dummy_mp3_probe`), summarize (`dummy_java_summarize`), convert (`dummy_zip_extract`, `dummy_docx_extract_text`), and edit (`dummy_sqlite_edit`) — all 5 action categories across all 7 new file types (zip appears in 3 categories, sqlite in 2, since each file type naturally supports multiple actions).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.live.scenarios.test_cases -v`
Expected: PASS

- [ ] **Step 5: Run each new scenario directly (offline, no live provider needed)**

`kind="offline_exec"` cases run pure Python without any LLM call. Run the harness filtered to just these IDs to confirm the code itself executes cleanly:

```bash
python scripts/run_live_scenarios.py --tier easy --ids dummy_zip_list,dummy_zip_extract,dummy_zip_create,dummy_java_summarize,dummy_sqlite_report,dummy_sqlite_edit,dummy_docx_extract_text,dummy_svg_analyze,dummy_webm_probe,dummy_mp3_probe
```

Expected: all 10 PASS. If `scripts/run_live_scenarios.py` does not support `--ids` filtering, run the full `--tier easy` pass instead and confirm these 10 IDs show PASS in the report.

- [ ] **Step 6: Commit**

```bash
git add tests/live/scenarios/cases.py tests/live/scenarios/test_cases.py
git commit -m "test(live-scenarios): add 10 create/analyze/summarize/convert/edit cases for zip/mp3/java/sqlite/docx/svg/webm"
```

---

### Task 7: Key-rotation test

**Files:**
- Modify: `tests/core/test_model_router.py` (add `import os`; add new test class)

**Interfaces:**
- Consumes: `KeyManager(getenv_fn=...)`, `KeyManager.reset_singleton()` (existing, unmodified); `tests.helpers.cli_args.make_interpreter_args` (existing, unmodified); `interp.model_router.generate_content_with_retries` (existing signature, unmodified by this task — Task 3 only adds a wrapping try/except around its body, not its signature).

- [ ] **Step 1: Write the failing test**

Add `import os` to the top of `tests/core/test_model_router.py` (currently only has `unittest`, `argparse.Namespace`, `unittest.mock`, `ModelRouter`, `Interpreter`). Then add this new test class at the end of the file:

```python
class TestModelRouterKeyRotation(unittest.TestCase):
	def setUp(self):
		from libs.key_manager import KeyManager
		KeyManager.reset_singleton()

	def tearDown(self):
		from libs.key_manager import KeyManager
		KeyManager.reset_singleton()
		for key in ("OPENAI_API_KEY", "OPENAI_API_KEY_1", "OPENAI_API_KEY_2"):
			os.environ.pop(key, None)

	def _make_interp(self, mode="code", model="gpt-4o"):
		from tests.helpers.cli_args import make_interpreter_args
		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), \
		     patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None):
			args = make_interpreter_args(mode=mode, model=model)
			return Interpreter(args)

	def _env(self, mapping):
		def getenv(name, default=None):
			return mapping.get(name, default)
		return getenv

	def test_generate_content_with_retries_rotates_to_second_key_on_failure(self):
		from libs.key_manager import KeyManager

		env = {"OPENAI_API_KEY_1": "sk-1", "OPENAI_API_KEY_2": "sk-2"}
		km = KeyManager(getenv_fn=self._env(env))
		interp = self._make_interp()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.MAX_LLM_RETRIES = 3
		interp.config_values = {}
		interp._key_manager = km
		interp.args.free = False

		seen_keys = []
		call_count = {"n": 0}

		def fake_generate_content(message, chat_history, config_values=None, image_file=None):
			call_count["n"] += 1
			seen_keys.append(os.environ.get("OPENAI_API_KEY"))
			if call_count["n"] == 1:
				raise RuntimeError("429 rate limit exceeded")
			return "ok from second key"

		interp.generate_content = fake_generate_content

		result = interp.model_router.generate_content_with_retries(
			"hello", [], config_values={},
			sleep_fn=lambda *_: None, display_fn=lambda *_: None,
		)

		self.assertEqual(result, "ok from second key")
		self.assertEqual(call_count["n"], 2)
		self.assertEqual(seen_keys[0], "sk-1")
		self.assertEqual(seen_keys[1], "sk-2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.core.test_model_router.TestModelRouterKeyRotation -v`
Expected: FAIL if key rotation is broken, or PASS immediately if rotation already works correctly (this test documents/locks in existing behavior — per the design spec's addendum, "extend `tests/test_key_manager.py` and add a live scenario that forces rotation across a multi-key pool and asserts the rotation... works," this is a coverage gap, not necessarily a bug). Either outcome is informative: if it fails, investigate `_prepare_retry_key`'s `km.acquire_key(provider)` call and `os.environ[api_key_name] = key_state.value` assignment (both already confirmed present in the current code) for a rotation defect; if it passes immediately, proceed to Step 3 as a no-op confirmation step.

- [ ] **Step 3: Fix rotation if the test fails, otherwise skip to Step 4**

If Step 2 failed, the most likely cause is `_prepare_retry_key` not being invoked before each retry attempt, or `os.environ[api_key_name]` not being read fresh by `fake_generate_content`'s environment lookup. Trace `ModelRouter.generate_content_with_retries`'s loop to confirm `_prepare_retry_key(km, provider, api_key_name, last_exception)` runs at the top of every iteration (already confirmed in this plan's investigation — see Task 3's `_prepare_retry_key` body) and that `provider`/`api_key_name` resolve to `"openai"`/`"OPENAI_API_KEY"` for `INTERPRETER_MODEL = "gpt-4o"`. Fix any discrepancy found; do not speculate further here since this step is conditional on an actual observed failure.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.core.test_model_router.TestModelRouterKeyRotation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_model_router.py
git commit -m "test(model-router): lock in key rotation across a multi-key pool on retry"
```

---

### Task 8: All-modes smoke coverage

**Files:**
- Modify: `tests/e2e/test_all_modes_e2e.py`

**Interfaces:**
- Consumes: whatever fixture/harness helpers `tests/e2e/test_all_modes_e2e.py` already uses for its existing mode coverage (read the file first — this task fills gaps, it does not redesign the harness).

- [ ] **Step 1: Audit existing coverage**

Run: `python -m unittest tests.e2e.test_all_modes_e2e -v` and read `tests/e2e/test_all_modes_e2e.py` in full to list which of `--cli`, `--agentic`, `--yolo`, `--gemini-style`, script mode, command mode, vision mode, and chat mode already have at least one real-request-shaped test (not just import/parse smoke).

- [ ] **Step 2: For each mode found missing a real-request test, add one**

Follow the existing file's established pattern exactly (do not introduce a second harness style). For each gap, add a test that: builds the mode's args via the file's existing args-construction helper, drives one real (or offline-safe mocked, consistent with how the file already handles live-vs-mocked) request through that mode's entrypoint, and asserts a non-crash, non-empty response — mirroring whatever assertion style neighboring tests in the same file already use for the modes that do have coverage. Since the exact gaps depend on Step 1's audit (not yet performed as of this plan being written), the implementer must read the file's existing test bodies for the already-covered modes and use them as the literal template for the newly added ones — same fixture setup, same mocking boundaries, same assertion shape.

- [ ] **Step 3: Run the full e2e suite**

Run: `python -m unittest tests.e2e.test_all_modes_e2e -v`
Expected: all PASS, with every one of `--cli`/`--agentic`/`--yolo`/`--gemini-style`/script/command/vision/chat now represented.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_all_modes_e2e.py
git commit -m "test(e2e): fill remaining mode-smoke gaps for yolo/gemini-style and any other uncovered modes"
```

---

### Task 9: Run the live suite for real

**Files:**
- None modified directly — this task runs the suite built by Tasks 5-6 against real configured providers and fixes whatever real failures surface.

- [ ] **Step 1: Confirm `.env` has at least one live provider configured**

Do not print key values. Confirm presence only:

```bash
python -c "import os; print([k for k in os.environ if k.upper().endswith('API_KEY') or k.upper().endswith('API_KEY_1')])"
```

- [ ] **Step 2: Run medium + complex tiers across all configured models**

```bash
python scripts/run_live_scenarios.py --tier medium --tier complex --all-models
```

- [ ] **Step 3: Triage the report**

Open the newest timestamped file in `scratch/live_scenario_reports/*.md`. For every `FAIL` (not `SKIP` — soft-skips on quota/billing/auth are expected and acceptable per `tests/live/scenarios/soft_skip.py`), open the corresponding scenario in `tests/live/scenarios/cases.py`, reproduce locally, and fix the root cause in production code (not by weakening the scenario's assertions).

- [ ] **Step 4: Re-run until green**

Repeat Steps 2-3 until the report shows zero `FAIL` entries (any number of `SKIP` is fine).

- [ ] **Step 5: Record the final report location**

Note the final timestamped `.md`/`.html` pair's path in the Task 12 commit message so the user can find it directly, e.g. `scratch/live_scenario_reports/2026-07-13T...-report.md`.

---

### Task 10: CI/CD replication as local merge gate

**Files:**
- None modified unless Step 3 surfaces a coverage gap on touched modules.

- [ ] **Step 1: Read the exact CI commands**

Read `.github/workflows/ci.yml` in full and extract the exact commands it runs (already known to include `scripts/run_ci_unit_tests.py` and a `--cov-fail-under=60` gate over `safety_manager`/`code_generator`/`llm_dispatcher`/`history_manager` + integration, per the design spec's addendum — confirm the exact current flags before running, since the file may have evolved).

- [ ] **Step 2: Run those exact commands locally**

```bash
python scripts/run_ci_unit_tests.py
```

(plus any coverage-gate command found in Step 1, run with its exact flags as written in `ci.yml`).

- [ ] **Step 3: Widen the coverage module set for touched files**

Add `libs.key_manager`, `libs.core.model_router`, `libs.core.main_loop`, `libs.agent.gemini_ui`, `libs.core.session` to the `--cov=` module list (alongside the existing 4-5 modules) and re-run:

```bash
python -m pytest --cov=libs.key_manager --cov=libs.core.model_router --cov=libs.core.main_loop --cov=libs.agent.gemini_ui --cov=libs.core.session --cov=libs.safety_manager --cov=libs.code_generator --cov=libs.llm_dispatcher --cov=libs.history_manager --cov-report=term-missing --cov-fail-under=80 tests/
```

If effective coverage on the touched modules falls short of 80%, add targeted tests for the uncovered lines in those specific modules only — do not chase 80% on unrelated legacy modules in this same pass (per the spec's explicit scope limit).

- [ ] **Step 4: Confirm green**

All of Step 2 and Step 3's commands must exit 0 before Task 12's merge.

---

### Task 11: Hygiene check

**Files:**
- None modified unless a violation is found.

- [ ] **Step 1: Confirm no new top-level sprawl**

```bash
git status --short
```

Confirm every new/modified path falls under `libs/`, `tests/`, `docs/superpowers/`, or `scratch/`/`logs/` (already-gitignored) — no new top-level directories.

- [ ] **Step 2: Confirm exhaustion/rotation logging is structured and secret-free**

Grep the new logging calls added in Tasks 1-3 for any raw key value leakage:

```bash
grep -rn "logger.warning\|logger.error" libs/key_manager.py libs/core/main_loop.py libs/core/model_router.py | grep -i "key_state.value\|api_key\b"
```

Expected: no matches — Task 2's `interp.logger.warning(...)` only logs `provider`/`eta_str`, never a key value; `_prepare_retry_key`'s existing `os.environ[api_key_name] = key_state.value` assignment is not logged anywhere.

- [ ] **Step 3: Record findings**

If Step 1 or Step 2 finds a violation, fix it and re-run. If clean, no commit is needed for this task — it is a verification pass, not a code change.

---

### Task 12: Workflow wrap-up

**Files:**
- None — this task is process-only.

- [ ] **Step 1: Confirm full suite is green**

```bash
python -m unittest discover -s tests -v
python scripts/run_ci_unit_tests.py
```

Both must exit 0, and Task 9's live report must show zero `FAIL`.

- [ ] **Step 2: Merge to `develop`**

If working in a worktree/branch per the standing instruction, merge into `develop` only now that Step 1 is confirmed green:

```bash
git checkout develop
git merge --no-ff <feature-branch> -m "merge: stability fixes (key exhaustion, banner wrap) + live testing expansion"
```

- [ ] **Step 3: Do NOT push**

Do not run `git push`. Per the standing instruction, pushing to `origin` requires separate, explicit authorization from the user — stop here and report completion, including the live report path from Task 9 Step 5.
