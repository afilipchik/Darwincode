from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from darwincode.types.models import EvalSpec


class ClusterMode(str, Enum):
    LOCAL = "local"    # Kind cluster — full lifecycle control, auto-init
    REMOTE = "remote"  # Existing K8s cluster — no lifecycle management


class DarwinConfig(BaseModel):
    plan: str = Field(description="High-level goal or path to a plan file")
    eval: EvalSpec = Field(description="Evaluation specification")
    repo_path: str = Field(description="Path to the target repository")
    agent_vendor: str = Field(default="claude-code", description="Agent vendor name")
    population_size: int = Field(default=5, ge=1, description="Agents per generation")
    max_generations: int = Field(default=3, ge=1, description="Max evolution iterations")
    timeout: int = Field(default=300, ge=30, description="Per-agent timeout in seconds")
    agent_config: dict = Field(default_factory=dict, description="Vendor-specific config")
    cluster_mode: ClusterMode = Field(
        default=ClusterMode.LOCAL,
        description="local = Kind with auto-init, remote = existing K8s cluster",
    )
    cluster_name: str = Field(default="darwincode", description="Kind cluster name (local mode)")
    kubeconfig: str | None = Field(
        default=None, description="Path to kubeconfig (remote mode, uses default if None)"
    )

    model_config = {"arbitrary_types_allowed": True}
