from __future__ import annotations

from abc import ABC, abstractmethod

from darwincode.types.models import AgentTask, Hypothesis


class AgentVendor(ABC):
    """Abstract agent vendor. Implement for each AI coding agent (Claude Code, Codex, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Vendor identifier (e.g. 'claude-code', 'codex')."""
        ...

    @abstractmethod
    def build_task_config(self, task: AgentTask) -> dict:
        """Build the task.json content for this vendor.

        Returns the dict to be written as task.json in the agent workspace.
        The entrypoint.sh reads this to dispatch to the right agent CLI.
        """
        ...

    @abstractmethod
    def build_prompt(
        self,
        base_prompt: str,
        hypotheses: list[Hypothesis],
        variant_index: int,
    ) -> str:
        """Build a prompt variant for an agent.

        Args:
            base_prompt: The step's base task prompt.
            hypotheses: Learnings from previous generations.
            variant_index: Which variant (0..N-1) this is, for prompt diversity.

        Returns:
            The complete prompt string to send to the agent.
        """
        ...
