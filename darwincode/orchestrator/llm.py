"""Call Claude via the claude CLI, using whatever auth the user has configured (OAuth or API key)."""

from __future__ import annotations

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def claude_query(prompt: str, timeout: int = 120) -> str:
    """Send a prompt to Claude via the claude CLI and return the text response.

    Uses the locally installed claude CLI, which picks up OAuth or API key auth
    automatically — no ANTHROPIC_API_KEY required if the user is logged in.

    Runs from /tmp to avoid the CLI picking up project context from cwd.
    """
    # Strip CLAUDECODE env var so the CLI doesn't think it's a nested session
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        [
            "claude",
            "-p", prompt,
            "--output-format", "json",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd="/tmp",  # Neutral dir — prevent CLI from reading project context
        env=env,
    )

    if result.returncode != 0:
        logger.error("claude CLI stderr: %s", result.stderr)
        raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {result.stderr}")

    # --output-format json returns a JSON object with a "result" field
    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            return data.get("result", result.stdout)
        # Handle unexpected array/other JSON output
        return result.stdout
    except json.JSONDecodeError:
        logger.error("claude CLI returned non-JSON: %s", result.stdout[:500])
        return result.stdout
