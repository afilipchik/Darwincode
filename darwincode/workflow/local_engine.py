from __future__ import annotations

import asyncio
import logging

from darwincode.eval.runner import EvalRunner
from darwincode.k8s.jobs import JobManager
from darwincode.k8s.monitor import PodMonitor
from darwincode.k8s.volumes import VolumeManager, host_to_node_path
from darwincode.types.models import (
    AgentResult,
    AgentTask,
    EvalResult,
    EvalSpec,
    WorkflowStatus,
)
from darwincode.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class LocalWorkflowEngine(WorkflowEngine):
    """Asyncio-based workflow engine using K8s Jobs via Kind."""

    def __init__(
        self,
        run_id: str,
        repo_path: str,
        cluster_name: str = "darwincode",
        protected_paths: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.repo_path = repo_path
        self.cluster_name = cluster_name
        self.protected_paths = protected_paths or []
        self.volumes = VolumeManager(run_id)
        self.jobs = JobManager(run_id)
        self.monitor = PodMonitor(run_id)
        self.eval_runner = EvalRunner(run_id)
        self._current_tasks: list[AgentTask] = []
        self._step_index = 0
        self._generation = 0

    async def execute_generation(
        self, tasks: list[AgentTask], timeout: int
    ) -> list[AgentResult]:
        self._current_tasks = tasks
        if tasks:
            self._step_index = tasks[0].step_index
            self._generation = tasks[0].generation

        # Prepare workspaces and create jobs
        for task in tasks:
            workspace = self.volumes.prepare_workspace(
                task, self.repo_path, self.protected_paths or None
            )
            # Convert host path → Kind node path for the K8s Job hostPath volume
            node_path = host_to_node_path(str(workspace))
            self.jobs.create_job(task, node_path)

        # Wait for all jobs in parallel
        results = await asyncio.gather(
            *[self.jobs.wait_for_job(task.id, timeout) for task in tasks]
        )

        return list(results)

    async def run_eval(
        self, results: list[AgentResult], eval_spec: EvalSpec
    ) -> list[EvalResult]:
        eval_results = []
        for result in results:
            eval_result = await self.eval_runner.evaluate(result, eval_spec)
            eval_results.append(eval_result)
        return eval_results

    async def get_status(self) -> WorkflowStatus:
        task_ids = [t.id for t in self._current_tasks]
        return self.monitor.get_status(self._step_index, self._generation, task_ids)

    async def cancel(self) -> None:
        self.jobs.cleanup_jobs()
        self._current_tasks = []
