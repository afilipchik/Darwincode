from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from kubernetes import client, config, watch

from darwincode.k8s.images import AGENT_IMAGE_NAME, AGENT_IMAGE_TAG
from darwincode.types.models import AgentResult, AgentStatus, AgentTask

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, run_id: str, namespace: str = "default") -> None:
        self.run_id = run_id
        self.namespace = namespace
        self._batch_v1 = None
        self._core_v1 = None

    @property
    def batch_v1(self):
        if self._batch_v1 is None:
            config.load_kube_config()
            self._batch_v1 = client.BatchV1Api()
            self._core_v1 = client.CoreV1Api()
        return self._batch_v1

    @property
    def core_v1(self):
        if self._core_v1 is None:
            config.load_kube_config()
            self._batch_v1 = client.BatchV1Api()
            self._core_v1 = client.CoreV1Api()
        return self._core_v1

    def _job_name(self, task_id: str) -> str:
        return f"darwin-{self.run_id[:8]}-{task_id}"

    def create_job(self, task: AgentTask, workspace_host_path: str) -> str:
        """Create a K8s Job for an agent task. Returns job name."""
        job_name = self._job_name(task.id)

        volume_mounts = [
            client.V1VolumeMount(
                name="workspace",
                mount_path="/workspace",
            ),
            # Claude Code credentials dir (.credentials.json lives here)
            client.V1VolumeMount(
                name="claude-auth",
                mount_path="/home/agent/.claude",
            ),
        ]

        # Pass ANTHROPIC_API_KEY from host env if set (optional fallback)
        env = []
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            env.append(client.V1EnvVar(name="ANTHROPIC_API_KEY", value=api_key))

        container = client.V1Container(
            name="agent",
            image=f"{AGENT_IMAGE_NAME}:{AGENT_IMAGE_TAG}",
            image_pull_policy="Never",  # Image is loaded into Kind
            volume_mounts=volume_mounts,
            env=env or None,
            resources=client.V1ResourceRequirements(
                requests={"cpu": "500m", "memory": "512Mi"},
                limits={"cpu": "2", "memory": "4Gi"},
            ),
        )

        volumes = [
            client.V1Volume(
                name="workspace",
                host_path=client.V1HostPathVolumeSource(
                    path=workspace_host_path,
                    type="Directory",
                ),
            ),
            # Mount .claude dir from workspace (contains .credentials.json)
            client.V1Volume(
                name="claude-auth",
                host_path=client.V1HostPathVolumeSource(
                    path=f"{workspace_host_path}/.claude",
                    type="Directory",
                ),
            ),
        ]

        pod_spec = client.V1PodSpec(
            containers=[container],
            volumes=volumes,
            restart_policy="Never",
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                labels={
                    "app": "darwincode",
                    "run-id": self.run_id[:8],
                    "task-id": task.id,
                },
            ),
            spec=client.V1JobSpec(
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "darwincode",
                            "task-id": task.id,
                        }
                    ),
                    spec=pod_spec,
                ),
                backoff_limit=0,
                ttl_seconds_after_finished=60,
                active_deadline_seconds=task.parent_hypotheses[0].generation * 60
                if task.parent_hypotheses
                else 600,
            ),
        )

        self.batch_v1.create_namespaced_job(namespace=self.namespace, body=job)
        logger.info("Created job '%s' for task '%s'", job_name, task.id)
        return job_name

    async def wait_for_job(self, task_id: str, timeout: int) -> AgentResult:
        """Wait for a job to complete and return the result."""
        job_name = self._job_name(task_id)
        start = time.time()

        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                self._delete_job(job_name)
                return AgentResult(
                    task_id=task_id,
                    status=AgentStatus.TIMEOUT,
                    output=f"Timed out after {timeout}s",
                    patch_path="",
                    duration_seconds=elapsed,
                )

            try:
                job = self.batch_v1.read_namespaced_job(job_name, self.namespace)
            except client.exceptions.ApiException:
                return AgentResult(
                    task_id=task_id,
                    status=AgentStatus.ERROR,
                    output="Job not found",
                    patch_path="",
                    duration_seconds=elapsed,
                )

            if job.status.succeeded and job.status.succeeded > 0:
                return self._collect_result(task_id, AgentStatus.SUCCESS, elapsed)

            if job.status.failed and job.status.failed > 0:
                return self._collect_result(task_id, AgentStatus.FAILURE, elapsed)

            # Check pod events for fatal errors (mount failures, image pull errors, etc.)
            error = self._check_pod_events(task_id)
            if error:
                logger.error("Pod error for task %s: %s", task_id, error)
                self._delete_job(job_name)
                return AgentResult(
                    task_id=task_id,
                    status=AgentStatus.ERROR,
                    output=f"Pod error: {error}",
                    patch_path="",
                    duration_seconds=elapsed,
                )

            await asyncio.sleep(5)

    def _check_pod_events(self, task_id: str) -> str | None:
        """Check pod events for fatal errors. Returns error message or None."""
        try:
            pods = self.core_v1.list_namespaced_pod(
                self.namespace,
                label_selector=f"app=darwincode,task-id={task_id}",
            )
            if not pods.items:
                return None

            pod = pods.items[0]
            pod_name = pod.metadata.name

            # Check container statuses for crash/error
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    if cs.state.waiting and cs.state.waiting.reason in (
                        "CrashLoopBackOff", "ErrImagePull", "ImagePullBackOff",
                        "CreateContainerConfigError",
                    ):
                        return f"{cs.state.waiting.reason}: {cs.state.waiting.message or ''}"

            # Check events for mount failures and other warnings
            events = self.core_v1.list_namespaced_event(
                self.namespace,
                field_selector=f"involvedObject.name={pod_name}",
            )
            for event in events.items:
                if event.type == "Warning" and event.reason in (
                    "FailedMount", "FailedScheduling", "FailedAttachVolume",
                ):
                    return f"{event.reason}: {event.message}"

        except Exception as e:
            logger.debug("Failed to check pod events for %s: %s", task_id, e)

        return None

    def _collect_result(
        self, task_id: str, status: AgentStatus, duration: float
    ) -> AgentResult:
        """Read results from the workspace filesystem."""
        from darwincode.k8s.volumes import WORKSPACES_BASE

        workspace = WORKSPACES_BASE / self.run_id / task_id
        results_dir = workspace / "results"
        transcript_dir = workspace / "transcript"

        output = ""
        output_file = results_dir / "output.log"
        if output_file.exists():
            output = output_file.read_text()

        patch_path = str(results_dir / "patch.diff")
        transcript_path = str(transcript_dir / "raw.jsonl")

        return AgentResult(
            task_id=task_id,
            status=status,
            output=output,
            patch_path=patch_path if Path(patch_path).exists() else "",
            duration_seconds=duration,
            transcript_path=transcript_path if Path(transcript_path).exists() else None,
        )

    def _delete_job(self, job_name: str) -> None:
        try:
            self.batch_v1.delete_namespaced_job(
                job_name,
                self.namespace,
                propagation_policy="Background",
            )
        except client.exceptions.ApiException:
            pass

    def cleanup_jobs(self) -> None:
        """Delete all jobs for this run."""
        try:
            jobs = self.batch_v1.list_namespaced_job(
                self.namespace,
                label_selector=f"app=darwincode,run-id={self.run_id[:8]}",
            )
            for job in jobs.items:
                self._delete_job(job.metadata.name)
        except client.exceptions.ApiException as e:
            logger.warning("Failed to cleanup jobs: %s", e)
