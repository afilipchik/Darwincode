from __future__ import annotations

from abc import ABC, abstractmethod

from darwincode.types.models import (
    AgentResult,
    AgentTask,
    EvalResult,
    EvalSpec,
    WorkflowStatus,
)


class WorkflowEngine(ABC):
    """Abstract workflow engine. Swap implementations without changing orchestration logic.

    MVP: LocalWorkflowEngine (asyncio + K8s Jobs)
    Future: TemporalWorkflowEngine (Temporal workflows + activities)
    """

    @abstractmethod
    async def execute_generation(
        self, tasks: list[AgentTask], timeout: int
    ) -> list[AgentResult]:
        """Run N agent tasks in parallel, return results when all complete."""
        ...

    @abstractmethod
    async def run_eval(
        self, results: list[AgentResult], eval_spec: EvalSpec
    ) -> list[EvalResult]:
        """Evaluate agent results against the test harness."""
        ...

    @abstractmethod
    async def get_status(self) -> WorkflowStatus:
        """Get current status of all running tasks (for live progress)."""
        ...

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel all running tasks."""
        ...
