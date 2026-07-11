# ReAct Agentic Code Interpreter — Design

**Date:** 2026-07-11  
**Status:** Approved for implementation planning  
**Pattern:** ReAct (Yao et al., 2022) — interleaved Thought → Action → Observation

## Goal

Make `--agentic` a true ReAct agent with four specialist actions (Coder, Executor, Reviewer, Debugger), structured trajectory logs, and unit tests per agent/sub-module.

Out of scope for this iteration: full policy engine, patch-only edits, repo RAG, HITL gates, multi-model routing, SBOM, eval harness.

## Architecture

Single ReAct controller owns the loop. Specialists are **actions**, not separate planners.

```
Task
  │
  ▼
┌─────────────────────────────────────┐
│  ReActController                    │
│  Thought → Action → Observation     │
│  until Finish | max_steps           │
└──────┬──────────┬──────────┬────────┘
       │          │          │
   code()     execute()   review()   debug()
   Coder      Executor    Reviewer   Debugger
       │          │          │          │
       └──────────┴──────────┴──────────┘
                    │
              TrajectoryLogger (JSON)
```

CLI entry remains `interpreter.py --agentic`. Existing sandbox (`ExecutionSafetyManager` / `CodeInterpreter`) is reused by Executor.

## ReAct loop

### Step format

```
Thought: <why this next step>
Action: <name>
Action Input: <json or free text>
Observation: <filled by runtime>
```

### Action catalog

| Action   | Input                                      | Observation                                      |
|----------|--------------------------------------------|--------------------------------------------------|
| `code`   | `{ "instruction": "..." }`                 | generated source                                 |
| `execute`| `{ "language": "python" }` (uses last code)| stdout / stderr                                  |
| `review` | `{}`                                       | `{ "passed": bool, "reason": "..." }`            |
| `debug`  | optional error; else last observation      | diagnosis + fix hints for next `code`            |
| `finish` | `{ "summary": "..." }`                     | terminal                                         |

### Stop conditions

1. `Action: finish` — always accepted as terminal; system prompt instructs the model to finish only after `review` returned `passed: true`. If finish occurs without a prior passing review, log a warning but still end (ReAct paper does not hard-block Finish).
2. `max_steps` exceeded → `FAILED` (default `max_steps=10`)
3. Invalid parse → one repair attempt, then fail
4. Identical `(Action, Action Input)` twice in a row → abort (stagnation)

### Carried state

`task`, `code`, `trajectory[]`, `last_observation`, `step_count`, `status`, `cost_metrics`

## Module layout

```
libs/
  agent/
    __init__.py
    react_controller.py   # loop, parse, dispatch, stop rules
    parser.py             # Thought/Action/Action Input extraction
    actions/
      coder.py
      executor.py
      reviewer.py
      debugger.py
    logger.py             # JSON trajectory writer
    prompts.py            # ReAct system + few-shot style instructions
  agent_graph.py          # thin wrapper / deprecate into react_controller
```

Each action module:

- Owns its LLM call (or sandbox call for Executor)
- Raises typed errors; never swallows failures
- Returns a string (or structured dict serialized to string) as Observation
- Logs via shared agent logger

## Logging

- File: `logs/agent_react.jsonl` (one JSON object per step + run summary)
- Fields: `run_id`, `step`, `thought`, `action`, `action_input`, `observation`, `tokens`, `cost`, `status`, `timestamp`
- Console: short Rich progress (agent name + truncated observation)
- No secrets in logs (reuse existing redaction if available; otherwise strip obvious `API_KEY=` patterns)

## Testing

| Suite                         | Covers                                      |
|-------------------------------|---------------------------------------------|
| `tests/test_react_parser.py`  | Thought/Action parsing, repair, bad input   |
| `tests/test_react_coder.py`   | Coder action (mocked LLM)                   |
| `tests/test_react_executor.py`| Executor + sandbox wiring (mocked)          |
| `tests/test_react_reviewer.py`| pass/fail JSON observation                  |
| `tests/test_react_debugger.py`| diagnosis output                            |
| `tests/test_react_controller.py` | loop: finish, max_steps, stagnation, route |
| Keep/adapt `tests/test_agent_graph.py` as compatibility or replace with controller tests |

All LLM and sandbox calls mocked in unit tests. No live API required for CI.

## Error handling

- LLM failure → observation = error text; controller may choose `debug` or `finish`
- Executor error → observation includes stderr; typical next Thought chooses `debug` then `code`
- Action exception → logged, counted as observation, does not crash the process unless unrecoverable
- Bounded retries via `max_steps` only (no unbounded inner loops)

## Integration

- `Interpreter.interpreter_agentic_main()` constructs `ReActController` with model/api_key/unsafe_mode from existing args
- Default language: python (same as today)
- `max_steps` defaults to `10` (overridable via constructor)

## Success criteria

- [ ] One ReAct controller with Thought/Action/Observation loop
- [ ] Four agents as actions: Coder, Debugger, Reviewer, Executor
- [ ] JSON trajectory logs
- [ ] Unit tests for parser, each agent, and controller
- [ ] `--agentic` runs the ReAct path end-to-end (manual smoke)

## Positioning

Policy-light ReAct agentic code interpreter: reason, act via coder/executor/reviewer/debugger, observe, log, and verify with tests.
