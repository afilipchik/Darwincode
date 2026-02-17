from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

KIND_CONFIG_TEMPLATE = """\
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: {home_dir}/.darwincode/workspaces
        containerPath: /workspaces
      - hostPath: {home_dir}/.claude.json
        containerPath: /host-home/.claude.json
        readOnly: true
"""


class ClusterManager:
    def __init__(self, name: str = "darwincode") -> None:
        self.name = name

    def exists(self) -> bool:
        result = subprocess.run(
            ["kind", "get", "clusters"],
            capture_output=True,
            text=True,
        )
        return self.name in result.stdout.strip().split("\n")

    def create(self) -> None:
        logger.info("Creating Kind cluster '%s'", self.name)
        home_dir = str(Path.home())
        # Ensure workspace dir exists before Kind tries to mount it
        (Path.home() / ".darwincode" / "workspaces").mkdir(parents=True, exist_ok=True)
        config_content = KIND_CONFIG_TEMPLATE.format(home_dir=home_dir)
        subprocess.run(
            ["kind", "create", "cluster", "--name", self.name, "--config", "-"],
            input=config_content,
            check=True,
            text=True,
        )

    def delete(self) -> None:
        logger.info("Deleting Kind cluster '%s'", self.name)
        subprocess.run(
            ["kind", "delete", "cluster", "--name", self.name],
            check=True,
        )

    def get_kubeconfig_path(self) -> str:
        result = subprocess.run(
            ["kind", "get", "kubeconfig-path", "--name", self.name],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
