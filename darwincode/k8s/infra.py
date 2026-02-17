"""Infrastructure manager — ensures K8s is ready before running agents.

In local mode: auto-creates Kind cluster, builds and loads the agent Docker image.
In remote mode: validates the cluster is reachable, image must already exist in registry.
"""

from __future__ import annotations

import logging
import subprocess

from rich.console import Console

from darwincode.k8s.cluster import ClusterManager
from darwincode.k8s.images import AGENT_IMAGE_NAME, AGENT_IMAGE_TAG, ImageManager
from darwincode.types.config import ClusterMode

logger = logging.getLogger(__name__)


class InfraManager:
    """Ensure K8s infrastructure is ready for an evolution run."""

    def __init__(
        self,
        cluster_mode: ClusterMode,
        cluster_name: str = "darwincode",
        console: Console | None = None,
    ) -> None:
        self.mode = cluster_mode
        self.cluster_name = cluster_name
        self.console = console or Console()

    def ensure_ready(self) -> None:
        """Make sure the cluster + agent image are available. Auto-init in local mode."""
        if self.mode == ClusterMode.LOCAL:
            self._ensure_local()
        else:
            self._ensure_remote()

    def _ensure_local(self) -> None:
        cluster = ClusterManager(self.cluster_name)
        images = ImageManager(self.cluster_name)

        # 1. Ensure Docker is running
        if not self._docker_running():
            raise RuntimeError(
                "Docker is not running. Please start Docker Desktop and try again."
            )

        # 2. Ensure Kind cluster exists
        if cluster.exists():
            self.console.print(
                f"  [dim]Kind cluster '{self.cluster_name}' already running[/dim]"
            )
        else:
            self.console.print(
                f"  [bold]Creating Kind cluster '{self.cluster_name}'...[/bold]"
            )
            cluster.create()
            self.console.print("  [green]Cluster created.[/green]")

        # 3. Verify cluster health — K8s API reachable and node Ready
        self._verify_cluster_health()

        # 4. Ensure agent image is built and loaded
        if self._image_exists_locally():
            self.console.print("  [dim]Agent image already built[/dim]")
        else:
            self.console.print("  [bold]Building agent Docker image...[/bold]")
            images.build_agent_image()
            self.console.print("  [green]Image built.[/green]")

        if not self._image_loaded_in_kind():
            self.console.print("  [bold]Loading image into Kind cluster...[/bold]")
            images.load_into_kind()
            self.console.print("  [green]Image loaded.[/green]")

    def _ensure_remote(self) -> None:
        """For remote mode, just verify the cluster is reachable."""
        try:
            from kubernetes import client, config

            config.load_kube_config()
            v1 = client.CoreV1Api()
            v1.list_namespace(limit=1)
            self.console.print("  [dim]Remote K8s cluster reachable[/dim]")
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect to remote K8s cluster: {e}\n"
                "Ensure your kubeconfig is set correctly."
            ) from e

    def _verify_cluster_health(self, max_wait: int = 60) -> None:
        """Verify the K8s cluster is healthy: API reachable, node Ready.

        Waits up to max_wait seconds for the node to become Ready (it takes
        a moment after cluster creation).
        """
        import time

        from kubernetes import client, config

        self.console.print("  [dim]Waiting for cluster to be ready...[/dim]")

        config.load_kube_config()
        v1 = client.CoreV1Api()

        deadline = time.time() + max_wait
        last_error = ""

        while time.time() < deadline:
            try:
                nodes = v1.list_node()
                if not nodes.items:
                    last_error = "No nodes found"
                    time.sleep(3)
                    continue

                all_ready = True
                for node in nodes.items:
                    ready = any(
                        c.type == "Ready" and c.status == "True"
                        for c in (node.status.conditions or [])
                    )
                    if not ready:
                        all_ready = False
                        last_error = f"Node '{node.metadata.name}' not Ready"
                        break

                if all_ready:
                    self.console.print("  [dim]Cluster health: OK[/dim]")
                    return

            except Exception as e:
                last_error = str(e)

            time.sleep(3)

        raise RuntimeError(
            f"Cluster not ready after {max_wait}s: {last_error}. "
            f"Try: kind delete cluster --name {self.cluster_name} && darwincode run ..."
        )

    def _docker_running(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _image_exists_locally(self) -> bool:
        result = subprocess.run(
            ["docker", "images", "-q", f"{AGENT_IMAGE_NAME}:{AGENT_IMAGE_TAG}"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())

    def _image_loaded_in_kind(self) -> bool:
        """Check if the image is available inside the Kind cluster."""
        try:
            result = subprocess.run(
                [
                    "docker", "exec", f"{self.cluster_name}-control-plane",
                    "crictl", "images", "--no-trunc",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return AGENT_IMAGE_NAME in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # If we can't check, load it to be safe
            return False
