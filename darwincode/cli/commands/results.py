from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from darwincode.state.run_state import RunStateStore

console = Console()

DEFAULT_STATE_DIR = Path.home() / ".darwincode" / "runs"


@click.command()
@click.option("--run-id", default=None, help="Run ID (defaults to latest)")
def results(run_id: str | None) -> None:
    """View results and hypotheses from an experiment."""
    store = RunStateStore(DEFAULT_STATE_DIR)

    if run_id:
        state = store.load(run_id)
    else:
        runs = store.list_runs()
        state = runs[-1] if runs else None

    if not state:
        console.print("[red]No runs found.[/red]")
        return

    console.print(f"[bold]Run {state.id}[/bold] — {state.status.value}\n")

    for gen in state.generations:
        table = Table(title=f"Step {gen.step_index} — Generation {gen.generation}")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Eval Score")
        table.add_column("Winner")

        for result, eval_result in zip(gen.results, gen.eval_results):
            is_winner = "<<" if result.task_id == gen.winner_id else ""
            table.add_row(
                result.task_id,
                result.status.value,
                f"{eval_result.score:.2f}",
                is_winner,
            )
        console.print(table)

        if gen.hypothesis:
            console.print(
                Panel(
                    gen.hypothesis.analysis,
                    title=f"Hypothesis (Gen {gen.generation})",
                    border_style="cyan",
                )
            )
        console.print()

    if state.hypotheses:
        console.print("[bold]All Hypotheses:[/bold]")
        for h in state.hypotheses:
            console.print(f"  Gen {h.generation}: {h.analysis}")
