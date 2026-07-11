# ReAct Agentic Interpreter Implementation Plan

> **For agentic workers:** Execute inline with TDD. Steps use checkbox syntax.

**Goal:** Replace the fixed LangGraph agent loop with a single ReAct controller (Thought → Action → Observation) exposing Coder, Executor, Reviewer, Debugger actions, plus JSON logs and unit tests.

**Architecture:** `ReActController` parses LLM steps, dispatches to action modules, appends observations, stops on `finish` / max_steps / stagnation. Executor reuses existing sandbox.

**Tech Stack:** Python, litellm, existing `CodeInterpreter` + `ExecutionSafetyManager`, pytest, rich

---

### Task 1: Parser

**Files:**
- Create: `libs/agent/parser.py`
- Test: `tests/test_react_parser.py`

- [ ] Write failing parser tests (Thought/Action/Action Input)
- [ ] Implement `parse_react_step` + `format_trajectory`
- [ ] Verify tests pass

### Task 2: Trajectory logger

**Files:**
- Create: `libs/agent/logger.py`
- Test: `tests/test_react_logger.py`

- [ ] Write failing logger tests
- [ ] Implement JSONL writer
- [ ] Verify tests pass

### Task 3: Action modules

**Files:**
- Create: `libs/agent/actions/{coder,executor,reviewer,debugger}.py`
- Create: `libs/agent/llm.py` (shared litellm wrapper)
- Create: `libs/agent/prompts.py`
- Tests: `tests/test_react_{coder,executor,reviewer,debugger}.py`

- [ ] Write failing action tests (mocked LLM/sandbox)
- [ ] Implement actions
- [ ] Verify tests pass

### Task 4: ReAct controller

**Files:**
- Create: `libs/agent/react_controller.py`
- Create: `libs/agent/__init__.py`
- Test: `tests/test_react_controller.py`

- [ ] Write failing controller tests (finish, max_steps, stagnation)
- [ ] Implement controller
- [ ] Verify tests pass

### Task 5: Wire CLI

**Files:**
- Modify: `libs/interpreter_lib.py` (`interpreter_agentic_main`)
- Modify: `libs/agent_graph.py` (thin re-export or deprecate)
- Ensure `langgraph` optional / not required for ReAct path

- [ ] Point `--agentic` at `ReActController`
- [ ] Smoke/e2e test with mocked LLM trajectory

### Task 6: Full test suite

- [ ] Run all `tests/test_react_*.py` + related
- [ ] Fix failures
- [ ] Confirm green

---
