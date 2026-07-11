"""
Backward-compatible entry for agentic mode.

Prefer `libs.agent.react_controller.ReActController` (ReAct Thought→Action→Observation).
This module re-exports the controller under the historical AgentGraph name.
"""
from libs.agent.react_controller import ReActController as AgentGraph

__all__ = ["AgentGraph"]
