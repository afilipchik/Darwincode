from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path

from darwincode.types.models import AgentTask

logger = logging.getLogger(__name__)

# Host path (where files actually live on the macOS host).
# MUST be under $HOME for Colima/Docker Desktop file sharing to work.
WORKSPACES_BASE = Path.home() / ".darwincode" / "workspaces"

# Kind node path (host path is mounted here via Kind extraMounts)
WORKSPACES_NODE_BASE = "/workspaces"


def host_to_node_path(host_path: str) -> str:
    """Convert a host workspace path to the corresponding Kind node path.

    The Kind cluster mounts ~/.darwincode/workspaces → /workspaces on the node.
    K8s Job hostPath volumes reference paths on the node, not the host.
    """
    return host_path.replace(str(WORKSPACES_BASE), WORKSPACES_NODE_BASE)


def _get_claude_credentials() -> dict | None:
    """Extract Claude Code OAuth credentials from the platform credential store.

    On macOS: reads from Keychain (service "Claude Code-credentials").
    On Linux: reads from ~/.claude/.credentials.json.
    Returns the credentials dict or None if not found.
    """
    # Try file-based credentials first (works on all platforms)
    creds_file = Path.home() / ".claude" / ".credentials.json"
    if creds_file.exists():
        try:
            return json.loads(creds_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # On macOS, extract from Keychain
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                [
                    "security", "find-generic-password",
                    "-s", "Claude Code-credentials",
                    "-w",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout.strip())
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to read Claude credentials from Keychain: %s", e)

    return None


class VolumeManager:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.run_dir = WORKSPACES_BASE / run_id

    def prepare_workspace(
        self, task: AgentTask, repo_path: str, protected_paths: list[str] | None = None
    ) -> Path:
        """Create a workspace directory for an agent task with repo copy and task.json."""
        workspace = self.run_dir / task.id
        workspace.mkdir(parents=True, exist_ok=True)

        # Copy the repo
        repo_dest = workspace / "repo"
        if repo_dest.exists():
            shutil.rmtree(repo_dest)
        shutil.copytree(repo_path, repo_dest, symlinks=True)

        # Snapshot protected paths (eval validation harness) before agent can modify them
        if protected_paths:
            self._save_protected_paths(workspace, repo_dest, protected_paths)

        # Create results and transcript dirs
        (workspace / "results").mkdir(exist_ok=True)
        (workspace / "transcript").mkdir(exist_ok=True)

        # Write task.json
        task_data = {
            "id": task.id,
            "generation": task.generation,
            "prompt": task.prompt,
            "vendor": "claude-code",  # Will be parameterized via agent vendor
            "parent_hypotheses": [
                {"analysis": h.analysis, "prompt_delta": h.prompt_delta}
                for h in task.parent_hypotheses
            ],
        }
        (workspace / "task.json").write_text(json.dumps(task_data, indent=2))

        # Write Claude Code credentials for the agent.
        # Claude Code stores OAuth tokens in the macOS Keychain; containers can't
        # access the keychain, so we extract the credentials and write them to
        # .claude/.credentials.json which Claude Code reads as a fallback.
        self._write_claude_credentials(workspace)

        # Make workspace writable by the non-root agent user in the container.
        # The container runs as uid 1000 (agent) but files are owned by the host user.
        self._make_writable(workspace)

        logger.info("Prepared workspace for task '%s' at %s", task.id, workspace)
        return workspace

    @staticmethod
    def _save_protected_paths(
        workspace: Path, repo_dir: Path, protected_paths: list[str]
    ) -> None:
        """Snapshot protected paths from repo into pristine/ for eval-time restoration."""
        pristine_dir = workspace / "pristine"
        for rel_path in protected_paths:
            src = repo_dir / rel_path
            if not src.exists():
                logger.warning("Protected path not found in repo: %s", rel_path)
                continue
            dest = pristine_dir / rel_path
            if src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        if pristine_dir.exists():
            logger.info("Saved %d protected path(s) to %s", len(protected_paths), pristine_dir)

    @staticmethod
    def _write_claude_credentials(workspace: Path) -> None:
        """Extract OAuth credentials and write .claude/.credentials.json for the agent."""
        creds = _get_claude_credentials()
        if not creds:
            logger.warning("No Claude Code credentials found — agent may fail to authenticate")
            return

        claude_dir = workspace / ".claude"
        claude_dir.mkdir(exist_ok=True)
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text(json.dumps(creds, indent=2))
        logger.debug("Wrote Claude credentials to %s", creds_file)

    @staticmethod
    def _make_writable(path: Path) -> None:
        """Recursively make a directory world-writable so the container agent user can write."""
        for dirpath, dirnames, filenames in os.walk(path):
            dp = Path(dirpath)
            dp.chmod(dp.stat().st_mode | stat.S_IWOTH | stat.S_IXOTH | stat.S_IROTH)
            for f in filenames:
                fp = dp / f
                fp.chmod(fp.stat().st_mode | stat.S_IWOTH | stat.S_IROTH)

    def get_workspace_path(self, task_id: str) -> Path:
        return self.run_dir / task_id

    def cleanup(self) -> None:
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
            logger.info("Cleaned up workspaces for run '%s'", self.run_id)
