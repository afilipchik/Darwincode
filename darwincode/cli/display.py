from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from darwincode.types.models import (
    AgentStatus,
    GenerationRecord,
    Hypothesis,
    PlanStep,
    RunState,
    WorkflowStatus,
)


STATUS_ICONS = {
    AgentStatus.PENDING: "[dim]waiting[/dim]",
    AgentStatus.RUNNING: "[yellow]running[/yellow]",
    AgentStatus.SUCCESS: "[green]done[/green]",
    AgentStatus.FAILURE: "[red]failed[/red]",
    AgentStatus.TIMEOUT: "[red]timeout[/red]",
    AgentStatus.ERROR: "[red]error[/red]",
}


class Display:
    """Rich-based TUI for displaying evolution progress."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def show_header(self, run_id: str) -> None:
        self.console.print(
            Panel(
                f"[bold]Evolution Run[/bold] #{run_id}",
                title="Darwincode",
                border_style="blue",
            )
        )

    def show_status(self, message: str) -> None:
        self.console.print(f"  {message}")

    def show_plan(self, steps: list[PlanStep]) -> None:
        self.console.print(f"\n[bold]Plan:[/bold] {len(steps)} steps decomposed")
        for step in steps:
            self.console.print(f"  {step.index + 1}. {step.description}")
        self.console.print()

    def show_step_start(self, step: PlanStep) -> None:
        self.console.rule(f"Step {step.index + 1}: {step.description}")

    def show_generation_start(
        self, step_index: int, generation: int, num_agents: int
    ) -> None:
        self.console.print(
            f"\n  [bold]Generation {generation}[/bold] — {num_agents} agents spawned"
        )

    def show_generation_results(self, record: GenerationRecord) -> None:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Score")
        table.add_column("")

        for result, eval_result in zip(record.results, record.eval_results):
            is_winner = "<<" if result.task_id == record.winner_id else ""
            status_text = STATUS_ICONS.get(result.status, result.status.value)
            table.add_row(
                result.task_id,
                status_text,
                f"{result.duration_seconds:.0f}s",
                f"{eval_result.score:.2f}",
                is_winner,
            )

        self.console.print(table)

    def show_workflow_status(self, status: WorkflowStatus) -> None:
        table = Table(title=f"Step {status.step_index} — Gen {status.generation}")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Progress")

        for task in status.tasks:
            status_text = STATUS_ICONS.get(task.status, task.status.value)
            table.add_row(task.task_id, status_text, task.progress)

        self.console.print(table)

    def show_hypothesis(self, hypothesis: Hypothesis) -> None:
        self.console.print(
            Panel(
                f"[bold]Analysis:[/bold] {hypothesis.analysis}\n\n"
                f"[bold]Prompt adjustment:[/bold] {hypothesis.prompt_delta}",
                title=f"Hypothesis (Gen {hypothesis.generation})",
                border_style="cyan",
            )
        )

    def show_winner(self, winner_id: str, step_index: int) -> None:
        self.console.print(
            f"\n  [bold green]Winner for step {step_index + 1}:[/bold green] {winner_id}"
        )

    def show_no_winner(self, step_index: int) -> None:
        self.console.print(
            f"\n  [bold yellow]No passing result for step {step_index + 1}. "
            f"Using best available.[/bold yellow]"
        )

    def show_completed(self, state: RunState) -> None:
        self.console.print(
            Panel(
                f"[bold green]Evolution complete![/bold green]\n"
                f"Steps: {len(state.plan_steps)}\n"
                f"Generations: {len(state.generations)}\n"
                f"Hypotheses: {len(state.hypotheses)}",
                border_style="green",
            )
        )

    def show_error(self, message: str) -> None:
        self.console.print(f"\n  [bold red]Error:[/bold red] {message}")
