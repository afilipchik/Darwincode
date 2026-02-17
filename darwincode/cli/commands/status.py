from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from darwincode.state.run_state import RunStateStore

console = Console()

DEFAULT_STATE_DIR = Path.home() / ".darwincode" / "runs"


@click.command()
@click.option("--run-id", default=None, help="Specific run ID to check")
def status(run_id: str | None) -> None:
    """Check status of running or recent experiments."""
    store = RunStateStore(DEFAULT_STATE_DIR)

    if run_id:
        state = store.load(run_id)
        if not state:
            console.print(f"[red]Run '{run_id}' not found.[/red]")
            return
        _print_run(state)
    else:
        runs = store.list_runs()
        if not runs:
            console.print("[dim]No runs found.[/dim]")
            return
        for r in runs[-5:]:
            _print_run(r)


def _print_run(state) -> None:
    table = Table(title=f"Run {state.id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Status", state.status.value)
    table.add_row("Step", f"{state.current_step}/{len(state.plan_steps)}")
    table.add_row("Generation", str(state.current_generation))
    table.add_row("Generations completed", str(len(state.generations)))
    console.print(table)
