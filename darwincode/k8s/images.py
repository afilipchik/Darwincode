from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

AGENT_IMAGE_NAME = "darwincode-agent"
AGENT_IMAGE_TAG = "latest"
DOCKER_DIR = Path(__file__).parent.parent.parent / "docker" / "agent"


class ImageManager:
    def __init__(self, cluster_name: str = "darwincode") -> None:
        self.cluster_name = cluster_name
        self.image = f"{AGENT_IMAGE_NAME}:{AGENT_IMAGE_TAG}"

    def build_agent_image(self) -> None:
        logger.info("Building agent image '%s' from %s", self.image, DOCKER_DIR)
        subprocess.run(
            ["docker", "build", "-t", self.image, str(DOCKER_DIR)],
            check=True,
        )

    def load_into_kind(self) -> None:
        logger.info("Loading image '%s' into Kind cluster '%s'", self.image, self.cluster_name)
        subprocess.run(
            ["kind", "load", "docker-image", self.image, "--name", self.cluster_name],
            check=True,
        )
