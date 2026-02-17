from pathlib import Path

import click
from rich.console import Console

console = Console()

DEFAULT_STATE_DIR = Path.home() / ".darwincode" / "runs"


@click.command()
@click.argument("agent_id")
@click.option("--run-id", default=None, help="Run ID (defaults to latest)")
@click.option("--raw", is_flag=True, help="Show raw JSONL transcript instead of plain output")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(agent_id: str, run_id: str | None, raw: bool, follow: bool) -> None:
    """Tail logs for an agent."""
    # Find the workspace directory for this agent
    runs_dir = DEFAULT_STATE_DIR
    if run_id:
        workspace_base = runs_dir / run_id / "workspaces"
    else:
        # Find latest run
        run_dirs = sorted(runs_dir.iterdir()) if runs_dir.exists() else []
        if not run_dirs:
            console.print("[red]No runs found.[/red]")
            return
        workspace_base = run_dirs[-1] / "workspaces"

    agent_dir = workspace_base / agent_id
    if not agent_dir.exists():
        console.print(f"[red]Agent workspace '{agent_id}' not found.[/red]")
        return

    if raw:
        log_file = agent_dir / "transcript" / "raw.jsonl"
    else:
        log_file = agent_dir / "results" / "output.log"

    if not log_file.exists():
        console.print(f"[red]Log file not found: {log_file}[/red]")
        return

    if follow:
        # Stream the file
        import time

        with open(log_file) as f:
            while True:
                line = f.readline()
                if line:
                    console.print(line, end="")
                else:
                    time.sleep(0.5)
    else:
        console.print(log_file.read_text())
