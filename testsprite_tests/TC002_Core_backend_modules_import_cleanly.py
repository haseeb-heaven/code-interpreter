"""TC002 — Core backend modules import cleanly after modular refactor."""

from __future__ import annotations

import unittest


class TC002_Core_Backend_Imports(unittest.TestCase):
	def test_modular_packages_import(self):
		from libs.agents.agent_pipeline import AgentPipeline
		from libs.agents.base_agent import AgentContext, BaseAgent
		from libs.core.model_router import ModelRouter
		from libs.core.prompt_builder import PromptBuilder
		from libs.core.session import SessionConfig
		from libs.execution.executor import CodeExecutor
		from libs.execution.repairer import RepairCircuitBreaker, Repairer
		from libs.modes.code_mode import CodeModeHandler

		self.assertTrue(callable(AgentPipeline))
		self.assertTrue(issubclass(BaseAgent, object))
		self.assertTrue(AgentContext)
		self.assertTrue(ModelRouter)
		self.assertTrue(PromptBuilder)
		self.assertTrue(SessionConfig)
		self.assertTrue(CodeExecutor)
		self.assertTrue(Repairer)
		self.assertTrue(RepairCircuitBreaker)
		self.assertTrue(CodeModeHandler)


if __name__ == "__main__":
	unittest.main()
