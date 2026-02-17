from __future__ import annotations

import json
import logging
from pathlib import Path

from kubernetes import client, config

from darwincode.k8s.volumes import WORKSPACES_BASE
from darwincode.types.models import AgentStatus, TaskStatus, WorkflowStatus

logger = logging.getLogger(__name__)


class PodMonitor:
    def __init__(self, run_id: str, namespace: str = "default") -> None:
        self.run_id = run_id
        self.namespace = namespace
        self._core_v1 = None

    @property
    def core_v1(self):
        if self._core_v1 is None:
            config.load_kube_config()
            self._core_v1 = client.CoreV1Api()
        return self._core_v1

    def get_status(
        self, step_index: int, generation: int, task_ids: list[str]
    ) -> WorkflowStatus:
        """Poll pod status and workspace status.json for all tasks."""
        tasks = []
        for task_id in task_ids:
            tasks.append(self._get_task_status(task_id))

        return WorkflowStatus(
            generation=generation,
            step_index=step_index,
            tasks=tasks,
        )

    def _get_task_status(self, task_id: str) -> TaskStatus:
        # Check workspace status.json first
        workspace = WORKSPACES_BASE / self.run_id / task_id
        status_file = workspace / "results" / "status.json"

        progress = ""
        if status_file.exists():
            try:
                data = json.loads(status_file.read_text())
                progress = data.get("progress", "")
                ws_status = data.get("status", "")
                if ws_status == "done":
                    return TaskStatus(
                        task_id=task_id,
                        status=AgentStatus.SUCCESS,
                        elapsed_seconds=0,
                        progress=progress,
                    )
                elif ws_status == "error":
                    return TaskStatus(
                        task_id=task_id,
                        status=AgentStatus.ERROR,
                        elapsed_seconds=0,
                        progress=progress,
                    )
            except (json.JSONDecodeError, OSError):
                pass

        # Fall back to K8s pod status
        try:
            pods = self.core_v1.list_namespaced_pod(
                self.namespace,
                label_selector=f"app=darwincode,task-id={task_id}",
            )
            if pods.items:
                pod = pods.items[0]
                phase = pod.status.phase
                if phase == "Running":
                    return TaskStatus(
                        task_id=task_id,
                        status=AgentStatus.RUNNING,
                        elapsed_seconds=0,
                        progress=progress or "Running in pod",
                    )
                elif phase == "Succeeded":
                    return TaskStatus(
                        task_id=task_id,
                        status=AgentStatus.SUCCESS,
                        elapsed_seconds=0,
                        progress="Completed",
                    )
                elif phase == "Failed":
                    return TaskStatus(
                        task_id=task_id,
                        status=AgentStatus.FAILURE,
                        elapsed_seconds=0,
                        progress="Pod failed",
                    )
        except Exception as e:
            logger.debug("Failed to get pod status for %s: %s", task_id, e)

        return TaskStatus(
            task_id=task_id,
            status=AgentStatus.PENDING,
            elapsed_seconds=0,
            progress=progress or "Waiting",
        )

    def get_agent_log_tail(self, task_id: str, lines: int = 20) -> str:
        """Get the last N lines of an agent's raw transcript."""
        workspace = WORKSPACES_BASE / self.run_id / task_id
        raw_jsonl = workspace / "transcript" / "raw.jsonl"

        if not raw_jsonl.exists():
            return "(no transcript yet)"

        all_lines = raw_jsonl.read_text().strip().split("\n")
        tail = all_lines[-lines:]

        # Extract text content from stream-json events
        output_lines = []
        for line in tail:
            try:
                event = json.loads(line)
                if event.get("type") == "assistant":
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            output_lines.append(block["text"])
            except json.JSONDecodeError:
                output_lines.append(line)

        return "\n".join(output_lines) if output_lines else "(no text output yet)"
