import asyncio
from pathlib import Path

import click
from rich.console import Console

from darwincode.orchestrator.orchestrator import Orchestrator
from darwincode.types.config import ClusterMode, DarwinConfig
from darwincode.types.models import EvalSpec

console = Console()


@click.command()
@click.option("--plan", required=True, help="Goal description or path to a plan file")
@click.option("--eval", "eval_command", required=True, help="Eval command (e.g. 'pytest tests/')")
@click.option("--repo", required=True, type=click.Path(exists=True), help="Path to target repo")
@click.option("--population", default=5, type=int, help="Agents per generation")
@click.option("--generations", default=3, type=int, help="Max generations per step")
@click.option("--agent", "agent_vendor", default="claude-code", help="Agent vendor")
@click.option("--timeout", default=300, type=int, help="Per-agent timeout in seconds")
@click.option("--cluster-name", default="darwincode", help="Kind cluster name")
@click.option(
    "--mode",
    "cluster_mode",
    type=click.Choice(["local", "remote"], case_sensitive=False),
    default="local",
    help="local = Kind (auto-init), remote = existing K8s cluster",
)
@click.option(
    "--protect",
    multiple=True,
    help="Protected eval paths (repo-relative, repeatable). "
    "These files are used as the validation harness and cannot be "
    "tampered with by agents. Example: --protect src/test/ --protect pom.xml",
)
def run(
    plan: str,
    eval_command: str,
    repo: str,
    population: int,
    generations: int,
    agent_vendor: str,
    timeout: int,
    cluster_name: str,
    cluster_mode: str,
    protect: tuple[str, ...],
) -> None:
    """Run an evolution experiment."""
    plan_text = plan
    plan_path = Path(plan)
    if plan_path.is_file():
        plan_text = plan_path.read_text()

    config = DarwinConfig(
        plan=plan_text,
        eval=EvalSpec(command=eval_command, timeout=timeout, protected_paths=list(protect)),
        repo_path=str(Path(repo).resolve()),
        agent_vendor=agent_vendor,
        population_size=population,
        max_generations=generations,
        timeout=timeout,
        cluster_mode=ClusterMode(cluster_mode),
        cluster_name=cluster_name,
    )

    orchestrator = Orchestrator(config)
    asyncio.run(orchestrator.run())
