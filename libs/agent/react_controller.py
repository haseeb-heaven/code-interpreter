"""ReAct controller — Thought → Action → Observation loop."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from rich.console import Console

from libs.agent.actions.coder import CoderAction
from libs.agent.actions.debugger import DebuggerAction
from libs.agent.actions.executor import ExecutorAction
from libs.agent.actions.reviewer import ReviewerAction
from libs.agent.language import resolve_react_execute_language
from libs.agent.llm import call_llm
from libs.agent.logger import TrajectoryLogger
from libs.agent.parser import ParseError, format_trajectory, parse_react_step
from libs.agent.prompts import REACT_SYSTEM_PROMPT
from libs.agent.step_ui import make_step_presenter
from libs.deps.install_flow import MissingBinaryHandler
from libs.deps.missing_binary import is_missing_binary_error
from libs.free_llms import FreeModelsExhaustedError, is_free_routing_failure, is_rate_limit_failure

console = Console()
logger = logging.getLogger(__name__)


class ReActController:
    """Single ReAct agent with specialist actions."""

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        code_interpreter: Any = None,
        safety_manager: Any = None,
        log_path: str = "logs/agent_react.jsonl",
        max_steps: int = 10,
        unsafe_mode: bool = False,
        *,
        gemini_style: bool = False,
        quiet_ui: bool = False,
        step_presenter: Any = None,
        auto_yes: bool = False,
        missing_binary_handler: Optional[MissingBinaryHandler] = None,
        confirm_fn: Optional[Callable[[str], bool]] = None,
        enable_missing_binary_search: bool = False,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.max_steps = max_steps
        self.log_path = log_path
        self.gemini_style = bool(gemini_style)
        self.auto_yes = bool(auto_yes)
        self.enable_missing_binary_search = bool(enable_missing_binary_search)
        self.presenter = step_presenter or make_step_presenter(
            gemini_style=self.gemini_style,
            quiet=quiet_ui,
            console=console,
        )
        self.missing_binary_handler = missing_binary_handler
        self.confirm_fn = confirm_fn

        if code_interpreter is None or safety_manager is None:
            from libs.code_interpreter import CodeInterpreter
            from libs.safety_manager import ExecutionSafetyManager

            safety_manager = safety_manager or ExecutionSafetyManager(unsafe_mode=unsafe_mode)
            code_interpreter = code_interpreter or CodeInterpreter(safety_manager=safety_manager)

        self.code_interpreter = code_interpreter
        self.safety_manager = safety_manager
        self.coder = CoderAction(
            model_name, api_key, code_interpreter, on_fallback=self._on_llm_fallback
        )
        self.executor = ExecutorAction(code_interpreter, safety_manager)
        self.reviewer = ReviewerAction(model_name, api_key, on_fallback=self._on_llm_fallback)
        self.debugger = DebuggerAction(model_name, api_key, on_fallback=self._on_llm_fallback)

    def _apply_model(self, model_name: str, api_key: Optional[str] = None) -> None:
        """Keep controller + specialist actions on the same active model."""
        self.model_name = model_name
        if api_key is not None:
            self.api_key = api_key
        self.coder.model_name = model_name
        self.reviewer.model_name = model_name
        self.debugger.model_name = model_name
        self.coder.api_key = self.api_key
        self.reviewer.api_key = self.api_key
        self.debugger.api_key = self.api_key
        # Keep specialist fallback hooks wired to the shared updater.
        self.coder.on_fallback = self._on_llm_fallback
        self.reviewer.on_fallback = self._on_llm_fallback
        self.debugger.on_fallback = self._on_llm_fallback

    def _on_llm_fallback(self, candidate: Dict[str, Any]) -> None:
        model_id = str(candidate.get("model") or "").strip()
        label = str(candidate.get("config") or model_id)
        if not model_id:
            return
        self._apply_model(model_id)
        console.print(
            f"[yellow]Free model fallback[/yellow]: switched to [bold]{label}[/bold] ({model_id})"
        )

    def _call_llm(self, messages: list) -> tuple[str, Dict[str, Any]]:
        return call_llm(
            self.model_name,
            messages,
            self.api_key,
            on_fallback=self._on_llm_fallback,
        )

    @staticmethod
    def _report_llm_failure(exc: BaseException) -> str:
        """Print a concise CLI error; avoid dumping huge litellm tracebacks."""
        if isinstance(exc, FreeModelsExhaustedError):
            logger.error("Controller LLM failure: %s", exc)
            console.print(f"[bold red]{exc}[/bold red]")
            console.print("[dim]Tip: /free  or  /model <name>[/dim]")
            return str(exc)
        logger.error("Controller LLM failure: %s", exc)
        short = str(exc).replace("\n", " ").strip()
        if len(short) > 240:
            short = short[:237] + "..."
        console.print(f"[bold red]LLM error:[/bold red] {short}")
        console.print("[dim]Tip: try /free or /model <name> for another free preset.[/dim]")
        return f"LLM error: {short}"

    def run(self, task: str) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        traj_logger = TrajectoryLogger(self.log_path, run_id=run_id)

        if hasattr(self.safety_manager, "set_user_intent_paths"):
            try:
                self.safety_manager.set_user_intent_paths(task or "")
            except Exception as exc:
                logger.debug("Could not set user-intent write paths: %s", exc)

        state: Dict[str, Any] = {
            "task": task,
            "code": "",
            "trajectory": [],
            "last_observation": "",
            "step_count": 0,
            "status": "RUNNING",
            "cost_metrics": {"total_cost": 0.0, "total_tokens": 0},
            "review_passed": False,
            "failure_reason": "",
            "summary": "",
            "run_id": run_id,
        }

        console.print(f"\n[bold green]ReAct agent starting[/bold green]: {task}\n")
        last_signature: Optional[tuple] = None

        while state["step_count"] < self.max_steps:
            step_num = state["step_count"] + 1
            try:
                with self.presenter.thinking(step_num):
                    step_text, step_metrics = self._think(state)
                state["cost_metrics"]["total_cost"] += step_metrics["cost"]
                state["cost_metrics"]["total_tokens"] += step_metrics["tokens"]
                react_step = parse_react_step(step_text)
            except ParseError as exc:
                repaired = self._repair_parse(state, str(exc))
                if repaired is None:
                    state["status"] = "FAILED"
                    state["failure_reason"] = f"Parse error: {exc}"
                    break
                react_step, repair_metrics = repaired
                state["cost_metrics"]["total_cost"] += repair_metrics["cost"]
                state["cost_metrics"]["total_tokens"] += repair_metrics["tokens"]
            except Exception as exc:
                state["status"] = "FAILED"
                state["failure_reason"] = self._report_llm_failure(exc)
                break

            signature = (react_step.action, json.dumps(react_step.action_input, sort_keys=True, default=str))
            if last_signature == signature:
                state["status"] = "FAILED"
                state["failure_reason"] = "stagnation: identical action repeated"
                state["step_count"] = step_num
                traj_logger.log_step(
                    step=step_num,
                    thought=react_step.thought,
                    action=react_step.action,
                    action_input=react_step.action_input,
                    observation=state["failure_reason"],
                    tokens=0,
                    cost=0.0,
                    status="FAILED",
                )
                break
            last_signature = signature

            self.presenter.show_thought(step_num, react_step.thought)
            self.presenter.show_action(step_num, react_step.action, react_step.action_input)

            if react_step.action == "finish":
                summary = ""
                if isinstance(react_step.action_input, dict):
                    summary = str(react_step.action_input.get("summary", ""))
                else:
                    summary = str(react_step.action_input)
                if not state["review_passed"]:
                    logger.warning("Finish without prior passing review (run_id=%s)", run_id)
                    console.print("[yellow]Warning: finish without passing review[/yellow]")
                observation = summary or "Finished"
                state["summary"] = summary
                state["status"] = "COMPLETED"
                state["step_count"] = step_num
                state["trajectory"].append(
                    {
                        "thought": react_step.thought,
                        "action": "finish",
                        "action_input": react_step.action_input,
                        "observation": observation,
                    }
                )
                traj_logger.log_step(
                    step=step_num,
                    thought=react_step.thought,
                    action="finish",
                    action_input=react_step.action_input,
                    observation=observation,
                    tokens=0,
                    cost=0.0,
                    status="COMPLETED",
                )
                self.presenter.show_observation(step_num, observation)
                break

            if react_step.action == "execute":
                # Confirm *before* entering the spinner: a Rich Status/Live
                # display collides with a blocking input() prompt (the prompt
                # text gets hidden behind spinner redraws), which is exactly
                # what made the original hang look unrecoverable. Resolving
                # this here also guarantees --yes/auto_yes never touches
                # stdin at all.
                approved, deny_reason = self._authorize_execute()
                if not approved:
                    self._finalize_step(
                        traj_logger, state, step_num, react_step, deny_reason, {"cost": 0.0, "tokens": 0}
                    )
                    continue

            try:
                with self.presenter.acting(step_num, react_step.action):
                    observation, action_metrics = self._dispatch(react_step, state)
            except FreeModelsExhaustedError as exc:
                state["status"] = "FAILED"
                state["failure_reason"] = self._report_llm_failure(exc)
                state["step_count"] = step_num
                break
            except Exception as exc:
                # Avoid dumping huge litellm rate-limit / routing tracebacks to the CLI.
                if is_free_routing_failure(exc) or is_rate_limit_failure(exc):
                    state["status"] = "FAILED"
                    state["failure_reason"] = self._report_llm_failure(exc)
                    state["step_count"] = step_num
                    break
                logger.exception("Action %s failed", react_step.action)
                observation = f"ACTION_ERROR: {exc}"
                action_metrics = {"cost": 0.0, "tokens": 0}

            # Missing binary (ffmpeg, etc.): search/ask/install instead of static dump.
            if react_step.action == "execute" and is_missing_binary_error(observation):
                observation = self._recover_missing_binary(observation)

            self._finalize_step(traj_logger, state, step_num, react_step, observation, action_metrics)

        if state["status"] == "RUNNING":
            state["status"] = "FAILED"
            state["failure_reason"] = state["failure_reason"] or "max_steps exceeded"

        traj_logger.log_summary(
            status=state["status"],
            steps=state["step_count"],
            total_tokens=int(state["cost_metrics"]["total_tokens"]),
            total_cost=float(state["cost_metrics"]["total_cost"]),
            failure_reason=state.get("failure_reason", ""),
            summary=state.get("summary", ""),
        )

        console.print("\n[bold magenta]=== ReAct workflow completed ===[/bold magenta]")
        console.print(f"Status: {state['status']}")
        console.print(f"Steps: {state['step_count']}")
        console.print(f"Tokens: {state['cost_metrics']['total_tokens']}")
        console.print(f"Cost: ${state['cost_metrics']['total_cost']:.4f}")
        return state

    def _authorize_execute(self) -> tuple[bool, str]:
        """Gate the "execute" action on user confirmation, fully honouring
        ``--yes``/``auto_yes`` and never blocking on stdin.

        Runs outside any presenter spinner (see ``run()``) so a real Y/N
        prompt is never obscured by a live-updating Rich Status display —
        that collision, combined with ``--yes`` not being wired here at all,
        is what made the original "Execute the code? Y/N" step hang forever.
        """
        if self.auto_yes:
            return True, ""
        if self.confirm_fn is None:
            # No controller-level confirm wired (e.g. direct/test construction).
            # Never fall back to a blocking input() here — proceed, matching
            # the rest of the agentic/tool execution paths in this codebase.
            return True, ""
        prompt = "Execute the code? Y/N "
        try:
            approved = bool(self.confirm_fn(prompt))
        except Exception as exc:
            logger.debug("confirm_fn failed during execute authorization: %s", exc)
            approved = False
        if approved:
            return True, ""
        return False, "Execution cancelled: user declined."

    def _finalize_step(
        self,
        traj_logger: TrajectoryLogger,
        state: Dict[str, Any],
        step_num: int,
        react_step: Any,
        observation: str,
        action_metrics: Dict[str, Any],
    ) -> None:
        """Record cost/trajectory/log/observation for one completed step."""
        state["cost_metrics"]["total_cost"] += action_metrics.get("cost", 0.0)
        state["cost_metrics"]["total_tokens"] += int(action_metrics.get("tokens", 0))
        state["last_observation"] = observation
        state["step_count"] = step_num
        state["trajectory"].append(
            {
                "thought": react_step.thought,
                "action": react_step.action,
                "action_input": react_step.action_input,
                "observation": observation,
            }
        )
        traj_logger.log_step(
            step=step_num,
            thought=react_step.thought,
            action=react_step.action,
            action_input=react_step.action_input,
            observation=observation,
            tokens=int(action_metrics.get("tokens", 0)),
            cost=float(action_metrics.get("cost", 0.0)),
            status="running",
        )
        self.presenter.show_observation(step_num, observation)

    def _think(self, state: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        history = format_trajectory(state["trajectory"])
        user = (
            f"Task: {state['task']}\n"
            f"Current code:\n{state['code'] or '(none)'}\n\n"
            f"Trajectory so far:\n{history or '(empty)'}\n\n"
            "Emit the next Thought / Action / Action Input."
        )
        return self._call_llm(
            [
                {"role": "system", "content": REACT_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ]
        )

    def _repair_parse(self, state: Dict[str, Any], error: str):
        repair_prompt = (
            f"Your previous output was invalid: {error}\n"
            "Reply again using ONLY:\n"
            "Thought: ...\nAction: ...\nAction Input: ...\n"
            f"Task: {state['task']}"
        )
        try:
            content, metrics = self._call_llm(
                [
                    {"role": "system", "content": REACT_SYSTEM_PROMPT},
                    {"role": "user", "content": repair_prompt},
                ]
            )
            return parse_react_step(content), metrics
        except Exception:
            return None

    def _dispatch(self, step, state: Dict[str, Any]) -> tuple[str, Dict[str, float]]:
        action = step.action
        action_input = step.action_input
        metrics = {"cost": 0.0, "tokens": 0}

        if action == "code":
            instruction = ""
            if isinstance(action_input, dict):
                instruction = str(action_input.get("instruction", action_input))
            else:
                instruction = str(action_input)
            result = self.coder.run(
                instruction=instruction or state["task"],
                task=state["task"],
                current_code=state["code"],
                history=format_trajectory(state["trajectory"]),
            )
            state["code"] = result.code
            return result.observation, result.metrics

        if action == "execute":
            # Models frequently send prose/empty language on later execute steps;
            # always coerce to a supported sandbox language (configured default).
            language = resolve_react_execute_language(action_input, self.code_interpreter)
            result = self.executor.run(code=state["code"], language=language)
            return result.observation, metrics

        if action == "review":
            result = self.reviewer.run(
                task=state["task"],
                code=state["code"],
                execution_result=state["last_observation"],
            )
            state["review_passed"] = result.passed
            return result.observation, result.metrics

        if action == "debug":
            error = ""
            if isinstance(action_input, dict):
                error = str(action_input.get("error", ""))
            result = self.debugger.run(
                task=state["task"],
                code=state["code"],
                error=error,
                last_observation=state["last_observation"],
            )
            return result.observation, result.metrics

        raise ValueError(f"Unhandled action: {action}")

    def _recover_missing_binary(self, observation: str) -> str:
        """Ask / optionally install when execute fails due to a missing PATH tool."""
        handler = self.missing_binary_handler
        if handler is None:
            search_fn = None
            if self.enable_missing_binary_search:
                search_fn = self._default_search
            handler = MissingBinaryHandler(
                confirm_fn=self.confirm_fn,
                search_fn=search_fn,
                print_fn=lambda msg: console.print(msg),
            )

        do_search = bool(self.enable_missing_binary_search or handler.search_fn)
        if do_search and hasattr(self.presenter, "searching"):
            with self.presenter.searching("install missing tool"):
                result = handler.handle(
                    observation,
                    auto_yes=self.auto_yes,
                    yolo=False,
                    do_search=True,
                )
        else:
            result = handler.handle(
                observation,
                auto_yes=self.auto_yes,
                yolo=False,
                do_search=False,
            )
        if result.detected and result.observation:
            return f"{observation}\n\n{result.observation}"
        return observation

    @staticmethod
    def _default_search(query: str) -> str:
        """Best-effort DuckDuckGo / WebSearchTool lookup for install tips."""
        try:
            from libs.tools.web_search_tool import WebSearchTool

            tool = WebSearchTool(provider="duckduckgo")
            out = tool.search(query, max_results=3)
            return out if isinstance(out, str) else str(out)
        except Exception as exc:
            logger.debug("Default missing-binary search failed: %s", exc)
            return f"(web search unavailable: {exc})"
