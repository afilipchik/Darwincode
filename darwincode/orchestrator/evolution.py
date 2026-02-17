from __future__ import annotations

import logging
import uuid

from darwincode.agents.vendor import AgentVendor
from darwincode.types.models import AgentTask, Hypothesis

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """Create prompt variants and mutate prompts based on hypotheses."""

    def __init__(self, vendor: AgentVendor) -> None:
        self.vendor = vendor

    def create_initial_population(
        self,
        base_prompt: str,
        step_index: int,
        population_size: int,
    ) -> list[AgentTask]:
        """Create the initial generation of agent tasks with diverse prompts."""
        tasks = []
        for i in range(population_size):
            prompt = self.vendor.build_prompt(base_prompt, [], i)
            tasks.append(
                AgentTask(
                    id=f"agent-{uuid.uuid4().hex[:8]}",
                    generation=0,
                    step_index=step_index,
                    prompt=prompt,
                    repo_snapshot_path="",  # Filled by workflow engine
                )
            )
        return tasks

    def evolve(
        self,
        base_prompt: str,
        step_index: int,
        generation: int,
        population_size: int,
        hypotheses: list[Hypothesis],
    ) -> list[AgentTask]:
        """Create the next generation of agent tasks, incorporating hypotheses."""
        tasks = []
        for i in range(population_size):
            prompt = self.vendor.build_prompt(base_prompt, hypotheses, i)
            tasks.append(
                AgentTask(
                    id=f"agent-{uuid.uuid4().hex[:8]}",
                    generation=generation,
                    step_index=step_index,
                    prompt=prompt,
                    repo_snapshot_path="",
                    parent_hypotheses=list(hypotheses),
                )
            )
        return tasks
